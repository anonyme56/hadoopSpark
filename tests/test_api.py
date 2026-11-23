"""Tests de l'API : authentification, roles, quotas, erreurs, injection SQL."""
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db = tmp_path / "test.db"
    monkeypatch.setenv("DB_URL", "sqlite:///%s" % db)
    monkeypatch.setenv("API_KEYS", "lect:lecteur,adm:admin")

    eng = create_engine("sqlite:///%s" % db)
    schema = open(os.path.join(os.path.dirname(__file__), "..", "database", "schema.sql")).read()
    lignes = [l for l in schema.splitlines() if not l.strip().startswith("--")]
    with eng.begin() as c:
        for instr in "\n".join(lignes).split(";"):
            if instr.strip():
                c.execute(text(instr))
        c.execute(text("INSERT INTO transaction_types VALUES (1,'TRANSFER')"))
        c.execute(text("INSERT INTO accounts VALUES ('C1','CLIENT'),('C2','CLIENT')"))
        c.execute(text("INSERT INTO transactions VALUES (1,'C1','C2',1,500.0,500.0,0.0,0.0,500.0,1,'2026-11-16 10:00:00')"))
        c.execute(text("INSERT INTO fraud_alerts VALUES (1,1,'compte vide','A_VERIFIER')"))

    import fraud_api as api
    api._engine = None
    api._appels.clear()
    monkeypatch.setattr(api, "QUOTA_PAR_MINUTE", 5)
    return TestClient(api.app)


def test_sans_cle_401(client):
    assert client.get("/transactions/1").status_code == 401


def test_mauvaise_cle_401(client):
    assert client.get("/transactions/1", headers={"X-API-Key": "x"}).status_code == 401


def test_lecture_ok(client):
    r = client.get("/transactions/1", headers={"X-API-Key": "lect"})
    assert r.status_code == 200
    assert r.json()["type"] == "TRANSFER" and r.json()["amount"] == 500.0


def test_inconnu_404(client):
    assert client.get("/transactions/42", headers={"X-API-Key": "lect"}).status_code == 404


def test_lecteur_ne_peut_pas_modifier(client):
    r = client.patch("/alerts/1", json={"status": "CONFIRMEE"}, headers={"X-API-Key": "lect"})
    assert r.status_code == 403


def test_admin_peut_modifier(client):
    r = client.patch("/alerts/1", json={"status": "CONFIRMEE"}, headers={"X-API-Key": "adm"})
    assert r.status_code == 200
    r = client.get("/alerts?status=CONFIRMEE", headers={"X-API-Key": "lect"})
    assert len(r.json()) == 1


def test_statut_invalide_422(client):
    r = client.patch("/alerts/1", json={"status": "N_IMPORTE_QUOI"}, headers={"X-API-Key": "adm"})
    assert r.status_code == 422


def test_filtre_statut_invalide_422(client):
    assert client.get("/alerts?status=XXX", headers={"X-API-Key": "lect"}).status_code == 422


def test_quota_429_avec_retry_after(client):
    h = {"X-API-Key": "lect"}
    codes = [client.get("/transactions/1", headers=h).status_code for _ in range(7)]
    assert codes[:5] == [200] * 5
    assert codes[5] == 429
    r = client.get("/transactions/1", headers=h)
    assert "retry-after" in r.headers


def test_quota_par_cle(client):
    for _ in range(6):
        client.get("/transactions/1", headers={"X-API-Key": "lect"})
    # l'autre cle n'est pas impactee
    assert client.get("/transactions/1", headers={"X-API-Key": "adm"}).status_code == 200


def test_injection_sql_sans_effet(client):
    r = client.get("/accounts/C1' OR '1'='1/stats", headers={"X-API-Key": "lect"})
    assert r.status_code == 404
    # la table existe toujours
    assert client.get("/transactions/1", headers={"X-API-Key": "lect"}).status_code == 200


def test_health_public(client):
    assert client.get("/health").status_code == 200
