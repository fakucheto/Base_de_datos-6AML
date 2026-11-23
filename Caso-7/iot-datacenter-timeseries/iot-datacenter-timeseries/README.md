# Monitoreo IoT en Datacenters (Series temporales) · Caso 7

[![CI](https://github.com/TU_USUARIO/iot-datacenter-timeseries/actions/workflows/ci.yml/badge.svg)](https://github.com/TU_USUARIO/iot-datacenter-timeseries/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%20|%203.11%20|%203.12-blue)
![Licencia](https://img.shields.io/badge/licencia-MIT-green)

Prototipo de base de datos para **capturar, almacenar y procesar telemetría** (temperatura, humedad y consumo
eléctrico) de sensores instalados en racks de datacenters, con el fin de **prevenir fallos por sobrecalentamiento**
y emitir alarmas críticas en menos de 2 segundos.

El proyecto combina tres modelos de datos sobre un mismo caso y los expone mediante una **API REST**:

| Modelo | Tecnología | Para qué se usa |
|---|---|---|
| Relacional (fuente de verdad) | SQLite | Serie temporal, reglas de negocio, alarmas, reportes y los 7 tipos de JOIN |
| Documental (NoSQL) | Almacén de documentos JSON estilo MongoDB | Documentos desnormalizados para tableros del NOC |
| Grafos | `networkx` (exporta GraphML) | Topología del datacenter, radio de impacto y trazabilidad de alarmas |
| API REST | FastAPI + Uvicorn | Conecta colectores IoT, el tablero del NOC y otras aplicaciones con la base de datos |

> **Alcance.** Es un prototipo académico de la Fase D (pruebas) y la Fase E (reglas, consultas, NoSQL y grafos).
> SQLite es un entorno de simulación; para producción se recomienda un motor de series temporales
> (ver [Limitaciones](#limitaciones-y-trabajo-futuro)).

## Contenido

1. [Contexto del caso](#contexto-del-caso)
2. [Estructura del repositorio](#estructura-del-repositorio)
3. [Instalación y ejecución](#instalación-y-ejecución)
4. [Modelo de datos](#modelo-de-datos)
5. [Reglas de negocio](#reglas-de-negocio)
6. [Consultas](#consultas)
7. [Los 7 tipos de JOIN](#los-7-tipos-de-join)
8. [NoSQL: documentos](#nosql-documentos)
9. [Grafos](#grafos)
10. [Conexión entre motores](#conexión-entre-motores)
11. [API REST: conexión de aplicaciones](#api-rest-conexión-de-aplicaciones)
12. [Rendimiento (prueba de carga)](#rendimiento-prueba-de-carga)
13. [Pruebas automáticas e integración continua](#pruebas-automáticas-e-integración-continua)
14. [Resultados esperados](#resultados-esperados)
15. [Limitaciones y trabajo futuro](#limitaciones-y-trabajo-futuro)
16. [Documentación adicional](#documentación-adicional)

## Contexto del caso

- **Problema:** un rack sobrecalentado puede causar un fallo catastrófico; hay que detectarlo y alertar rápido.
- **Objetivo medible:** alarma crítica en menos de 2 segundos.
- **Escala:** 500 sensores, una lectura cada 5 segundos (unos 8,6 millones de registros por día).
- **Retención:** 30 días caliente y 2 años de histórico agregado.
- **Actores:** sensores IoT, ingenieros del NOC (centro de operaciones de red) y motor de alertas.
- **Fuera de alcance:** el control físico de los aires acondicionados (actuadores).
- **Escenarios:** ingesta masiva, promedios horarios por pasillo, limpieza por retención, datos fuera de orden, inserción
  en lote tras reconexión, energía intermitente y saturación de disco.

La trazabilidad completa de requisitos funcionales y no funcionales está en [`docs/REQUISITOS.md`](docs/REQUISITOS.md).

## Estructura del repositorio

```
iot-datacenter-timeseries/
├── src/
│   ├── Caso7.py              # Fase D: esquema base, integridad, concurrencia, plan de ejecución y 7 JOINs
│   ├── Caso7_Fase_E.py       # Fase E: reglas, consultas, retención, NoSQL, grafos y verificación cruzada
│   ├── api.py                # API REST (FastAPI) que conecta aplicaciones con la base de datos
│   └── benchmark.py          # Prueba de carga: throughput de ingesta y latencia de alerta
├── tests/
│   ├── conftest.py
│   ├── test_caso7.py         # 18 pruebas de la base de datos (Fases D y E)
│   └── test_api.py           # 19 pruebas de la API REST
├── docs/
│   ├── ARQUITECTURA.md       # Diagramas (Mermaid) y decisiones de diseño
│   ├── REQUISITOS.md         # Trazabilidad RF/RNF -> código
│   └── presentacion/         # Diapositivas (.pptx, importables en Canva)
├── ejemplos/                 # Salidas reales: consola, documentos JSON y grafo GraphML
├── .github/workflows/ci.yml  # Integración continua (Python 3.10, 3.11 y 3.12)
├── requirements.txt
├── LICENSE
└── README.md
```

## Instalación y ejecución

**Requisitos:** Python 3.10 o superior y SQLite 3.25 o superior (funciones de ventana). Para que los ejemplos de
RIGHT y FULL JOIN usen la sintaxis nativa se necesita SQLite 3.39 o superior; con una versión anterior el código usa
equivalentes con LEFT JOIN y UNION.

```bash
# 1. Clonar el repositorio
git clone https://github.com/TU_USUARIO/iot-datacenter-timeseries.git
cd iot-datacenter-timeseries

# 2. (Opcional) entorno virtual
python -m venv .venv
source .venv/bin/activate        # En Windows: .venv\Scripts\activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Ejecutar la Fase D (integridad, concurrencia, plan de ejecución y 7 JOINs)
python src/Caso7.py

# 5. Ejecutar la Fase E (reglas, consultas, retención, NoSQL y grafos)
python src/Caso7_Fase_E.py

# 6. Levantar la API REST (Swagger en http://127.0.0.1:8000/docs)
uvicorn api:app --app-dir src --reload

# 7. Medir rendimiento de ingesta y latencia de alerta
python src/benchmark.py
```

Cada ejecución reconstruye la base desde cero. Se generan en la carpeta actual:
`iot_datacenter_fase_d.db`, `documentos_iot.json` y `grafo_datacenter.graphml` (ignorados por Git).

## Modelo de datos

Seis tablas y dos vistas. El diagrama entidad-relación está en [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md).

| Objeto | Descripción |
|---|---|
| `sensor_iot` | Catálogo de sensores: rack, métrica (TEMPERATURA, HUMEDAD, CONSUMO_KW), umbral y estado operativo |
| `lectura_telemetria` | Serie temporal. Clave primaria compuesta (sensor, timestamp), llave foránea al sensor |
| `rack_pasillo` | Mapa de racks por pasillo (relación lógica con los sensores, sin llave foránea) |
| `alarma` | Alarmas inmutables, con llave foránea compuesta hacia la lectura que las originó |
| `incidencia_noc` | Gestión de incidencias: ABIERTA, RECONOCIDA o CERRADA |
| `resumen_horario` | Histórico agregado por sensor y hora (downsampling) |
| `v_estabilidad_termica` | Vista: temperatura promedio, máxima y % sobre el umbral por rack |
| `v_consumo_por_pasillo` | Vista: consumo promedio y pico por pasillo (insumo del PUE) |

**Restricciones de integridad:** `PRIMARY KEY` compuesta (evita duplicados), `FOREIGN KEY` (sin lecturas huérfanas),
`CHECK` (solo métricas, estados y niveles válidos), `NOT NULL` y `DEFAULT`. Un índice por tiempo descendente acelera
la consulta de lecturas recientes.

## Reglas de negocio

Se implementan como **triggers** dentro de la base, por lo que se cumplen sin importar qué aplicación inserte datos.

| Regla | Qué hace |
|---|---|
| **RN1** | Rechaza lecturas con timestamp anterior al año 2000 o posterior a mañana |
| **RN2** | Rechaza lecturas de sensores que no están ACTIVO (baja lógica sin afectar al resto) |
| **RN3** | Calcula el nivel de alerta: CRITICO si supera el umbral, PRECAUCION desde el 90 % del umbral, NORMAL en los demás casos |
| **RN4** | Toda lectura PRECAUCION o CRITICA genera una alarma; las críticas abren una incidencia |
| **RN5** | Las alarmas son inmutables: no se pueden modificar ni borrar |
| **RN6** | Flujo de incidencias ABIERTA → RECONOCIDA (exige responsable) → CERRADA; no se reabre |

## Consultas

| Consulta | Descripción | Técnica |
|---|---|---|
| C1 | Promedio horario de temperatura por pasillo | JOIN, LEFT JOIN, `GROUP BY` por hora |
| C2 | Última lectura de cada sensor | Función de ventana `ROW_NUMBER() OVER (PARTITION BY ...)` |
| C3 | Top 3 sensores con más alarmas críticas | JOIN, `GROUP BY`, `ORDER BY` |
| C4 | Incidencias del NOC con su alarma | JOIN |
| C5 | Estabilidad térmica por rack | Vista |
| C6 | Consumo eléctrico por pasillo | Vista |

**Retención y downsampling** (`aplicar_retencion`): resume por hora los datos con más de 30 días en
`resumen_horario` y luego los borra de la tabla caliente, **salvo las lecturas que respaldan una alarma**, para no
romper la trazabilidad.

## Los 7 tipos de JOIN

Ejecutados por `probar_tipos_de_join()` en `src/Caso7.py`, todos sobre el mismo escenario (sensores, racks y pasillos).

| JOIN | Ejemplo en el caso | Resultado esperado |
|---|---|---|
| INNER | Lecturas que superan el umbral de su sensor | SEN_02 con 85,0 y SEN_01 con 29,5 |
| LEFT | Cantidad de lecturas por sensor | SEN_03 y SEN_04 con 0 |
| RIGHT | Racks del mapa de pasillos, tengan sensor o no | Rack_C1 sin sensor |
| FULL | Auditoría de huérfanos de ambos lados | SEN_04 sin pasillo y Rack_C1 sin sensor |
| CROSS | Cada sensor activo contra cada nivel de alerta | 3 sensores × 2 niveles = 6 filas |
| SELF | Sensores que comparten rack | SEN_01 con SEN_03 en Rack_A1 |
| NATURAL | Une automáticamente por `id_sensor` | Lecturas de SEN_01 con su rack |

> **Advertencia sobre NATURAL JOIN:** depende de que las columnas tengan el mismo nombre; si se agrega otra columna
> homónima, el resultado cambia sin aviso. En producción se prefiere `INNER JOIN ... ON`.

## NoSQL: documentos

La clase `ColeccionDocumentos` es un almacén documental mínimo con filtros estilo MongoDB (`$gt`, `$gte`, `$lt`,
`$in`) y rutas con punto (`ubicacion.pasillo`). Los datos de SQL se **desnormalizan** en dos colecciones:

```json
{
  "_id": "SEN_01",
  "tipo_metrica": "TEMPERATURA",
  "umbral": 28.0,
  "estado": "ACTIVO",
  "ubicacion": { "rack": "Rack_A1", "pasillo": "Pasillo_Frio_1" },
  "ultimas_lecturas": [{ "ts": 1700099999, "valor": 31.5, "nivel": "CRITICO" }],
  "estadisticas": { "n": 38, "promedio": 24.92, "max": 31.5 }
}
```

Equivalente en MongoDB:

```javascript
db.sensores.find({ tipo_metrica: "TEMPERATURA", "ubicacion.pasillo": "Pasillo_Frio_1", "estadisticas.max": { $gt: 28 } })
```

**Por qué encaja:** cada documento trae todo lo necesario para una pantalla del NOC sin JOINs, y permite que
distintos sensores tengan campos diferentes sin cambiar un esquema. Ver un ejemplo completo en
[`ejemplos/documentos_iot.json`](ejemplos/documentos_iot.json).

## Grafos

Se modela la topología con `networkx`: **Datacenter → Pasillo → Rack → Sensor → Alarma**, con las relaciones
`CONTIENE`, `TIENE_SENSOR` y `GENERO`. Los racks sin pasillo se conectan a un nodo `SIN_PASILLO`.

| Consulta | Pregunta de negocio | Resultado en la demo |
|---|---|---|
| G1 | ¿Qué sensores se afectan si falla la refrigeración de un pasillo? | 6 sensores del Pasillo_Frio_1 |
| G2 | ¿Qué racks no tienen sensores? | Rack_C1 |
| G3 | ¿Cuántas alarmas hay por pasillo? | Conteo por pasillo |
| G4 | ¿Por qué cadena llega una alarma? | DC_Principal → Pasillo_Frio_1 → Rack_A1 → SEN_01 → ALM_4 |
| G5 | ¿Qué sensores no tienen pasillo asignado? | SEN_04 |

Equivalente en Neo4j (Cypher) para G1:

```cypher
MATCH (:Pasillo {nombre: 'Pasillo_Frio_1'})-[:CONTIENE*]->(:Rack)-[:TIENE_SENSOR]->(s:Sensor)
RETURN s
```

El grafo se exporta a [`ejemplos/grafo_datacenter.graphml`](ejemplos/grafo_datacenter.graphml), que se abre en Gephi o
se importa a Neo4j.

> Se eligió grafos en lugar de un enfoque vectorial porque la jerarquía del datacenter y las preguntas de impacto
> encajan de forma natural. Un enfoque vectorial (similitud entre ventanas de lecturas para anticipar fallos) queda
> como trabajo futuro.

## Conexión entre motores

- `conexion()` es un administrador de contexto único para la base relacional: activa llaves foráneas y modo WAL,
  usa `timeout` de 10 segundos y hace `commit` o `rollback` automáticamente.
- SQLite es la fuente de verdad; documentos y grafo se construyen leyendo de ella.
- `verificar_integracion()` compara conteos de sensores y alarmas en los tres almacenes y avisa si hay diferencias.

## API REST: conexión de aplicaciones

`src/api.py` conecta aplicaciones externas (colectores IoT, tablero del NOC, scripts) con la base de datos. Cada
petición abre su propia conexión mediante `conexion()`. Las reglas de negocio siguen viviendo en la base: la API solo
traduce sus errores a códigos HTTP.

```bash
uvicorn api:app --app-dir src --reload      # http://127.0.0.1:8000/docs  (Swagger interactivo)
```

Si no existe una base con el esquema completo, la API la crea sola con datos de demostración.

| Método y ruta | Descripción | Requisito |
|---|---|---|
| `GET /salud` | Estado del servicio | |
| `GET /sensores`, `GET /sensores/{id}` | Listar y consultar sensores (filtros `estado`, `metrica`) | RF1 |
| `POST /sensores` | Registrar un sensor | RF1 |
| `PATCH /sensores/{id}/estado` | Baja lógica (MANTENIMIENTO, INACCESIBLE) | RF10 |
| `POST /lecturas` | Ingestar una lectura: devuelve nivel de alerta y alarma generada | RF2, RF3, RF4 |
| `POST /lecturas/lote` | Ingesta en lote atómica, omite reenvíos duplicados | Escenario alternativo |
| `GET /sensores/{id}/lecturas` | Serie temporal por rango de fechas | RF6 |
| `GET /pasillos/{pasillo}/promedio-horario` | Promedio horario por pasillo | RF6 |
| `GET /alarmas` | Alarmas, filtrables por severidad | RF5 |
| `GET /incidencias`, `PATCH /incidencias/{id}` | El NOC reconoce y cierra incidencias | RF8 |
| `GET /reportes/estabilidad-termica`, `GET /reportes/consumo-por-pasillo` | Reportes sobre las vistas | RF9 |
| `GET /documentos/sensores` | Consulta documental con filtros estilo MongoDB | NoSQL |
| `GET /grafo/impacto/{nodo}` | Racks y sensores afectados si falla un pasillo o rack | Grafos |

**Códigos de error:** `422` dato inválido (RN1 timestamp, RN2 sensor no activo), `409` conflicto (RN5, RN6 o registro
duplicado), `404` recurso inexistente. Cada respuesta incluye la cabecera `X-Tiempo-Proceso-ms`.

**Ejemplos con `curl`:**

```bash
# Ingestar una lectura crítica (umbral de SEN_01 = 28): la base la clasifica y crea la alarma
curl -X POST http://127.0.0.1:8000/lecturas -H "Content-Type: application/json" \
     -d '{"id_sensor":"SEN_01","timestamp_lectura":1700099999,"valor_metrica":31.5}'
# -> {"id_sensor":"SEN_01", ... ,"nivel_alerta":"CRITICO","id_alarma":71}

# Un sensor en mantenimiento rechaza lecturas (RN2): responde 422
curl -X POST http://127.0.0.1:8000/lecturas -H "Content-Type: application/json" \
     -d '{"id_sensor":"SEN_03","timestamp_lectura":1700000000,"valor_metrica":10}'

# El NOC reconoce una incidencia (RN6 exige responsable)
curl -X PATCH http://127.0.0.1:8000/incidencias/1 -H "Content-Type: application/json" \
     -d '{"estado":"RECONOCIDA","responsable":"ing.noc.1"}'

# Radio de impacto si falla la refrigeración de un pasillo
curl http://127.0.0.1:8000/grafo/impacto/Pasillo_Frio_1
```

## Rendimiento (prueba de carga)

`python src/benchmark.py` crea 500 sensores con todas las reglas activas, ingesta 10.000 lecturas en lotes de 500 y
mide después la latencia entre una lectura crítica y la confirmación de su alarma e incidencia.

Resultado de una ejecución de referencia (equipo de desarrollo; **varía según el equipo**, ver
[`ejemplos/salida_benchmark.txt`](ejemplos/salida_benchmark.txt)):

| Medida | Objetivo | Resultado de referencia |
|---|---|---|
| Ingesta (RNF1) | 10.000 métricas/minuto | Muy por encima del objetivo (millones por minuto) |
| Latencia de alerta (RNF2) | < 2.000 ms | Mediana ~2 ms, máximo ~3 ms |

> Es una medición del **prototipo en SQLite**: un solo proceso, sin red y sin el protocolo MQTT/HTTP. Demuestra que el
> diseño de la base no es el cuello de botella, pero no sustituye una prueba de carga del sistema completo.

## Pruebas automáticas e integración continua

```bash
pytest -v
```

Las 37 pruebas (18 de base de datos y 19 de la API) cubren: clave primaria, llave foránea, `CHECK`, concurrencia sin pérdida de datos, plan de ejecución
con índice, las reglas RN1 a RN6, vistas, retención, LEFT y FULL JOIN, consistencia entre SQL, documentos y grafo,
filtros documentales y consultas de grafo; en la API, la ingesta, los códigos de error 404, 409 y 422, la baja lógica, el
lote atómico, el flujo de incidencias, los reportes, los documentos y el grafo. Cada prueba usa una carpeta temporal.

El flujo de [GitHub Actions](.github/workflows/ci.yml) ejecuta las pruebas, ambos scripts y la prueba de carga en Python 3.10, 3.11 y
3.12 en cada `push` a `main` y en cada `pull request`.

## Resultados esperados

Las salidas reales de una ejecución están en [`ejemplos/salida_fase_d.txt`](ejemplos/salida_fase_d.txt) y
[`ejemplos/salida_fase_e.txt`](ejemplos/salida_fase_e.txt). Fragmento de la Fase E:

```
Sensores -> SQL: 7 | Documentos: 7 | Grafo: 7
Alarmas  -> SQL: 71 | Documentos: 71 | Grafo: 71
[OK] Los tres almacenes son consistentes.
```

## Limitaciones y trabajo futuro

- La prueba de carga mide solo el prototipo en SQLite (un proceso, sin red); falta una prueba del sistema completo con
  500 sensores reales o simulados enviando por MQTT/HTTP.
- La API no incluye autenticación ni limitación de peticiones; en producción debe ir detrás de HTTPS y de un control de acceso.
- SQLite admite **un solo escritor a la vez**: en la prueba de concurrencia los hilos se turnan. Para el volumen real
  se recomienda TimescaleDB, InfluxDB o ClickHouse.
- Los triggers evalúan alertas dentro de la inserción; a gran escala conviene un servicio de streaming.
- El almacén documental y el grafo se reconstruyen por lotes; una versión real los mantendría sincronizados por eventos
  y usaría MongoDB y Neo4j.
- La ingesta por MQTT (broker), los buffers locales de los colectores y los escenarios de energía intermitente y saturación de
  disco no están implementados.
- El PUE completo requiere el consumo total de la instalación; aquí solo se calcula el consumo por pasillo.
- Particionado por tiempo, modo de recuperación ante fallos y un enfoque vectorial para detección de anomalías.

## Documentación adicional

- [Arquitectura y diagramas](docs/ARQUITECTURA.md)
- [Trazabilidad de requisitos](docs/REQUISITOS.md)
- [Presentación (.pptx)](docs/presentacion/Caso7_Presentacion.pptx)

## Licencia

Distribuido bajo la licencia MIT. Ver [`LICENSE`](LICENSE).
