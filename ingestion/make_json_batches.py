"""Outil de TEST LOCAL uniquement (sans Kafka).
Decoupe le CSV en fichiers JSON (1 objet par ligne) dans data/json_in/, pour que
streaming_to_hdfs.py --source files puisse les lire comme un flux.
Les timestamps sont etales sur plusieurs minutes (comme un vrai flux)."""
import csv
import json
import os
import sys
from datetime import datetime, timedelta, timezone

csv_path = sys.argv[1] if len(sys.argv) > 1 else "data/paysim_synth.csv"
out_dir = sys.argv[2] if len(sys.argv) > 2 else "data/json_in"
os.makedirs(out_dir, exist_ok=True)

base = datetime(2026, 11, 16, 9, 0, 0, tzinfo=timezone.utc)
TAILLE_FICHIER = 5000

lignes = []
fichier_no = 0


def vider():
    global lignes, fichier_no
    if not lignes:
        return
    with open(os.path.join(out_dir, "batch_%03d.json" % fichier_no), "w") as f:
        f.write("\n".join(lignes) + "\n")
    fichier_no += 1
    lignes = []


with open(csv_path) as f:
    for i, row in enumerate(csv.DictReader(f)):
        msg = {
            "transaction_id": i + 1,
            "sender_id": row["nameOrig"],
            "receiver_id": row["nameDest"],
            "amount": float(row["amount"]),
            "type": row["type"],
            "oldbalance_org": float(row["oldbalanceOrg"]),
            "newbalance_org": float(row["newbalanceOrig"]),
            "oldbalance_dest": float(row["oldbalanceDest"]),
            "newbalance_dest": float(row["newbalanceDest"]),
            "is_fraud": int(row["isFraud"]),
            "timestamp": (base + timedelta(seconds=i * 0.6)).isoformat(),
        }
        lignes.append(json.dumps(msg))
        if len(lignes) >= TAILLE_FICHIER:
            vider()
vider()
print("fichiers ecrits dans", out_dir, ":", fichier_no)
