"""Implementación de grafos (networkx): estudiantes en riesgo conectados a programa y estrato.
Responde: ¿qué programas y estratos concentran más estudiantes en riesgo?"""
import sys
from pathlib import Path
import networkx as nx
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.append(str(Path(__file__).parent.parent / "connection"))
from conexion import conectar

con = conectar()
filas = con.execute("""
    SELECT substr(e.hash_identidad,1,6) AS est, p.nombre_programa AS prog, d.estrato AS estrato,
           SUM(f.alerta_riesgo) AS alertas
    FROM fact_rendimiento f
    JOIN dim_estudiante e ON f.id_estudiante_sk=e.id_estudiante_sk
    JOIN dim_programa p ON f.id_programa_sk=p.id_programa_sk
    JOIN dim_demografia d ON f.id_demografia_sk=d.id_demografia_sk
    GROUP BY e.hash_identidad, p.nombre_programa, d.estrato
    HAVING alertas >= 3""").fetchall()

G = nx.Graph()
for r in filas:
    est, prog, estr = f"E:{r['est']}", f"P:{r['prog']}", f"Estrato {r['estrato']}"
    G.add_node(est, tipo="estudiante"); G.add_node(prog, tipo="programa"); G.add_node(estr, tipo="estrato")
    G.add_edge(est, prog); G.add_edge(est, estr)

print(f"Grafo: {G.number_of_nodes()} nodos, {G.number_of_edges()} aristas")
print("Programas/estratos con más estudiantes en riesgo (grado del nodo):")
hubs = sorted(((n, G.degree(n)) for n, a in G.nodes(data=True) if a["tipo"] != "estudiante"), key=lambda x: -x[1])
for n, g in hubs[:6]:
    print(f"  {n}: {g}")

nx.write_graphml(G, Path(__file__).parent / "grafo_riesgo.graphml")
colores = {"estudiante": "#cccccc", "programa": "#4c78a8", "estrato": "#f58518"}
pos = nx.spring_layout(G, seed=7, k=0.4)
plt.figure(figsize=(11, 8))
nx.draw(G, pos, node_color=[colores[G.nodes[n]["tipo"]] for n in G],
        node_size=[300 if G.nodes[n]["tipo"] != "estudiante" else 40 for n in G], edge_color="#bbbbbb", width=0.5)
nx.draw_networkx_labels(G, pos, {n: n for n in G if G.nodes[n]["tipo"] != "estudiante"}, font_size=8)
plt.title("Estudiantes en riesgo vs. programa y estrato")
plt.savefig(Path(__file__).parent / "grafo_riesgo.png", dpi=150, bbox_inches="tight")
print("Guardado: grafo_riesgo.png y grafo_riesgo.graphml")
