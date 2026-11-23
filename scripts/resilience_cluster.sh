#!/bin/bash
# Tests de resilience sur le cluster Docker (C1.4 critere C3) - A LANCER PAR VOUS, avec captures.
# Prerequis : docker-compose up -d --build ; spark_jobs/streaming_to_hdfs.py en cours d'execution (voir README).
set -u

echo "=== TEST 1 : panne de Kafka pendant le streaming ==="
python ingestion/producer.py --servers localhost:9092 --rate 200 --max 3000 &
PROD=$!
sleep 5
docker stop kafka                         # CAPTURE : docker ps (kafka absent)
sleep 15
docker start kafka
wait $PROD 2>/dev/null
sleep 30
echo "Lignes en Parquet apres reprise (a comparer au nombre envoye) :"
docker exec spark-master /opt/spark/bin/spark-submit /opt/spark/work-dir/spark_jobs/count_parquet.py 2>/dev/null | tail -1

echo "=== TEST 2 : arret/relance du job Spark (checkpoint) ==="
echo "1) Ctrl+C sur le job streaming   2) python ingestion/producer.py --max 2000   3) relancer le job"
echo "4) verifier : aucun doublon (voir count_parquet.py : lignes == ids distincts)"

echo "=== TEST 3 : arret du datanode HDFS ==="
docker stop datanode
sleep 10
docker exec namenode hdfs dfsadmin -report | head -20     # CAPTURE : 0 datanode vivant
docker start datanode
sleep 20
docker exec namenode hdfs dfsadmin -report | head -20     # CAPTURE : datanode revenu

echo "=== TEST 4 : redemarrage de MongoDB (volume persistant) ==="
docker restart mongodb
sleep 10
docker exec mongodb mongosh fraude --quiet --eval "db.nodes.countDocuments()"   # doit etre inchange
