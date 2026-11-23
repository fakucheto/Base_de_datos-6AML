# Componente NoSQL (documental)
Cada estudiante es un **documento** con sus versiones SCD2 y su rendimiento **embebido**, así una lectura no necesita JOINs.
- Generar: `python nosql/exportar_documentos.py` → `estudiantes.json`
- Importar en MongoDB: `mongoimport --db dw --collection estudiantes --jsonArray --file nosql/estudiantes.json`
- Consulta equivalente a la vista de riesgo: `db.estudiantes.find({ en_riesgo: true })`
