import sqlite3
import os
import threading

DB_NAME = "iot_datacenter_fase_d.db"

def inicializar_entorno():
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)
    
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()

    # DDL Físico Completo Caso 7
    cursor.execute("""
    CREATE TABLE sensor_iot (
        id_sensor TEXT PRIMARY KEY,
        rack_ubicacion TEXT NOT NULL,
        tipo_metrica TEXT NOT NULL CHECK (tipo_metrica IN ('TEMPERATURA', 'HUMEDAD', 'CONSUMO_KW')),
        umbral_limite REAL NOT NULL,
        estado_operativo TEXT DEFAULT 'ACTIVO' CHECK (estado_operativo IN ('ACTIVO', 'MANTENIMIENTO', 'INACCESIBLE'))
    );
    """)

    cursor.execute("""
    CREATE TABLE lectura_telemetria (
        id_sensor TEXT NOT NULL,
        timestamp_lectura INTEGER NOT NULL,
        valor_metrica REAL NOT NULL,
        nivel_alerta TEXT DEFAULT 'NORMAL' CHECK (nivel_alerta IN ('NORMAL', 'PRECAUCION', 'CRITICO')),
        PRIMARY KEY (id_sensor, timestamp_lectura),
        FOREIGN KEY (id_sensor) REFERENCES sensor_iot(id_sensor)
    );
    """)

    # Tabla auxiliar: mapa de racks por pasillo (requisito: consultas por pasillo del datacenter)
    cursor.execute("""
    CREATE TABLE rack_pasillo (
        rack_ubicacion TEXT PRIMARY KEY,
        pasillo TEXT NOT NULL
    );
    """)

    cursor.execute("CREATE INDEX idx_telemetria_tiempo ON lectura_telemetria(timestamp_lectura DESC);")
    
    # Datos semilla de prueba
    cursor.execute("INSERT INTO sensor_iot VALUES ('SEN_01', 'Rack_A1', 'TEMPERATURA', 28.0, 'ACTIVO');")
    cursor.execute("INSERT INTO sensor_iot VALUES ('SEN_02', 'Rack_A2', 'HUMEDAD', 80.0, 'ACTIVO');")
    # Sensores adicionales para los ejemplos de JOIN
    cursor.execute("INSERT INTO sensor_iot VALUES ('SEN_03', 'Rack_A1', 'CONSUMO_KW', 15.0, 'MANTENIMIENTO');")  # sin lecturas, mismo rack que SEN_01
    cursor.execute("INSERT INTO sensor_iot VALUES ('SEN_04', 'Rack_Z9', 'TEMPERATURA', 30.0, 'ACTIVO');")       # rack sin pasillo asignado
    # Mapa de racks por pasillo
    cursor.execute("INSERT INTO rack_pasillo VALUES ('Rack_A1', 'Pasillo_Frio_1');")
    cursor.execute("INSERT INTO rack_pasillo VALUES ('Rack_A2', 'Pasillo_Frio_1');")
    cursor.execute("INSERT INTO rack_pasillo VALUES ('Rack_C1', 'Pasillo_Caliente_2');")  # rack sin sensores instalados
    conn.commit()
    conn.close()
    print("[+] Entorno inicializado limpiamente.")

# 1. Pruebas de Integridad (Normales, Límites, Duplicados y Fechas Extremas)
def probar_integridad_y_limites():
    print("\n--- [FASE D] 1. PRUEBAS DE INTEGRIDAD Y CASOS LÍMITE ---")
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()

    # Caso Normal
    try:
        cursor.execute("INSERT INTO lectura_telemetria VALUES ('SEN_01', 1700000000, 24.5, 'NORMAL');")
        conn.commit()
        print("[ÉXITO] Inserción normal aceptada.")
    except Exception as e:
        print(f"[FALLO] {e}")

    # Caso Límite / Fecha Extrema (Epoch negativo o muy lejano)
    try:
        cursor.execute("INSERT INTO lectura_telemetria VALUES ('SEN_01', -1, 22.0, 'NORMAL');")
        conn.commit()
        print("[ÉXITO] Fecha extrema (timestamp negativo/histórico) aceptada por el esquema numérico.")
    except Exception as e:
        print(f"[FALLO] {e}")

    # Caso Duplicado (Violación de Clave Primaria compuesta id_sensor + timestamp)
    try:
        cursor.execute("INSERT INTO lectura_telemetria VALUES ('SEN_01', 1700000000, 25.0, 'NORMAL');")
        conn.commit()
    except sqlite3.IntegrityError as e:
        print(f"[ÉXITO] Duplicado rechazado correctamente por Primary Key: {e}")

    # Caso Referencia Inválida (Foreign Key)
    try:
        cursor.execute("INSERT INTO lectura_telemetria VALUES ('SEN_999', 1700000000, 20.0, 'NORMAL');")
        conn.commit()
    except sqlite3.IntegrityError as e:
        print(f"[ÉXITO] Referencia inválida de sensor rechazada por Foreign Key: {e}")

    conn.close()

