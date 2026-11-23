"""PARTIE 3 - Modelisation : prediction de la fraude (is_fraud) avec Spark MLlib.

- feature engineering (ecart a la moyenne du compte, frequence horaire, erreurs de solde...)
- comparaison Regression Logistique vs Random Forest
- evaluation : AUC (ROC et PR), matrice de confusion, rappel, precision
- sauvegarde du meilleur modele (PipelineModel) pour la partie 4

Cluster : spark-submit spark_jobs/train_fraud.py
Local   : python spark_jobs/train_fraud.py --parquet out_lake/transactions_parquet --model out_model --master "local[2]"
"""
import argparse
import json
import os
import time

from pyspark.ml import Pipeline
from pyspark.ml.classification import LogisticRegression, RandomForestClassifier
from pyspark.ml.evaluation import BinaryClassificationEvaluator
from pyspark.ml.feature import StringIndexer, OneHotEncoder, VectorAssembler
from pyspark.sql import SparkSession, Window
from pyspark.sql.functions import col, avg, count, when, hour, date_trunc, lit, log1p

import config


def ajouter_features(df):
    """Creation des variables explicatives."""
    # variables de solde : dans une fraude le compte est vide apres l'operation
    df = df.withColumn("erreur_solde_orig", col("oldbalance_org") - col("amount") - col("newbalance_org"))
    df = df.withColumn("erreur_solde_dest", col("oldbalance_dest") + col("amount") - col("newbalance_dest"))
    df = df.withColumn("compte_vide", when((col("oldbalance_org") > 0) & (col("newbalance_org") == 0), 1).otherwise(0))
    df = df.withColumn("ratio_montant_solde", col("amount") / (col("oldbalance_org") + 1))
    df = df.withColumn("log_montant", log1p(col("amount")))

    # ecart a la moyenne des transactions du compte emetteur
    w_compte = Window.partitionBy("sender_id")
    df = df.withColumn("moyenne_compte", avg("amount").over(w_compte))
    df = df.withColumn("ecart_moyenne", col("amount") - col("moyenne_compte"))

    # frequence horaire : nb de transactions du compte dans la meme heure
    df = df.withColumn("heure_bloc", date_trunc("hour", col("ts")))
    w_heure = Window.partitionBy("sender_id", "heure_bloc")
    df = df.withColumn("freq_horaire", count("*").over(w_heure))
    df = df.withColumn("heure", hour(col("ts")))
    return df


