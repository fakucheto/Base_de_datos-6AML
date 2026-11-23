-- =====================================================================
-- Caso 4 - DW Deserción Estudiantil (OLAP) | Esquema en estrella | SQLite
-- =====================================================================
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;  -- lecturas concurrentes durante la carga ETL (RN-07)

CREATE TABLE dim_tiempo (
    id_tiempo       INTEGER PRIMARY KEY,
    anio            INTEGER NOT NULL,
    semestre        INTEGER NOT NULL CHECK (semestre IN (1, 2)),
    mes             INTEGER NOT NULL CHECK (mes BETWEEN 1 AND 12),
    es_cierre_ciclo BOOLEAN NOT NULL DEFAULT 0,
    UNIQUE (anio, mes)
);

-- SCD Tipo 2 (RN-02) y anonimización (RN-01)
CREATE TABLE dim_estudiante (
    id_estudiante_sk INTEGER PRIMARY KEY AUTOINCREMENT,
    hash_identidad   TEXT NOT NULL,
    cohorte          TEXT NOT NULL,
    sede             TEXT NOT NULL,
    fecha_inicio     DATE NOT NULL,
    fecha_fin        DATE,
    es_activo        BOOLEAN NOT NULL DEFAULT 1,
    UNIQUE (hash_identidad, fecha_inicio)
);

CREATE TABLE dim_demografia (
    id_demografia_sk INTEGER PRIMARY KEY AUTOINCREMENT,
    estrato          INTEGER NOT NULL CHECK (estrato BETWEEN 1 AND 6),  -- RN-08
    tipo_colegio     TEXT NOT NULL,
    region           TEXT NOT NULL,
    UNIQUE (estrato, tipo_colegio, region)
);

-- Desnormalizada a propósito (rompe 3FN) para evitar JOINs
CREATE TABLE dim_programa (
    id_programa_sk  INTEGER PRIMARY KEY AUTOINCREMENT,
    facultad        TEXT NOT NULL,
    nombre_programa TEXT NOT NULL,
    nivel_academico TEXT NOT NULL,
    UNIQUE (nombre_programa, nivel_academico)
);

-- NUEVA: RN-03 exige vincular cada hecho a un curso
CREATE TABLE dim_curso (
    id_curso_sk INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo      TEXT NOT NULL UNIQUE,
    nombre      TEXT NOT NULL,
    creditos    INTEGER NOT NULL CHECK (creditos > 0)
);

-- Granularidad: nota e inasistencias mensuales por estudiante y asignatura
CREATE TABLE fact_rendimiento (
    id_tiempo         INTEGER NOT NULL,
    id_estudiante_sk  INTEGER NOT NULL,
    id_demografia_sk  INTEGER NOT NULL,
    id_programa_sk    INTEGER NOT NULL,
    id_curso_sk       INTEGER NOT NULL,
    nota              REAL    NOT NULL CHECK (nota >= 0.0 AND nota <= 5.0),   -- RN-06
    inasistencias     INTEGER NOT NULL DEFAULT 0 CHECK (inasistencias >= 0),  -- RN-11
    creditos_cursados INTEGER NOT NULL CHECK (creditos_cursados > 0),
    -- RN-12: indicador derivado de riesgo (scoring)
    alerta_riesgo     BOOLEAN GENERATED ALWAYS AS
                      (CASE WHEN nota < 3.0 AND inasistencias >= 6 THEN 1 ELSE 0 END) STORED,
    PRIMARY KEY (id_tiempo, id_estudiante_sk, id_curso_sk),
    FOREIGN KEY (id_tiempo)        REFERENCES dim_tiempo(id_tiempo),
    FOREIGN KEY (id_estudiante_sk) REFERENCES dim_estudiante(id_estudiante_sk),
    FOREIGN KEY (id_demografia_sk) REFERENCES dim_demografia(id_demografia_sk),
    FOREIGN KEY (id_programa_sk)   REFERENCES dim_programa(id_programa_sk),
    FOREIGN KEY (id_curso_sk)      REFERENCES dim_curso(id_curso_sk)
);

-- RN-05: hechos inmutables (SQLite no tiene REVOKE; se simula con triggers)
CREATE TRIGGER trg_fact_no_update BEFORE UPDATE ON fact_rendimiento
BEGIN SELECT RAISE(ABORT, 'RN-05: fact_rendimiento es inmutable (UPDATE prohibido)'); END;

CREATE TRIGGER trg_fact_no_delete BEFORE DELETE ON fact_rendimiento
BEGIN SELECT RAISE(ABORT, 'RN-05: fact_rendimiento es inmutable (DELETE prohibido)'); END;

-- RN-04: promedio ponderado mensual, persistido (tabla agregada)
CREATE TABLE agg_promedio_mensual (
    id_tiempo          INTEGER NOT NULL,
    id_estudiante_sk   INTEGER NOT NULL,
    promedio_ponderado REAL NOT NULL,
    PRIMARY KEY (id_tiempo, id_estudiante_sk),
    FOREIGN KEY (id_tiempo) REFERENCES dim_tiempo(id_tiempo),
    FOREIGN KEY (id_estudiante_sk) REFERENCES dim_estudiante(id_estudiante_sk)
);

-- RF9 / Q7: auditoría de accesos
CREATE TABLE log_acceso (
    id_log   INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario  TEXT NOT NULL,
    rol      TEXT NOT NULL CHECK (rol IN ('analista','decanatura','etl')),
    objeto   TEXT NOT NULL,
    fecha    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_fact_cubo ON fact_rendimiento(id_programa_sk, id_demografia_sk, id_tiempo);
CREATE INDEX idx_estudiante_hash ON dim_estudiante(hash_identidad);

-- Vista agregada para analistas (RN-09): sin datos granulares del estudiante
CREATE VIEW vw_riesgo_desercion AS
SELECT e.cohorte, p.nombre_programa, d.estrato,
       ROUND(AVG(f.nota), 2)   AS prom_grupal,
       SUM(f.inasistencias)    AS inasistencias_totales,
       SUM(f.alerta_riesgo)    AS registros_en_alerta
FROM fact_rendimiento f
JOIN dim_estudiante e ON f.id_estudiante_sk = e.id_estudiante_sk
JOIN dim_programa   p ON f.id_programa_sk   = p.id_programa_sk
JOIN dim_demografia d ON f.id_demografia_sk = d.id_demografia_sk
GROUP BY e.cohorte, p.nombre_programa, d.estrato;
