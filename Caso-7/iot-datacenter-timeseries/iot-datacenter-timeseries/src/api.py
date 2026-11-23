"""
API REST del Caso 7: conecta aplicaciones externas (colectores IoT, tablero del NOC, scripts)
con la base de datos del proyecto.

Ejecutar desde la raíz del repositorio:
    uvicorn api:app --app-dir src --reload
Documentación interactiva (Swagger):  http://127.0.0.1:8000/docs

Todas las reglas de negocio (RN1 a RN6) viven en la base de datos como triggers: la API solo
traduce sus errores a códigos HTTP.
    422  dato inválido (RN1 timestamp, RN2 sensor no activo)
    409  conflicto de estado o duplicado (RN5 alarma inmutable, RN6 flujo de incidencias, clave duplicada)
    404  recurso inexistente (sensor, incidencia, nodo del grafo)
"""
import os
import sqlite3
import time
from contextlib import asynccontextmanager
from typing import List, Literal, Optional

import networkx as nx
from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, Field

import Caso7
import Caso7_Fase_E as fe

Metrica = Literal["TEMPERATURA", "HUMEDAD", "CONSUMO_KW"]
EstadoSensor = Literal["ACTIVO", "MANTENIMIENTO", "INACCESIBLE"]

INSERT_LECTURA = "INSERT INTO lectura_telemetria (id_sensor, timestamp_lectura, valor_metrica) VALUES (?, ?, ?)"
INSERT_LECTURA_IGNORA = INSERT_LECTURA.replace("INSERT INTO", "INSERT OR IGNORE INTO")


# ----------------------------------------------------------------------------
# Arranque: si no existe una base con el esquema completo, se crea con datos de demostración
# ----------------------------------------------------------------------------
def _base_valida():
    if not os.path.exists(Caso7.DB_NAME):
        return False
    conn = sqlite3.connect(Caso7.DB_NAME)
    try:
        return conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'incidencia_noc'").fetchone() is not None
    finally:
        conn.close()


def preparar_base():
    if not _base_valida():
        Caso7.inicializar_entorno()
        with fe.conexion() as conn:
            fe.ampliar_esquema(conn)
            fe.crear_reglas_negocio(conn)
            fe.cargar_datos_demo(conn)


@asynccontextmanager
async def lifespan(_app):
    preparar_base()
    yield


