# 2. Reglas de negocio y su implementación

| ID | Regla | Implementación | Prueba (en `queries/pruebas_reglas.py`) |
|---|---|---|---|
| RN-01 | Identidad no persiste en texto plano | `hash_identidad` (SHA-256) + claves subrogadas | Buscar nombre/documento en `dim_estudiante` → no existe |
| RN-02 | Cambio de estrato/sede genera nuevo registro | SCD Tipo 2 (`fecha_inicio`, `fecha_fin`, `es_activo`) | Consulta Q4 muestra versiones históricas |
| RN-03 | Inasistencia ligada a tiempo, curso y estudiante | FK de estrella + PK compuesta | Insertar hecho con tiempo inexistente → rechazado |
| RN-04 | Promedio ponderado mensual persistido | Tabla `agg_promedio_mensual` | Comparar con SUMA(nota*créditos)/SUMA(créditos) |
| RN-05 | Hechos inmutables | Triggers que bloquean UPDATE/DELETE | `UPDATE fact_rendimiento` → rechazado |
| RN-06 | Nota entre 0.0 y 5.0 | `CHECK` | Insertar nota 6.0 → rechazado |
| RN-07 | Cargas batch no bloquean lecturas | `PRAGMA journal_mode = WAL` | Lectura concurrente durante INSERT masivo |
| RN-08 | Estrato entre 1 y 6 | `CHECK` | Estrato 9 → rechazado |
| RN-09 | Solo Decanatura ve el cruce exacto | Vista agregada `vw_riesgo_desercion` + roles (ver nota) | Analista consulta solo la vista |
| RN-10 | Cohorte con periodo válido | FK a `dim_tiempo` | Hecho con periodo inexistente → rechazado |
| RN-11 | Inasistencias no negativas | `CHECK (inasistencias >= 0)` | Insertar -2 → rechazado |
| RN-12 | Indicador de riesgo derivado | Columna generada `alerta_riesgo` (nota < 3.0 y ≥ 6 inasistencias) | Validar contra notas e inasistencias |

> **Nota (RN-05 y RN-09):** SQLite no tiene `GRANT/REVOKE` ni roles. La inmutabilidad se simula con triggers y el control por rol se documenta
> sobre vistas; en un motor como PostgreSQL se implementaría con `REVOKE UPDATE, DELETE` y `ROW LEVEL SECURITY`.
