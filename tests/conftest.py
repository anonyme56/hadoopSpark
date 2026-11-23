import os
import sys

# racine du depot + dossiers de code : permet "import fraud_api", "import streaming_to_hdfs", etc.
RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for dossier in ("", "api", "spark_jobs", "genai", "database", "graph", "ingestion"):
    sys.path.insert(0, os.path.join(RACINE, dossier))
