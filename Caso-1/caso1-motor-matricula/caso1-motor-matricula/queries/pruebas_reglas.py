"""Pruebas de las 12 reglas de negocio. Cada una se ejecuta dentro de un SAVEPOINT y se deshace."""
import sqlite3, sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent / "connection"))
from conexion import conectar

con = conectar()
M = "INSERT INTO matricula(id_estudiante,id_seccion,estado) VALUES "
def ids(est, sec): return f"(SELECT id_estudiante FROM estudiante WHERE codigo='{est}'),(SELECT id_seccion FROM seccion WHERE codigo='{sec}')"

def rechazada(nombre, sql, previo=()):
    con.execute("SAVEPOINT t")
    try:
        for p in previo: con.execute(p)
        con.execute(sql)
        print(f"FALLÓ  {nombre}: la base aceptó la operación")
    except sqlite3.Error as e:
        print(f"OK     {nombre}: rechazado -> {e}")
    finally:
        con.execute("ROLLBACK TO t"); con.execute("RELEASE t")

def verificar(nombre, fn):
    con.execute("SAVEPOINT t")
    try:
        ok, detalle = fn()
        print(("OK     " if ok else "FALLÓ  ") + f"{nombre}: {detalle}")
    finally:
        con.execute("ROLLBACK TO t"); con.execute("RELEASE t")

rechazada("RN-01 prerrequisito pendiente", M + f"({ids('EST_002','SEC_MAT2_01')},'CONFIRMADA')")
rechazada("RN-02 sobreventa del último cupo", M + f"({ids('EST_003','SEC_FAIL_3')},'CONFIRMADA')",
          previo=[M + f"({ids('EST_004','SEC_FAIL_3')},'CONFIRMADA')"])
rechazada("RN-03 choque de horario", M + f"({ids('EST_002','SEC_CHOQUE_1')},'CONFIRMADA')")
rechazada("RN-04 estado no listado", M + f"({ids('EST_003','SEC_FIS1_01')},'XX')")
rechazada("RN-05 curso con 0 créditos", "INSERT INTO curso(codigo,nombre,creditos) VALUES ('X1','Prueba',0)")
rechazada("RN-06 doble inserción idéntica", M + f"({ids('EST_002','SEC_MAT1_01')},'CONFIRMADA')")

def rn07():
    for e in ("EST_003", "EST_004"):
        con.execute(M + f"({ids(e,'SEC_FIS1_01')},'ESPERA')")
    cola = [r["estudiante"] for r in con.execute("SELECT estudiante FROM vw_lista_espera ORDER BY posicion")]
    return cola == ["EST_003", "EST_004"], f"cola FIFO = {cola}"
verificar("RN-07 lista de espera por orden de llegada", rn07)

def rn08():
    antes = con.execute("SELECT cupos_ocupados FROM seccion WHERE codigo='SEC_MAT1_01'").fetchone()[0]
    con.execute("UPDATE matricula SET estado='CANCELADA' WHERE id_estudiante=2 AND id_seccion=1")
    desp = con.execute("SELECT cupos_ocupados FROM seccion WHERE codigo='SEC_MAT1_01'").fetchone()[0]
    return desp == antes - 1, f"cupos_ocupados {antes} -> {desp}"
verificar("RN-08 cancelación libera el cupo", rn08)

def rn09():
    con.execute("UPDATE seccion SET cupo_maximo=40 WHERE codigo='SEC_MAT1_01'")
    n = con.execute("SELECT COUNT(*) FROM log_auditoria WHERE id_registro=1 AND campo='cupo_maximo'").fetchone()[0]
    return n == 1, f"{n} registro(s) en log_auditoria"
verificar("RN-09 auditoría de cambio manual de cupo", rn09)

rechazada("RN-10 periodo solapado",
          "INSERT INTO periodo(nombre,fecha_inicio,fecha_fin,fecha_limite_cancelacion) VALUES ('2026-X','2026-10-01','2027-01-30','2027-01-15')")
rechazada("RN-11 reducir cupo bajo los confirmados", "UPDATE seccion SET cupo_maximo=1 WHERE codigo='SEC_MAT1_01'",
          previo=[M + f"({ids('EST_003','SEC_MAT1_01')},'CONFIRMADA')"])
rechazada("RN-12 estudiante suspendido", M + f"({ids('EST_003','SEC_FIS1_01')},'CONFIRMADA')",
          previo=["UPDATE estudiante SET estado='SUSPENDIDO' WHERE codigo='EST_003'"])