# 2. Pruebas de Concurrencia Multisesión (Dos o más hilos/sesiones escribiendo simultáneamente)
ERRORES_CONCURRENCIA = []  # errores reportados por los hilos (para no afirmar éxito si hubo fallos)

def sesion_escritora_concurriente(nombre_sesion, timestamp_base):
    try:
        conn = sqlite3.connect(DB_NAME, timeout=10)
        conn.execute("PRAGMA foreign_keys = ON;")
        cursor = conn.cursor()
        # Cada sesión inserta ráfagas masivas independientes
        for i in range(50):
            ts = timestamp_base + i
            cursor.execute("INSERT OR IGNORE INTO lectura_telemetria VALUES ('SEN_02', ?, ?, 'NORMAL');", (ts, 45.0 + (i % 5)))
        conn.commit()
        conn.close()
        print(f"[CONCURRENCIA] {nombre_sesion} finalizó su lote con éxito.")
    except Exception as e:
        ERRORES_CONCURRENCIA.append((nombre_sesion, str(e)))
        print(f"[CONCURRENCIA] Error en {nombre_sesion}: {e}")

def probar_concurrencia_multisesion():
    print("\n--- [FASE D] 2. PRUEBAS DE CONCURRENCIA MULTISESIÓN ---")
    ERRORES_CONCURRENCIA.clear()
    # Lanzamos dos sesiones concurrentes simulando colectores IoT enviando datos al tiempo
    t1 = threading.Thread(target=sesion_escritora_concurriente, args=("Sesion_Colector_A", 1800000100))
    t2 = threading.Thread(target=sesion_escritora_concurriente, args=("Sesion_Colector_B", 1800000200))

    t1.start()
    t2.start()
    t1.join()
    t2.join()
    if ERRORES_CONCURRENCIA:
        print(f"[FALLO] Hubo errores en {len(ERRORES_CONCURRENCIA)} sesión(es): {ERRORES_CONCURRENCIA}")
    else:
        print("[ÉXITO] Ambas sesiones concluyeron sin bloqueos fatales (Deadlocks) gracias al diseño Append-Only.")

# 3. Rendimiento y Plan de Ejecución
def probar_rendimiento_plan():
    print("\n--- [FASE D] 3. RENDIMIENTO Y PLAN DE EJECUCIÓN (EXPLAIN) ---")
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
   # Análisis del plan para consulta de rango temporal
    cursor.execute("EXPLAIN QUERY PLAN SELECT * FROM lectura_telemetria WHERE id_sensor = 'SEN_02' AND timestamp_lectura > 1800000100;")
    planes = cursor.fetchall()
    for plan in planes:
        print(f"[PLAN EXPLAIN] {plan}")
    conn.close()


# 4. Ejemplos reales de los 7 tipos de JOIN aplicados al Monitoreo IoT
def _mostrar(titulo, descripcion, cursor, sql):
    print(f"\n  >> {titulo}")
    print(f"     Caso de uso: {descripcion}")
    cursor.execute(sql)
    cols = [d[0] for d in cursor.description]
    print(f"     Columnas: {cols}")
    filas = cursor.fetchall()
    for fila in filas:
        print(f"     {fila}")
    if not filas:
        print("     (sin resultados)")

