"""Modelo NoSQL (documental, estilo MongoDB): exporta el DW a documentos JSON.
Un documento por estudiante con su rendimiento embebido (sin JOINs)."""
import json, sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "connection"))
from conexion import conectar

con = conectar()
docs = []
for e in con.execute("SELECT DISTINCT hash_identidad FROM dim_estudiante LIMIT 200").fetchall():
    h = e["hash_identidad"]
    versiones = [dict(v) for v in con.execute(
        "SELECT sede, cohorte, fecha_inicio, fecha_fin, es_activo FROM dim_estudiante WHERE hash_identidad=? ORDER BY fecha_inicio", (h,))]
    rendimiento = [dict(r) for r in con.execute("""
        SELECT t.anio, t.mes, c.nombre AS curso, f.nota, f.inasistencias, f.alerta_riesgo, d.estrato, p.nombre_programa AS programa
        FROM fact_rendimiento f
        JOIN dim_estudiante e ON f.id_estudiante_sk=e.id_estudiante_sk
        JOIN dim_tiempo t ON f.id_tiempo=t.id_tiempo
        JOIN dim_curso c ON f.id_curso_sk=c.id_curso_sk
        JOIN dim_demografia d ON f.id_demografia_sk=d.id_demografia_sk
        JOIN dim_programa p ON f.id_programa_sk=p.id_programa_sk
        WHERE e.hash_identidad=? ORDER BY t.anio, t.mes""", (h,))]
    docs.append({"_id": h[:16], "hash_identidad": h, "versiones": versiones, "rendimiento": rendimiento,
                 "en_riesgo": any(r["alerta_riesgo"] for r in rendimiento)})

salida = Path(__file__).parent / "estudiantes.json"
salida.write_text(json.dumps(docs, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"{len(docs)} documentos exportados a {salida.name}")
print("Equivalente MongoDB: db.estudiantes.find({en_riesgo: true})")
