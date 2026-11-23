# 2. Reglas de negocio y su implementación

| ID | Regla | Implementación | Prueba (`queries/pruebas_reglas.py`) |
|---|---|---|---|
| RN-01 | Sin prerrequisito aprobado no se matricula | Trigger `trg_matricula_prerequisitos` + tabla `aprobacion` | Juan → Cálculo Integral sin aprobar Cálculo Diferencial |
| RN-02 | Confirmadas ≤ cupo máximo | `CHECK (cupos_ocupados <= cupo_maximo)` + transacción `BEGIN IMMEDIATE` | Dos estudiantes por el último cupo (`connection/concurrencia.py`) |
| RN-03 | Sin cruces de horario | Trigger `trg_matricula_sin_cruce` sobre `horario_seccion` | Matricular con choque LUN 08–10 vs 09–11 |
| RN-04 | Estados válidos | `CHECK (estado IN (...))` | Estado `'XX'` |
| RN-05 | Curso con créditos > 0 | `CHECK (creditos > 0)` | Curso con 0 créditos |
| RN-06 | Sin doble matrícula activa | `UNIQUE (id_estudiante, id_seccion)` | Doble inserción idéntica |
| RN-07 | Lista de espera FIFO | `fecha_inscripcion` con milisegundos + vista `vw_lista_espera` | Consulta de la cola |
| RN-08 | Cancelar libera el cupo | Triggers `trg_cupo_*` | Conteo de cupos tras cancelar |
| RN-09 | Cambios manuales auditados | Tabla `log_auditoria` + trigger `trg_audit_cupo` | Cambiar cupo y revisar el log |
| RN-10 | Periodos sin solapamiento | Trigger `trg_periodo_sin_solape` | Periodo solapado |
| RN-11 | El cupo no baja de los confirmados | Trigger `trg_cupo_no_reducir` | Reducir cupo por debajo de los confirmados |
| RN-12 | Suspendido no matricula | `estudiante.estado` + trigger `trg_matricula_suspension` | Matricular a un suspendido |

> **Nota:** SQLite no tiene roles ni `GRANT`. El RBAC (estudiante / administrador) se documenta en `03_modelo_y_decisiones.md` y se implementaría con permisos reales en PostgreSQL.
