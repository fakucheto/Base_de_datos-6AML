"""
CASO 7 - FASE E: Monitoreo IoT en Datacenters (Time-Series)
Extiende Caso7.py con los requisitos: base de datos, contexto, reglas de negocio,
consultas, NoSQL, conexión entre motores, documentos y grafos.

Ejecutar (con Caso7.py en la misma carpeta):   python Caso7_Fase_E.py
Requiere:  pip install networkx
"""
import json
import os
import random
import sqlite3
from contextlib import contextmanager

import networkx as nx

from Caso7 import DB_NAME, inicializar_entorno  # reutiliza el esquema base

# ============================================================================
# 1. CONTEXTO DEL CASO (usado por los reportes de consola)
# ============================================================================
CONTEXTO = {
    "problema": "Capturar y procesar telemetría de sensores de racks para prevenir "
                "fallos por sobrecalentamiento",
    "objetivo_medible": "Alarma crítica en menos de 2 segundos",
    "escala": "500 sensores, 1 lectura cada 5 s (~8,6 millones de registros por día)",
    "retencion": "30 días caliente + 2 años histórico agregado",
    "fuera_de_alcance": "Control físico de los aires acondicionados (actuadores)",
}

DOCS_JSON = "documentos_iot.json"
GRAFO_FILE = "grafo_datacenter.graphml"
T0 = 1700000000  # instante base de los datos de demostración (UTC)


def titulo(texto):
    print(f"\n{'=' * 78}\n{texto}\n{'=' * 78}")


def mostrar(subtitulo, filas):
    print(f"\n  >> {subtitulo}")
    filas = [dict(f) if not isinstance(f, dict) else f for f in filas]
    if not filas:
        print("     (sin resultados)")
        return
    for f in filas:
        print("     " + " | ".join(f"{k}={v}" for k, v in f.items()))


