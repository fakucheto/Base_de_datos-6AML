"""Crea matricula.db desde schema.sql y datos_iniciales.sql."""
import sqlite3
from pathlib import Path

BASE = Path(__file__).parent
DB = BASE / "matricula.db"

def main():
    if DB.exists():
        DB.unlink()
    con = sqlite3.connect(DB)
    con.executescript((BASE / "schema.sql").read_text(encoding="utf-8"))
    con.executescript((BASE / "datos_iniciales.sql").read_text(encoding="utf-8"))
    con.commit()
    n = con.execute("SELECT COUNT(*) FROM matricula").fetchone()[0]
    print(f"Base creada: {DB.name} ({n} matrículas iniciales).")
    con.close()

if __name__ == "__main__":
    main()
