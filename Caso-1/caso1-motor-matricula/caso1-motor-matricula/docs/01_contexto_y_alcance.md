# 1. Contexto y alcance — Caso 1: Motor de Matrícula (OLTP)

## Problema y objetivo medible
Gestionar la inscripción académica concurrente garantizando que ningún estudiante se matricule en cursos que superen el cupo máximo del aula o que violen la matriz de prerrequisitos aprobados. **Meta:** respuesta < 500 ms por transacción bajo picos de alta concurrencia.

## Límite del sistema
- **Incluye:** desde la selección de horarios hasta la confirmación de matrícula y el bloqueo de cupos.
- **Excluye:** pasarelas de pago y plataformas LMS externas.

## Actores
| Actor | Rol |
|---|---|
| Estudiante | Solicita inscripción o cancelación |
| Administrador académico | Modifica cupos y audita |
| Sistema | Verifica reglas y actualiza estados de forma atómica |

## Escenarios
- **Normales:** inscripción exitosa con prerrequisitos y cupos libres; ajuste de horario sin cruces; consulta de historial vigente.
- **Alternativos:** lista de espera automática cuando la sección está llena; cupo condicional por homologación pendiente.
- **De fallo:** condición de carrera por el último cupo; corte de conectividad (rollback automático).

## Escala y retención
10.000 estudiantes activos · 2.000 secciones por período · picos de 5.000 solicitudes concurrentes · retención de 5 años.

## Requisitos funcionales
1. Registro de estudiantes con documento y correo únicos
2. Catálogo de cursos, créditos y prerrequisitos
3. Apertura de secciones por periodo con cupo máximo
4. Inscripción con validación previa de prerrequisitos
5. Rechazo de cruces de horario
6. Cupos ocupados/disponibles en tiempo real
7. Listas de espera cronológicas
8. Cambios de capacidad y forzado excepcional por administradores, con bitácora
9. Consulta de historiales de matrícula
10. Cancelación voluntaria dentro de la ventana del calendario

## Requisitos no funcionales
| Atributo | Meta |
|---|---|
| Consistencia ACID | Sin sobreventa de cupos bajo concurrencia masiva |
| Rendimiento | Verificar cupo e inscribir en < 500 ms |
| Disponibilidad | 99,99 % en ventanas de apertura de matrículas |
| Integridad estructural | Foreign Keys y Check Constraints estrictos |
| Auditoría y retención | Registros inmutables por al menos 5 años |
