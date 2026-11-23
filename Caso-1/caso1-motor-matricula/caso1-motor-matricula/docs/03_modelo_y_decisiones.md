# 3. Modelo, concurrencia y decisiones de diseño

## Modelo lógico (3FN)
`estudiante`, `curso`, `prerequisito` (autorrelación), `periodo`, `seccion`, `horario_seccion`, `matricula` (asociativa), `aprobacion` y `log_auditoria`.

**Desnormalización justificada:** `seccion.cupos_ocupados` es redundante frente al conteo de `matricula`, pero permite consultar disponibilidad en tiempo real. La consistencia la garantizan los triggers y las transacciones.

## Decisiones conceptuales difíciles
1. Prerrequisitos y co-requisitos mediante una tabla puente autorreferenciada.
2. La lista de espera como una extensión de `matricula` (estado `ESPERA` + orden de llegada).

## Concurrencia
Invariante: `cupos_ocupados <= cupo_maximo`. Se usa `BEGIN IMMEDIATE` para serializar el acceso al último cupo y evitar condiciones de carrera. `connection/concurrencia.py` lo demuestra: 20 hilos compiten por 1 cupo y resulta 1 confirmado y 19 en espera.

## Seguridad (RBAC)
- **Estudiante:** lee `curso` y `seccion`; escribe solo sus solicitudes en `matricula`.
- **Administrador:** CRUD sobre la estructura académica.
- Correos y documentos protegidos por privilegios de conexión (sin cifrado reversible por columna).

## Operación
Respaldos diarios en caliente con `VACUUM INTO` y copias incrementales. Monitoreo de `busy_timeout` y de la tasa de fallos por saturación de cupos.

## Cambios respecto al DDL del expediente
Se agregaron `periodo` (RN-10), `horario_seccion` (RN-03), `aprobacion` (RN-01), `log_auditoria` (RN-09), `estudiante.estado` (RN-12) y `correo UNIQUE` (RF-1). Se implementaron los triggers de RN-01, 03, 08, 09, 10, 11 y 12. Se corrigió la vista `vw_cupos_disponibles`, que en el documento no tenía `SELECT`. Se añadieron `codigo` en estudiante y sección, la vista `vw_lista_espera` y el índice `idx_matricula_seccion`.
