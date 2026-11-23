-- Consultas del Caso 4 (SQLite). Q1-Q8 del Expediente Técnico.

-- Q1 (Analítica clave): promedio por cohorte, programa y estrato, últimos 5 años
SELECT e.cohorte, p.nombre_programa, d.estrato, ROUND(AVG(f.nota),2) AS promedio
FROM fact_rendimiento f
JOIN dim_estudiante e ON f.id_estudiante_sk = e.id_estudiante_sk
JOIN dim_programa   p ON f.id_programa_sk   = p.id_programa_sk
JOIN dim_demografia d ON f.id_demografia_sk = d.id_demografia_sk
JOIN dim_tiempo     t ON f.id_tiempo        = t.id_tiempo
WHERE t.anio >= 2022
GROUP BY e.cohorte, p.nombre_programa, d.estrato
ORDER BY promedio;

-- Q2 (Roll-up temporal): inasistencias por semestre y facultad
SELECT t.anio, t.semestre, p.facultad, SUM(f.inasistencias) AS inasistencias
FROM fact_rendimiento f
JOIN dim_tiempo   t ON f.id_tiempo = t.id_tiempo
JOIN dim_programa p ON f.id_programa_sk = p.id_programa_sk
GROUP BY t.anio, t.semestre, p.facultad
ORDER BY t.anio, t.semestre, p.facultad;

-- Q3 (Operacional): historial completo de un hash (cambiar por un hash real)
SELECT t.anio, t.mes, c.nombre AS curso, f.nota, f.inasistencias, f.alerta_riesgo
FROM fact_rendimiento f
JOIN dim_estudiante e ON f.id_estudiante_sk = e.id_estudiante_sk
JOIN dim_tiempo t ON f.id_tiempo = t.id_tiempo
JOIN dim_curso  c ON f.id_curso_sk = c.id_curso_sk
WHERE e.hash_identidad = (SELECT hash_identidad FROM dim_estudiante LIMIT 1)
ORDER BY t.anio, t.mes;

-- Q4 (Operacional): versiones históricas SCD2 (es_activo = 0)
SELECT id_estudiante_sk, substr(hash_identidad,1,12) AS hash_corto, sede, fecha_inicio, fecha_fin
FROM dim_estudiante WHERE es_activo = 0;

-- Q5 (Operacional): conteos para conciliación post-ETL
SELECT 'fact_rendimiento' AS tabla, COUNT(*) AS filas FROM fact_rendimiento
UNION ALL SELECT 'dim_estudiante', COUNT(*) FROM dim_estudiante
UNION ALL SELECT 'dim_demografia', COUNT(*) FROM dim_demografia
UNION ALL SELECT 'dim_programa',   COUNT(*) FROM dim_programa
UNION ALL SELECT 'dim_curso',      COUNT(*) FROM dim_curso
UNION ALL SELECT 'dim_tiempo',     COUNT(*) FROM dim_tiempo;

-- Q6 (Operacional): facultades con varianza atípica de inasistencias
-- (SQLite no trae STDDEV; varianza = E[x^2] - E[x]^2)
SELECT p.facultad,
       ROUND(AVG(f.inasistencias),2) AS media,
       ROUND(AVG(f.inasistencias*f.inasistencias) - AVG(f.inasistencias)*AVG(f.inasistencias),2) AS varianza
FROM fact_rendimiento f JOIN dim_programa p ON f.id_programa_sk = p.id_programa_sk
GROUP BY p.facultad ORDER BY varianza DESC;

-- Q7 (Auditoría): uso histórico por usuario
SELECT usuario, rol, objeto, COUNT(*) AS accesos, MAX(fecha) AS ultimo_acceso
FROM log_acceso GROUP BY usuario, rol, objeto ORDER BY accesos DESC;

-- Q8 (Excepción): claves huérfanas tras una carga fallida
SELECT COUNT(*) AS huerfanos
FROM fact_rendimiento f
LEFT JOIN dim_estudiante e ON f.id_estudiante_sk = e.id_estudiante_sk
LEFT JOIN dim_tiempo     t ON f.id_tiempo        = t.id_tiempo
LEFT JOIN dim_curso      c ON f.id_curso_sk      = c.id_curso_sk
WHERE e.id_estudiante_sk IS NULL OR t.id_tiempo IS NULL OR c.id_curso_sk IS NULL;

-- Evidencia del plan de ejecución (Q1)
EXPLAIN QUERY PLAN
SELECT p.nombre_programa, d.estrato, AVG(f.nota)
FROM fact_rendimiento f
JOIN dim_programa p ON f.id_programa_sk = p.id_programa_sk
JOIN dim_demografia d ON f.id_demografia_sk = d.id_demografia_sk
GROUP BY p.nombre_programa, d.estrato;
