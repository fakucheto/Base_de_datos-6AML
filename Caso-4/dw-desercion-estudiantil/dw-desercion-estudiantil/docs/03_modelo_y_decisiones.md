# 3. Modelo dimensional y decisiones de diseño

## Esquema en estrella
- **Hecho:** `fact_rendimiento` (nota, inasistencias, créditos, alerta_riesgo). Granularidad: nota e inasistencia mensual por estudiante y asignatura.
- **Dimensiones:** `dim_estudiante` (anonimizada, SCD2), `dim_tiempo`, `dim_programa`, `dim_demografia`, `dim_curso`.

## Decisiones difíciles
1. **Claves subrogadas vs. naturales:** independizan el DW de cambios en los sistemas de origen.
2. **Desnormalización en estrella:** facultad y programa en una sola `dim_programa` (viola 3FN a propósito) para reducir JOINs.
3. **SCD Tipo 2 en `dim_estudiante`:** conservar el historial de sede/estrato, no sobrescribirlo.
4. **Ofuscación temprana:** el DW solo recibe el hash del estudiante.
5. **Granularidad mínima:** permite drill-down / roll-up por cohortes.

## Transacciones y concurrencia
Consistencia eventual; modo WAL: las lecturas no ven datos a medio escribir mientras el ETL carga el lote.

## Seguridad y privacidad
Analista → solo vistas agregadas. ETL → escritura en ventanas nocturnas. Hash irreversible desde el origen.

## Escalamiento y operación
Tabla de hechos estrecha + índice compuesto `idx_fact_cubo`. Backup en frío tras cada batch (RPO = 24 h).
Trade-off: velocidad de consulta a cambio de almacenamiento extra por desnormalización.

## Cambios respecto al diseño inicial
Se añadió `dim_curso` (RN-03), `alerta_riesgo` (RN-12), `agg_promedio_mensual` (RN-04), `log_acceso` (Q7/RF-9), triggers (RN-05),
`es_cierre_ciclo` y `sede` (RN-02), y una clave primaria compuesta en la tabla de hechos.
