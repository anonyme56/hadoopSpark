"""Producteur Kafka : envoie des transactions JSON dans le topic 'transactions'.

Source : le CSV PaySim (ou la version synthetique generee par gen_data.py).
Chaque ligne devient un message JSON avec un timestamp d'envoi (event time).

Usage :
    python ingestion/producer.py --csv data/paysim_synth.csv --rate 50 --max 5000
(depuis l'hote : --servers localhost:9092 ; depuis un conteneur : kafka:29092)
"""
import argparse
import csv
import json
import time
from datetime import datetime, timezone

from kafka import KafkaProducer


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--csv", default="data/paysim_synth.csv")
    p.add_argument("--servers", default="localhost:9092")
    p.add_argument("--topic", default="transactions")
    p.add_argument("--rate", type=float, default=50, help="messages par seconde")
    p.add_argument("--max", type=int, default=5000)
    args = p.parse_args()

    producer = KafkaProducer(
        bootstrap_servers=args.servers,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    )

    delai = 1.0 / args.rate
    envoyes = 0
    with open(args.csv) as f:
        for row in csv.DictReader(f):
            msg = {
                "transaction_id": envoyes + 1,
                "sender_id": row["nameOrig"],
                "receiver_id": row["nameDest"],
                "amount": float(row["amount"]),
                "type": row["type"],
                "oldbalance_org": float(row["oldbalanceOrg"]),
                "newbalance_org": float(row["newbalanceOrig"]),
                "oldbalance_dest": float(row["oldbalanceDest"]),
                "newbalance_dest": float(row["newbalanceDest"]),
                "is_fraud": int(row["isFraud"]),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            producer.send(args.topic, msg)
            envoyes += 1
            if envoyes % 500 == 0:
                print(envoyes, "messages envoyes")
            if envoyes >= args.max:
                break
            time.sleep(delai)

    producer.flush()
    print("termine :", envoyes, "messages dans", args.topic)


if __name__ == "__main__":
    main()
