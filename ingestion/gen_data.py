"""Genere un jeu de donnees synthetique au format PaySim.

Le vrai dataset Kaggle (ealaxi/paysim1) n'est pas telechargeable ici, donc on
simule la meme structure : step, type, amount, nameOrig, oldbalanceOrg, ...
On cree aussi un petit reseau de "mules" pour avoir des hubs de fraude visibles
dans Gephi (plusieurs comptes frauduleux qui vident leur argent vers les memes
comptes destinataires).

Usage : python ingestion/gen_data.py --n 100000 --out data/paysim_synth.csv
"""
import argparse
import csv
import os
import random

random.seed(42)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=100000)
    p.add_argument("--out", default="data/paysim_synth.csv")
    args = p.parse_args()

    os.makedirs(os.path.dirname(args.out), exist_ok=True)

    clients = ["C%07d" % i for i in range(1, 8001)]
    marchands = ["M%06d" % i for i in range(1, 501)]
    mules = ["C9%06d" % i for i in range(1, 11)]   # 10 comptes mules

    # solde de depart de chaque client
    soldes = {c: random.uniform(0, 80000) for c in clients}

    types_normaux = ["PAYMENT", "CASH_IN", "CASH_OUT", "TRANSFER", "DEBIT"]
    poids = [0.38, 0.22, 0.28, 0.08, 0.04]

    with open(args.out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["step", "type", "amount", "nameOrig", "oldbalanceOrg",
                    "newbalanceOrig", "nameDest", "oldbalanceDest",
                    "newbalanceDest", "isFraud", "isFlaggedFraud"])
        for i in range(args.n):
            step = 1 + (i * 720) // args.n          # 720 h = 30 jours
            fraude = 0

            # ~1,2% de fraudes : on vide le compte via TRANSFER puis CASH_OUT
            if random.random() < 0.012:
                orig = random.choice(clients)
                old = soldes[orig]
                if old < 500:
                    old = random.uniform(2000, 300000)
                montant = old                          # compte vide
                typ = random.choice(["TRANSFER", "CASH_OUT"])
                dest = random.choice(mules) if random.random() < 0.7 else random.choice(clients)
                new = 0.0
                old_d = random.uniform(0, 20000)
                new_d = old_d + (montant if typ == "TRANSFER" else 0)
                fraude = 1
            else:
                typ = random.choices(types_normaux, poids)[0]
                orig = random.choice(clients)
                old = soldes[orig]
                montant = min(abs(random.lognormvariate(8.5, 1.2)), 400000)
                if typ == "CASH_IN":
                    new = old + montant
                else:
                    montant = min(montant, old) if old > 0 else 0.0
                    new = old - montant
                dest = random.choice(marchands) if typ in ("PAYMENT", "DEBIT") else random.choice(clients)
                old_d = 0.0 if dest.startswith("M") else random.uniform(0, 50000)
                new_d = 0.0 if dest.startswith("M") else old_d + montant
                soldes[orig] = max(new, 0.0)

            flag = 1 if (typ == "TRANSFER" and montant > 200000) else 0
            w.writerow([step, typ, round(montant, 2), orig, round(old, 2),
                        round(new, 2), dest, round(old_d, 2), round(new_d, 2),
                        fraude, flag])

    print("ecrit :", args.out, "-", args.n, "lignes")


if __name__ == "__main__":
    main()
