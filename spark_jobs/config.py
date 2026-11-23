"""Parametres communs aux scripts.
Les valeurs par defaut correspondent au cluster docker-compose.
On peut les surcharger avec des variables d'environnement (utile pour tester en local)."""
import os

KAFKA_SERVERS = os.getenv("KAFKA_SERVERS", "kafka:29092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "transactions")

HDFS_BASE = os.getenv("HDFS_BASE", "hdfs://namenode:9000/data")
PARQUET_PATH = HDFS_BASE + "/transactions_parquet"
CHECKPOINT_PATH = HDFS_BASE + "/checkpoints/transactions"
MODEL_PATH = HDFS_BASE + "/models/fraud_rf"

MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongodb:27017")
MONGO_DB = "fraude"
