"""Demostración de RNF-1 (ACID): 20 estudiantes compiten por el ÚLTIMO cupo. Debe haber exactamente 1 confirmado."""
import shutil, sqlite3, tempfile, threading
from pathlib import Path
from conexion import DB_PATH, inscribir

tmp = Path(tempfile.mkdtemp()) / "demo.db"
shutil.copy(DB_PATH, tmp)
con = sqlite3.connect(tmp)
con.execute("INSERT INTO seccion(codigo,id_curso,id_periodo,cupo_maximo) VALUES ('SEC_ULTIMO',7,1,1)")
for i in range(20):
    con.execute("INSERT INTO estudiante(codigo,documento,nombre_completo,correo) VALUES (?,?,?,?)",
                (f"CON_{i:02d}", f"9{i:03d}", f"Concurrente {i}", f"c{i}@ecci.edu.co"))
con.commit(); con.close()

resultados = []
def hilo(i):
    resultados.append(inscribir(f"CON_{i:02d}", "SEC_ULTIMO", ruta=tmp))

hilos = [threading.Thread(target=hilo, args=(i,)) for i in range(20)]
[h.start() for h in hilos]; [h.join() for h in hilos]

con = sqlite3.connect(tmp)
ocupados, maximo = con.execute("SELECT cupos_ocupados, cupo_maximo FROM seccion WHERE codigo='SEC_ULTIMO'").fetchone()
print({e: resultados.count(e) for e in set(resultados)})
print(f"cupos_ocupados={ocupados} <= cupo_maximo={maximo}  ->", "OK, sin sobreventa" if ocupados <= maximo else "FALLO")
