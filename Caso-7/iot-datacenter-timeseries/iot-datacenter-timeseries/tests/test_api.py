"""Pruebas de la API REST: conexión de aplicaciones externas con la base de datos."""
import pytest
from fastapi.testclient import TestClient

import api

T0 = 1700000000


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # cada prueba crea su propia base de demostración
    with TestClient(api.app) as c:
        yield c


def test_salud_y_cabecera_de_tiempo(client):
    r = client.get("/salud")
    assert r.status_code == 200 and r.json()["estado"] == "ok"
    assert "x-tiempo-proceso-ms" in r.headers


def test_listar_y_filtrar_sensores(client):
    assert len(client.get("/sensores").json()) == 7
    mant = client.get("/sensores", params={"estado": "MANTENIMIENTO"}).json()
    assert [s["id_sensor"] for s in mant] == ["SEN_03"]


def test_sensor_inexistente_devuelve_404(client):
    assert client.get("/sensores/NO_EXISTE").status_code == 404


def test_registrar_sensor_y_rechazar_duplicado(client):
    nuevo = {"id_sensor": "SEN_10", "rack_ubicacion": "Rack_A1", "tipo_metrica": "TEMPERATURA", "umbral_limite": 30}
    assert client.post("/sensores", json=nuevo).status_code == 201
    assert client.post("/sensores", json=nuevo).status_code == 409


def test_metrica_invalida_devuelve_422(client):
    malo = {"id_sensor": "X", "rack_ubicacion": "R", "tipo_metrica": "PRESION", "umbral_limite": 1}
    assert client.post("/sensores", json=malo).status_code == 422


def test_lectura_critica_genera_alarma(client):
    r = client.post("/lecturas", json={"id_sensor": "SEN_01", "timestamp_lectura": T0 + 99999, "valor_metrica": 31.5})
    assert r.status_code == 201
    cuerpo = r.json()
    assert cuerpo["nivel_alerta"] == "CRITICO" and cuerpo["id_alarma"] is not None
    inc = client.get("/incidencias", params={"estado": "ABIERTA"}).json()
    assert any(i["id_alarma"] == cuerpo["id_alarma"] for i in inc)


def test_lectura_normal_no_genera_alarma(client):
    r = client.post("/lecturas", json={"id_sensor": "SEN_01", "timestamp_lectura": T0 + 88888, "valor_metrica": 20.0})
    assert r.json()["nivel_alerta"] == "NORMAL" and r.json()["id_alarma"] is None


def test_reglas_rn1_y_rn2_devuelven_422(client):
    r1 = client.post("/lecturas", json={"id_sensor": "SEN_01", "timestamp_lectura": -1, "valor_metrica": 22})
    assert r1.status_code == 422 and "RN1" in r1.json()["detail"]
    r2 = client.post("/lecturas", json={"id_sensor": "SEN_03", "timestamp_lectura": T0, "valor_metrica": 10})
    assert r2.status_code == 422 and "RN2" in r2.json()["detail"]


def test_lectura_de_sensor_inexistente_404(client):
    r = client.post("/lecturas", json={"id_sensor": "SEN_999", "timestamp_lectura": T0, "valor_metrica": 1})
    assert r.status_code == 404


def test_lectura_duplicada_409(client):
    lectura = {"id_sensor": "SEN_01", "timestamp_lectura": T0 + 77777, "valor_metrica": 20}
    assert client.post("/lecturas", json=lectura).status_code == 201
    assert client.post("/lecturas", json=lectura).status_code == 409


def test_baja_logica_de_sensor_detiene_su_ingesta(client):
    assert client.patch("/sensores/SEN_01/estado", json={"estado": "MANTENIMIENTO"}).status_code == 200
    r = client.post("/lecturas", json={"id_sensor": "SEN_01", "timestamp_lectura": T0 + 66666, "valor_metrica": 20})
    assert r.status_code == 422
    # los demás sensores siguen ingestando (RF10)
    r = client.post("/lecturas", json={"id_sensor": "SEN_05", "timestamp_lectura": T0 + 66666, "valor_metrica": 20})
    assert r.status_code == 201


