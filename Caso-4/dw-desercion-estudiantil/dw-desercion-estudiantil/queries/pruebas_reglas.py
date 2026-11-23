"""Pruebas negativas: cada operación debe ser RECHAZADA por la base de datos."""
import sqlite3, sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "connection"))
from conexion import conectar

INS = ("INSERT INTO fact_rendimiento(id_tiempo,id_estudiante_sk,id_demografia_sk,id_programa_sk,"
       "id_curso_sk,nota,inasistencias,creditos_cursados) VALUES ")
PRUEBAS = [
    ("RN-08 estrato 9", "INSERT INTO dim_demografia(estrato,tipo_colegio,region) VALUES (9,'Público','Bogotá')"),
    ("RN-06 nota 6.0", INS + "(1,1,1,1,1,6.0,0,3)"),
    ("RN-11 inasistencia -2", INS + "(1,1,1,1,1,3.0,-2,3)"),
    ("RN-03/10 tiempo inexistente", INS + "(9999,1,1,1,1,3.0,0,3)"),
    ("RN-05 UPDATE en hechos", "UPDATE fact_rendimiento SET nota = 5.0"),
    ("RN-05 DELETE en hechos", "DELETE FROM fact_rendimiento"),
]
con = conectar()
for nombre, sql in PRUEBAS:
    try:
        con.execute(sql)
        print(f"FALLÓ  {nombre}: la base aceptó la operación")
    except sqlite3.Error as e:
        print(f"OK     {nombre}: rechazado -> {e}")
con.rollback()
