# DW Deserción Estudiantil (OLAP) — Caso 4
Data Warehouse en esquema estrella (SQLite) para detectar estudiantes en riesgo de abandono. Universidad ECCI — Ingeniería de Sistemas.

**Autor:** Johan Fabián Quiroga Sánchez

## Estructura
| Carpeta | Contenido |
|---|---|
| `docs/` | Contexto, reglas de negocio y decisiones de diseño |
| `database/` | `schema.sql` (DDL), `crear_base_datos.py` (carga datos sintéticos) y `datawarehouse.db` |
| `queries/` | `consultas.sql` (Q1–Q8) y `pruebas_reglas.py` (pruebas negativas) |
| `connection/` | `conexion.py` — conexión Python ↔ SQLite |
| `nosql/` | Modelo documental (JSON / MongoDB) |
| `graph/` | Implementación de grafos con networkx |

## Cómo ejecutarlo
```bash
pip install -r requirements.txt
python database/crear_base_datos.py   # crea la base
python connection/conexion.py         # prueba la conexión
python queries/pruebas_reglas.py      # verifica las reglas de negocio
python nosql/exportar_documentos.py   # componente NoSQL
python graph/grafo_desercion.py       # componente de grafos
```
Las consultas de `queries/consultas.sql` se pueden abrir y ejecutar en DBeaver o DB Browser for SQLite.
