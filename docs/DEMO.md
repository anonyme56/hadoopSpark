# Déroulé de la démonstration (≈ 10 min de démo + 15 min d'exposé)

À répéter au moins une fois avant le jour J : les premiers démarrages de HDFS et Kafka sont lents.

## Avant de commencer (hors démo, 5 min avant)
- `docker-compose up -d --build` terminé, `docker ps` : tout est "Up"
- Topic créé, dossier HDFS `/data` créé, Gephi ouvert avec `results/gephi/graphe_fraude.gexf`
- Ollama lancé (`ollama run llama3` une fois pour charger le modèle), 3 terminaux prêts
- **Plan B** : une vidéo enregistrée de la démo complète, au cas où le réseau ou Docker plante

## Déroulé

| Min | Action | Ce qu'on montre | Ce qu'on dit |
|---|---|---|---|
| 0:00 | `docker ps` + Spark UI (:8080) | Cluster complet démarré | Chaque brique a un rôle : Kafka tampon, HDFS stockage, Spark calcul |
| 1:00 | Terminal 1 : job `spark_jobs/streaming_to_hdfs.py` | Console en attente | Schéma imposé, watermark 2 min, checkpoint |
| 1:30 | Terminal 2 : `ingestion/producer.py --rate 100 --max 5000` | Messages envoyés ; Kafdrop (:9000) | Les transactions arrivent en continu |
| 2:30 | Terminal 1 | Métriques par minute qui défilent | Volume et montant par type en temps réel |
| 3:30 | HDFS UI (:9870) → `/data/transactions_parquet` | Dossiers `type=...` | Parquet partitionné : lectures rapides |
| 4:30 | **Résilience** : `docker stop kafka`, 10 s, `docker start kafka` | `docker ps` puis le job qui reprend | Les offsets permettent de rattraper sans perte |
| 5:30 | `spark_jobs/hdfs_to_mongo.py` puis Mongo-Express (:8082) | Collections `nodes` et `edges` | Un nœud par compte, un arc par couple |
| 6:30 | Gephi | Les 10 hubs en rouge | Dire que ce sont les mules du jeu de test |
| 7:30 | `spark_jobs/train_fraud.py` (résultats déjà calculés si trop long) | AUC, rappel, matrice | 970 fausses alertes vs 185 : Random Forest retenu |
| 8:30 | `genai/genai_agent.py --provider ollama --n 1` | Motifs, explication, email | Pas de lien, pas de demande de données sensibles |
| 9:30 | `curl` sur l'API : 401, 200, 403 | Sécurité de l'API | Clé, rôles, quotas |

## Questions probables du jury (préparer les réponses)

1. **Pourquoi Kafka et pas lire directement un fichier ?** Découplage et rejouabilité : si Spark tombe, rien n'est perdu.
2. **Pourquoi Parquet ?** Format colonne compressé ; on ne lit que les colonnes utiles ; partitionnement par type.
3. **À quoi sert le watermark ?** Il fixe jusqu'où on attend les messages en retard et permet à Spark de libérer l'état des fenêtres anciennes.
4. **Pourquoi MongoDB et PostgreSQL ?** Graphe de documents souples pour l'analyse réseau ; données structurées avec intégrité pour les transactions et alertes.
5. **Pourquoi pondérer la classe fraude ?** 1,2 % de fraudes : sans poids, répondre toujours « normal » donne 98,8 % d'exactitude et ne détecte rien.
6. **Vos scores sont très élevés, pourquoi ?** Données synthétiques avec un schéma de fraude unique ; à confirmer sur PaySim. (Ne pas défendre ces scores comme réalistes.)
7. **Comment éviter qu'un LLM envoie un email de phishing ?** Prompt restrictif, motifs calculés par le code, tests sur l'absence de lien, validation par le conseiller.
8. **Qu'est-ce qui ne passerait pas à l'échelle ?** Un seul broker, un seul datanode, API mono-processus, MongoDB sans authentification.
9. **Quel est l'impact RGPD ?** Identifiants de comptes = données personnelles : pseudonymisation, durée de conservation, droits d'accès, décision automatisée avec recours humain.