# ============================================================================
# 2. ARMANDO CONEXIÓN: una sola puerta de entrada a la base relacional
# ============================================================================
@contextmanager
def conexion(db=DB_NAME):
    """Abre una conexión con las reglas del proyecto y hace commit/rollback solo."""
    conn = sqlite3.connect(db, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")   # integridad referencial
    conn.execute("PRAGMA journal_mode = WAL;")  # lecturas mientras se escribe
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ============================================================================
# 3. BASE DE DATOS: ampliación del esquema (alarmas, incidencias, resúmenes, vistas)
# ============================================================================
def ampliar_esquema(conn):
    conn.executescript("""
    -- RF5: alarmas almacenadas de forma inmutable (ver triggers RN5)
    CREATE TABLE alarma (
        id_alarma INTEGER PRIMARY KEY AUTOINCREMENT,
        id_sensor TEXT NOT NULL,
        timestamp_lectura INTEGER NOT NULL,
        severidad TEXT NOT NULL CHECK (severidad IN ('PRECAUCION', 'CRITICO')),
        valor_metrica REAL NOT NULL,
        creada_en INTEGER NOT NULL DEFAULT (CAST(strftime('%s','now') AS INTEGER)),
        FOREIGN KEY (id_sensor, timestamp_lectura)
            REFERENCES lectura_telemetria(id_sensor, timestamp_lectura)
    );

    -- RF8: el NOC reconoce, gestiona y cierra incidencias
    CREATE TABLE incidencia_noc (
        id_incidencia INTEGER PRIMARY KEY AUTOINCREMENT,
        id_alarma INTEGER NOT NULL UNIQUE REFERENCES alarma(id_alarma),
        estado TEXT NOT NULL DEFAULT 'ABIERTA'
            CHECK (estado IN ('ABIERTA', 'RECONOCIDA', 'CERRADA')),
        responsable TEXT,
        nota_cierre TEXT
    );

    -- RF7: downsampling (resumen por hora) para datos fuera de la ventana caliente
    CREATE TABLE resumen_horario (
        id_sensor TEXT NOT NULL REFERENCES sensor_iot(id_sensor),
        hora_epoch INTEGER NOT NULL,
        promedio REAL NOT NULL,
        minimo REAL NOT NULL,
        maximo REAL NOT NULL,
        n_lecturas INTEGER NOT NULL,
        PRIMARY KEY (id_sensor, hora_epoch)
    );

    CREATE INDEX idx_alarma_sensor ON alarma(id_sensor, timestamp_lectura);

    -- RF9: vistas para reportes de estabilidad térmica y eficiencia energética
    CREATE VIEW v_estabilidad_termica AS
    SELECT s.rack_ubicacion,
           COALESCE(p.pasillo, 'SIN_PASILLO') AS pasillo,
           ROUND(AVG(l.valor_metrica), 2) AS temp_promedio,
           MAX(l.valor_metrica) AS temp_maxima,
           ROUND(100.0 * SUM(l.valor_metrica > s.umbral_limite) / COUNT(*), 1) AS pct_sobre_umbral
    FROM sensor_iot s
    JOIN lectura_telemetria l ON l.id_sensor = s.id_sensor
    LEFT JOIN rack_pasillo p ON p.rack_ubicacion = s.rack_ubicacion
    WHERE s.tipo_metrica = 'TEMPERATURA'
    GROUP BY s.rack_ubicacion, pasillo;

    CREATE VIEW v_consumo_por_pasillo AS
    SELECT COALESCE(p.pasillo, 'SIN_PASILLO') AS pasillo,
           ROUND(AVG(l.valor_metrica), 2) AS kw_promedio,
           MAX(l.valor_metrica) AS kw_pico,
           COUNT(DISTINCT s.id_sensor) AS sensores
    FROM sensor_iot s
    JOIN lectura_telemetria l ON l.id_sensor = s.id_sensor
    LEFT JOIN rack_pasillo p ON p.rack_ubicacion = s.rack_ubicacion
    WHERE s.tipo_metrica = 'CONSUMO_KW'
    GROUP BY pasillo;
    """)


# ============================================================================
# 4. REGLAS DE NEGOCIO: implementadas como triggers dentro de la base
# ============================================================================
def crear_reglas_negocio(conn):
    conn.executescript("""
    -- RN1 y RN2: validar la lectura antes de aceptarla
    CREATE TRIGGER trg_valida_lectura BEFORE INSERT ON lectura_telemetria
    BEGIN
        SELECT RAISE(ABORT, 'RN1: timestamp fuera del rango UTC valido (2000-01-01 hasta manana)')
        WHERE NEW.timestamp_lectura < 946684800
           OR NEW.timestamp_lectura > CAST(strftime('%s','now') AS INTEGER) + 86400;
        SELECT RAISE(ABORT, 'RN2: el sensor no esta ACTIVO (mantenimiento o inaccesible)')
        WHERE (SELECT estado_operativo FROM sensor_iot WHERE id_sensor = NEW.id_sensor) <> 'ACTIVO';
    END;

    -- RN3: el nivel de alerta lo calcula la base contra el umbral del sensor
    --      CRITICO: supera el umbral | PRECAUCION: >= 90 % del umbral | NORMAL: el resto
    CREATE TRIGGER trg_clasifica_alerta AFTER INSERT ON lectura_telemetria
    BEGIN
        UPDATE lectura_telemetria
           SET nivel_alerta = CASE
               WHEN NEW.valor_metrica > (SELECT umbral_limite FROM sensor_iot WHERE id_sensor = NEW.id_sensor)
                    THEN 'CRITICO'
               WHEN NEW.valor_metrica >= 0.9 * (SELECT umbral_limite FROM sensor_iot WHERE id_sensor = NEW.id_sensor)
                    THEN 'PRECAUCION'
               ELSE 'NORMAL' END
         WHERE id_sensor = NEW.id_sensor AND timestamp_lectura = NEW.timestamp_lectura;
    END;

    -- RN4: toda lectura PRECAUCION o CRITICA genera una alarma; las CRITICAS abren incidencia
    CREATE TRIGGER trg_genera_alarma AFTER UPDATE OF nivel_alerta ON lectura_telemetria
    WHEN NEW.nivel_alerta IN ('PRECAUCION', 'CRITICO') AND OLD.nivel_alerta <> NEW.nivel_alerta
    BEGIN
        INSERT INTO alarma (id_sensor, timestamp_lectura, severidad, valor_metrica)
        VALUES (NEW.id_sensor, NEW.timestamp_lectura, NEW.nivel_alerta, NEW.valor_metrica);
    END;

    CREATE TRIGGER trg_abre_incidencia AFTER INSERT ON alarma
    WHEN NEW.severidad = 'CRITICO'
    BEGIN
        INSERT INTO incidencia_noc (id_alarma) VALUES (NEW.id_alarma);
    END;

    -- RN5: las alarmas son inmutables (no se editan ni se borran)
    CREATE TRIGGER trg_alarma_no_update BEFORE UPDATE ON alarma
    BEGIN SELECT RAISE(ABORT, 'RN5: las alarmas son inmutables, no se pueden modificar'); END;

    CREATE TRIGGER trg_alarma_no_delete BEFORE DELETE ON alarma
    BEGIN SELECT RAISE(ABORT, 'RN5: las alarmas son inmutables, no se pueden borrar'); END;

    -- RN6: flujo de la incidencia ABIERTA -> RECONOCIDA -> CERRADA
    CREATE TRIGGER trg_incidencia_flujo BEFORE UPDATE OF estado ON incidencia_noc
    BEGIN
        SELECT RAISE(ABORT, 'RN6: una incidencia CERRADA no puede reabrirse')
        WHERE OLD.estado = 'CERRADA';
        SELECT RAISE(ABORT, 'RN6: la incidencia debe RECONOCERSE antes de cerrarse')
        WHERE OLD.estado = 'ABIERTA' AND NEW.estado = 'CERRADA';
        SELECT RAISE(ABORT, 'RN6: reconocer una incidencia exige indicar un responsable')
        WHERE NEW.estado = 'RECONOCIDA' AND NEW.responsable IS NULL;
    END;
    """)


# ============================================================================
# Datos de demostración
# ============================================================================
def cargar_datos_demo(conn):
    conn.executemany("INSERT INTO sensor_iot VALUES (?, ?, ?, ?, ?);", [
        ("SEN_05", "Rack_A2", "TEMPERATURA", 30.0, "ACTIVO"),
        ("SEN_06", "Rack_A2", "CONSUMO_KW", 15.0, "ACTIVO"),
        ("SEN_07", "Rack_A1", "CONSUMO_KW", 15.0, "ACTIVO"),
    ])
    rng = random.Random(42)
    perfiles = [("SEN_01", 25, 4), ("SEN_02", 60, 15), ("SEN_04", 27, 4),
                ("SEN_05", 26, 5), ("SEN_06", 10, 3), ("SEN_07", 12, 4)]
    filas = []
    for sensor, base, amp in perfiles:
        for i in range(36):  # 3 horas, una lectura cada 5 minutos
            filas.append((sensor, T0 + i * 300, round(base + rng.uniform(-amp, amp), 1)))
    # Datos "fríos" (40 días atrás) para demostrar downsampling y retención
    for sensor in ("SEN_01", "SEN_05"):
        for i in range(6):
            filas.append((sensor, T0 - 40 * 86400 + i * 300, round(24 + rng.uniform(-2, 2), 1)))
    conn.executemany(
        "INSERT INTO lectura_telemetria (id_sensor, timestamp_lectura, valor_metrica) VALUES (?, ?, ?);",
        filas)
    return len(filas)


# ============================================================================
# 4b. Demostración de las reglas de negocio
# ============================================================================
def intentar(conn, descripcion, sql, params=()):
    try:
        conn.execute(sql, params)
        print(f"  [ACEPTADO]  {descripcion}")
    except sqlite3.Error as e:
        print(f"  [RECHAZADO] {descripcion}\n              -> {e}")


def probar_reglas_negocio(conn):
    titulo("REGLAS DE NEGOCIO (triggers)")
    ins = "INSERT INTO lectura_telemetria (id_sensor, timestamp_lectura, valor_metrica) VALUES (?, ?, ?);"
    intentar(conn, "RN1 timestamp -1 (fuera de rango)", ins, ("SEN_01", -1, 22.0))
    intentar(conn, "RN1 timestamp en el año 2099", ins, ("SEN_01", 4102444800, 22.0))
    intentar(conn, "RN2 lectura de SEN_03 (en MANTENIMIENTO)", ins, ("SEN_03", T0, 10.0))
    intentar(conn, "RN3 lectura de 31,5 sobre umbral 28 (debe quedar CRITICO)", ins, ("SEN_01", T0 + 99999, 31.5))
    r = conn.execute("SELECT nivel_alerta FROM lectura_telemetria WHERE id_sensor='SEN_01' AND timestamp_lectura=?",
                     (T0 + 99999,)).fetchone()
    print(f"              nivel asignado automaticamente: {r['nivel_alerta']}")
    intentar(conn, "RN5 modificar una alarma", "UPDATE alarma SET severidad='PRECAUCION' WHERE id_alarma=1;")
    intentar(conn, "RN5 borrar una alarma", "DELETE FROM alarma WHERE id_alarma=1;")
    inc = conn.execute("SELECT id_incidencia FROM incidencia_noc ORDER BY id_incidencia LIMIT 1").fetchone()[0]
    intentar(conn, "RN6 cerrar incidencia sin reconocerla",
             "UPDATE incidencia_noc SET estado='CERRADA' WHERE id_incidencia=?;", (inc,))
    intentar(conn, "RN6 reconocer sin responsable",
             "UPDATE incidencia_noc SET estado='RECONOCIDA' WHERE id_incidencia=?;", (inc,))
    intentar(conn, "RN6 reconocer con responsable",
             "UPDATE incidencia_noc SET estado='RECONOCIDA', responsable='ing.noc.1' WHERE id_incidencia=?;", (inc,))
    intentar(conn, "RN6 cerrar incidencia reconocida",
             "UPDATE incidencia_noc SET estado='CERRADA', nota_cierre='Ajuste de ventilacion' WHERE id_incidencia=?;",
             (inc,))
    intentar(conn, "RN6 reabrir incidencia cerrada",
             "UPDATE incidencia_noc SET estado='ABIERTA' WHERE id_incidencia=?;", (inc,))


# ============================================================================
# 5. CONSULTAS (RF6, RF7, RF8, RF9)
# ============================================================================
def ejecutar_consultas(conn):
    titulo("CONSULTAS")

    mostrar("C1. Promedio horario de temperatura por pasillo (escenario normal 2)", conn.execute("""
        SELECT COALESCE(p.pasillo, 'SIN_PASILLO') AS pasillo,
               datetime((l.timestamp_lectura / 3600) * 3600, 'unixepoch') AS hora_utc,
               ROUND(AVG(l.valor_metrica), 2) AS temp_promedio,
               COUNT(*) AS lecturas
        FROM lectura_telemetria l
        JOIN sensor_iot s ON s.id_sensor = l.id_sensor
        LEFT JOIN rack_pasillo p ON p.rack_ubicacion = s.rack_ubicacion
        WHERE s.tipo_metrica = 'TEMPERATURA' AND l.timestamp_lectura >= ?
        GROUP BY pasillo, hora_utc ORDER BY pasillo, hora_utc LIMIT 8;""", (T0,)).fetchall())

    mostrar("C2. Ultima lectura de cada sensor (funcion de ventana ROW_NUMBER)", conn.execute("""
        SELECT id_sensor, datetime(timestamp_lectura, 'unixepoch') AS momento_utc, valor_metrica, nivel_alerta
        FROM (SELECT l.*, ROW_NUMBER() OVER (PARTITION BY id_sensor ORDER BY timestamp_lectura DESC) AS rn
              FROM lectura_telemetria l WHERE timestamp_lectura >= ?)
        WHERE rn = 1 ORDER BY id_sensor;""", (T0,)).fetchall())

    mostrar("C3. Top 3 sensores con mas alarmas CRITICAS", conn.execute("""
        SELECT a.id_sensor, s.rack_ubicacion, COUNT(*) AS alarmas_criticas, MAX(a.valor_metrica) AS pico
        FROM alarma a JOIN sensor_iot s ON s.id_sensor = a.id_sensor
        WHERE a.severidad = 'CRITICO'
        GROUP BY a.id_sensor, s.rack_ubicacion ORDER BY alarmas_criticas DESC LIMIT 3;""").fetchall())

    mostrar("C4. Incidencias del NOC con su alarma (RF8)", conn.execute("""
        SELECT i.id_incidencia, i.estado, COALESCE(i.responsable, '-') AS responsable,
               a.id_sensor, a.valor_metrica
        FROM incidencia_noc i JOIN alarma a ON a.id_alarma = i.id_alarma
        ORDER BY i.id_incidencia LIMIT 5;""").fetchall())

    mostrar("C5. Vista de estabilidad termica por rack (RF9)",
            conn.execute("SELECT * FROM v_estabilidad_termica ORDER BY rack_ubicacion;").fetchall())
    mostrar("C6. Vista de consumo electrico por pasillo (base del reporte PUE)",
            conn.execute("SELECT * FROM v_consumo_por_pasillo ORDER BY pasillo;").fetchall())


def aplicar_retencion(conn, dias=30):
    """RF7 y RNF5: resume por hora los datos fríos y luego los purga de la tabla caliente."""
    titulo("RETENCION Y DOWNSAMPLING (30 dias caliente)")
    ahora = conn.execute("SELECT MAX(timestamp_lectura) FROM lectura_telemetria;").fetchone()[0]
    limite = ahora - dias * 86400
    antes = conn.execute("SELECT COUNT(*) FROM lectura_telemetria;").fetchone()[0]
    conn.execute("""
        INSERT OR REPLACE INTO resumen_horario
        SELECT id_sensor, (timestamp_lectura / 3600) * 3600,
               ROUND(AVG(valor_metrica), 2), MIN(valor_metrica), MAX(valor_metrica), COUNT(*)
        FROM lectura_telemetria WHERE timestamp_lectura < ?
        GROUP BY id_sensor, (timestamp_lectura / 3600) * 3600;""", (limite,))
    borradas = conn.execute("""
        DELETE FROM lectura_telemetria
        WHERE timestamp_lectura < ?
          AND NOT EXISTS (SELECT 1 FROM alarma a
                          WHERE a.id_sensor = lectura_telemetria.id_sensor
                            AND a.timestamp_lectura = lectura_telemetria.timestamp_lectura);""",
                            (limite,)).rowcount
    despues = conn.execute("SELECT COUNT(*) FROM lectura_telemetria;").fetchone()[0]
    print(f"  Lecturas antes: {antes} | purgadas: {borradas} | despues: {despues}")
    mostrar("Resumen horario conservado (historico agregado)",
            conn.execute("""SELECT id_sensor, datetime(hora_epoch,'unixepoch') AS hora_utc, promedio, minimo, maximo,
                                   n_lecturas FROM resumen_horario ORDER BY id_sensor, hora_epoch LIMIT 4;""").fetchall())


# ============================================================================
# 6. NoSQL + DOCUMENTOS: almacén documental (modelo estilo MongoDB)
# ============================================================================
class ColeccionDocumentos:
    """Colección mínima de documentos JSON con filtros estilo MongoDB ($gt, $gte, $lt, $in)."""

    def __init__(self, nombre):
        self.nombre, self.docs = nombre, []

    def insertar(self, doc):
        self.docs.append(doc)

    @staticmethod
    def _valor(doc, ruta):
        for parte in ruta.split("."):
            doc = doc.get(parte) if isinstance(doc, dict) else None
        return doc

    def buscar(self, filtro=None):
        def cumple(doc):
            for campo, cond in (filtro or {}).items():
                v = self._valor(doc, campo)
                if isinstance(cond, dict):
                    for op, ref in cond.items():
                        ok = {"$gt": lambda: v is not None and v > ref, "$gte": lambda: v is not None and v >= ref,
                              "$lt": lambda: v is not None and v < ref, "$in": lambda: v in ref}[op]()
                        if not ok:
                            return False
                elif v != cond:
                    return False
            return True
        return [d for d in self.docs if cumple(d)]


def construir_documentos(conn):
    """Desnormaliza SQL en documentos: el sensor lleva dentro rack, pasillo y sus ultimas lecturas."""
    sensores, alarmas = ColeccionDocumentos("sensores"), ColeccionDocumentos("alarmas")
    for s in conn.execute("""SELECT s.*, p.pasillo FROM sensor_iot s
                             LEFT JOIN rack_pasillo p ON p.rack_ubicacion = s.rack_ubicacion
                             ORDER BY s.id_sensor""").fetchall():
        ult = conn.execute("""SELECT timestamp_lectura AS ts, valor_metrica AS valor, nivel_alerta AS nivel
                              FROM lectura_telemetria WHERE id_sensor = ?
                              ORDER BY timestamp_lectura DESC LIMIT 3""", (s["id_sensor"],)).fetchall()
        st = conn.execute("""SELECT COUNT(*) AS n, ROUND(AVG(valor_metrica), 2) AS prom, MAX(valor_metrica) AS max
                             FROM lectura_telemetria WHERE id_sensor = ?""", (s["id_sensor"],)).fetchone()
        sensores.insertar({
            "_id": s["id_sensor"], "tipo_metrica": s["tipo_metrica"], "umbral": s["umbral_limite"],
            "estado": s["estado_operativo"],
            "ubicacion": {"rack": s["rack_ubicacion"], "pasillo": s["pasillo"] or "SIN_PASILLO"},
            "ultimas_lecturas": [dict(u) for u in ult],
            "estadisticas": {"n": st["n"], "promedio": st["prom"], "max": st["max"]},
        })
    for a in conn.execute("""SELECT a.*, s.rack_ubicacion, s.tipo_metrica, COALESCE(p.pasillo,'SIN_PASILLO') AS pasillo,
                                    i.estado AS inc_estado, i.responsable
                             FROM alarma a JOIN sensor_iot s ON s.id_sensor = a.id_sensor
                             LEFT JOIN rack_pasillo p ON p.rack_ubicacion = s.rack_ubicacion
                             LEFT JOIN incidencia_noc i ON i.id_alarma = a.id_alarma
                             ORDER BY a.id_alarma""").fetchall():
        alarmas.insertar({
            "_id": a["id_alarma"], "severidad": a["severidad"], "valor": a["valor_metrica"],
            "timestamp": a["timestamp_lectura"],
            "sensor": {"id": a["id_sensor"], "rack": a["rack_ubicacion"], "pasillo": a["pasillo"],
                       "tipo": a["tipo_metrica"]},
            "incidencia": {"estado": a["inc_estado"], "responsable": a["responsable"]} if a["inc_estado"] else None,
        })
    return sensores, alarmas


def probar_nosql(conn):
    titulo("NoSQL: almacen de DOCUMENTOS (estilo MongoDB)")
    sensores, alarmas = construir_documentos(conn)
    with open(DOCS_JSON, "w", encoding="utf-8") as f:
        json.dump({"sensores": sensores.docs, "alarmas": alarmas.docs}, f, ensure_ascii=False, indent=2)
    print(f"  Coleccion 'sensores': {len(sensores.docs)} documentos | 'alarmas': {len(alarmas.docs)} documentos")
    print(f"  Exportado a {DOCS_JSON}")
    print("\n  Ejemplo de documento (sensor):")
    print("  " + json.dumps(sensores.docs[0], ensure_ascii=False, indent=2).replace("\n", "\n  "))

    q1 = sensores.buscar({"tipo_metrica": "TEMPERATURA", "ubicacion.pasillo": "Pasillo_Frio_1",
                          "estadisticas.max": {"$gt": 28}})
    print("\n  >> Q1: sensores de TEMPERATURA del Pasillo_Frio_1 con maximo > 28")
    print("     Mongo: db.sensores.find({tipo_metrica:'TEMPERATURA','ubicacion.pasillo':'Pasillo_Frio_1','estadisticas.max':{$gt:28}})")
    print("     Resultado:", [d["_id"] for d in q1])
    q2 = alarmas.buscar({"severidad": "CRITICO", "sensor.pasillo": {"$in": ["Pasillo_Frio_1", "SIN_PASILLO"]}})
    print("\n  >> Q2: alarmas CRITICAS en Pasillo_Frio_1 o sin pasillo (sin ningun JOIN)")
    print("     Mongo: db.alarmas.find({severidad:'CRITICO','sensor.pasillo':{$in:[...]}})")
    print("     Resultado:", [(d["_id"], d["sensor"]["id"], d["valor"]) for d in q2][:6])
    return sensores, alarmas


# ============================================================================
# 7. GRAFOS: topología Datacenter -> Pasillo -> Rack -> Sensor -> Alarma
# ============================================================================
def construir_grafo(conn):
    G = nx.DiGraph()
    G.add_node("DC_Principal", tipo="Datacenter")
    for r in conn.execute("SELECT rack_ubicacion, pasillo FROM rack_pasillo").fetchall():
        G.add_node(r["pasillo"], tipo="Pasillo")
        G.add_edge("DC_Principal", r["pasillo"], rel="CONTIENE")
        G.add_node(r["rack_ubicacion"], tipo="Rack")
        G.add_edge(r["pasillo"], r["rack_ubicacion"], rel="CONTIENE")
    for s in conn.execute("SELECT * FROM sensor_iot").fetchall():
        if s["rack_ubicacion"] not in G:  # rack sin pasillo asignado
            G.add_node("SIN_PASILLO", tipo="Pasillo")
            G.add_edge("DC_Principal", "SIN_PASILLO", rel="CONTIENE")
            G.add_node(s["rack_ubicacion"], tipo="Rack")
            G.add_edge("SIN_PASILLO", s["rack_ubicacion"], rel="CONTIENE")
        G.add_node(s["id_sensor"], tipo="Sensor", metrica=s["tipo_metrica"], estado=s["estado_operativo"])
        G.add_edge(s["rack_ubicacion"], s["id_sensor"], rel="TIENE_SENSOR")
    for a in conn.execute("SELECT id_alarma, id_sensor, severidad FROM alarma").fetchall():
        nodo = f"ALM_{a['id_alarma']}"
        G.add_node(nodo, tipo="Alarma", severidad=a["severidad"])
        G.add_edge(a["id_sensor"], nodo, rel="GENERO")
    return G


def _de_tipo(G, nodos, tipo):
    return sorted(n for n in nodos if G.nodes[n]["tipo"] == tipo)


def probar_grafos(conn):
    titulo("GRAFOS: topologia del datacenter (networkx; equivalente en Neo4j/Cypher)")
    G = construir_grafo(conn)
    tipos = {}
    for _, d in G.nodes(data=True):
        tipos[d["tipo"]] = tipos.get(d["tipo"], 0) + 1
    print(f"  Nodos: {G.number_of_nodes()} {tipos} | Aristas: {G.number_of_edges()}")

    pas = "Pasillo_Frio_1"
    afectados = _de_tipo(G, nx.descendants(G, pas), "Sensor")
    print(f"\n  >> G1. Radio de impacto: si falla la refrigeracion de {pas}, sensores afectados:")
    print("     Cypher: MATCH (:Pasillo {nombre:'Pasillo_Frio_1'})-[:CONTIENE*]->(:Rack)-[:TIENE_SENSOR]->(s) RETURN s")
    print("    ", afectados)

    print("\n  >> G2. Racks sin sensores (cobertura faltante):")
    print("    ", sorted(n for n in G if G.nodes[n]["tipo"] == "Rack" and G.out_degree(n) == 0))

    print("\n  >> G3. Alarmas por pasillo (recorrido de descendientes):")
    for p in _de_tipo(G, G.nodes, "Pasillo"):
        al = _de_tipo(G, nx.descendants(G, p), "Alarma")
        print(f"      {p}: {len(al)} alarmas")

    crit = [n for n, d in G.nodes(data=True) if d["tipo"] == "Alarma" and d["severidad"] == "CRITICO"]
    if crit:
        ruta = nx.shortest_path(G, "DC_Principal", crit[0])
        print(f"\n  >> G4. Trazabilidad de la alarma {crit[0]} desde el datacenter:")
        print("     " + " -> ".join(ruta))

    print("\n  >> G5. Sensores en el pasillo SIN_PASILLO (inventario incompleto):")
    print("    ", _de_tipo(G, nx.descendants(G, "SIN_PASILLO"), "Sensor") if "SIN_PASILLO" in G else [])

    nx.write_graphml(G, GRAFO_FILE)
    print(f"\n  Grafo exportado a {GRAFO_FILE} (importable en Gephi o Neo4j)")
    return G


# ============================================================================
# 2b. ARMANDO CONEXIÓN: verificación cruzada SQL <-> Documentos <-> Grafo
# ============================================================================
def verificar_integracion(conn, sensores, alarmas, G):
    titulo("CONEXION ENTRE MOTORES: verificacion cruzada")
    n_sql_s = conn.execute("SELECT COUNT(*) FROM sensor_iot").fetchone()[0]
    n_sql_a = conn.execute("SELECT COUNT(*) FROM alarma").fetchone()[0]
    n_g_s = sum(1 for _, d in G.nodes(data=True) if d["tipo"] == "Sensor")
    n_g_a = sum(1 for _, d in G.nodes(data=True) if d["tipo"] == "Alarma")
    print(f"  Sensores -> SQL: {n_sql_s} | Documentos: {len(sensores.docs)} | Grafo: {n_g_s}")
    print(f"  Alarmas  -> SQL: {n_sql_a} | Documentos: {len(alarmas.docs)} | Grafo: {n_g_a}")
    ok = n_sql_s == len(sensores.docs) == n_g_s and n_sql_a == len(alarmas.docs) == n_g_a
    print("  [OK] Los tres almacenes son consistentes." if ok else "  [ALERTA] Hay diferencias entre almacenes.")


# ============================================================================
def main():
    titulo("CASO 7 - FASE E | " + CONTEXTO["problema"])
    for k, v in CONTEXTO.items():
        print(f"  {k}: {v}")

    inicializar_entorno()                      # esquema base del Caso 7
    with conexion() as conn:
        ampliar_esquema(conn)                  # 3. base de datos ampliada
        crear_reglas_negocio(conn)             # 4. reglas de negocio
        n = cargar_datos_demo(conn)
        print(f"\n  [+] {n} lecturas de demostracion cargadas; los triggers generaron alarmas e incidencias.")
        probar_reglas_negocio(conn)
        ejecutar_consultas(conn)               # 5. consultas
        aplicar_retencion(conn)
        sensores, alarmas = probar_nosql(conn)  # 6. NoSQL + documentos
        G = probar_grafos(conn)                # 7. grafos
        verificar_integracion(conn, sensores, alarmas, G)  # conexión entre motores


if __name__ == "__main__":
    main()
