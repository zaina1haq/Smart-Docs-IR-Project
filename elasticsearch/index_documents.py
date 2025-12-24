from elasticsearch import Elasticsearch, helpers
from sentence_transformers import SentenceTransformer
import json
import os
from tqdm import tqdm   # ✅ NEW

es = Elasticsearch("http://localhost:9200")
model = SentenceTransformer("all-MiniLM-L6-v2")

INDEX_NAME = "smart-docs-ir"
DATA_DIR = "../jsonl_output_with_countrykeys"

def embed(text):
    return model.encode(text, normalize_embeddings=True).tolist()


# ✅ NEW: count valid documents first (for progress bar)
def count_valid_docs():
    total = 0
    for file in os.listdir(DATA_DIR):
        if not file.endswith(".jsonl"):
            continue

        path = os.path.join(DATA_DIR, file)
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    doc = json.loads(line)
                    if doc.get("id") and doc.get("content", "").strip():
                        total += 1
                except:
                    pass
    return total


def generate_actions(pbar):   # ✅ pbar added
    for file in os.listdir(DATA_DIR):
        if not file.endswith(".jsonl"):
            continue

        path = os.path.join(DATA_DIR, file)
        with open(path, encoding="utf-8") as f:
            for line in f:
                doc = json.loads(line)
                if not doc.get("id"):
                    continue

                content = doc.get("content", "").strip()
                if not content:
                    continue

                doc["content_embedding"] = embed(content)

                yield {
                    "_index": INDEX_NAME,
                    "_id": doc.get("id"),
                    "_source": doc
                }

                pbar.update(1)   # ✅ UPDATE progress


if __name__ == "__main__":
    print("🔢 Counting documents...")
    total_docs = count_valid_docs()
    print(f"📄 Total documents to index: {total_docs}")

    with tqdm(total=total_docs, desc="Indexing", unit="doc") as pbar:
        success, failed = helpers.bulk(
            es,
            generate_actions(pbar),   # ✅ pass progress bar
            stats_only=True
        )

    print("Indexed:", success)
    print("Failed:", failed)
