"""PARTIE 4 - Agent IA : explication des alertes de fraude + email client.

Pour chaque transaction marquee frauduleuse par le modele Spark (partie 3) :
  1. on recupere les metadonnees et on calcule les MOTIFS du score (regles lisibles
     basees sur les variables du modele : compte vide, ratio montant/solde, ...)
  2. le LLM redige une explication vulgarisee pour le conseiller bancaire
  3. le LLM redige un email rassurant pour le client (validation via l'application)

Fournisseurs (--provider) :
  ollama   : modele local (ex. llama3) via http://localhost:11434
  openai   : API OpenAI (variable d'environnement OPENAI_API_KEY, modele gpt-4o)
  template : pas de LLM, textes generes par gabarit (pour tester le flux hors-ligne)

Usage :
    python genai/genai_agent.py --alertes results/alertes_fraude.csv --provider ollama --n 3
"""
import argparse
import json
import os

import pandas as pd
import requests


def motifs_risque(a):
    """Raisons du score, calculees a partir des features (explicable, pas d'IA ici)."""
    m = []
    if a["oldbalance_org"] > 0 and a["newbalance_org"] == 0:
        m.append("le compte a ete entierement vide par l'operation")
    if a["ratio_montant_solde"] > 0.9:
        m.append("le montant represente %.0f%% du solde disponible" % (100 * a["ratio_montant_solde"]))
    if a["ecart_moyenne"] > 3 * max(abs(a["amount"] - a["ecart_moyenne"]), 1):
        m.append("le montant est tres superieur aux habitudes du compte")
    if a["freq_horaire"] >= 3:
        m.append("%d operations en moins d'une heure" % a["freq_horaire"])
    if a["type"] in ("TRANSFER", "CASH_OUT"):
        m.append("type d'operation a risque (%s)" % a["type"])
    return m or ["combinaison de variables inhabituelle pour ce compte"]


def masquer(compte):
    return compte[:2] + "*****" + compte[-2:]


def prompt_conseiller(a, motifs):
    return (
        "Tu aides un conseiller bancaire. Une transaction a ete marquee comme suspecte par un modele "
        "de detection de fraude.\n"
        "Transaction : id=%s, type=%s, montant=%.2f EUR, compte emetteur=%s, compte destinataire=%s.\n"
        "Motifs du score de risque : %s.\n"
        "Redige en 4 phrases maximum, en francais simple et sans jargon, pourquoi cette operation est "
        "suspecte et ce que le conseiller doit faire. Ne pretends pas que la fraude est certaine."
        % (a["transaction_id"], a["type"], a["amount"], masquer(a["sender_id"]),
           masquer(a["receiver_id"]), "; ".join(motifs)))


def prompt_client(a):
    return (
        "Redige un email en francais pour un client de la banque Hexa-Bank. Une operation de %.2f EUR "
        "(%s) sur son compte a ete detectee comme inhabituelle. Demande-lui de confirmer ou refuser "
        "l'operation directement dans son application mobile. Ton rassurant et securitaire. "
        "Regles : ne mets AUCUN lien, ne demande jamais de mot de passe, de code ou de coordonnees "
        "bancaires, rappelle que la banque ne les demande jamais. Donne un objet et un corps, "
        "signe 'Le service securite Hexa-Bank'." % (a["amount"], a["type"]))


def appeler_llm(prompt, provider, modele):
    if provider == "ollama":
        r = requests.post("http://localhost:11434/api/generate",
                          json={"model": modele or "llama3", "prompt": prompt, "stream": False},
                          timeout=180)
        r.raise_for_status()
        return r.json()["response"].strip()
    if provider == "openai":
        r = requests.post("https://api.openai.com/v1/chat/completions",
                          headers={"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"]},
                          json={"model": modele or "gpt-4o",
                                "messages": [{"role": "user", "content": prompt}],
                                "temperature": 0.3},
                          timeout=60)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    raise ValueError(provider)


def gabarit_conseiller(a, motifs):
    return ("La transaction %s (%s de %.2f EUR) a ete signalee par le modele car : %s. "
            "Ce n'est pas une certitude de fraude : nous conseillons de contacter le client pour "
            "verifier l'operation avant de la valider definitivement."
            % (a["transaction_id"], a["type"], a["amount"], "; ".join(motifs)))


def gabarit_client(a):
    return ("Objet : Verification d'une operation sur votre compte\n\n"
            "Bonjour,\n\n"
            "Une operation de %.2f EUR (%s) a ete detectee sur votre compte et nous semble inhabituelle. "
            "Par precaution, merci de confirmer ou de refuser cette operation directement dans votre "
            "application Hexa-Bank, rubrique \"Operations a verifier\".\n\n"
            "Pour votre securite, ce message ne contient aucun lien et nous ne vous demanderons jamais "
            "votre mot de passe, vos codes ou vos coordonnees bancaires.\n\n"
            "Le service securite Hexa-Bank" % (a["amount"], a["type"]))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--alertes", default="results/alertes_fraude.csv")
    p.add_argument("--provider", choices=["ollama", "openai", "template"], default="template")
    p.add_argument("--modele", default=None)
    p.add_argument("--n", type=int, default=3)
    p.add_argument("--out", default="results/agent_reponses.json")
    args = p.parse_args()

    alertes = pd.read_csv(args.alertes)
    # on traite d'abord les alertes au plus gros montant
    alertes = alertes.sort_values("amount", ascending=False).head(args.n)

    sorties = []
    for _, a in alertes.iterrows():
        a = a.to_dict()
        motifs = motifs_risque(a)
        if args.provider == "template":
            expl, mail = gabarit_conseiller(a, motifs), gabarit_client(a)
        else:
            expl = appeler_llm(prompt_conseiller(a, motifs), args.provider, args.modele)
            mail = appeler_llm(prompt_client(a), args.provider, args.modele)
        sorties.append({"transaction_id": int(a["transaction_id"]), "type": a["type"],
                        "montant": a["amount"], "vraie_fraude": int(a["label"]),
                        "motifs": motifs, "explication_conseiller": expl, "email_client": mail,
                        "fournisseur": args.provider})
        print("=" * 70)
        print("Transaction", int(a["transaction_id"]), "|", a["type"], "|", a["amount"], "EUR")
        print("Motifs :", "; ".join(motifs))
        print("\n[Conseiller]\n" + expl)
        print("\n[Email client]\n" + mail)

    with open(args.out, "w") as f:
        json.dump(sorties, f, indent=2, ensure_ascii=False)
    print("\nreponses ecrites dans", args.out)


if __name__ == "__main__":
    main()
