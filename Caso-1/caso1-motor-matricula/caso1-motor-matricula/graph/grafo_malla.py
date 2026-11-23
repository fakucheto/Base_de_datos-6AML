"""Grafos (networkx): malla curricular y prerrequisitos.
G2: impacto en cascada si se reprueba una materia. G3: materias habilitadas para un estudiante."""
import sys
from pathlib import Path
import networkx as nx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.append(str(Path(__file__).parent.parent / "connection"))
from conexion import conectar

con = conectar()
G = nx.DiGraph()
for c in con.execute("SELECT * FROM curso"):
    G.add_node(c["codigo"], nombre=c["nombre"], tipo="asignatura")
for p in con.execute("""SELECT c1.codigo a, c2.codigo b FROM prerequisito p
                        JOIN curso c1 ON c1.id_curso=p.id_prerequisito JOIN curso c2 ON c2.id_curso=p.id_curso"""):
    G.add_edge(p["a"], p["b"], rel="ES_PRERREQUISITO_DE")

def impacto(codigo):  # G2
    niveles = nx.single_source_shortest_path_length(G, codigo)
    return sorted(((v, n) for v, n in niveles.items() if v != codigo), key=lambda x: (x[1], x[0]))

def habilitadas(est):  # G3
    aprob = {r["codigo"] for r in con.execute(
        "SELECT c.codigo FROM aprobacion a JOIN curso c ON c.id_curso=a.id_curso JOIN estudiante e ON e.id_estudiante=a.id_estudiante WHERE e.codigo=?", (est,))}
    return sorted(c for c in G if c not in aprob and set(G.predecessors(c)) <= aprob and G.in_degree(c) > 0)

print("G2 - Si se reprueba MAT101 se bloquean:")
for v, n in impacto("MAT101"):
    print(f"  {v} {G.nodes[v]['nombre']} (nivel {n})")
print("G3 - Materias habilitadas para EST_001:", habilitadas("EST_001"))

for i, gen in enumerate(nx.topological_generations(G)):
    for n in gen: G.nodes[n]["capa"] = i
pos = nx.multipartite_layout(G, subset_key="capa")
plt.figure(figsize=(10, 6))
nx.draw(G, pos, with_labels=True, node_color="#4c78a8", font_color="white", node_size=2200, font_size=8, arrows=True)
plt.title("Malla curricular: ES_PRERREQUISITO_DE")
plt.savefig(Path(__file__).parent / "malla_curricular.png", dpi=150, bbox_inches="tight")
nx.write_graphml(G, Path(__file__).parent / "malla_curricular.graphml")
print("Guardado: malla_curricular.png y malla_curricular.graphml")
