"""API REST de consultation des transactions et des alertes de fraude (competence C2.1).

- Authentification par cle d'API (en-tete X-API-Key), cles lues dans la variable d'environnement
  API_KEYS au format "cle1:lecteur,cle2:admin"
- Roles : lecteur (GET) / admin (GET + modification du statut d'une alerte)
- Quotas : 60 requetes par minute et par cle (HTTP 429 + en-tete Retry-After)
- Requetes SQL parametrees (pas de concatenation -> pas d'injection SQL)
- Documentation automatique : /docs (OpenAPI)

Lancement : DB_URL=postgresql+psycopg2://fraude:fraude@postgres:5432/fraude \
            API_KEYS="cle-lecteur:lecteur,cle-admin:admin" uvicorn --app-dir api fraud_api:app --host 0.0.0.0 --port 8000
"""
import hmac
import os
import time
from collections import defaultdict, deque
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import create_engine, text

QUOTA_PAR_MINUTE = int(os.getenv("API_QUOTA", "60"))

app = FastAPI(title="Hexa-Bank - API fraude", version="1.0")

_engine = None
_appels = defaultdict(deque)   # cle -> horodatages des appels recents


def engine():
    global _engine
    if _engine is None:
        _engine = create_engine(os.getenv("DB_URL", "sqlite:///fraude.db"))
    return _engine


def cles_autorisees():
    """Relu a chaque appel pour pouvoir changer les cles sans code (et pour les tests)."""
    res = {}
    for item in os.getenv("API_KEYS", "").split(","):
        if ":" in item:
            cle, role = item.split(":", 1)
            res[cle.strip()] = role.strip()
    return res


def authentifier(response: Response, x_api_key: Optional[str] = Header(default=None)):
    """Verifie la cle, applique le quota, renvoie le role."""
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Cle d'API manquante (en-tete X-API-Key)")
    role = None
    for cle, r in cles_autorisees().items():
        if hmac.compare_digest(cle, x_api_key):     # comparaison a temps constant
            role = r
    if role is None:
        raise HTTPException(status_code=401, detail="Cle d'API invalide")

    maintenant = time.time()
    fenetre = _appels[x_api_key]
    while fenetre and maintenant - fenetre[0] > 60:
        fenetre.popleft()
    if len(fenetre) >= QUOTA_PAR_MINUTE:
        attente = int(60 - (maintenant - fenetre[0])) + 1
        raise HTTPException(status_code=429, detail="Quota depasse",
                            headers={"Retry-After": str(attente)})
    fenetre.append(maintenant)
    response.headers["X-RateLimit-Remaining"] = str(QUOTA_PAR_MINUTE - len(fenetre))
    return role


def exiger_admin(role: str = Depends(authentifier)):
    if role != "admin":
        raise HTTPException(status_code=403, detail="Droits insuffisants (role admin requis)")
    return role


@app.get("/health")
def health():
    with engine().connect() as c:
        c.execute(text("SELECT 1"))
    return {"status": "ok"}


@app.get("/transactions/{transaction_id}")
def lire_transaction(transaction_id: int, role: str = Depends(authentifier)):
    with engine().connect() as c:
        r = c.execute(text(
            "SELECT t.transaction_id, t.sender_id, t.receiver_id, ty.type_code AS type, t.amount, "
            "t.is_fraud, t.tx_time FROM transactions t JOIN transaction_types ty ON ty.type_id = t.type_id "
            "WHERE t.transaction_id = :i"), {"i": transaction_id}).mappings().first()
    if r is None:
        raise HTTPException(status_code=404, detail="Transaction inconnue")
    return {**dict(r), "tx_time": str(r["tx_time"])}


@app.get("/accounts/{account_id}/stats")
def stats_compte(account_id: str, role: str = Depends(authentifier)):
    with engine().connect() as c:
        if not c.execute(text("SELECT 1 FROM accounts WHERE account_id = :a"), {"a": account_id}).first():
            raise HTTPException(status_code=404, detail="Compte inconnu")
        env = c.execute(text("SELECT COUNT(*) AS n, COALESCE(SUM(amount),0) AS total, "
                             "COALESCE(SUM(is_fraud),0) AS fraudes FROM transactions WHERE sender_id = :a"),
                        {"a": account_id}).mappings().first()
        rec = c.execute(text("SELECT COUNT(*) AS n, COALESCE(SUM(amount),0) AS total, "
                             "COALESCE(SUM(is_fraud),0) AS fraudes FROM transactions WHERE receiver_id = :a"),
                        {"a": account_id}).mappings().first()
    return {"account_id": account_id,
            "envoyees": {"nb": env["n"], "total": round(env["total"], 2), "fraudes": env["fraudes"]},
            "recues": {"nb": rec["n"], "total": round(rec["total"], 2), "fraudes": rec["fraudes"]}}


@app.get("/alerts")
def lister_alertes(status: Optional[str] = Query(default=None, pattern="^(A_VERIFIER|CONFIRMEE|REJETEE)$"),
                   limit: int = Query(default=20, ge=1, le=100),
                   role: str = Depends(authentifier)):
    sql = ("SELECT a.alert_id, a.transaction_id, a.status, a.risk_reasons, t.amount "
           "FROM fraud_alerts a JOIN transactions t ON t.transaction_id = a.transaction_id ")
    params = {"l": limit}
    if status:
        sql += "WHERE a.status = :s "
        params["s"] = status
    sql += "ORDER BY t.amount DESC LIMIT :l"
    with engine().connect() as c:
        return [dict(r) for r in c.execute(text(sql), params).mappings()]


class MajAlerte(BaseModel):
    status: str


@app.patch("/alerts/{alert_id}")
def maj_alerte(alert_id: int, corps: MajAlerte, role: str = Depends(exiger_admin)):
    if corps.status not in ("A_VERIFIER", "CONFIRMEE", "REJETEE"):
        raise HTTPException(status_code=422, detail="Statut invalide")
    with engine().begin() as c:
        n = c.execute(text("UPDATE fraud_alerts SET status = :s WHERE alert_id = :i"),
                      {"s": corps.status, "i": alert_id}).rowcount
    if n == 0:
        raise HTTPException(status_code=404, detail="Alerte inconnue")
    return {"alert_id": alert_id, "status": corps.status}
