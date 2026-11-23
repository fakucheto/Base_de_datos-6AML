"""Pruebas automáticas del Caso 7 (Fase D y Fase E).

Cada prueba trabaja en una carpeta temporal para no tocar archivos del repositorio.
"""
import sqlite3

import pytest

import Caso7
import Caso7_Fase_E as fe

T0 = fe.T0
INS = "INSERT INTO lectura_telemetria (id_sensor, timestamp_lectura, valor_metrica) VALUES (?, ?, ?);"


@pytest.fixture
def base_d(tmp_path, monkeypatch):
    """Entorno de la Fase D (esquema base y 2 sensores)."""
    monkeypatch.chdir(tmp_path)
    Caso7.inicializar_entorno()
    return tmp_path


@pytest.fixture
def base_e(base_d):
    """Entorno completo de la Fase E: esquema ampliado, triggers y datos de demostración."""
    with fe.conexion() as conn:
        fe.ampliar_esquema(conn)
        fe.crear_reglas_negocio(conn)
        fe.cargar_datos_demo(conn)
    return base_d


# ---------------------------------------------------------------- Fase D
def test_clave_primaria_rechaza_duplicados(base_d):
    with fe.conexion() as conn:
        conn.execute(INS, ("SEN_01", T0, 24.5))
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(INS, ("SEN_01", T0, 25.0))


def test_llave_foranea_rechaza_sensor_inexistente(base_d):
    with fe.conexion() as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(INS, ("SEN_999", T0, 20.0))


def test_check_rechaza_metrica_invalida(base_d):
    with fe.conexion() as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO sensor_iot VALUES ('X', 'Rack_X', 'PRESION', 1.0, 'ACTIVO');")


def test_concurrencia_no_pierde_datos(base_d):
    Caso7.probar_concurrencia_multisesion()
    assert Caso7.ERRORES_CONCURRENCIA == []
    with fe.conexion() as conn:
        n = conn.execute("SELECT COUNT(*) FROM lectura_telemetria WHERE id_sensor='SEN_02'").fetchone()[0]
    assert n == 100


def test_plan_de_ejecucion_usa_indice(base_d):
    conn = sqlite3.connect(Caso7.DB_NAME)
    plan = conn.execute(
        "EXPLAIN QUERY PLAN SELECT * FROM lectura_telemetria "
        "WHERE id_sensor = 'SEN_02' AND timestamp_lectura > 1800000100;").fetchall()
    conn.close()
    detalle = " ".join(str(p[-1]) for p in plan)
    assert "SEARCH" in detalle and "INDEX" in detalle and "SCAN" not in detalle


# ---------------------------------------------------------------- Fase E: reglas
def test_rn1_rechaza_timestamp_invalido(base_e):
    with fe.conexion() as conn:
        for ts in (-1, 4102444800):
            with pytest.raises(sqlite3.IntegrityError, match="RN1"):
                conn.execute(INS, ("SEN_01", ts, 22.0))


def test_rn2_rechaza_sensor_en_mantenimiento(base_e):
    with fe.conexion() as conn:
        with pytest.raises(sqlite3.IntegrityError, match="RN2"):
            conn.execute(INS, ("SEN_03", T0, 10.0))


def test_rn3_rn4_clasifica_y_genera_alarma_e_incidencia(base_e):
    with fe.conexion() as conn:
        conn.execute(INS, ("SEN_01", T0 + 99999, 31.5))  # umbral de SEN_01 = 28
        nivel = conn.execute("SELECT nivel_alerta FROM lectura_telemetria WHERE id_sensor='SEN_01' "
                             "AND timestamp_lectura=?", (T0 + 99999,)).fetchone()[0]
        assert nivel == "CRITICO"
        alarma = conn.execute("SELECT id_alarma, severidad FROM alarma WHERE id_sensor='SEN_01' "
                              "AND timestamp_lectura=?", (T0 + 99999,)).fetchone()
        assert alarma["severidad"] == "CRITICO"
        inc = conn.execute("SELECT estado FROM incidencia_noc WHERE id_alarma=?", (alarma["id_alarma"],)).fetchone()
        assert inc["estado"] == "ABIERTA"


def test_rn3_lectura_normal_no_genera_alarma(base_e):
    with fe.conexion() as conn:
        antes = conn.execute("SELECT COUNT(*) FROM alarma").fetchone()[0]
        conn.execute(INS, ("SEN_01", T0 + 88888, 20.0))
        despues = conn.execute("SELECT COUNT(*) FROM alarma").fetchone()[0]
    assert antes == despues


def test_rn5_alarmas_inmutables(base_e):
    with fe.conexion() as conn:
        with pytest.raises(sqlite3.IntegrityError, match="RN5"):
            conn.execute("UPDATE alarma SET severidad='PRECAUCION' WHERE id_alarma=1")
        with pytest.raises(sqlite3.IntegrityError, match="RN5"):
            conn.execute("DELETE FROM alarma WHERE id_alarma=1")


