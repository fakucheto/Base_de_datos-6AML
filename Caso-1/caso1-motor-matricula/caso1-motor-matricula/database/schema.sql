-- =====================================================================
-- Caso 1 - Motor de Matrícula (OLTP) | SQLite
-- =====================================================================
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE periodo (
    id_periodo               INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre                   TEXT NOT NULL UNIQUE,
    nivel                    TEXT NOT NULL DEFAULT 'PREGRADO',
    fecha_inicio             DATE NOT NULL,
    fecha_fin                DATE NOT NULL,
    fecha_limite_cancelacion DATE NOT NULL,
    CHECK (fecha_fin > fecha_inicio),
    CHECK (fecha_limite_cancelacion BETWEEN fecha_inicio AND fecha_fin)
);

CREATE TABLE estudiante (
    id_estudiante   INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo          TEXT NOT NULL UNIQUE,
    documento       TEXT NOT NULL UNIQUE,
    nombre_completo TEXT NOT NULL,
    correo          TEXT NOT NULL UNIQUE,
    programa        TEXT NOT NULL DEFAULT 'Ingeniería de Sistemas',
    estado          TEXT NOT NULL DEFAULT 'ACTIVO' CHECK (estado IN ('ACTIVO','SUSPENDIDO'))  -- RN-12
);

CREATE TABLE curso (
    id_curso INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo   TEXT NOT NULL UNIQUE,
    nombre   TEXT NOT NULL,
    creditos INTEGER NOT NULL CHECK (creditos > 0)                                           -- RN-05
);

CREATE TABLE prerequisito (
    id_curso        INTEGER NOT NULL,
    id_prerequisito INTEGER NOT NULL,
    PRIMARY KEY (id_curso, id_prerequisito),
    CHECK (id_curso <> id_prerequisito),
    FOREIGN KEY (id_curso)        REFERENCES curso(id_curso) ON DELETE CASCADE,
    FOREIGN KEY (id_prerequisito) REFERENCES curso(id_curso) ON DELETE CASCADE
);

-- Historial de materias aprobadas (necesario para validar RN-01)
CREATE TABLE aprobacion (
    id_estudiante INTEGER NOT NULL,
    id_curso      INTEGER NOT NULL,
    nota          REAL NOT NULL CHECK (nota >= 3.0 AND nota <= 5.0),
    PRIMARY KEY (id_estudiante, id_curso),
    FOREIGN KEY (id_estudiante) REFERENCES estudiante(id_estudiante),
    FOREIGN KEY (id_curso)      REFERENCES curso(id_curso)
);

CREATE TABLE seccion (
    id_seccion     INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo         TEXT NOT NULL UNIQUE,
    id_curso       INTEGER NOT NULL,
    id_periodo     INTEGER NOT NULL,
    cupo_maximo    INTEGER NOT NULL CHECK (cupo_maximo > 0),
    cupos_ocupados INTEGER NOT NULL DEFAULT 0 CHECK (cupos_ocupados >= 0 AND cupos_ocupados <= cupo_maximo),  -- RN-02
    FOREIGN KEY (id_curso)   REFERENCES curso(id_curso) ON DELETE CASCADE,
    FOREIGN KEY (id_periodo) REFERENCES periodo(id_periodo)
);

CREATE TABLE horario_seccion (
    id_horario  INTEGER PRIMARY KEY AUTOINCREMENT,
    id_seccion  INTEGER NOT NULL,
    dia_semana  TEXT NOT NULL CHECK (dia_semana IN ('LUN','MAR','MIE','JUE','VIE','SAB')),
    hora_inicio TEXT NOT NULL,
    hora_fin    TEXT NOT NULL,
    CHECK (hora_fin > hora_inicio),
    FOREIGN KEY (id_seccion) REFERENCES seccion(id_seccion) ON DELETE CASCADE
);

