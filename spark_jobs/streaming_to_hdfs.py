"""PARTIE 1 - Spark Structured Streaming : Kafka -> nettoyage -> HDFS (Parquet) + metriques.

Deux requetes de streaming tournent en parallele :
  1. ecriture des transactions nettoyees en Parquet dans le Data Lake HDFS
  2. metriques temps reel : volume de transactions par minute et montant total par type

Mode normal (cluster docker) :
    spark-submit --master spark://spark-master:7077 \
        --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 spark_jobs/streaming_to_hdfs.py
Mode test local sans Kafka (lit des fichiers JSON deposes dans un dossier) :
    python spark_jobs/streaming_to_hdfs.py --source files --input data/json_in --once
"""
import argparse

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json, to_timestamp, window, count, sum as sum_, round as round_
from pyspark.sql.types import (StructType, StructField, StringType, IntegerType,
                               LongType, DoubleType)

import config

# Schema impose (pas de inferSchema : plus rapide et plus sur, cf. cours chap. 3)
SCHEMA = StructType([
    StructField("transaction_id", LongType(), True),
    StructField("sender_id", StringType(), True),
    StructField("receiver_id", StringType(), True),
    StructField("amount", DoubleType(), True),
    StructField("type", StringType(), True),
    StructField("oldbalance_org", DoubleType(), True),
    StructField("newbalance_org", DoubleType(), True),
    StructField("oldbalance_dest", DoubleType(), True),
    StructField("newbalance_dest", DoubleType(), True),
    StructField("is_fraud", IntegerType(), True),
    StructField("timestamp", StringType(), True),
])

TYPES_VALIDES = ["PAYMENT", "CASH_IN", "CASH_OUT", "TRANSFER", "DEBIT"]


def lire_flux(spark, args):
    """Retourne le DataFrame brut (colonne 'json' en texte)."""
    if args.source == "kafka":
        brut = (spark.readStream.format("kafka")
                .option("kafka.bootstrap.servers", config.KAFKA_SERVERS)
                .option("subscribe", config.KAFKA_TOPIC)
                .option("startingOffsets", "earliest")
                .load())
        # la valeur Kafka est binaire -> on la caste en string
        return brut.selectExpr("CAST(value AS STRING) AS json")
    # mode test : fichiers JSON (un objet par ligne)
    fichiers = (spark.readStream.schema("value STRING")
                .option("maxFilesPerTrigger", 2)
                .text(args.input))
    return fichiers.withColumnRenamed("value", "json")


def nettoyer(brut):
    """Typage + nettoyage a la volee."""
    df = brut.select(from_json(col("json"), SCHEMA).alias("t")).select("t.*")
    df = df.withColumn("ts", to_timestamp(col("timestamp")))
    df = (df.dropna(subset=["transaction_id", "sender_id", "receiver_id", "amount", "type", "ts"])
            .filter(col("amount") >= 0)
            .filter(col("type").isin(TYPES_VALIDES))
            .drop("timestamp"))
    return df


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--source", choices=["kafka", "files"], default="kafka")
    p.add_argument("--input", default="data/json_in")
    p.add_argument("--parquet", default=config.PARQUET_PATH)
    p.add_argument("--checkpoint", default=config.CHECKPOINT_PATH)
    p.add_argument("--once", action="store_true", help="traite ce qui est dispo puis s'arrete")
    p.add_argument("--master", default=None)
    args = p.parse_args()

    builder = (SparkSession.builder.appName("tp_fraude_partie1")
               # peu de donnees -> 200 partitions de shuffle (defaut) c'est trop
               .config("spark.sql.shuffle.partitions", "8")
               .config("spark.ui.showConsoleProgress", "false"))
    if args.master:
        builder = builder.master(args.master)
    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel("WARN")

    df = nettoyer(lire_flux(spark, args))

    trigger = {"availableNow": True} if args.once else {"processingTime": "10 seconds"}

    # --- requete 1 : stockage Parquet dans HDFS (data lake) ---
    q_parquet = (df.writeStream
                 .format("parquet")
                 .option("path", args.parquet)
                 .option("checkpointLocation", args.checkpoint + "/parquet")
                 .partitionBy("type")          # partition par type : lectures colonnes + filtre rapide
                 .outputMode("append")
                 .trigger(**trigger)
                 .start())

    # --- requete 2 : metriques temps reel ---
    # watermark 2 min : on tolere les messages en retard, puis Spark libere l'etat
    metriques = (df.withWatermark("ts", "2 minutes")
                 .groupBy(window(col("ts"), "1 minute"), col("type"))
                 .agg(count("*").alias("nb_transactions"),
                      round_(sum_("amount"), 2).alias("montant_total")))

    def afficher(batch_df, batch_id):
        n = batch_df.count()
        print("--- micro-batch %d : %d lignes de metriques ---" % (batch_id, n))
        (batch_df.select(col("window.start").alias("debut"), "type",
                         "nb_transactions", "montant_total")
         .orderBy("debut", "type").show(12, truncate=False))

    q_metrics = (metriques.writeStream
                 .outputMode("update")
                 .foreachBatch(afficher)
                 .option("checkpointLocation", args.checkpoint + "/metrics")
                 .trigger(**trigger)
                 .start())

    if args.once:
        # on attend la fin des DEUX requetes avant de quitter
        q_parquet.awaitTermination()
        q_metrics.awaitTermination()
    else:
        spark.streams.awaitAnyTermination()


if __name__ == "__main__":
    main()
