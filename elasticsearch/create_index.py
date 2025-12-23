from elasticsearch import Elasticsearch
import json

es = Elasticsearch("http://localhost:9200")
INDEX_NAME = "smart-docs-ir"

with open("mapping.json") as f:
    mapping = json.load(f)

if es.indices.exists(index=INDEX_NAME):
    es.indices.delete(index=INDEX_NAME)

es.indices.create(index=INDEX_NAME, body=mapping)