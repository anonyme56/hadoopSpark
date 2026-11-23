# Plateforme Big Data de détection de fraude (FinTech)

Projet Bloc 1 – Expert en ingénierie des données. Pipeline : **Kafka → Spark Streaming → HDFS (Parquet) → MongoDB → Gephi → Spark MLlib → agent IA**.

## Arborescence

```
fraud-platform/
├── docker-compose.yml, Dockerfile   cluster complet
├── ingestion/     gen_data.py, producer.py, make_json_batches.py   -> Kafka
├── spark_jobs/    config.py, streaming_to_hdfs.py, hdfs_to_mongo.py, train_fraud.py, count_parquet.py
├── graph/         export_gephi.py                                  -> Gephi
├── genai/         genai_agent.py                                   -> agent IA
├── database/      schema.sql, load_relational.py                   -> PostgreSQL
├── api/           fraud_api.py                                     -> API REST securisee
├── tests/         27 tests pytest
├── scripts/       tests de charge/resilience, generation des figures
├── docs/          rapport (.docx), diaporama (.pptx), DEMO.md, scripts de generation
├── results/       sorties reelles des executions (consoles, metriques, figures, gephi/)
└── data/          jeux de donnees (non versionne)
```

Toutes les commandes se lancent **depuis la racine du depot**.

## Contenu

