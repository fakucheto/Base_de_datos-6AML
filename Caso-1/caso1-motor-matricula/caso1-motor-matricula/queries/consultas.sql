-- Consultas del Caso 1 (SQLite)

-- Q1 (crítica): disponibilidad de una sección
SELECT cupo_maximo - cupos_ocupados AS disponibles FROM seccion WHERE codigo = 'SEC_MAT1_01';

-- Q2: matrículas vigentes de un estudiante
SELECT e.nombre_completo, s.codigo AS seccion, c.nombre AS curso, m.estado
FROM matricula m
JOIN estudiante e ON e.id_estudiante = m.id_estudiante
JOIN seccion s    ON s.id_seccion = m.id_seccion
JOIN curso c      ON c.id_curso = s.id_curso
WHERE e.codigo = 'EST_001' AND m.estado <> 'CANCELADA';

-- Q3: cola de espera en orden de llegada (RN-07)
SELECT * FROM vw_lista_espera ORDER BY seccion, posicion;

-- Q4: historial académico (aprobadas)
SELECT e.codigo, c.codigo AS curso, a.nota
FROM aprobacion a JOIN estudiante e ON e.id_estudiante=a.id_estudiante JOIN curso c ON c.id_curso=a.id_curso;

-- Q5: materias habilitadas para un estudiante (todos sus prerrequisitos aprobados)
SELECT c.codigo, c.nombre
FROM curso c
WHERE NOT EXISTS (SELECT 1 FROM aprobacion a WHERE a.id_curso=c.id_curso
                  AND a.id_estudiante=(SELECT id_estudiante FROM estudiante WHERE codigo='EST_001'))
  AND NOT EXISTS (SELECT 1 FROM prerequisito p WHERE p.id_curso=c.id_curso
                  AND p.id_prerequisito NOT IN (SELECT id_curso FROM aprobacion
                      WHERE id_estudiante=(SELECT id_estudiante FROM estudiante WHERE codigo='EST_001')));

-- Q6: auditoría de cambios de cupo (RN-09)
SELECT * FROM log_auditoria ORDER BY fecha DESC;

-- Q7: verificación de la invariante cupos_ocupados = confirmadas reales
SELECT s.codigo, s.cupos_ocupados,
       (SELECT COUNT(*) FROM matricula m WHERE m.id_seccion=s.id_seccion AND m.estado='CONFIRMADA') AS confirmadas_reales
FROM seccion s;

-- ===== Los 7 tipos de JOIN =====
-- INNER: estudiantes con matrícula confirmada
SELECT e.codigo, e.nombre_completo, m.id_seccion, m.estado
FROM estudiante e INNER JOIN matricula m ON e.id_estudiante = m.id_estudiante WHERE m.estado = 'CONFIRMADA';
-- LEFT: todos los estudiantes, incluso sin matrícula
SELECT e.codigo, e.nombre_completo, COUNT(m.id_matricula) AS total_materias
FROM estudiante e LEFT JOIN matricula m ON e.id_estudiante = m.id_estudiante GROUP BY e.id_estudiante;
-- RIGHT: todas las secciones, tengan o no alumnos
SELECT s.codigo, s.cupo_maximo, m.id_estudiante
FROM matricula m RIGHT JOIN seccion s ON m.id_seccion = s.id_seccion;
-- FULL: huérfanos de ambos lados
SELECT e.codigo, s.codigo AS seccion
FROM estudiante e FULL JOIN matricula m ON e.id_estudiante = m.id_estudiante
FULL JOIN seccion s ON m.id_seccion = s.id_seccion;
-- CROSS: estudiantes activos x secciones (borradores / encuestas)
SELECT e.codigo, s.codigo AS seccion FROM estudiante e CROSS JOIN seccion s WHERE e.estado = 'ACTIVO';
-- SELF: compañeros de clase
SELECT a.id_seccion, a.id_estudiante AS estudiante_1, b.id_estudiante AS estudiante_2
FROM matricula a JOIN matricula b ON a.id_seccion = b.id_seccion AND a.id_estudiante < b.id_estudiante;
-- NATURAL: columnas homónimas (id_estudiante); en producción usar ON explícito
SELECT * FROM estudiante NATURAL JOIN matricula;

-- Plan de ejecución de Q1: debe mostrar SEARCH, no SCAN
EXPLAIN QUERY PLAN SELECT cupo_maximo - cupos_ocupados FROM seccion WHERE id_curso = 1 AND id_periodo = 1;
