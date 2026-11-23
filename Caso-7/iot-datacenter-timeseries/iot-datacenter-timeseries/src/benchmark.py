"""
Prueba de carga del prototipo: mide el rendimiento de ingesta (RNF1) y la latencia de alerta (RNF2).

    python src/benchmark.py [lecturas_totales]      (por defecto 10000)

Trabaja en una carpeta temporal y con todas las reglas de negocio activas (triggers, alarmas e incidencias).
Los resultados dependen del equipo donde se ejecute: es una medición del PROTOTIPO en SQLite, no del sistema final.
"""
import os
import random
import statistics
import sys
import tempfile
import time

import Caso7
import Caso7_Fase_E as fe

N_SENSORES = 500          # escala del caso
INTERVALO_S = 5           # una lectura cada 5 segundos por sensor
OBJETIVO_METRICAS_MIN = 10_000
OBJETIVO_LATENCIA_MS = 2_000


def preparar():
    Caso7.inicializar_entorno()
    with fe.conexion() as conn:
        fe.ampliar_esquema(conn)
        fe.crear_reglas_negocio(conn)
        conn.executemany("INSERT INTO sensor_iot VALUES (?, ?, 'TEMPERATURA', 28.0, 'ACTIVO')",
                         [(f"B_{i:03d}", f"Rack_{i % 50:02d}") for i in range(N_SENSORES)])


def medir_throughput(total):
    rng = random.Random(1)
    filas = [(f"B_{i % N_SENSORES:03d}", fe.T0 + (i // N_SENSORES) * INTERVALO_S, round(rng.uniform(20, 30), 1))
             for i in range(total)]
    inicio = time.perf_counter()
    with fe.conexion() as conn:
        for k in range(0, total, 500):  # lotes de 500 lecturas, un commit por lote
            conn.executemany("INSERT INTO lectura_telemetria (id_sensor, timestamp_lectura, valor_metrica) "
                             "VALUES (?, ?, ?)", filas[k:k + 500])
            conn.commit()
    seg = time.perf_counter() - inicio
    with fe.conexion() as conn:
        alarmas = conn.execute("SELECT COUNT(*) FROM alarma").fetchone()[0]
    return total / seg * 60, seg, alarmas


def medir_latencia(muestras=300):
    """Tiempo desde que llega la lectura crítica hasta que la alarma y la incidencia están confirmadas (commit)."""
    tiempos = []
    for i in range(muestras):
        sensor, ts = f"B_{i % N_SENSORES:03d}", fe.T0 + 10_000_000 + i
        t0 = time.perf_counter()
        with fe.conexion() as conn:
            conn.execute("INSERT INTO lectura_telemetria (id_sensor, timestamp_lectura, valor_metrica) "
                         "VALUES (?, ?, 35.0)", (sensor, ts))
        with fe.conexion() as conn:
            ok = conn.execute("SELECT 1 FROM alarma a JOIN incidencia_noc i ON i.id_alarma = a.id_alarma "
                              "WHERE a.id_sensor = ? AND a.timestamp_lectura = ?", (sensor, ts)).fetchone()
        tiempos.append((time.perf_counter() - t0) * 1000)
        assert ok, "la alarma no se generó"
    tiempos.sort()
    return statistics.median(tiempos), tiempos[int(len(tiempos) * 0.95) - 1], tiempos[-1]


def main():
    total = int(sys.argv[1]) if len(sys.argv) > 1 else 10_000
    original = os.getcwd()
    with tempfile.TemporaryDirectory() as tmp:
        os.chdir(tmp)
        try:
            print(f"Preparando {N_SENSORES} sensores con las reglas de negocio activas...")
            preparar()
            mpm, seg, alarmas = medir_throughput(total)
            p50, p95, pmax = medir_latencia()
        finally:
            os.chdir(original)
    print(f"\nRNF1 - Ingesta: {total} lecturas en {seg:.2f} s = {mpm:,.0f} métricas/minuto "
          f"(objetivo: {OBJETIVO_METRICAS_MIN:,}) -> {'CUMPLE' if mpm >= OBJETIVO_METRICAS_MIN else 'NO CUMPLE'}")
    print(f"           Alarmas generadas durante la carga: {alarmas}")
    print(f"RNF2 - Latencia de alerta (lectura crítica -> alarma e incidencia confirmadas), 300 muestras:")
    print(f"           mediana {p50:.2f} ms | p95 {p95:.2f} ms | máximo {pmax:.2f} ms "
          f"(objetivo: < {OBJETIVO_LATENCIA_MS} ms) -> {'CUMPLE' if pmax < OBJETIVO_LATENCIA_MS else 'NO CUMPLE'}")
    print("\nNota: medición del prototipo en SQLite, de un solo proceso y sin red; no sustituye una prueba de carga "
          "del sistema completo con ingesta MQTT/HTTP.")


if __name__ == "__main__":
    main()
