"""Test de resilience (local) : reprise du streaming sur checkpoint, sans perte ni doublon.

1. 1er passage : le job traite seulement 10 fichiers sur 20 (50 000 messages)
2. "panne" : le job s'arrete ; les 10 autres fichiers arrivent pendant ce temps
3. 2eme passage : relance avec le MEME checkpoint -> il ne doit traiter que les 10 nouveaux fichiers
Verification : 100 000 lignes au total, 100 000 transaction_id distincts.

Equivalent sur le cluster : voir resilience_cluster.sh (arret/relance d'un conteneur).
"""
import glob
import os
import shutil
import subprocess
import sys

import pandas as pd

BASE = "out_resilience"
shutil.rmtree(BASE, ignore_errors=True)
os.makedirs(BASE + "/in")
fichiers = sorted(glob.glob("data/json_in/batch_*.json"))
moitie = len(fichiers) // 2


def lancer():
    subprocess.run([sys.executable, "spark_jobs/streaming_to_hdfs.py", "--source", "files", "--input", BASE + "/in",
                    "--once", "--master", "local[2]", "--parquet", BASE + "/parquet",
                    "--checkpoint", BASE + "/ckpt"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)


def compter():
    d = pd.read_parquet(BASE + "/parquet")
    return len(d), d["transaction_id"].nunique()


for f in fichiers[:moitie]:
    shutil.copy(f, BASE + "/in")
lancer()
n1, d1 = compter()
print("passage 1 : %d lignes (%d ids distincts)" % (n1, d1))

for f in fichiers[moitie:]:          # pendant la "panne", de nouveaux messages arrivent
    shutil.copy(f, BASE + "/in")
lancer()                              # relance avec le meme checkpoint
n2, d2 = compter()
print("passage 2 : %d lignes (%d ids distincts)" % (n2, d2))

ok = (n1 == 50000 and n2 == 100000 and d2 == 100000)
print("RESULTAT :", "OK - reprise sans perte ni doublon" if ok else "ECHEC")
shutil.rmtree(BASE, ignore_errors=True)
sys.exit(0 if ok else 1)
