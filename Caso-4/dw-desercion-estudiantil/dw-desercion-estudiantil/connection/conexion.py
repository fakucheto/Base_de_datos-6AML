"""Conexión a la base de datos SQLite del DW y ejecución de consultas."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "database" / "datawarehouse.db"

def conectar(ruta=DB_PATH) -> sqlite3.Connection:
    if not Path(ruta).exists():
        raise FileNotFoundError("Primero ejecuta: python database/crear_base_datos.py")
    con = sqlite3.connect(ruta)
    con.execute("PRAGMA foreign_keys = ON")
    con.row_factory = sqlite3.Row
    return con

def consultar(sql: str, params=()):
    with conectar() as con:
        return [dict(r) for r in con.execute(sql, params).fetchall()]

if __name__ == "__main__":
    print("Conexión OK. Primeras filas de la vista de riesgo (vw_riesgo_desercion):")
    for fila in consultar("SELECT * FROM vw_riesgo_desercion ORDER BY prom_grupal LIMIT 5"):
        print(fila)
