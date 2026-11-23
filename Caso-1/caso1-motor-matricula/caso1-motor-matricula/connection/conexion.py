"""Conexión a SQLite y operaciones transaccionales del motor de matrícula."""
import sqlite3
from datetime import date
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "database" / "matricula.db"

def conectar(ruta=DB_PATH) -> sqlite3.Connection:
    if not Path(ruta).exists():
        raise FileNotFoundError("Primero ejecuta: python database/crear_base_datos.py")
    con = sqlite3.connect(ruta, timeout=10, isolation_level=None)  # transacciones manuales
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA busy_timeout = 10000")
    con.row_factory = sqlite3.Row
    return con

def consultar(sql, params=(), ruta=DB_PATH):
    con = conectar(ruta)
    try:
        return [dict(r) for r in con.execute(sql, params).fetchall()]
    finally:
        con.close()

def inscribir(codigo_estudiante, codigo_seccion, ruta=DB_PATH) -> str:
    """Inscripción atómica. BEGIN IMMEDIATE serializa el acceso al último cupo (sin sobreventa).
    Devuelve CONFIRMADA, ESPERA o 'RECHAZADA: <motivo de la regla de negocio>'."""
    con = conectar(ruta)
    try:
        con.execute("BEGIN IMMEDIATE")
        fila = con.execute("""SELECT e.id_estudiante, s.id_seccion, s.cupo_maximo - s.cupos_ocupados AS libres
                              FROM estudiante e, seccion s WHERE e.codigo=? AND s.codigo=?""",
                           (codigo_estudiante, codigo_seccion)).fetchone()
        if fila is None:
            con.execute("ROLLBACK")
            return "RECHAZADA: estudiante o sección inexistente"
        estado = "CONFIRMADA" if fila["libres"] > 0 else "ESPERA"
        con.execute("INSERT INTO matricula(id_estudiante,id_seccion,estado) VALUES (?,?,?)",
                    (fila["id_estudiante"], fila["id_seccion"], estado))
        con.execute("COMMIT")
        return estado
    except sqlite3.Error as e:
        if con.in_transaction:
            con.execute("ROLLBACK")
        return f"RECHAZADA: {e}"
    finally:
        con.close()

def cancelar(codigo_estudiante, codigo_seccion, hoy=None, ruta=DB_PATH) -> str:
    """Cancelación voluntaria dentro de la ventana del calendario (RF-10). El trigger libera el cupo."""
    hoy = (hoy or date.today()).isoformat()
    con = conectar(ruta)
    try:
        con.execute("BEGIN IMMEDIATE")
        f = con.execute("""SELECT m.id_matricula, p.fecha_limite_cancelacion AS limite
                           FROM matricula m JOIN estudiante e ON e.id_estudiante=m.id_estudiante
                           JOIN seccion s ON s.id_seccion=m.id_seccion JOIN periodo p ON p.id_periodo=s.id_periodo
                           WHERE e.codigo=? AND s.codigo=? AND m.estado<>'CANCELADA'""",
                        (codigo_estudiante, codigo_seccion)).fetchone()
        if f is None:
            con.execute("ROLLBACK"); return "RECHAZADA: no existe matrícula activa"
        if hoy > f["limite"]:
            con.execute("ROLLBACK"); return f"RECHAZADA: fuera de la ventana de cancelación ({f['limite']})"
        con.execute("UPDATE matricula SET estado='CANCELADA' WHERE id_matricula=?", (f["id_matricula"],))
        con.execute("COMMIT")
        return "CANCELADA"
    except sqlite3.Error as e:
        if con.in_transaction:
            con.execute("ROLLBACK")
        return f"RECHAZADA: {e}"
    finally:
        con.close()

if __name__ == "__main__":
    print("Conexión OK. Cupos disponibles (vw_cupos_disponibles):")
    for f in consultar("SELECT * FROM vw_cupos_disponibles"):
        print(f)
    print("Inscribir EST_003 en SEC_MAT1_01 ->", inscribir("EST_003", "SEC_MAT1_01"))
