"""NoSQL (documental, MongoDB): un documento 'sesion_matricula' por estudiante, sin JOINs."""
import json, sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "connection"))
from conexion import conectar

con = conectar()
periodo = con.execute("SELECT nombre FROM periodo LIMIT 1").fetchone()["nombre"]
docs = []
for e in con.execute("SELECT * FROM estudiante").fetchall():
    horario = [dict(r) for r in con.execute("""
        SELECT s.codigo AS id_seccion, c.creditos, h.dia_semana, h.hora_inicio || '-' || h.hora_fin AS hora
        FROM matricula m JOIN seccion s ON s.id_seccion=m.id_seccion JOIN curso c ON c.id_curso=s.id_curso
        JOIN horario_seccion h ON h.id_seccion=s.id_seccion
        WHERE m.id_estudiante=? AND m.estado <> 'CANCELADA'""", (e["id_estudiante"],))]
    docs.append({"_id": e["codigo"], "estudiante_id": e["codigo"], "nombre": e["nombre_completo"],
                 "programa": e["programa"], "periodo": periodo, "max_creditos_permitidos": 20,
                 "creditos_seleccionados": sum(h["creditos"] for h in horario),
                 "estado_sesion": "EN_PROCESO", "horario_borrador": horario})
salida = Path(__file__).parent / "sesion_matricula.json"
salida.write_text(json.dumps(docs, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"{len(docs)} documentos exportados a {salida.name}")
