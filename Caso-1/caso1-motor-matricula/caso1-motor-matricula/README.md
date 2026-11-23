# Motor de Matrícula (OLTP) — Caso 1
Motor de inscripción académica concurrente en SQLite, sin sobreventa de cupos y con 12 reglas de negocio verificadas. Universidad ECCI — Ingeniería de Sistemas.

**Autor:** Johan Fabián Quiroga Sánchez

## Estructura
| Carpeta | Contenido |
|---|---|
| `docs/` | Contexto, reglas de negocio y decisiones de diseño |
| `database/` | `schema.sql` (DDL y triggers), `datos_iniciales.sql`, `crear_base_datos.py` y `matricula.db` |
| `queries/` | `consultas.sql` (consultas, 7 JOIN y plan de ejecución) y `pruebas_reglas.py` (RN-01 a RN-12) |
| `connection/` | `conexion.py` (conexión, `inscribir`, `cancelar`) y `concurrencia.py` |
| `nosql/` | Documentos `sesion_matricula` (MongoDB) |
| `graph/` | Malla curricular con networkx y script Cypher para Neo4j |

## Cómo ejecutarlo
```bash
pip install -r requirements.txt
python database/crear_base_datos.py     # crea la base
python queries/pruebas_reglas.py        # verifica las 12 reglas
python connection/concurrencia.py       # demuestra que no hay sobreventa
python nosql/exportar_documentos.py     # componente NoSQL
python graph/grafo_malla.py             # componente de grafos
```
