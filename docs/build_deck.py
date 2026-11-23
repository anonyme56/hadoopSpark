"""Diaporama de soutenance (python-pptx). Les notes de chaque diapo servent de script oral."""
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt

BLEU = RGBColor(0x1F, 0x38, 0x64)
CLAIR = RGBColor(0xDC, 0xE6, 0xF2)
GRIS = RGBColor(0x55, 0x55, 0x55)
ROUGE = RGBColor(0xC0, 0x39, 0x2B)

prs = Presentation()
prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
VIDE = prs.slide_layouts[6]


def texte(slide, x, y, w, h, t, taille=18, gras=False, couleur=None, align=None):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    lignes = t if isinstance(t, list) else [t]
    for i, l in enumerate(lignes):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = l
        p.font.size, p.font.bold = Pt(taille), gras
        p.font.color.rgb = couleur or RGBColor(0x22, 0x22, 0x22)
        p.space_after = Pt(6)
        if align:
            p.alignment = align
    return tb


def diapo(titre, notes):
    s = prs.slides.add_slide(VIDE)
    bande = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, Inches(1.0))
    bande.fill.solid(); bande.fill.fore_color.rgb = BLEU; bande.line.fill.background()
    texte(s, 0.6, 0.18, 12, 0.7, titre, 28, True, RGBColor(255, 255, 255))
    s.notes_slide.notes_text_frame.text = notes
    return s


def puces(slide, x, y, w, items, taille=20):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(5))
    tf = tb.text_frame; tf.word_wrap = True
    for i, it in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = "•  " + it
        p.font.size = Pt(taille); p.space_after = Pt(10)
        p.font.color.rgb = RGBColor(0x22, 0x22, 0x22)


def boite(slide, x, y, w, h, t, fond=CLAIR, taille=13):
    b = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    b.fill.solid(); b.fill.fore_color.rgb = fond
    b.line.color.rgb = BLEU
    tf = b.text_frame; tf.word_wrap = True; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    for i, l in enumerate(t.split("\n")):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = l; p.alignment = PP_ALIGN.CENTER
        p.font.size = Pt(taille); p.font.bold = (i == 0)
        p.font.color.rgb = RGBColor(0x1A, 0x1A, 0x1A)
    return b


def fleche(slide, x1, y1, x2, y2):
    c = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = BLEU; c.line.width = Pt(2.25)
    ln = c.line._get_or_add_ln()
    from lxml import etree
    ln.append(etree.SubElement(ln, "{http://schemas.openxmlformats.org/drawingml/2006/main}tailEnd", type="triangle"))


# 1 ---------------------------------------------------------------- titre
s = prs.slides.add_slide(VIDE)
fond = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
fond.fill.solid(); fond.fill.fore_color.rgb = BLEU; fond.line.fill.background()
texte(s, 0.9, 2.1, 11.5, 2, "Détection de fraude en temps réel :\nKafka, Spark, HDFS, MongoDB et IA générative", 38, True, RGBColor(255, 255, 255))
texte(s, 0.9, 4.4, 11.5, 1, "Évaluation certificative Bloc 1 – Expert en ingénierie des données (RNCP40875)", 20, False, RGBColor(220, 230, 242))
texte(s, 0.9, 5.2, 11.5, 1, "ALI Yohan  |  École Hexagone  |  Novembre 2026", 18, False, RGBColor(220, 230, 242))
s.notes_slide.notes_text_frame.text = ("Présentation (30 s) : j'ai construit une plateforme qui ingère des transactions bancaires, "
                                       "repère la fraude, analyse les réseaux de comptes et prévient le client. Durée prévue : 15 min + démo.")

# 2 ---------------------------------------------------------------- besoin
s = diapo("Le besoin métier", "Contexte FinTech : trois questions auxquelles la plateforme répond. 1 min.")
puces(s, 0.7, 1.4, 12, [
    "Traiter les transactions au fil de l'eau, pas le lendemain",
    "Repérer les comptes frauduleux, et les comptes « mules » qui centralisent l'argent",
    "Comprendre comment l'argent circule entre les comptes (analyse de réseau)",
    "Prévenir le client avec un message clair et sûr, sans surcharger les conseillers",
], 24)
texte(s, 0.7, 5.6, 12, 1, "Jeu de données : schéma PaySim, 100 000 transactions, 1,2 % de fraudes (synthétique pour les mesures)", 16, False, GRIS)

# 3 ---------------------------------------------------------------- archi
s = diapo("Architecture (Docker Compose)", "Parcourir le schéma de gauche à droite. Justifier : Kafka = tampon, HDFS = stockage durable, "
          "Spark = un seul moteur pour streaming/SQL/ML, Mongo = graphe, Postgres = données structurées normalisées. 3 min.")
