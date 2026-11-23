"""Tests de l'agent IA : motifs, masquage, garde-fous de l'email (mode gabarit)."""
import re

from genai_agent import gabarit_client, masquer, motifs_risque, prompt_client, prompt_conseiller

ALERTE = {"transaction_id": 1, "sender_id": "C0001234", "receiver_id": "C9000001", "type": "TRANSFER",
          "amount": 1000.0, "oldbalance_org": 1000.0, "newbalance_org": 0.0,
          "ratio_montant_solde": 1.0, "freq_horaire": 1, "ecart_moyenne": 900.0}


def test_motifs_compte_vide():
    m = " ".join(motifs_risque(ALERTE))
    assert "vide" in m and "100%" in m


def test_motifs_par_defaut():
    a = dict(ALERTE, oldbalance_org=10.0, newbalance_org=5.0, ratio_montant_solde=0.1,
             ecart_moyenne=0.0, type="PAYMENT")
    assert motifs_risque(a) == ["combinaison de variables inhabituelle pour ce compte"]


def test_masquage_compte():
    assert masquer("C0001234") == "C0*****34"
    assert "C0001234" not in prompt_conseiller(ALERTE, ["x"])


def test_email_sans_lien_ni_demande_sensible():
    mail = gabarit_client(ALERTE)
    assert not re.search(r"https?://|www\.", mail)
    assert "ne vous demanderons jamais" in mail
    assert "application" in mail


def test_prompt_client_interdit_liens():
    p = prompt_client(ALERTE).lower()
    assert "aucun lien" in p and "mot de passe" in p
