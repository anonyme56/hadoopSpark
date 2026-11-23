"""Charge les transactions du data lake (Parquet) + les alertes du modele dans la base relationnelle.

PostgreSQL (cluster) : python database/load_relational.py --db postgresql+psycopg2://fraude:fraude@localhost:5432/fraude
SQLite (test local)  : python database/load_relational.py --db sqlite:///fraude.db
Le chargement est idempotent : on repart d'une base vide a chaque execution.
"""
import argparse
import os
import time

import pandas as pd
from sqlalchemy import create_engine, text

TYPES = ["PAYMENT", "CASH_IN", "CASH_OUT", "TRANSFER", "DEBIT"]


def executer_script(conn, chemin):
    """Execute le fichier .sql instruction par instruction."""
    sql = open(chemin).read()
    lignes = [l for l in sql.splitlines() if not l.strip().startswith("--")]
    for instr in "\n".join(lignes).split(";"):
        if instr.strip():
            conn.execute(text(instr))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db", default="sqlite:///fraude.db")
    p.add_argument("--parquet", default="out_lake/transactions_parquet")
    p.add_argument("--alertes", default="results/alertes_fraude.csv")
    p.add_argument("--schema", default="database/schema.sql")
    args = p.parse_args()

    t0 = time.time()
    engine = create_engine(args.db)

    tx = pd.read_parquet(args.parquet)
    # lecture d'un dossier partitionne : la colonne "type" peut etre de type category
    tx["type"] = tx["type"].astype(str)

    with engine.begin() as conn:
        for t in ["fraud_alerts", "transactions", "accounts", "transaction_types"]:
            conn.execute(text("DROP TABLE IF EXISTS " + t))
        executer_script(conn, args.schema)

        conn.execute(text("INSERT INTO transaction_types(type_id, type_code) VALUES (:i, :c)"),
                     [{"i": i + 1, "c": c} for i, c in enumerate(TYPES)])

        comptes = pd.unique(pd.concat([tx["sender_id"], tx["receiver_id"]]))
        conn.execute(text("INSERT INTO accounts(account_id, account_kind) VALUES (:a, :k)"),
                     [{"a": c, "k": "MARCHAND" if c.startswith("M") else "CLIENT"} for c in comptes])

    ids_type = {c: i + 1 for i, c in enumerate(TYPES)}
    df = pd.DataFrame({
        "transaction_id": tx["transaction_id"], "sender_id": tx["sender_id"],
        "receiver_id": tx["receiver_id"], "type_id": tx["type"].map(ids_type),
        "amount": tx["amount"], "oldbalance_org": tx["oldbalance_org"],
        "newbalance_org": tx["newbalance_org"], "oldbalance_dest": tx["oldbalance_dest"],
        "newbalance_dest": tx["newbalance_dest"], "is_fraud": tx["is_fraud"],
        "tx_time": pd.to_datetime(tx["ts"]).dt.tz_localize(None),
    })
    df.to_sql("transactions", engine, if_exists="append", index=False, chunksize=5000)

    if os.path.exists(args.alertes):
        al = pd.read_csv(args.alertes)
        motifs = al.apply(lambda r: "ratio montant/solde=%.2f; freq_horaire=%d; solde apres=%.0f"
                          % (r["ratio_montant_solde"], r["freq_horaire"], r["newbalance_org"]), axis=1)
        out = pd.DataFrame({"alert_id": range(1, len(al) + 1), "transaction_id": al["transaction_id"],
                            "risk_reasons": motifs, "status": "A_VERIFIER"})
        out.to_sql("fraud_alerts", engine, if_exists="append", index=False)

    with engine.connect() as conn:
        for t in ["transaction_types", "accounts", "transactions", "fraud_alerts"]:
            n = conn.execute(text("SELECT COUNT(*) FROM " + t)).scalar()
            print("%-18s %d lignes" % (t, n))
    print("charge en %.1f s" % (time.time() - t0))


if __name__ == "__main__":
    main()