def test_lote_omite_duplicados_y_es_atomico(client):
    lote = {"lecturas": [
        {"id_sensor": "SEN_01", "timestamp_lectura": T0, "valor_metrica": 24.0},        # ya existe en la demo
        {"id_sensor": "SEN_01", "timestamp_lectura": T0 + 55555, "valor_metrica": 20.0},
    ]}
    r = client.post("/lecturas/lote", json=lote).json()
    assert (r["recibidas"], r["insertadas"], r["omitidas"]) == (2, 1, 1)
    # lote con una lectura inválida: no entra ninguna
    malo = {"lecturas": [
        {"id_sensor": "SEN_01", "timestamp_lectura": T0 + 44444, "valor_metrica": 20.0},
        {"id_sensor": "SEN_01", "timestamp_lectura": -5, "valor_metrica": 20.0},
    ]}
    assert client.post("/lecturas/lote", json=malo).status_code == 422
    filas = client.get("/sensores/SEN_01/lecturas", params={"desde": T0 + 44444, "hasta": T0 + 44444}).json()
    assert filas == []


def test_consultar_lecturas_por_rango(client):
    filas = client.get("/sensores/SEN_01/lecturas", params={"desde": T0, "hasta": T0 + 600, "limite": 50}).json()
    assert len(filas) == 3 and filas[0]["timestamp_lectura"] > filas[-1]["timestamp_lectura"]


def test_promedio_horario_por_pasillo(client):
    filas = client.get("/pasillos/Pasillo_Frio_1/promedio-horario", params={"metrica": "TEMPERATURA"}).json()
    assert len(filas) >= 3 and all("promedio" in f for f in filas)


def test_flujo_de_incidencias_rn6(client):
    inc = client.get("/incidencias").json()[0]["id_incidencia"]
    assert client.patch(f"/incidencias/{inc}", json={"estado": "CERRADA"}).status_code == 409
    assert client.patch(f"/incidencias/{inc}", json={"estado": "RECONOCIDA"}).status_code == 409  # sin responsable
    ok = client.patch(f"/incidencias/{inc}", json={"estado": "RECONOCIDA", "responsable": "noc1"})
    assert ok.status_code == 200 and ok.json()["estado"] == "RECONOCIDA"
    cerrada = client.patch(f"/incidencias/{inc}", json={"estado": "CERRADA", "nota_cierre": "Ajuste de ventilacion"})
    assert cerrada.json()["estado"] == "CERRADA"
    assert client.patch(f"/incidencias/{inc}", json={"estado": "ABIERTA"}).status_code == 409
    assert client.patch("/incidencias/99999", json={"estado": "RECONOCIDA", "responsable": "x"}).status_code == 404


def test_alarmas_filtradas_por_severidad(client):
    criticas = client.get("/alarmas", params={"severidad": "CRITICO", "limite": 500}).json()
    assert criticas and all(a["severidad"] == "CRITICO" for a in criticas)


def test_reportes(client):
    racks = {r["rack_ubicacion"] for r in client.get("/reportes/estabilidad-termica").json()}
    assert {"Rack_A1", "Rack_A2", "Rack_Z9"} <= racks
    assert any(p["pasillo"] == "Pasillo_Frio_1" for p in client.get("/reportes/consumo-por-pasillo").json())


def test_documentos_con_filtros_estilo_mongo(client):
    docs = client.get("/documentos/sensores", params={"tipo_metrica": "TEMPERATURA", "pasillo": "Pasillo_Frio_1",
                                                      "max_mayor_que": 28}).json()
    assert {d["_id"] for d in docs} == {"SEN_01", "SEN_05"}


def test_grafo_radio_de_impacto(client):
    r = client.get("/grafo/impacto/Pasillo_Frio_1").json()
    assert set(r["sensores_afectados"]) == {"SEN_01", "SEN_02", "SEN_03", "SEN_05", "SEN_06", "SEN_07"}
    assert client.get("/grafo/impacto/NO_EXISTE").status_code == 404
