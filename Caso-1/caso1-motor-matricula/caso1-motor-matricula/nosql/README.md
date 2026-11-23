# Componente NoSQL (documental)
En los picos de matrícula, el borrador del horario vive en un **documento por estudiante** (`sesion_matricula`), no en la base relacional.
- Generar: `python nosql/exportar_documentos.py` → `sesion_matricula.json`
- Importar: `mongoimport --db sistema_matricula --collection sesion_matricula --jsonArray --file nosql/sesion_matricula.json`
- Actualización atómica de una sesión:
```js
db.sesion_matricula.updateOne({ estudiante_id: "EST_001" },
  { $inc: { creditos_seleccionados: 3 },
    $push: { horario_borrador: { id_seccion: "SEC_FIS1_01", creditos: 3, dia_semana: "MIE", hora: "10:00-12:00" } } })
```
Arquitectura políglota: SQLite = verdad transaccional (cupos), MongoDB = carrito de sesión, grafo = malla curricular.