def probar_tipos_de_join():
    print("\n--- [FASE D] 4. EJEMPLOS DE LOS 7 TIPOS DE JOIN ---")
    conn = sqlite3.connect(DB_NAME)
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()

    # Lecturas adicionales (incluye valores sobre el umbral y una lectura fuera de orden)
    lecturas = [
        ("SEN_01", 1700000005, 29.5, "CRITICO"),
        ("SEN_01", 1700000010, 27.0, "PRECAUCION"),
        ("SEN_01", 1700000003, 26.0, "NORMAL"),   # llegó tarde por latencia de red
        ("SEN_02", 1700000005, 85.0, "CRITICO"),
    ]
    cursor.executemany("INSERT OR IGNORE INTO lectura_telemetria VALUES (?, ?, ?, ?);", lecturas)
    conn.commit()

    # SQLite soporta RIGHT/FULL JOIN desde la versión 3.39.0
    soporta_right_full = sqlite3.sqlite_version_info >= (3, 39, 0)
    print(f"  SQLite versión {sqlite3.sqlite_version} | RIGHT/FULL JOIN nativos: {soporta_right_full}")

    # 1) INNER JOIN: solo lecturas que tienen sensor y superan el umbral (motor de alertas)
    _mostrar("1. INNER JOIN", "Lecturas que superan el umbral del sensor (alarmas a emitir)", cursor, """
        SELECT s.id_sensor, s.rack_ubicacion, l.timestamp_lectura, l.valor_metrica, s.umbral_limite
        FROM lectura_telemetria l
        INNER JOIN sensor_iot s ON l.id_sensor = s.id_sensor
        WHERE l.valor_metrica > s.umbral_limite
        ORDER BY l.timestamp_lectura;
    """)

    # 2) LEFT JOIN: todos los sensores, incluso los que no han reportado (detecta sensores caídos)
    _mostrar("2. LEFT JOIN", "Cantidad de lecturas por sensor; 0 = sensor mudo/en mantenimiento", cursor, """
        SELECT s.id_sensor, s.estado_operativo, COUNT(l.timestamp_lectura) AS total_lecturas
        FROM sensor_iot s
        LEFT JOIN lectura_telemetria l ON s.id_sensor = l.id_sensor
        GROUP BY s.id_sensor, s.estado_operativo
        ORDER BY s.id_sensor;
    """)

    # 3) RIGHT JOIN: todos los racks del mapa de pasillos, tengan o no sensores instalados
    if soporta_right_full:
        sql_right = """
            SELECT p.pasillo, p.rack_ubicacion, s.id_sensor, s.tipo_metrica
            FROM sensor_iot s
            RIGHT JOIN rack_pasillo p ON s.rack_ubicacion = p.rack_ubicacion
            ORDER BY p.pasillo, p.rack_ubicacion;
        """
    else:  # Equivalente: invertir tablas y usar LEFT JOIN
        sql_right = """
            SELECT p.pasillo, p.rack_ubicacion, s.id_sensor, s.tipo_metrica
            FROM rack_pasillo p
            LEFT JOIN sensor_iot s ON s.rack_ubicacion = p.rack_ubicacion
            ORDER BY p.pasillo, p.rack_ubicacion;
        """
    _mostrar("3. RIGHT JOIN", "Racks por pasillo; Rack_C1 aparece sin sensor (cobertura faltante)", cursor, sql_right)

    # 4) FULL JOIN: sensores sin pasillo Y racks sin sensor en una sola auditoría
    if soporta_right_full:
        sql_full = """
            SELECT s.id_sensor, s.rack_ubicacion AS rack_sensor, p.rack_ubicacion AS rack_mapa, p.pasillo
            FROM sensor_iot s
            FULL JOIN rack_pasillo p ON s.rack_ubicacion = p.rack_ubicacion
            ORDER BY s.id_sensor;
        """
    else:  # Equivalente: UNION de LEFT JOIN en ambos sentidos
        sql_full = """
            SELECT s.id_sensor, s.rack_ubicacion, p.rack_ubicacion, p.pasillo
            FROM sensor_iot s LEFT JOIN rack_pasillo p ON s.rack_ubicacion = p.rack_ubicacion
            UNION
            SELECT s.id_sensor, s.rack_ubicacion, p.rack_ubicacion, p.pasillo
            FROM rack_pasillo p LEFT JOIN sensor_iot s ON s.rack_ubicacion = p.rack_ubicacion;
        """
    _mostrar("4. FULL JOIN", "Auditoría: SEN_04 (Rack_Z9) sin pasillo y Rack_C1 sin sensor", cursor, sql_full)

    # 5) CROSS JOIN: producto cartesiano sensor x nivel de escalamiento (plan de notificaciones)
    _mostrar("5. CROSS JOIN", "Matriz de notificaciones: cada sensor activo contra cada nivel de alerta", cursor, """
        SELECT s.id_sensor, n.nivel_alerta, n.canal_notificacion
        FROM sensor_iot s
        CROSS JOIN (
            SELECT 'PRECAUCION' AS nivel_alerta, 'Panel NOC' AS canal_notificacion
            UNION ALL SELECT 'CRITICO', 'Panel NOC + SMS'
        ) n
        WHERE s.estado_operativo = 'ACTIVO'
        ORDER BY s.id_sensor, n.nivel_alerta;
    """)

    # 6) SELF JOIN: la tabla sensor_iot contra sí misma, sensores que comparten rack
    _mostrar("6. SELF JOIN", "Pares de sensores en el mismo rack (correlación de métricas)", cursor, """
        SELECT a.id_sensor AS sensor_1, a.tipo_metrica AS metrica_1,
               b.id_sensor AS sensor_2, b.tipo_metrica AS metrica_2, a.rack_ubicacion
        FROM sensor_iot a
        JOIN sensor_iot b ON a.rack_ubicacion = b.rack_ubicacion
                         AND a.id_sensor < b.id_sensor;
    """)

    # 7) NATURAL JOIN: une por columnas homónimas (aquí solo id_sensor en ambas tablas)
    _mostrar("7. NATURAL JOIN", "Lecturas con datos del sensor, unido automáticamente por id_sensor", cursor, """
        SELECT id_sensor, rack_ubicacion, timestamp_lectura, valor_metrica, nivel_alerta
        FROM sensor_iot
        NATURAL JOIN lectura_telemetria
        WHERE id_sensor = 'SEN_01'
        ORDER BY timestamp_lectura;
    """)

    conn.close()

if __name__ == "__main__":
    inicializar_entorno()
    probar_integridad_y_limites()
    probar_concurrencia_multisesion()
    probar_rendimiento_plan()
    probar_tipos_de_join()