| Fichier | Rôle |
|---|---|
| `docker-compose.yml`, `Dockerfile` | Cluster : Zookeeper, Kafka, Kafdrop, HDFS (namenode+datanode), Spark (master+worker), MongoDB, Mongo-Express |
| `spark_jobs/config.py` | Adresses (Kafka, HDFS, Mongo) communes aux scripts |
| `ingestion/gen_data.py` | Génère un jeu au format PaySim (si le CSV Kaggle n'est pas utilisé) |
| `ingestion/producer.py` | Producteur Kafka : envoie les transactions en JSON |
| `spark_jobs/streaming_to_hdfs.py` | **Partie 1** : Kafka → nettoyage/typage → Parquet HDFS + métriques par minute |
| `spark_jobs/hdfs_to_mongo.py` | **Partie 2** : HDFS → collections `nodes` / `edges` dans MongoDB |
| `graph/export_gephi.py` | **Partie 2** : export CSV/GEXF pour Gephi + analyse réseau |
| `spark_jobs/train_fraud.py` | **Partie 3** : MLlib, régression logistique vs Random Forest |
| `genai/genai_agent.py` | **Partie 4** : explication conseiller + email client (Ollama / OpenAI) |
| `ingestion/make_json_batches.py` | Outil de test local sans Kafka |

## Ajouts : base relationnelle, API, tests

| Fichier | Rôle |
|---|---|
| `database/schema.sql`, `database/load_relational.py` | Schéma PostgreSQL normalisé (3FN) + chargement depuis le data lake |
| `api/fraud_api.py` | API FastAPI : clé `X-API-Key`, rôles lecteur/admin, quota 60 req/min, doc sur `/docs` |
| `tests/` | 27 tests pytest (Spark, API, agent, intégrité base) : `python -m pytest tests -q` |
| `scripts/load_test.py` | Test de charge de l'API (1/10/50 clients) |
| `scripts/resilience_checkpoint_test.py` | Reprise du streaming sur checkpoint (local) |
| `scripts/resilience_cluster.sh`, `spark_jobs/count_parquet.py` | Scénarios de panne sur le cluster Docker (à lancer et capturer) |
| `docs/` (rapport, diaporama, `DEMO.md`, scripts de génération) | Diaporama et déroulé de la démo |

## Lancement sur le cluster Docker

```bash
docker-compose up -d --build
docker ps                                   # CAPTURE 1 : tous les conteneurs "Up"

# Données : PaySim Kaggle dans data/ ou version synthétique
python ingestion/gen_data.py --n 100000 --out data/paysim_synth.csv

# Dossier HDFS
docker exec namenode hdfs dfs -mkdir -p /data

# Topic Kafka
docker exec kafka kafka-topics --bootstrap-server kafka:29092 --create --topic transactions --partitions 1 --replication-factor 1

# Partie 1 : streaming (laisser tourner)
docker exec -it spark-master /opt/spark/bin/spark-submit --master spark://spark-master:7077 \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 \
  /opt/spark/work-dir/spark_jobs/streaming_to_hdfs.py

# Dans un autre terminal : producteur (depuis l'hôte)
pip install kafka-python
python ingestion/producer.py --csv data/paysim_synth.csv --servers localhost:9092 --rate 100 --max 20000

docker exec namenode hdfs dfs -ls -R /data/transactions_parquet | head     # CAPTURE 2

# Partie 2 : HDFS -> Mongo
docker exec -it spark-master /opt/spark/bin/spark-submit --master spark://spark-master:7077 \
  --packages org.mongodb.spark:mongo-spark-connector_2.12:10.3.0 \
  /opt/spark/work-dir/spark_jobs/hdfs_to_mongo.py
pip install pymongo networkx matplotlib pandas
python graph/export_gephi.py --source mongo --mongo mongodb://localhost:27017   # puis ouvrir results/gephi/graphe_fraude.gexf dans Gephi

# Partie 3 : entraînement
docker exec -it spark-master /opt/spark/bin/spark-submit --master spark://spark-master:7077 \
  /opt/spark/work-dir/spark_jobs/train_fraud.py

# Base relationnelle : chargement PostgreSQL depuis le data lake + les alertes du modèle
pip install sqlalchemy psycopg2-binary
python database/load_relational.py --db postgresql+psycopg2://fraude:fraude@localhost:5432/fraude \
   --parquet out_lake/transactions_parquet      # ou lire depuis HDFS puis copier en local
docker exec -it postgres psql -U fraude -c "\dt"          # CAPTURE

# API (déjà démarrée par docker-compose sur :8000) - changer les clés !
export API_KEYS="cle-lecteur:lecteur,cle-admin:admin"
curl -i localhost:8000/transactions/1                                   # 401
curl -i -H "X-API-Key: cle-lecteur" localhost:8000/transactions/49121   # 200
curl -i -X PATCH -H "X-API-Key: cle-lecteur" -H "Content-Type: application/json" \
     -d '{"status":"CONFIRMEE"}' localhost:8000/alerts/1                # 403
curl -i -X PATCH -H "X-API-Key: cle-admin" -H "Content-Type: application/json" \
     -d '{"status":"CONFIRMEE"}' localhost:8000/alerts/1                # 200

# charge (lancer l'API avec API_QUOTA=100000000 pour ne pas être bloqué par le quota)
python scripts/load_test.py --clients 1 10 50 --duree 10

# Partie 4 : agent (Ollama local ou OpenAI)
python genai/genai_agent.py --alertes results/alertes_fraude.csv --provider ollama --modele llama3 --n 3
```

## Test local sans Docker (ce qui a servi à produire `results/`)

```bash
pip install pyspark==3.5.1 pyarrow pandas networkx matplotlib requests
python ingestion/gen_data.py --n 100000 --out data/paysim_synth.csv
python ingestion/make_json_batches.py data/paysim_synth.csv data/json_in
python spark_jobs/streaming_to_hdfs.py --source files --input data/json_in --once --master "local[2]" \
   --parquet out_lake/transactions_parquet --checkpoint out_lake/checkpoints
python spark_jobs/hdfs_to_mongo.py --parquet out_lake/transactions_parquet --sink json --out out_graph --master "local[2]"
python graph/export_gephi.py --source json --dir out_graph --out gephi
python spark_jobs/train_fraud.py --parquet out_lake/transactions_parquet --model out_model --master "local[2]"
python scripts/make_figures.py
python genai/genai_agent.py --provider template --n 2
```

## Captures d'écran à faire pour le rapport (cluster Docker)

1. `docker ps` : tous les services démarrés
2. Spark Master UI `http://localhost:8080` : 1 worker, application en cours
3. Kafdrop `http://localhost:9000` : topic `transactions` avec des messages
4. Spark UI `http://localhost:4040` : onglet *Structured Streaming*
5. HDFS UI `http://localhost:9870` → Utilities → Browse : `/data/transactions_parquet/type=...`
6. Mongo-Express `http://localhost:8082` : base `fraude`, collections `nodes` et `edges`
7. Gephi : graphe après *Layout ForceAtlas 2*, taille = degré entrant, couleur = classe de modularité, avec les statistiques (Degré moyen, Modularité) lancées
8. Terminal : sortie de `spark_jobs/train_fraud.py` (AUC, rappel) et de `genai_agent.py` (email généré par le LLM)
9. PostgreSQL : `\dt` et `SELECT COUNT(*)` sur les 4 tables
10. API : `/docs` dans le navigateur + curl 401 / 200 / 403 / 429
11. `pytest` : les 27 tests en vert
12. Résilience : `resilience_cluster.sh` (docker ps avec kafka arrêté, `hdfs dfsadmin -report`, `count_parquet.py`)

## Limites connues

- Le dataset utilisé dans `results/` est **synthétique** (PaySim Kaggle non téléchargeable depuis l'environnement de développement). Les fraudes y suivent un schéma simple (compte vidé), donc les scores sont plus élevés que sur le vrai PaySim.
- Le mode `template` de l'agent n'appelle aucun LLM : à relancer avec `--provider ollama` ou `openai` pour la démo.
- Le fichier `docker-compose.yml` n'a pas pu être exécuté dans l'environnement de développement (pas de démon Docker). Les services `postgres` et `api` n'ont donc jamais tourné en conteneur.
- La base relationnelle, l'API, les tests et le test de charge ont été exécutés sur **SQLite** (SQL portable via SQLAlchemy), pas sur PostgreSQL. Les chiffres de charge sont des ordres de grandeur sur une machine à 2 cœurs.
- Le mode Kafka de `streaming_to_hdfs.py` et l'écriture MongoDB de `hdfs_to_mongo.py` n'ont pas été exécutés (seulement la logique Spark via fichiers JSON / sortie JSON).
- Mots de passe PostgreSQL et clés d'API du compose = valeurs de démonstration.
