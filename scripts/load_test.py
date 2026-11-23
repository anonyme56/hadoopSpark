"""Test de charge de l'API : N clients en parallele pendant D secondes.
Mesure debit (req/s), latences p50/p95/p99 et taux d'erreur.

Usage : python scripts/load_test.py --url http://localhost:8000 --key cle-lecteur --clients 1 10 50 --duree 10
(penser a lancer l'API avec API_QUOTA=1000000, sinon le quota par minute bloque le test)
"""
import argparse
import random
import statistics
import threading
import time

import requests


def worker(url, key, fin, latences, erreurs, ids):
    s = requests.Session()
    while time.time() < fin:
        tid = random.choice(ids)
        t0 = time.perf_counter()
        try:
            r = s.get("%s/transactions/%d" % (url, tid), headers={"X-API-Key": key}, timeout=10)
            ok = r.status_code == 200
        except requests.RequestException:
            ok = False
        latences.append((time.perf_counter() - t0) * 1000)
        if not ok:
            erreurs.append(1)


def pct(v, p):
    return v[min(len(v) - 1, int(len(v) * p / 100))]


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--url", default="http://localhost:8000")
    a.add_argument("--key", default="cle-lecteur")
    a.add_argument("--clients", type=int, nargs="+", default=[1, 10, 50])
    a.add_argument("--duree", type=int, default=10)
    a.add_argument("--max-id", type=int, default=100000)
    a.add_argument("--out", default="results/08_load_test.txt")
    args = a.parse_args()

    ids = list(range(1, args.max_id + 1))
    lignes = ["%-9s %-10s %-9s %-9s %-9s %-8s" % ("clients", "req/s", "p50 ms", "p95 ms", "p99 ms", "erreurs")]
    for n in args.clients:
        lat, err = [], []
        fin = time.time() + args.duree
        th = [threading.Thread(target=worker, args=(args.url, args.key, fin, lat, err, ids)) for _ in range(n)]
        [t.start() for t in th]
        [t.join() for t in th]
        lat.sort()
        lignes.append("%-9d %-10.0f %-9.1f %-9.1f %-9.1f %d/%d" % (
            n, len(lat) / args.duree, statistics.median(lat), pct(lat, 95), pct(lat, 99), len(err), len(lat)))
        print(lignes[-1])
    with open(args.out, "w") as f:
        f.write("\n".join(lignes) + "\n")
    print("\n".join(lignes))


if __name__ == "__main__":
    main()