def mesures(pred, nom):
    """AUC + matrice de confusion + rappel/precision."""
    roc = BinaryClassificationEvaluator(labelCol="label", metricName="areaUnderROC").evaluate(pred)
    pr = BinaryClassificationEvaluator(labelCol="label", metricName="areaUnderPR").evaluate(pred)
    lignes = pred.groupBy("label", "prediction").count().collect()
    m = {(int(r["label"]), int(r["prediction"])): r["count"] for r in lignes}
    tp, fn = m.get((1, 1), 0), m.get((1, 0), 0)
    fp, tn = m.get((0, 1), 0), m.get((0, 0), 0)
    rappel = tp / (tp + fn) if tp + fn else 0.0
    precision = tp / (tp + fp) if tp + fp else 0.0
    f1 = 2 * precision * rappel / (precision + rappel) if precision + rappel else 0.0
    return {"modele": nom, "auc_roc": round(roc, 4), "auc_pr": round(pr, 4),
            "rappel": round(rappel, 4), "precision": round(precision, 4), "f1": round(f1, 4),
            "TP": tp, "FN": fn, "FP": fp, "TN": tn}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--parquet", default=config.PARQUET_PATH)
    p.add_argument("--model", default=config.MODEL_PATH)
    p.add_argument("--out", default="results")
    p.add_argument("--master", default=None)
    args = p.parse_args()
    os.makedirs(args.out, exist_ok=True)

    b = (SparkSession.builder.appName("tp_fraude_partie3")
         .config("spark.sql.shuffle.partitions", "8")
         .config("spark.ui.showConsoleProgress", "false"))
    if args.master:
        b = b.master(args.master)
    spark = b.getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")

    df = spark.read.parquet(args.parquet)
    df = ajouter_features(df).withColumn("label", col("is_fraud").cast("double"))

    # La partition "type" vient du nom de dossier Parquet : on la retrouve comme colonne
    train, test = df.randomSplit([0.8, 0.2], seed=42)
    nb_fraude = train.filter(col("label") == 1).count()
    nb_total = train.count()
    print("train : %d lignes dont %d fraudes (%.2f%%)" % (nb_total, nb_fraude, 100.0 * nb_fraude / nb_total))

    # classes tres desequilibrees -> poids pour les fraudes
    poids_fraude = (nb_total - nb_fraude) / float(nb_fraude)
    train = train.withColumn("poids", when(col("label") == 1, lit(poids_fraude)).otherwise(lit(1.0)))
    print("poids de la classe fraude : %.1f" % poids_fraude)

    # types deja filtres dans le streaming (5 valeurs) -> one-hot de taille 4 (dropLast)
    indexer = StringIndexer(inputCol="type", outputCol="type_idx")
    encoder = OneHotEncoder(inputCols=["type_idx"], outputCols=["type_vec"])
    colonnes = ["type_vec", "log_montant", "erreur_solde_orig", "erreur_solde_dest", "compte_vide",
                "ratio_montant_solde", "ecart_moyenne", "freq_horaire", "heure"]
    assembler = VectorAssembler(inputCols=colonnes, outputCol="features")

    lr = LogisticRegression(featuresCol="features", labelCol="label", weightCol="poids",
                            maxIter=50, regParam=0.01)
    rf = RandomForestClassifier(featuresCol="features", labelCol="label", weightCol="poids",
                                numTrees=60, maxDepth=8, seed=42)

    resultats, modeles = [], {}
    for nom, algo in [("Regression logistique", lr), ("Random Forest", rf)]:
        pipe = Pipeline(stages=[indexer, encoder, assembler, algo])
        t0 = time.time()
        modele = pipe.fit(train)
        duree = time.time() - t0
        pred = modele.transform(test)
        r = mesures(pred, nom)
        r["temps_entrainement_s"] = round(duree, 1)
        resultats.append(r)
        modeles[nom] = modele
        print(json.dumps(r, ensure_ascii=False))

    # importance des variables du Random Forest
    rf_model = modeles["Random Forest"].stages[-1]
    # noms des 4 colonnes one-hot : labels appris par l'indexer (le dernier est la categorie de reference)
    labels_type = modeles["Random Forest"].stages[0].labels
    noms_features = ["type=" + l for l in labels_type[:-1]] + colonnes[1:]
    assert len(noms_features) == len(rf_model.featureImportances), "noms de features desalignes"
    imp = sorted(zip(noms_features, rf_model.featureImportances.toArray()), key=lambda x: -x[1])
    print("importance des variables (RF) :")
    for n, v in imp[:6]:
        print("  %-22s %.3f" % (n, v))

    # on garde le modele avec le meilleur rappel (critique en fraude), puis l'AUC
    meilleur = max(resultats, key=lambda r: (r["rappel"], r["auc_roc"]))
    print("modele retenu :", meilleur["modele"])
    modeles[meilleur["modele"]].write().overwrite().save(args.model)
    print("modele sauvegarde dans", args.model)

    with open(os.path.join(args.out, "metriques_modeles.json"), "w") as f:
        json.dump({"resultats": resultats, "importance_rf": [(n, float(v)) for n, v in imp],
                   "modele_retenu": meilleur["modele"]}, f, indent=2, ensure_ascii=False)

    # echantillon de predictions pour la partie 4 (alertes)
    pred_rf = modeles[meilleur["modele"]].transform(test)
    alertes = (pred_rf.filter(col("prediction") == 1)
               .select("transaction_id", "sender_id", "receiver_id", "type", "amount",
                       "oldbalance_org", "newbalance_org", "erreur_solde_orig",
                       "ratio_montant_solde", "freq_horaire", "ecart_moyenne", "label")
               .limit(200))
    alertes.toPandas().to_csv(os.path.join(args.out, "alertes_fraude.csv"), index=False)
    print("alertes ecrites :", os.path.join(args.out, "alertes_fraude.csv"))


if __name__ == "__main__":
    main()
