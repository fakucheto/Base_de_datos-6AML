"""Crea datawarehouse.db a partir de schema.sql y carga datos sintéticos (ETL simulado)."""
import hashlib, random, sqlite3
from pathlib import Path

BASE = Path(__file__).parent
DB = BASE / "datawarehouse.db"
random.seed(42)

def sha(texto: str) -> str:  # RN-01: la identidad llega ya enmascarada
    return hashlib.sha256(texto.encode()).hexdigest()

def main():
    if DB.exists():
        DB.unlink()
    con = sqlite3.connect(DB)
    con.executescript((BASE / "schema.sql").read_text(encoding="utf-8"))

    for anio in range(2022, 2027):
        for mes in range(1, 13):
            con.execute("INSERT INTO dim_tiempo(anio,semestre,mes,es_cierre_ciclo) VALUES (?,?,?,?)",
                        (anio, 1 if mes <= 6 else 2, mes, 1 if mes in (6, 12) else 0))

    programas = [("Ingeniería", "Ingeniería de Sistemas"), ("Ingeniería", "Ingeniería Industrial"),
                 ("Ciencias Económicas", "Administración"), ("Ciencias Económicas", "Contaduría"),
                 ("Salud", "Psicología")]
    con.executemany("INSERT INTO dim_programa(facultad,nombre_programa,nivel_academico) VALUES (?,?,'Pregrado')", programas)

    for estrato in range(1, 7):
        for colegio in ("Público", "Privado"):
            for region in ("Bogotá", "Otras regiones"):
                con.execute("INSERT INTO dim_demografia(estrato,tipo_colegio,region) VALUES (?,?,?)", (estrato, colegio, region))

    cursos = [("BD101", "Bases de Datos", 3), ("PRG101", "Programación", 3), ("MAT101", "Cálculo", 4),
              ("EST101", "Estadística", 3), ("ING101", "Ingeniería de Software", 3), ("RED101", "Redes", 2)]
    con.executemany("INSERT INTO dim_curso(codigo,nombre,creditos) VALUES (?,?,?)", cursos)

    tiempos = {(a, m): i for i, a, m in con.execute("SELECT id_tiempo,anio,mes FROM dim_tiempo").fetchall()}
    n_dem = con.execute("SELECT COUNT(*) FROM dim_demografia").fetchone()[0]

    meses_eval = [(a, m) for a in range(2023, 2026) for m in (6, 12)]  # cierres de ciclo
    for n in range(200):
        h = sha(f"estudiante-{n}")
        cohorte = random.choice(["2022-1", "2022-2", "2023-1", "2023-2"])
        dem1 = random.randint(1, n_dem)
        if n % 20 == 0:                              # 10 estudiantes con cambio SCD2
            dem2 = random.randint(1, n_dem)
            con.execute("INSERT INTO dim_estudiante(hash_identidad,cohorte,sede,fecha_inicio,fecha_fin,es_activo) VALUES (?,?,?,?,?,0)",
                        (h, cohorte, "Sede Norte", "2022-01-15", "2024-12-31"))
            v1 = con.execute("SELECT last_insert_rowid()").fetchone()[0]
            con.execute("INSERT INTO dim_estudiante(hash_identidad,cohorte,sede,fecha_inicio,fecha_fin,es_activo) VALUES (?,?,?,?,NULL,1)",
                        (h, cohorte, "Sede Centro", "2025-01-01"))
            v2 = con.execute("SELECT last_insert_rowid()").fetchone()[0]
        else:
            con.execute("INSERT INTO dim_estudiante(hash_identidad,cohorte,sede,fecha_inicio,fecha_fin,es_activo) VALUES (?,?,?,?,NULL,1)",
                        (h, cohorte, "Sede Norte", "2022-01-15"))
            v1 = v2 = con.execute("SELECT last_insert_rowid()").fetchone()[0]
            dem2 = dem1
        prog = random.randint(1, len(programas))
        riesgo = random.random() < 0.2
        for (a, m) in meses_eval:
            sk, dem = (v1, dem1) if a < 2025 else (v2, dem2)
            for curso in random.sample(range(1, len(cursos) + 1), 3):
                nota = round(min(5, max(0, random.gauss(2.6 if riesgo else 3.8, 0.6))), 1)
                inas = max(0, int(random.gauss(8 if riesgo else 2, 2)))
                con.execute("""INSERT INTO fact_rendimiento
                    (id_tiempo,id_estudiante_sk,id_demografia_sk,id_programa_sk,id_curso_sk,nota,inasistencias,creditos_cursados)
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (tiempos[(a, m)], sk, dem, prog, curso, nota, inas, cursos[curso - 1][2]))

    # RN-04: promedio ponderado por créditos, persistido
    con.execute("""INSERT INTO agg_promedio_mensual
        SELECT id_tiempo, id_estudiante_sk, ROUND(SUM(nota*creditos_cursados)*1.0/SUM(creditos_cursados),2)
        FROM fact_rendimiento GROUP BY id_tiempo, id_estudiante_sk""")

    con.executemany("INSERT INTO log_acceso(usuario,rol,objeto) VALUES (?,?,?)",
                    [("analista1", "analista", "vw_riesgo_desercion"), ("analista1", "analista", "vw_riesgo_desercion"),
                     ("analista2", "analista", "vw_riesgo_desercion"), ("decano1", "decanatura", "fact_rendimiento")])
    con.commit()
    n = con.execute("SELECT COUNT(*) FROM fact_rendimiento").fetchone()[0]
    print(f"Base creada: {DB.name} con {n} hechos.")
    con.close()

if __name__ == "__main__":
    main()