CREATE TABLE matricula (
    id_matricula      INTEGER PRIMARY KEY AUTOINCREMENT,
    id_estudiante     INTEGER NOT NULL,
    id_seccion        INTEGER NOT NULL,
    estado            TEXT NOT NULL CHECK (estado IN ('PENDIENTE','CONFIRMADA','CANCELADA','ESPERA')),  -- RN-04
    fecha_inscripcion TIMESTAMP NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now')),                  -- RN-07 (FIFO)
    UNIQUE (id_estudiante, id_seccion),                                                                  -- RN-06
    FOREIGN KEY (id_estudiante) REFERENCES estudiante(id_estudiante),
    FOREIGN KEY (id_seccion)    REFERENCES seccion(id_seccion)
);

CREATE TABLE log_auditoria (
    id_log          INTEGER PRIMARY KEY AUTOINCREMENT,
    tabla           TEXT NOT NULL,
    id_registro     INTEGER NOT NULL,
    campo           TEXT NOT NULL,
    valor_anterior  TEXT,
    valor_nuevo     TEXT,
    usuario         TEXT NOT NULL DEFAULT 'administrador',
    fecha           TIMESTAMP NOT NULL DEFAULT (strftime('%Y-%m-%d %H:%M:%f','now'))
);

-- Índices (Q1 y consultas de historial)
CREATE INDEX idx_matricula_estudiante ON matricula(id_estudiante);
CREATE INDEX idx_matricula_seccion    ON matricula(id_seccion, estado, fecha_inscripcion);
CREATE INDEX idx_seccion_curso        ON seccion(id_curso, id_periodo);

-- ---------------------------------------------------------------------
-- REGLAS DE NEGOCIO COMO TRIGGERS
-- ---------------------------------------------------------------------
-- RN-10: periodos sin solapamiento para el mismo nivel
CREATE TRIGGER trg_periodo_sin_solape BEFORE INSERT ON periodo
BEGIN
  SELECT RAISE(ABORT,'RN-10: el periodo se solapa con otro del mismo nivel')
  WHERE EXISTS (SELECT 1 FROM periodo p WHERE p.nivel = NEW.nivel
                AND p.fecha_inicio <= NEW.fecha_fin AND NEW.fecha_inicio <= p.fecha_fin);
END;

-- RN-12: estudiante suspendido no puede matricular
CREATE TRIGGER trg_matricula_suspension BEFORE INSERT ON matricula WHEN NEW.estado <> 'CANCELADA'
BEGIN
  SELECT RAISE(ABORT,'RN-12: estudiante en suspensión institucional')
  WHERE EXISTS (SELECT 1 FROM estudiante WHERE id_estudiante = NEW.id_estudiante AND estado = 'SUSPENDIDO');
END;

-- RN-01: prerrequisitos aprobados
CREATE TRIGGER trg_matricula_prerequisitos BEFORE INSERT ON matricula WHEN NEW.estado <> 'CANCELADA'
BEGIN
  SELECT RAISE(ABORT,'RN-01: prerrequisito sin aprobar')
  WHERE EXISTS (
    SELECT 1 FROM seccion s JOIN prerequisito p ON p.id_curso = s.id_curso
    WHERE s.id_seccion = NEW.id_seccion
      AND NOT EXISTS (SELECT 1 FROM aprobacion a
                      WHERE a.id_estudiante = NEW.id_estudiante AND a.id_curso = p.id_prerequisito));
END;

