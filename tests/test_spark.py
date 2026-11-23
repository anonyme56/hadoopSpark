"""Tests Spark (session locale) : nettoyage du flux et features du modele."""
import json

import pytest
from pyspark.sql import SparkSession

from streaming_to_hdfs import nettoyer
from train_fraud import ajouter_features


@pytest.fixture(scope="module")
def spark():
    s = (SparkSession.builder.master("local[1]").appName("tests")
         .config("spark.ui.enabled", "false").config("spark.sql.shuffle.partitions", "2").getOrCreate())
    s.sparkContext.setLogLevel("ERROR")
    yield s
    s.stop()


def ligne(**kw):
    base = {"transaction_id": 1, "sender_id": "C1", "receiver_id": "C2", "amount": 100.0, "type": "TRANSFER",
            "oldbalance_org": 100.0, "newbalance_org": 0.0, "oldbalance_dest": 0.0,
            "newbalance_dest": 100.0, "is_fraud": 0, "timestamp": "2026-11-16T10:00:00+00:00"}
    base.update(kw)
    return json.dumps(base)


def test_nettoyage_garde_seulement_les_lignes_valides(spark):
    lignes = [ligne(),                                   # ok
              ligne(transaction_id=2, amount=-5.0),      # montant negatif
              ligne(transaction_id=3, type="VIREMENT"),  # type inconnu
              ligne(transaction_id=4, sender_id=None),   # valeur manquante
              ligne(transaction_id=5, timestamp="pas une date"),
              "{ceci n'est pas du json"]                 # message corrompu
    df = spark.createDataFrame([(l,) for l in lignes], ["json"])
    res = nettoyer(df).collect()
    assert [r["transaction_id"] for r in res] == [1]


def test_nettoyage_type_des_colonnes(spark):
    df = spark.createDataFrame([(ligne(),)], ["json"])
    types = dict(nettoyer(df).dtypes)
    assert types["amount"] == "double" and types["ts"] == "timestamp"


def test_features_compte_vide_et_ratio(spark):
    df = spark.createDataFrame([(ligne(),)], ["json"])
    f = ajouter_features(nettoyer(df)).collect()[0]
    assert f["compte_vide"] == 1
    assert abs(f["ratio_montant_solde"] - 100.0 / 101.0) < 1e-9
    assert f["erreur_solde_orig"] == 0.0


def test_features_frequence_horaire(spark):
    lignes = [ligne(transaction_id=i, timestamp="2026-11-16T10:%02d:00+00:00" % (i * 5)) for i in range(1, 4)]
    lignes.append(ligne(transaction_id=9, timestamp="2026-11-16T12:00:00+00:00"))
    df = spark.createDataFrame([(l,) for l in lignes], ["json"])
    f = {r["transaction_id"]: r["freq_horaire"] for r in ajouter_features(nettoyer(df)).collect()}
    assert f[1] == f[2] == f[3] == 3 and f[9] == 1
