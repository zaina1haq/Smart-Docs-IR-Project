import os
import json

DATA_DIR = "../data_processed"


def count_core_attributes(docs):
    total_docs = len(docs)

    if total_docs == 0:
        print("❌ No documents to analyze.")
        return

    stats = {
        "title": 0,
        "content": 0,
        "authors": 0,
        "date": 0,
        "geopoint": 0,
        "temporalExpressions": 0,
        "georeferences": 0
    }

    for d in docs:
        if d.get("title"):
            stats["title"] += 1

        if d.get("content"):
            stats["content"] += 1

        if isinstance(d.get("authors"), list) and len(d["authors"]) > 0:
            stats["authors"] += 1

        if d.get("date"):
            stats["date"] += 1

        if isinstance(d.get("temporalExpressions"), list) and len(d["temporalExpressions"]) > 0:
            stats["temporalExpressions"] += 1

        if isinstance(d.get("georeferences"), list) and len(d["georeferences"]) > 0:
            stats["georeferences"] += 1

        gp = d.get("geopoint")
        if isinstance(gp, dict) and "lat" in gp and "lon" in gp:
            stats["geopoint"] += 1

    print("\n📊 CORE ATTRIBUTE COVERAGE")
    print("=" * 45)
    print(f"Total documents: {total_docs}\n")

    for k, v in stats.items():
        pct = (v / total_docs) * 100
        print(f"{k:22s}: {v:6d}  ({pct:5.1f}%)")


# =====================
# LOAD JSON FILES
# =====================
all_docs = []

for file in os.listdir(DATA_DIR):
    if file.endswith(".json"):
        with open(os.path.join(DATA_DIR, file), "r", encoding="utf-8") as f:
            data = json.load(f)

            if isinstance(data, list):
                all_docs.extend(data)
            elif isinstance(data, dict):
                all_docs.append(data)

print(f"📂 Loaded {len(all_docs)} documents")

count_core_attributes(all_docs)
