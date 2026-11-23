"""Figures du rapport a partir de results/metriques_modeles.json."""
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

d = json.load(open("results/metriques_modeles.json"))
res = d["resultats"]

# --- matrices de confusion ---
fig, axes = plt.subplots(1, 2, figsize=(9, 3.8))
for ax, r in zip(axes, res):
    m = np.array([[r["TN"], r["FP"]], [r["FN"], r["TP"]]])
    ax.imshow(m, cmap="Blues")
    for i in range(2):
        for j in range(2):
            ax.text(j, i, f"{m[i, j]:,}".replace(",", " "), ha="center", va="center",
                    color="white" if m[i, j] > m.max() / 2 else "black", fontsize=12)
    ax.set_xticks([0, 1]); ax.set_xticklabels(["predit normal", "predit fraude"])
    ax.set_yticks([0, 1]); ax.set_yticklabels(["reel normal", "reel fraude"])
    ax.set_title(r["modele"])
fig.suptitle("Matrices de confusion (jeu de test)")
fig.tight_layout()
fig.savefig("results/fig_confusion.png", dpi=140)

# --- comparaison des metriques ---
fig, ax = plt.subplots(figsize=(7.5, 3.8))
mets = ["auc_roc", "auc_pr", "rappel", "precision", "f1"]
x = np.arange(len(mets)); w = 0.38
for k, r in enumerate(res):
    vals = [r[m] for m in mets]
    b = ax.bar(x + (k - 0.5) * w, vals, w, label=r["modele"])
    for xi, v in zip(x + (k - 0.5) * w, vals):
        ax.text(xi, v + 0.01, f"{v:.2f}", ha="center", fontsize=8)
ax.set_xticks(x); ax.set_xticklabels(["AUC ROC", "AUC PR", "Rappel", "Precision", "F1"])
ax.set_ylim(0, 1.12); ax.legend(loc="lower right")
ax.set_title("Regression logistique vs Random Forest")
fig.tight_layout()
fig.savefig("results/fig_comparaison.png", dpi=140)

# --- importance des variables ---
imp = d["importance_rf"][:8]
fig, ax = plt.subplots(figsize=(7, 3.6))
ax.barh([n for n, _ in imp][::-1], [v for _, v in imp][::-1], color="#3b6ea5")
ax.set_title("Importance des variables (Random Forest)")
fig.tight_layout()
fig.savefig("results/fig_importance.png", dpi=140)
print("figures ok")