app = FastAPI(
    title="API IoT Datacenter (Caso 7)",
    description="Ingesta de telemetría, alarmas, incidencias del NOC, reportes, documentos y grafo.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def medir_tiempo(request: Request, call_next):
    """Agrega el tiempo de proceso de cada petición (útil para vigilar la latencia de alerta de 2 s)."""
    inicio = time.perf_counter()
    respuesta = await call_next(request)
    respuesta.headers["X-Tiempo-Proceso-ms"] = f"{(time.perf_counter() - inicio) * 1000:.2f}"
    return respuesta


def _error(e: sqlite3.Error) -> HTTPException:
    """Traduce errores de la base (constraints y triggers) a respuestas HTTP."""
    msg = str(e)
    if msg.startswith(("RN1", "RN2")):
        return HTTPException(422, msg)
    if msg.startswith(("RN5", "RN6")):
        return HTTPException(409, msg)
    if "FOREIGN KEY" in msg:
        return HTTPException(404, "El sensor indicado no existe")
    if "UNIQUE" in msg or "PRIMARY KEY" in msg:
        return HTTPException(409, "Registro duplicado")
    return HTTPException(400, msg)


def _filas(cursor_o_filas):
    return [dict(f) for f in cursor_o_filas]


def _sensor_o_404(conn, id_sensor):
    s = conn.execute("SELECT * FROM sensor_iot WHERE id_sensor = ?", (id_sensor,)).fetchone()
    if s is None:
        raise HTTPException(404, f"Sensor {id_sensor} no encontrado")
    return s


# ----------------------------------------------------------------------------
# Modelos de entrada
# ----------------------------------------------------------------------------
class SensorIn(BaseModel):
    id_sensor: str = Field(min_length=1, max_length=40, examples=["SEN_10"])
    rack_ubicacion: str = Field(min_length=1, examples=["Rack_A1"])
    tipo_metrica: Metrica
    umbral_limite: float = Field(examples=[28.0])


class EstadoIn(BaseModel):
    estado: EstadoSensor


class LecturaIn(BaseModel):
    id_sensor: str
    timestamp_lectura: int = Field(description="Epoch UTC en segundos", examples=[1700000000])
    valor_metrica: float


class LoteIn(BaseModel):
    lecturas: List[LecturaIn] = Field(min_length=1, max_length=5000)


class IncidenciaIn(BaseModel):
    estado: Literal["ABIERTA", "RECONOCIDA", "CERRADA"]
    responsable: Optional[str] = None
    nota_cierre: Optional[str] = None


# ----------------------------------------------------------------------------
# Salud
# ----------------------------------------------------------------------------
@app.get("/", tags=["Salud"])
def raiz():
    return {"servicio": "API IoT Datacenter (Caso 7)", "documentacion": "/docs", "salud": "/salud"}


@app.get("/salud", tags=["Salud"])
def salud():
    with fe.conexion() as conn:
        n = conn.execute("SELECT COUNT(*) FROM sensor_iot").fetchone()[0]
    return {"estado": "ok", "sqlite": sqlite3.sqlite_version, "sensores": n}


# ----------------------------------------------------------------------------
# Sensores (RF1, RF10)
# ----------------------------------------------------------------------------
@app.get("/sensores", tags=["Sensores"])
def listar_sensores(estado: Optional[EstadoSensor] = None, metrica: Optional[Metrica] = None):
    sql, params = "SELECT * FROM sensor_iot WHERE 1=1", []
    if estado:
        sql += " AND estado_operativo = ?"
        params.append(estado)
    if metrica:
        sql += " AND tipo_metrica = ?"
        params.append(metrica)
    with fe.conexion() as conn:
        return _filas(conn.execute(sql + " ORDER BY id_sensor", params).fetchall())


@app.get("/sensores/{id_sensor}", tags=["Sensores"])
def obtener_sensor(id_sensor: str):
    with fe.conexion() as conn:
        return dict(_sensor_o_404(conn, id_sensor))


@app.post("/sensores", status_code=201, tags=["Sensores"])
def registrar_sensor(s: SensorIn):
    try:
        with fe.conexion() as conn:
            conn.execute("INSERT INTO sensor_iot (id_sensor, rack_ubicacion, tipo_metrica, umbral_limite) "
                         "VALUES (?, ?, ?, ?)", (s.id_sensor, s.rack_ubicacion, s.tipo_metrica, s.umbral_limite))
    except sqlite3.Error as e:
        raise _error(e)
    return {**s.model_dump(), "estado_operativo": "ACTIVO"}


@app.patch("/sensores/{id_sensor}/estado", tags=["Sensores"])
def cambiar_estado_sensor(id_sensor: str, body: EstadoIn):
    """Baja lógica: un sensor en MANTENIMIENTO o INACCESIBLE deja de aceptar lecturas (RN2)."""
    with fe.conexion() as conn:
        _sensor_o_404(conn, id_sensor)
        conn.execute("UPDATE sensor_iot SET estado_operativo = ? WHERE id_sensor = ?", (body.estado, id_sensor))
    return {"id_sensor": id_sensor, "estado_operativo": body.estado}


# ----------------------------------------------------------------------------
# Lecturas (RF2, RF3, RF4, RF6)
# ----------------------------------------------------------------------------
@app.post("/lecturas", status_code=201, tags=["Lecturas"])
def ingestar_lectura(lec: LecturaIn):
    """Ingesta una lectura. La base la valida (RN1, RN2), la clasifica (RN3) y genera la alarma (RN4)."""
    try:
        with fe.conexion() as conn:
            conn.execute(INSERT_LECTURA, (lec.id_sensor, lec.timestamp_lectura, lec.valor_metrica))
            nivel = conn.execute("SELECT nivel_alerta FROM lectura_telemetria WHERE id_sensor = ? "
                                 "AND timestamp_lectura = ?", (lec.id_sensor, lec.timestamp_lectura)).fetchone()[0]
            alarma = conn.execute("SELECT id_alarma FROM alarma WHERE id_sensor = ? AND timestamp_lectura = ?",
                                  (lec.id_sensor, lec.timestamp_lectura)).fetchone()
    except sqlite3.Error as e:
        raise _error(e)
    return {**lec.model_dump(), "nivel_alerta": nivel, "id_alarma": alarma[0] if alarma else None}


@app.post("/lecturas/lote", status_code=201, tags=["Lecturas"])
def ingestar_lote(lote: LoteIn, ignorar_duplicados: bool = True):
    """Ingesta en lote (por ejemplo, tras una reconexión). Es atómica: si una lectura viola una regla, no entra ninguna.
    Con `ignorar_duplicados` los reenvíos de lecturas ya existentes se omiten sin error."""
    sql = INSERT_LECTURA_IGNORA if ignorar_duplicados else INSERT_LECTURA
    insertadas = 0
    try:
        with fe.conexion() as conn:
            for lec in lote.lecturas:
                insertadas += conn.execute(sql, (lec.id_sensor, lec.timestamp_lectura, lec.valor_metrica)).rowcount
    except sqlite3.Error as e:
        raise _error(e)
    return {"recibidas": len(lote.lecturas), "insertadas": insertadas, "omitidas": len(lote.lecturas) - insertadas}


@app.get("/sensores/{id_sensor}/lecturas", tags=["Lecturas"])
def consultar_lecturas(id_sensor: str, desde: Optional[int] = None, hasta: Optional[int] = None,
                       limite: int = Query(100, ge=1, le=1000)):
    """Serie temporal de un sensor filtrada por rango de fechas (epoch UTC). Más recientes primero."""
    sql, params = "SELECT * FROM lectura_telemetria WHERE id_sensor = ?", [id_sensor]
    if desde is not None:
        sql += " AND timestamp_lectura >= ?"
        params.append(desde)
    if hasta is not None:
        sql += " AND timestamp_lectura <= ?"
        params.append(hasta)
    with fe.conexion() as conn:
        _sensor_o_404(conn, id_sensor)
        return _filas(conn.execute(sql + " ORDER BY timestamp_lectura DESC LIMIT ?", params + [limite]).fetchall())


@app.get("/pasillos/{pasillo}/promedio-horario", tags=["Lecturas"])
def promedio_horario(pasillo: str, metrica: Metrica = "TEMPERATURA", desde: Optional[int] = None,
                     hasta: Optional[int] = None):
    """Promedio por hora de una métrica en un pasillo (escenario normal 2 del caso)."""
    sql = """SELECT datetime((l.timestamp_lectura / 3600) * 3600, 'unixepoch') AS hora_utc,
                    ROUND(AVG(l.valor_metrica), 2) AS promedio, COUNT(*) AS lecturas
             FROM lectura_telemetria l
             JOIN sensor_iot s ON s.id_sensor = l.id_sensor
             LEFT JOIN rack_pasillo p ON p.rack_ubicacion = s.rack_ubicacion
             WHERE s.tipo_metrica = ? AND COALESCE(p.pasillo, 'SIN_PASILLO') = ?"""
    params = [metrica, pasillo]
    if desde is not None:
        sql += " AND l.timestamp_lectura >= ?"
        params.append(desde)
    if hasta is not None:
        sql += " AND l.timestamp_lectura <= ?"
        params.append(hasta)
    with fe.conexion() as conn:
        return _filas(conn.execute(sql + " GROUP BY hora_utc ORDER BY hora_utc", params).fetchall())


# ----------------------------------------------------------------------------
# Alarmas e incidencias del NOC (RF5, RF8)
# ----------------------------------------------------------------------------
@app.get("/alarmas", tags=["NOC"])
def listar_alarmas(severidad: Optional[Literal["PRECAUCION", "CRITICO"]] = None,
                   limite: int = Query(50, ge=1, le=500)):
    sql, params = "SELECT * FROM alarma WHERE 1=1", []
    if severidad:
        sql += " AND severidad = ?"
        params.append(severidad)
    with fe.conexion() as conn:
        return _filas(conn.execute(sql + " ORDER BY id_alarma DESC LIMIT ?", params + [limite]).fetchall())


@app.get("/incidencias", tags=["NOC"])
def listar_incidencias(estado: Optional[Literal["ABIERTA", "RECONOCIDA", "CERRADA"]] = None,
                       limite: int = Query(50, ge=1, le=500)):
    sql = """SELECT i.*, a.id_sensor, a.valor_metrica, a.timestamp_lectura
             FROM incidencia_noc i JOIN alarma a ON a.id_alarma = i.id_alarma WHERE 1=1"""
    params = []
    if estado:
        sql += " AND i.estado = ?"
        params.append(estado)
    with fe.conexion() as conn:
        return _filas(conn.execute(sql + " ORDER BY i.id_incidencia LIMIT ?", params + [limite]).fetchall())


@app.patch("/incidencias/{id_incidencia}", tags=["NOC"])
def gestionar_incidencia(id_incidencia: int, body: IncidenciaIn):
    """El NOC reconoce y cierra incidencias. El flujo ABIERTA, RECONOCIDA, CERRADA lo impone la RN6."""
    try:
        with fe.conexion() as conn:
            if conn.execute("SELECT 1 FROM incidencia_noc WHERE id_incidencia = ?", (id_incidencia,)).fetchone() is None:
                raise HTTPException(404, f"Incidencia {id_incidencia} no encontrada")
            conn.execute("UPDATE incidencia_noc SET estado = ?, responsable = COALESCE(?, responsable), "
                         "nota_cierre = COALESCE(?, nota_cierre) WHERE id_incidencia = ?",
                         (body.estado, body.responsable, body.nota_cierre, id_incidencia))
            fila = conn.execute("SELECT * FROM incidencia_noc WHERE id_incidencia = ?", (id_incidencia,)).fetchone()
    except sqlite3.Error as e:
        raise _error(e)
    return dict(fila)


# ----------------------------------------------------------------------------
# Reportes (RF9)
# ----------------------------------------------------------------------------
@app.get("/reportes/estabilidad-termica", tags=["Reportes"])
def reporte_estabilidad():
    with fe.conexion() as conn:
        return _filas(conn.execute("SELECT * FROM v_estabilidad_termica ORDER BY rack_ubicacion").fetchall())


@app.get("/reportes/consumo-por-pasillo", tags=["Reportes"])
def reporte_consumo():
    with fe.conexion() as conn:
        return _filas(conn.execute("SELECT * FROM v_consumo_por_pasillo ORDER BY pasillo").fetchall())


# ----------------------------------------------------------------------------
# NoSQL (documentos) y grafo
# ----------------------------------------------------------------------------
@app.get("/documentos/sensores", tags=["NoSQL y grafo"])
def documentos_sensores(pasillo: Optional[str] = None, tipo_metrica: Optional[Metrica] = None,
                        max_mayor_que: Optional[float] = None):
    """Consulta el almacén documental (sensores desnormalizados) con filtros estilo MongoDB."""
    filtro = {}
    if pasillo:
        filtro["ubicacion.pasillo"] = pasillo
    if tipo_metrica:
        filtro["tipo_metrica"] = tipo_metrica
    if max_mayor_que is not None:
        filtro["estadisticas.max"] = {"$gt": max_mayor_que}
    with fe.conexion() as conn:
        sensores, _ = fe.construir_documentos(conn)
    return sensores.buscar(filtro)


@app.get("/grafo/impacto/{nodo}", tags=["NoSQL y grafo"])
def grafo_impacto(nodo: str):
    """Radio de impacto: qué racks y sensores se afectan si falla un pasillo, rack o el datacenter completo."""
    with fe.conexion() as conn:
        G = fe.construir_grafo(conn)
    if nodo not in G:
        raise HTTPException(404, f"Nodo {nodo} no existe en el grafo")
    desc = nx.descendants(G, nodo)
    return {"nodo": nodo, "tipo": G.nodes[nodo]["tipo"],
            "racks_afectados": fe._de_tipo(G, desc, "Rack"),
            "sensores_afectados": fe._de_tipo(G, desc, "Sensor"),
            "alarmas_asociadas": len(fe._de_tipo(G, desc, "Alarma"))}
