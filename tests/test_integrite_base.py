"""Controle d'integrite de la base relationnelle chargee (C1.1 critere C3/C4).
Ignore si fraude.db n'existe pas (lancer load_relational.py avant)."""
import os

import pytest
from sqlalchemy import create_engine, text

DB = os.path.join(os.path.dirname(__file__), "..", "fraude.db")
pytestmark = pytest.mark.skipif(not os.path.exists(DB), reason="fraude.db absente")


@pytest.fixture(scope="module")
def conn():
    with create_engine("sqlite:///" + DB).connect() as c:
        yield c


def un(conn, sql):
    return conn.execute(text(sql)).scalar()


def test_pas_de_transaction_orpheline_emetteur(conn):
    assert un(conn, "SELECT COUNT(*) FROM transactions t LEFT JOIN accounts a ON a.account_id=t.sender_id "
                    "WHERE a.account_id IS NULL") == 0


def test_pas_de_transaction_orpheline_destinataire(conn):
    assert un(conn, "SELECT COUNT(*) FROM transactions t LEFT JOIN accounts a ON a.account_id=t.receiver_id "
                    "WHERE a.account_id IS NULL") == 0


def test_types_references(conn):
    assert un(conn, "SELECT COUNT(*) FROM transactions t LEFT JOIN transaction_types y ON y.type_id=t.type_id "
                    "WHERE y.type_id IS NULL") == 0


def test_montants_positifs(conn):
    assert un(conn, "SELECT COUNT(*) FROM transactions WHERE amount < 0") == 0


def test_alertes_reference_des_transactions(conn):
    assert un(conn, "SELECT COUNT(*) FROM fraud_alerts a LEFT JOIN transactions t "
                    "ON t.transaction_id=a.transaction_id WHERE t.transaction_id IS NULL") == 0


def test_pas_de_doublon_de_transaction(conn):
    assert un(conn, "SELECT COUNT(*) - COUNT(DISTINCT transaction_id) FROM transactions") == 0