-- RN-03: sin cruces de horario dentro del mismo periodo
CREATE TRIGGER trg_matricula_sin_cruce BEFORE INSERT ON matricula WHEN NEW.estado <> 'CANCELADA'
BEGIN
  SELECT RAISE(ABORT,'RN-03: cruce de horario con otra materia matriculada')
  WHERE EXISTS (
    SELECT 1
    FROM horario_seccion n
    JOIN seccion sn ON sn.id_seccion = n.id_seccion
    JOIN horario_seccion o ON o.dia_semana = n.dia_semana
         AND o.hora_inicio < n.hora_fin AND n.hora_inicio < o.hora_fin
    JOIN seccion so ON so.id_seccion = o.id_seccion AND so.id_periodo = sn.id_periodo
    JOIN matricula m ON m.id_seccion = o.id_seccion AND m.id_estudiante = NEW.id_estudiante
                    AND m.estado <> 'CANCELADA'
    WHERE n.id_seccion = NEW.id_seccion AND o.id_seccion <> NEW.id_seccion);
END;

-- RN-08 / RN-02: inventario de cupos siempre sincronizado
CREATE TRIGGER trg_cupo_ins AFTER INSERT ON matricula WHEN NEW.estado = 'CONFIRMADA'
BEGIN UPDATE seccion SET cupos_ocupados = cupos_ocupados + 1 WHERE id_seccion = NEW.id_seccion; END;

CREATE TRIGGER trg_cupo_libera AFTER UPDATE OF estado ON matricula
WHEN OLD.estado = 'CONFIRMADA' AND NEW.estado <> 'CONFIRMADA'
BEGIN UPDATE seccion SET cupos_ocupados = cupos_ocupados - 1 WHERE id_seccion = NEW.id_seccion; END;

CREATE TRIGGER trg_cupo_ocupa AFTER UPDATE OF estado ON matricula
WHEN OLD.estado <> 'CONFIRMADA' AND NEW.estado = 'CONFIRMADA'
BEGIN UPDATE seccion SET cupos_ocupados = cupos_ocupados + 1 WHERE id_seccion = NEW.id_seccion; END;

CREATE TRIGGER trg_cupo_del AFTER DELETE ON matricula WHEN OLD.estado = 'CONFIRMADA'
BEGIN UPDATE seccion SET cupos_ocupados = cupos_ocupados - 1 WHERE id_seccion = OLD.id_seccion; END;

-- RN-11: el cupo no puede bajar de los confirmados
CREATE TRIGGER trg_cupo_no_reducir BEFORE UPDATE OF cupo_maximo ON seccion
WHEN NEW.cupo_maximo < OLD.cupos_ocupados
BEGIN SELECT RAISE(ABORT,'RN-11: el cupo no puede ser menor a los estudiantes confirmados'); END;

-- RN-09: auditoría de cambios manuales de cupo
CREATE TRIGGER trg_audit_cupo AFTER UPDATE OF cupo_maximo ON seccion
WHEN OLD.cupo_maximo <> NEW.cupo_maximo
BEGIN
  INSERT INTO log_auditoria(tabla,id_registro,campo,valor_anterior,valor_nuevo)
  VALUES ('seccion', NEW.id_seccion, 'cupo_maximo', OLD.cupo_maximo, NEW.cupo_maximo);
END;

-- ---------------------------------------------------------------------
-- VISTAS
-- ---------------------------------------------------------------------
CREATE VIEW vw_cupos_disponibles AS
SELECT s.id_seccion, s.codigo AS seccion, c.nombre AS curso, p.nombre AS periodo,
       (s.cupo_maximo - s.cupos_ocupados) AS cupos_libres
FROM seccion s
JOIN curso c   ON s.id_curso = c.id_curso
JOIN periodo p ON s.id_periodo = p.id_periodo;

-- RN-07: cola de espera en orden de llegada
CREATE VIEW vw_lista_espera AS
SELECT s.codigo AS seccion, e.codigo AS estudiante, m.fecha_inscripcion,
       ROW_NUMBER() OVER (PARTITION BY m.id_seccion ORDER BY m.fecha_inscripcion, m.id_matricula) AS posicion
FROM matricula m
JOIN seccion s    ON m.id_seccion = s.id_seccion
JOIN estudiante e ON m.id_estudiante = e.id_estudiante
WHERE m.estado = 'ESPERA';
