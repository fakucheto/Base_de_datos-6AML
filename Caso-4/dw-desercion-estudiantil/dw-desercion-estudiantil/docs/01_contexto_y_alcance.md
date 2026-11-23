# 1. Contexto y alcance — Caso 4: DW Deserción Estudiantil (OLAP)

## Problema y objetivo medible
Identificar estudiantes en riesgo de abandono cruzando históricos académicos, asistencia y factores socioeconómicos.
**Objetivo:** reducir la deserción en un 15 % con alertas tempranas, mediante consultas analíticas que respondan en **menos de 10 segundos**.

## Límite del sistema
- **Incluye:** repositorio analítico (Data Warehouse) en esquema estrella y flujos de lectura.
- **Excluye:** intervención psicológica directa, sistemas transaccionales de origen y el pipeline ETL de ingesta.

## Actores
| Actor | Rol |
|---|---|
| Analistas de retención | Consultan tableros de riesgo |
| Decanatura | Evalúa políticas a partir de reportes |
| Pipeline ETL | Inserciones en lotes nocturnos |

## Escenarios
- **Normales:** ingesta batch nocturna; consulta de riesgo por estrato y cohorte; generación del cubo OLAP al cierre de semestre.
- **Alternativos:** recálculo de dimensiones SCD Tipo 2 por cambio de programa/sede; carga incremental a mediodía por corrección masiva de notas.
- **De fallo:** ETL interrumpido (estado inconsistente); timeouts en agregaciones por falta de índices.

## Volumen y velocidad
Terabytes de históricos, baja velocidad transaccional, escrituras en batch nocturno, retención > 10 años.

## Requisitos no funcionales
| Atributo | Meta |
|---|---|
| Rendimiento | Agregaciones por facultad < 10 s |
| Privacidad | Anonimización obligatoria |
| Consistencia | Eventual, desfase máx. 24 h |
| Disponibilidad | Media (ventanas de mantenimiento nocturnas) |
| Escalabilidad | Optimizado para lecturas pesadas |
