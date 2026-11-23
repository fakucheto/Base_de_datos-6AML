# Componente de grafos
Malla curricular como grafo dirigido: asignaturas (nodos) y `ES_PRERREQUISITO_DE` (aristas). Evita consultas recursivas (`WITH RECURSIVE`) en el motor relacional.
- `python graph/grafo_malla.py` → impacto en cascada (G2), materias habilitadas (G3), `malla_curricular.png` y `.graphml`.
- `neo4j_script.cypher`: mismo modelo para Neo4j AuraDB Free (consultas G1, G2 y G3).
