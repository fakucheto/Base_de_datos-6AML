-- Datos de prueba del Caso 1
INSERT INTO periodo(nombre,nivel,fecha_inicio,fecha_fin,fecha_limite_cancelacion)
VALUES ('2026-2','PREGRADO','2026-08-03','2026-12-05','2026-11-30');

INSERT INTO curso(codigo,nombre,creditos) VALUES
 ('MAT101','Calculo Diferencial',4), ('MAT102','Calculo Integral',4), ('MAT201','Ecuaciones Diferenciales',4),
 ('INF201','Bases de Datos I',3), ('INF202','Bases de Datos Avanzadas',3), ('INF301','Inteligencia Artificial',3),
 ('FIS101','Fisica I',3);

-- (curso, prerrequisito): ids según el orden anterior
INSERT INTO prerequisito(id_curso,id_prerequisito) VALUES (2,1),(3,2),(5,4),(6,5),(6,2);

INSERT INTO estudiante(codigo,documento,nombre_completo,correo) VALUES
 ('EST_001','1001','Andres Diaz','adiaz@ecci.edu.co'),
 ('EST_002','1002','Juan Gutierrez','jgutierrez@ecci.edu.co'),
 ('EST_003','1003','Johan Quiroga','jquiroga@ecci.edu.co'),
 ('EST_004','1004','Carlos Perez','cperez@ecci.edu.co');

INSERT INTO aprobacion(id_estudiante,id_curso,nota) VALUES (1,1,4.5),(1,4,4.2);

INSERT INTO seccion(codigo,id_curso,id_periodo,cupo_maximo) VALUES
 ('SEC_MAT1_01',1,1,30), ('SEC_MAT2_01',2,1,30), ('SEC_BD1_01',4,1,25),
 ('SEC_FIS1_01',7,1,30), ('SEC_FAIL_3',1,1,1),  ('SEC_CHOQUE_1',7,1,30);

INSERT INTO horario_seccion(id_seccion,dia_semana,hora_inicio,hora_fin) VALUES
 (1,'LUN','08:00','10:00'), (2,'MAR','10:00','12:00'), (3,'MAR','08:00','10:00'),
 (4,'MIE','10:00','12:00'), (5,'JUE','14:00','16:00'), (6,'LUN','09:00','11:00');

INSERT INTO matricula(id_estudiante,id_seccion,estado) VALUES (1,2,'CONFIRMADA'), (2,1,'CONFIRMADA');
