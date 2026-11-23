# Image Spark officielle + libs python utiles pour les scripts du projet
FROM apache/spark:3.5.0

USER root
RUN pip install --no-cache-dir pandas pyarrow numpy requests kafka-python pymongo