boite(s, 0.4, 1.7, 1.9, 1.1, "Producteur\nproducer.py")
boite(s, 2.7, 1.7, 1.9, 1.1, "Kafka\ntopic transactions")
boite(s, 5.0, 1.7, 2.3, 1.1, "Spark Streaming\nnettoyage + métriques")
boite(s, 7.7, 1.7, 2.3, 1.1, "HDFS\nParquet (data lake)")
boite(s, 10.4, 1.7, 2.5, 1.1, "Spark batch\ngraphe + MLlib")
for x1, x2 in [(2.3, 2.7), (4.6, 5.0), (7.3, 7.7), (10.0, 10.4)]:
    fleche(s, x1, 2.25, x2, 2.25)
boite(s, 7.4, 4.0, 2.4, 1.1, "MongoDB\nnodes / edges", RGBColor(0xE2, 0xF0, 0xD9))
boite(s, 10.4, 4.0, 2.5, 1.1, "PostgreSQL\nschéma normalisé", RGBColor(0xE2, 0xF0, 0xD9))
boite(s, 4.4, 4.0, 2.4, 1.1, "Gephi\nexport GEXF/CSV", RGBColor(0xFF, 0xF2, 0xCC))
boite(s, 10.4, 5.6, 2.5, 1.0, "API REST\nclé + quotas", RGBColor(0xFF, 0xF2, 0xCC))
boite(s, 7.4, 5.6, 2.4, 1.0, "Agent IA\nLlama 3 / GPT-4o", RGBColor(0xFF, 0xF2, 0xCC))
fleche(s, 11.6, 2.8, 11.6, 4.0); fleche(s, 9.6, 2.8, 8.6, 4.0)
fleche(s, 7.4, 4.55, 6.8, 4.55); fleche(s, 11.6, 5.1, 11.6, 5.6); fleche(s, 10.4, 5.1, 9.8, 5.9)
texte(s, 0.5, 5.4, 6.5, 1.4, ["Réplication HDFS = 1 et un seul broker : choix de formation,",
                              "à passer à 3 en production (haute disponibilité)."], 15, False, GRIS)

# 4 ---------------------------------------------------------------- partie 1
s = diapo("Partie 1 – Streaming Kafka → Spark → HDFS", "Montrer le terminal du job (métriques par minute) puis le dossier Parquet dans l'interface HDFS. "
          "Insister : schéma imposé, watermark 2 min, checkpoint. 2 min.")
puces(s, 0.7, 1.4, 6.3, [
    "Schéma imposé, nettoyage à la volée (nuls, montants négatifs, types inconnus)",
    "Parquet partitionné par type d'opération",
    "Métriques par fenêtre d'1 min, watermark 2 min",
    "Checkpoint : reprise sans perte ni doublon",
], 19)
boite(s, 7.5, 1.6, 5.2, 1.2, "100 000 messages\n0 rejet, 100 000 lignes Parquet", CLAIR, 18)
boite(s, 7.5, 3.1, 5.2, 1.2, "≈ 3 600 msg/s en local (2 cœurs)\nJVM incluse, hors cluster", CLAIR, 18)
boite(s, 7.5, 4.6, 5.2, 1.2, "Test de reprise : 50 000 + 50 000\n= 100 000 lignes, 0 doublon", RGBColor(0xE2, 0xF0, 0xD9), 18)

# 5 ---------------------------------------------------------------- partie 2
s = diapo("Partie 2 – Graphe de transactions", "Ouvrir le GEXF dans Gephi : ForceAtlas 2, taille = degré entrant. Dire honnêtement que les 10 hubs sont "
          "les mules injectées dans le jeu synthétique, et que Q est gonflée par les petites composantes. 3 min.")
s.shapes.add_picture("results/gephi/graphe_apercu.png", Inches(0.5), Inches(1.2), height=Inches(5.9))
puces(s, 8.0, 1.5, 5, [
    "8 510 comptes, 99 745 arcs",
    "1 233 arcs impliqués dans une fraude",
    "10 hubs : 67 à 97 fraudes reçues chacun",
    "Sous-graphe exporté : 3 454 nœuds",
], 18)
texte(s, 8.0, 5.0, 4.9, 1.8, "Limite : ces hubs sont ceux injectés dans les données de test. Sur du vrai PaySim, le résultat reste à mesurer.", 14, False, ROUGE)

# 6 ---------------------------------------------------------------- partie 3
s = diapo("Partie 3 – Modèle de détection (MLlib)", "Expliquer le déséquilibre (1,2 %) et le poids de classe. Le rappel est identique, la précision change : "
          "970 vs 185 fausses alertes. Dire que les scores sont trop beaux à cause du jeu synthétique. 3 min.")
