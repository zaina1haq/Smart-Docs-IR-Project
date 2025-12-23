from elasticsearch import Elasticsearch, helpers
from sentence_transformers import SentenceTransformer
import json
import os

es = Elasticsearch("http://localhost:9200")
model = SentenceTransformer("all-MiniLM-L6-v2")

INDEX_NAME = "smart-docs-ir"
DATA_DIR = "../jsonl_output_with_countrykeys"

def embed(text):
    return model.encode(text, normalize_embeddings=True).tolist()

def generate_actions():
    for file in os.listdir(DATA_DIR):
        if not file.endswith(".jsonl"):
            continue

        path = os.path.join(DATA_DIR, file)
        with open(path, encoding="utf-8") as f:
            for line in f:                     # ✅ سطر سطر
                doc = json.loads(line)        # ✅ JSONL
                if not doc.get("id"):
                    continue
                full_text = doc.get("title", "") + " " + doc.get("content", "")
                doc["content_embedding"] = embed(full_text)

                yield {
                    "_index": INDEX_NAME,
                    "_id": doc.get("id"),
                    "_source": doc
                }

if __name__ == "__main__":
    success, failed = helpers.bulk(es, generate_actions(), stats_only=True)
    print("Indexed:", success)
    print("Failed:", failed)