def test_rn6_flujo_de_incidencias(base_e):
    with fe.conexion() as conn:
        inc = conn.execute("SELECT id_incidencia FROM incidencia_noc LIMIT 1").fetchone()[0]
        with pytest.raises(sqlite3.IntegrityError, match="RN6"):
            conn.execute("UPDATE incidencia_noc SET estado='CERRADA' WHERE id_incidencia=?", (inc,))
        with pytest.raises(sqlite3.IntegrityError, match="RN6"):
            conn.execute("UPDATE incidencia_noc SET estado='RECONOCIDA' WHERE id_incidencia=?", (inc,))
        conn.execute("UPDATE incidencia_noc SET estado='RECONOCIDA', responsable='noc1' WHERE id_incidencia=?", (inc,))
        conn.execute("UPDATE incidencia_noc SET estado='CERRADA' WHERE id_incidencia=?", (inc,))
        with pytest.raises(sqlite3.IntegrityError, match="RN6"):
            conn.execute("UPDATE incidencia_noc SET estado='ABIERTA' WHERE id_incidencia=?", (inc,))


# ---------------------------------------------------------------- Fase E: consultas y retención
def test_vistas_devuelven_datos(base_e):
    with fe.conexion() as conn:
        racks = {r["rack_ubicacion"] for r in conn.execute("SELECT * FROM v_estabilidad_termica")}
        pasillos = {r["pasillo"] for r in conn.execute("SELECT * FROM v_consumo_por_pasillo")}
    assert {"Rack_A1", "Rack_A2", "Rack_Z9"} <= racks
    assert "Pasillo_Frio_1" in pasillos


def test_retencion_resume_y_purga_datos_frios(base_e):
    """Resume todo el dato frío y lo purga, salvo las lecturas que respaldan una alarma (trazabilidad)."""
    limite = T0 - 30 * 86400
    with fe.conexion() as conn:
        antes = conn.execute("SELECT COUNT(*) FROM lectura_telemetria").fetchone()[0]
        con_alarma = conn.execute("SELECT COUNT(*) FROM alarma WHERE timestamp_lectura < ?", (limite,)).fetchone()[0]
        fe.aplicar_retencion(conn, dias=30)
        despues = conn.execute("SELECT COUNT(*) FROM lectura_telemetria").fetchone()[0]
        resumen = conn.execute("SELECT SUM(n_lecturas) FROM resumen_horario").fetchone()[0]
        frias = conn.execute("SELECT COUNT(*) FROM lectura_telemetria WHERE timestamp_lectura < ?",
                             (limite,)).fetchone()[0]
    assert resumen == 12                      # 6 lecturas frías de SEN_01 + 6 de SEN_05, todas resumidas
    assert antes - despues == 12 - con_alarma  # se purga todo lo frío que no respalda una alarma
    assert frias == con_alarma                # las lecturas con alarma se conservan


def test_left_join_detecta_sensores_sin_lecturas(base_e):
    with fe.conexion() as conn:
        filas = conn.execute("""SELECT s.id_sensor FROM sensor_iot s
                                LEFT JOIN lectura_telemetria l ON l.id_sensor = s.id_sensor
                                WHERE l.id_sensor IS NULL""").fetchall()
    assert [f[0] for f in filas] == ["SEN_03"]


@pytest.mark.skipif(sqlite3.sqlite_version_info < (3, 39, 0), reason="FULL JOIN requiere SQLite 3.39+")
def test_full_join_encuentra_huerfanos(base_e):
    with fe.conexion() as conn:
        filas = conn.execute("""SELECT s.id_sensor, p.rack_ubicacion FROM sensor_iot s
                                FULL JOIN rack_pasillo p ON s.rack_ubicacion = p.rack_ubicacion
                                WHERE s.id_sensor IS NULL OR p.rack_ubicacion IS NULL""").fetchall()
    assert {(f[0], f[1]) for f in filas} == {("SEN_04", None), (None, "Rack_C1")}


# ---------------------------------------------------------------- Fase E: NoSQL y grafos
def test_documentos_y_grafo_son_consistentes_con_sql(base_e):
    with fe.conexion() as conn:
        sensores, alarmas = fe.construir_documentos(conn)
        G = fe.construir_grafo(conn)
        n_s = conn.execute("SELECT COUNT(*) FROM sensor_iot").fetchone()[0]
        n_a = conn.execute("SELECT COUNT(*) FROM alarma").fetchone()[0]
    assert len(sensores.docs) == n_s == sum(1 for _, d in G.nodes(data=True) if d["tipo"] == "Sensor")
    assert len(alarmas.docs) == n_a == sum(1 for _, d in G.nodes(data=True) if d["tipo"] == "Alarma")


def test_filtros_documentales(base_e):
    with fe.conexion() as conn:
        sensores, _ = fe.construir_documentos(conn)
    ids = [d["_id"] for d in sensores.buscar({"tipo_metrica": "TEMPERATURA", "ubicacion.pasillo": "Pasillo_Frio_1",
                                              "estadisticas.max": {"$gt": 28}})]
    assert set(ids) == {"SEN_01", "SEN_05"}


def test_grafo_radio_de_impacto_y_huerfanos(base_e):
    import networkx as nx
    with fe.conexion() as conn:
        G = fe.construir_grafo(conn)
    afectados = {n for n in nx.descendants(G, "Pasillo_Frio_1") if G.nodes[n]["tipo"] == "Sensor"}
    assert afectados == {"SEN_01", "SEN_02", "SEN_03", "SEN_05", "SEN_06", "SEN_07"}
    assert [n for n in G if G.nodes[n]["tipo"] == "Rack" and G.out_degree(n) == 0] == ["Rack_C1"]
    assert "SEN_04" in nx.descendants(G, "SIN_PASILLO")
