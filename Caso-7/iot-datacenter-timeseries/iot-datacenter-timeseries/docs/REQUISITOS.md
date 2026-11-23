# Trazabilidad de requisitos

## Requisitos funcionales

| RF | Requisito | Dónde se implementa |
|---|---|---|
| RF1 | Registro y parametrización de sensores por rack | Tabla `sensor_iot` (rack, métrica, umbral, estado) |
| RF2 | Ingesta continua de telemetría | `lectura_telemetria`, `conexion()` y la API REST (`POST /lecturas`, `POST /lecturas/lote`); el protocolo MQTT con broker queda fuera del prototipo |
| RF3 | Validar integridad del paquete | `NOT NULL`, `CHECK`, llave foránea y trigger RN1 (timestamp UTC válido) |
| RF4 | Evaluar contra umbrales | Triggers RN3 y RN4 |
| RF5 | Alarmas inmutables con marca de tiempo y severidad | Tabla `alarma` y triggers RN5 |
| RF6 | Consultas por rango de fechas, sensor y pasillo | Consultas C1 a C3, clave compuesta, índices, colección `sensores` y rutas `GET /sensores/{id}/lecturas` y `GET /pasillos/{pasillo}/promedio-horario` |
| RF7 | Downsampling del histórico | `resumen_horario` y `aplicar_retencion()` |
| RF8 | Gestión de incidencias del NOC | Tabla `incidencia_noc`, trigger RN6 y `PATCH /incidencias/{id}` |
| RF9 | Vistas agregadas para reportes (PUE, estabilidad térmica) | `v_estabilidad_termica` y `v_consumo_por_pasillo` |
| RF10 | Baja lógica de sensores | Estado `MANTENIMIENTO`/`INACCESIBLE`, trigger RN2 y `PATCH /sensores/{id}/estado` |

## Requisitos no funcionales

| RNF | Requisito | Estado en este prototipo |
|---|---|---|
| RNF1 | 10.000 métricas por minuto | Medido en el prototipo con `src/benchmark.py` (lotes de 500 con reglas activas); ver `ejemplos/salida_benchmark.txt` |
| RNF2 | Alerta en menos de 2 s | La alarma se crea en la misma transacción de la inserción (trigger); latencia medida en `benchmark.py` (milisegundos en el prototipo) |
| RNF3 | Consultas estables al crecer los datos | `EXPLAIN QUERY PLAN` muestra `SEARCH` con índice (no `SCAN`) |
| RNF4 | Disponibilidad y resiliencia | Modo WAL, `timeout` y `INSERT OR IGNORE` para reenvíos; buffers locales fuera de alcance |
| RNF5 | Retención y purgado | `aplicar_retencion()`: resume por hora y purga lo anterior a 30 días |

## Escenarios del caso

| Escenario | Cobertura |
|---|---|
| Ingesta masiva | Lotes de 50 inserciones por commit (concurrencia) |
| Promedios horarios por pasillo | Consulta C1 |
| Limpieza por retención | `aplicar_retencion()` |
| Recepción fuera de orden | Lectura con timestamp anterior en la fase de JOINs; la clave no depende del orden |
| Inserción en lote tras reconexión | `INSERT OR IGNORE` |
| Energía intermitente / saturación de disco | **No cubiertos**: trabajo futuro |
