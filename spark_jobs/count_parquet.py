"""Compte les lignes et les transaction_id distincts du Parquet (verification d'absence de doublons).
Usage : spark-submit spark_jobs/count_parquet.py  (ou python count_parquet.py chemin_local)"""
import sys

from pyspark.sql import SparkSession
from pyspark.sql.functions import countDistinct

import config

chemin = sys.argv[1] if len(sys.argv) > 1 else config.PARQUET_PATH
spark = SparkSession.builder.appName("count_parquet").getOrCreate()
spark.sparkContext.setLogLevel("ERROR")
df = spark.read.parquet(chemin)
n = df.count()
d = df.agg(countDistinct("transaction_id")).collect()[0][0]
print("lignes=%d ids_distincts=%d doublons=%d" % (n, d, n - d))
