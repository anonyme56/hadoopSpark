"""PARTIE 2 - Pipeline HDFS (Parquet) -> Data Lab NoSQL (MongoDB), modele graphe.

On transforme les transactions en :
  - Nodes : un document par compte (nb envois/receptions, montants, nb de fraudes)
  - Edges : un document par couple (emetteur -> destinataire) agrege

Cluster :
    spark-submit --packages org.mongodb.spark:mongo-spark-connector_2.12:10.3.0 spark_jobs/hdfs_to_mongo.py
Test local sans Mongo (ecrit en JSON dans un dossier) :
    python spark_jobs/hdfs_to_mongo.py --parquet out_lake/transactions_parquet --sink json --out out_graph
"""
import argparse

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, count, sum as sum_, round as round_, when, lit

import config


def ecrire(df, nom, args):
    if args.sink == "mongo":
        (df.write.format("mongodb")
           .mode("overwrite")
           .option("connection.uri", config.MONGO_URI)
           .option("database", config.MONGO_DB)
           .option("collection", nom)
           .save())
    else:
        df.coalesce(1).write.mode("overwrite").json(args.out + "/" + nom)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--parquet", default=config.PARQUET_PATH)
    p.add_argument("--sink", choices=["mongo", "json"], default="mongo")
    p.add_argument("--out", default="out_graph")
    p.add_argument("--master", default=None)
    args = p.parse_args()

    b = (SparkSession.builder.appName("tp_fraude_partie2")
         .config("spark.sql.shuffle.partitions", "8")
         .config("spark.ui.showConsoleProgress", "false"))
    if args.master:
        b = b.master(args.master)
    spark = b.getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")

    tx = spark.read.parquet(args.parquet)
    print("transactions lues dans le data lake :", tx.count())

    # ---- EDGES : un arc par couple emetteur -> destinataire ----
    edges = (tx.groupBy("sender_id", "receiver_id")
               .agg(count("*").alias("nb_tx"),
                    round_(sum_("amount"), 2).alias("montant_total"),
                    sum_("is_fraud").alias("nb_fraudes"))
               .withColumnRenamed("sender_id", "source")
               .withColumnRenamed("receiver_id", "target"))

    # ---- NODES : un noeud par compte ----
    sortant = (tx.groupBy(col("sender_id").alias("id"))
                 .agg(count("*").alias("nb_envois"),
                      round_(sum_("amount"), 2).alias("total_envoye"),
                      sum_("is_fraud").alias("fraudes_emises")))
    entrant = (tx.groupBy(col("receiver_id").alias("id"))
                 .agg(count("*").alias("nb_receptions"),
                      round_(sum_("amount"), 2).alias("total_recu"),
                      sum_("is_fraud").alias("fraudes_recues")))
    nodes = (sortant.join(entrant, "id", "full_outer")
             .na.fill(0)
             .withColumn("type_compte", when(col("id").startswith("M"), lit("MARCHAND")).otherwise(lit("CLIENT"))))

    print("noeuds :", nodes.count(), "| arcs :", edges.count())
    print("arcs impliques dans au moins une fraude :", edges.filter(col("nb_fraudes") > 0).count())

    ecrire(nodes, "nodes", args)
    ecrire(edges, "edges", args)
    print("ecriture terminee (", args.sink, ")")


if __name__ == "__main__":
    main()