s.shapes.add_picture("results/fig_comparaison.png", Inches(0.5), Inches(1.3), width=Inches(6.4))
s.shapes.add_picture("results/fig_confusion.png", Inches(7.0), Inches(1.4), width=Inches(6.0))
puces(s, 0.7, 4.6, 12, [
    "Pipeline : StringIndexer → OneHotEncoder → VectorAssembler → modèle ; classe fraude pondérée (≈ 81)",
    "Random Forest retenu : mêmes fraudes détectées, 5 fois moins de fausses alertes",
    "Variables clés : compte vidé, part du solde utilisée ; entraînement ≈ 8 s",
], 17)

# 7 ---------------------------------------------------------------- partie 4
s = diapo("Partie 4 – Agent IA", "Démo : lancer genai_agent.py avec Ollama sur une alerte. Montrer les motifs (calculés par le code), l'explication conseiller, "
          "puis l'email. Insister sur les garde-fous. 2 min.")
boite(s, 0.6, 1.6, 3.4, 1.4, "Alerte du modèle\nmétadonnées + score")
boite(s, 4.7, 1.6, 3.4, 1.4, "Motifs du score\nrègles lisibles (code)")
boite(s, 8.8, 1.6, 3.9, 1.4, "LLM (Ollama / GPT-4o)\nexplication + email")
fleche(s, 4.0, 2.3, 4.7, 2.3); fleche(s, 8.1, 2.3, 8.8, 2.3)
puces(s, 0.7, 3.5, 12, [
    "Comptes masqués dans les prompts ; le conseiller décide, l'agent propose",
    "Email : aucun lien, jamais de demande de mot de passe ou de données bancaires",
    "Tests automatiques sur ces garde-fous ; à valider avec le vrai LLM sur 10–20 alertes",
], 19)

# 8 ---------------------------------------------------------------- BDD + API
s = diapo("Base relationnelle et API", "Montrer le schéma normalisé, puis la démo curl : sans clé 401, lecteur 200, lecteur qui modifie 403, admin 200, "
          "quota 429. Mentionner les requêtes paramétrées. 2 min.")
puces(s, 0.7, 1.4, 6, [
    "PostgreSQL, 4 tables en 3FN : comptes, types, transactions, alertes",
    "Clés étrangères, contraintes CHECK, index",
    "Contrôles d'intégrité automatisés (6 tests)",
], 18)
puces(s, 7.0, 1.4, 6, [
    "API FastAPI : clé X-API-Key, rôles lecteur / admin",
    "Quota 60 req/min par clé (429 + Retry-After)",
    "SQL paramétré, doc OpenAPI sur /docs",
], 18)
boite(s, 0.7, 4.3, 5.8, 1.5, "Charge (SQLite, 1 machine)\n0 erreur jusqu'à 50 clients simultanés", CLAIR, 17)
boite(s, 7.0, 4.3, 5.8, 1.5, "≈ 1 100 req/s ; p95 = 64 ms à 50 clients", CLAIR, 17)

# 9 ---------------------------------------------------------------- qualité
s = diapo("Tests et résilience", "27 tests automatiques. Puis le scénario de résilience cluster (arrêt de Kafka, du datanode, redémarrage de Mongo) - "
          "à rejouer en direct si le temps le permet. 2 min.")
puces(s, 0.7, 1.4, 12, [
    "27 tests pytest : nettoyage Spark, features, API (auth, quotas, injection SQL), agent IA, intégrité de la base",
    "Reprise sur checkpoint validée : aucune perte, aucun doublon",
    "Scénarios cluster scriptés (resilience_cluster.sh) : arrêt de Kafka, du datanode HDFS, redémarrage de MongoDB",
    "Ce qui reste hors périmètre : réplication à 3, authentification MongoDB, TLS",
], 20)

# 10 --------------------------------------------------------------- conclusion
s = diapo("Bilan et limites", "Terminer sur les limites : on les assume, c'est ce qui rend les résultats crédibles. Questions. 1 min.")
puces(s, 0.7, 1.4, 6, ["Plateforme complète de bout en bout", "Choix justifiés par le besoin", "Code testé et reproductible (Docker)"], 21)
puces(s, 7.0, 1.4, 5.8, [
    "Mesures sur données synthétiques → valider sur PaySim",
    "Un seul nœud par service",
    "Scoring en flux (modèle dans le streaming) = prochaine étape",
], 20)

prs.save("docs/Soutenance_Projet_Fraude.pptx")
print("deck ok :", len(prs.slides.__iter__.__self__._sldIdLst), "diapos")
