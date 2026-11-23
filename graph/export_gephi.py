"""PARTIE 2 (suite) - Export du graphe depuis le Data Lab vers Gephi.

Lit les collections nodes / edges (MongoDB ou dossier JSON), garde un sous-graphe
lisible (toutes les transactions frauduleuses + les plus gros flux normaux), puis ecrit :
  - results/gephi/nodes.csv, results/gephi/edges.csv  (import "Tableur" de Gephi)
  - results/gephi/graphe_fraude.gexf          (ouverture directe dans Gephi)
  - results/gephi/analyse_reseau.txt          (degre, modularite, hubs : meme analyse que dans Gephi)
  - results/gephi/graphe_apercu.png           (apercu rapide, rendu avec matplotlib)

Usage :
    python graph/export_gephi.py --source mongo --mongo mongodb://localhost:27017
    python graph/export_gephi.py --source json --dir out_graph
"""
import argparse
import glob
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd
from networkx.algorithms.community import greedy_modularity_communities, modularity


def charger(args):
    if args.source == "mongo":
        from pymongo import MongoClient
        db = MongoClient(args.mongo)["fraude"]
        nodes = pd.DataFrame(list(db.nodes.find({}, {"_id": 0})))
        edges = pd.DataFrame(list(db.edges.find({}, {"_id": 0})))
    else:
        def lire(nom):
            fichiers = glob.glob(os.path.join(args.dir, nom, "part-*.json"))
            return pd.concat([pd.read_json(f, lines=True) for f in fichiers])
        nodes, edges = lire("nodes"), lire("edges")
    return nodes, edges


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", choices=["mongo", "json"], default="json")
    p.add_argument("--mongo", default="mongodb://localhost:27017")
    p.add_argument("--dir", default="out_graph")
    p.add_argument("--out", default="results/gephi")
    p.add_argument("--normaux", type=int, default=1500, help="nb de flux normaux gardes pour le contexte")
    args = p.parse_args()
    os.makedirs(args.out, exist_ok=True)

    nodes, edges = charger(args)

    # --- sous-graphe lisible ---
    fraude = edges[edges["nb_fraudes"] > 0]
    normaux = edges[edges["nb_fraudes"] == 0].nlargest(args.normaux, "montant_total")
    sub = pd.concat([fraude, normaux])
    ids = set(sub["source"]) | set(sub["target"])
    sub_nodes = nodes[nodes["id"].isin(ids)].copy()
    print("sous-graphe :", len(sub_nodes), "noeuds,", len(sub), "arcs")

    # --- analyse reseau (equivalent de ce qu'on fait dans Gephi) ---
    G = nx.DiGraph()
    for _, r in sub.iterrows():
        G.add_edge(r["source"], r["target"], weight=float(r["montant_total"]),
                   nb_tx=int(r["nb_tx"]), nb_fraudes=int(r["nb_fraudes"]))
    ug = G.to_undirected()
    comms = list(greedy_modularity_communities(ug, weight="weight"))
    mod = modularity(ug, comms, weight="weight")
    classe = {n: i for i, c in enumerate(comms) for n in c}
    deg_in = dict(G.in_degree())
    deg_out = dict(G.out_degree())
    deg_w_in = dict(G.in_degree(weight="nb_fraudes"))

    sub_nodes["in_degree"] = sub_nodes["id"].map(deg_in).fillna(0).astype(int)
    sub_nodes["out_degree"] = sub_nodes["id"].map(deg_out).fillna(0).astype(int)
    sub_nodes["fraudes_in"] = sub_nodes["id"].map(deg_w_in).fillna(0).astype(int)
    sub_nodes["modularity_class"] = sub_nodes["id"].map(classe).fillna(-1).astype(int)

    # --- fichiers pour Gephi ---
    n_csv = sub_nodes.rename(columns={"id": "Id"})
    n_csv.insert(1, "Label", n_csv["Id"])
    n_csv.to_csv(os.path.join(args.out, "nodes.csv"), index=False)
    e_csv = sub.rename(columns={"source": "Source", "target": "Target"}).copy()
    e_csv["Type"] = "Directed"
    e_csv["Weight"] = e_csv["montant_total"]
    e_csv.to_csv(os.path.join(args.out, "edges.csv"), index=False)

    for _, r in sub_nodes.iterrows():
        G.nodes[r["id"]].update({
            "label": r["id"], "type_compte": r["type_compte"],
            "in_degree": int(r["in_degree"]), "modularity_class": int(r["modularity_class"]),
            "fraudes_in": int(r["fraudes_in"])})
    nx.write_gexf(G, os.path.join(args.out, "graphe_fraude.gexf"))

    # --- hubs ---
    hubs = sub_nodes.sort_values(["fraudes_in", "in_degree"], ascending=False).head(10)
    with open(os.path.join(args.out, "analyse_reseau.txt"), "w") as f:
        f.write("Noeuds : %d | Arcs : %d\n" % (G.number_of_nodes(), G.number_of_edges()))
        f.write("Composantes connexes : %d\n" % nx.number_connected_components(ug))
        f.write("Communautes (modularite gloutonne) : %d | Q = %.3f\n\n" % (len(comms), mod))
        f.write("Top 10 comptes par fraudes recues (hubs suspects) :\n")
        f.write(hubs[["id", "in_degree", "fraudes_in", "total_recu", "modularity_class"]].to_string(index=False))
        f.write("\n")
    print(open(os.path.join(args.out, "analyse_reseau.txt")).read())

    # --- apercu image ---
    # on ne dessine que le sous-reseau frauduleux (sinon illisible)
    gf = nx.Graph()
    for _, r in fraude.iterrows():
        gf.add_edge(r["source"], r["target"])
    hubs_ids = set(hubs["id"])
    pos = nx.spring_layout(gf, seed=7, k=0.12, iterations=80)
    couleurs, tailles = [], []
    for n in gf.nodes():
        if n in hubs_ids:
            couleurs.append("#d62728"); tailles.append(260)
        else:
            couleurs.append("#7f9fc9"); tailles.append(9)
    fig, ax = plt.subplots(figsize=(11, 9))
    nx.draw_networkx_edges(gf, pos, alpha=0.18, width=0.4, ax=ax)
    nx.draw_networkx_nodes(gf, pos, node_size=tailles, node_color=couleurs, ax=ax)
    nx.draw_networkx_labels(gf, pos, labels={n: n for n in hubs_ids}, font_size=7, ax=ax)
    ax.set_title("Sous-reseau des transactions frauduleuses\n(rouge = comptes hubs recevant le plus de fraudes)")
    ax.axis("off")
    fig.tight_layout()
    fig.savefig(os.path.join(args.out, "graphe_apercu.png"), dpi=130)
    print("export termine dans", args.out)


if __name__ == "__main__":
    main()
