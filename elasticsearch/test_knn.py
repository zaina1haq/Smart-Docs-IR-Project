# # from elasticsearch import Elasticsearch
# # from sentence_transformers import SentenceTransformer

# # es = Elasticsearch("http://localhost:9200")
# # model = SentenceTransformer("all-MiniLM-L6-v2")

# # query = "global"
# # vector = model.encode(query).tolist()

# # res = es.search(
# #     index="project-index",
# #     knn={
# #         "field": "content_embedding",
# #         "query_vector": vector,
# #         "k": 10,
# #         "num_candidates": 100
# #     }
# # )

# # print("Top semantic results:")
# # for hit in res["hits"]["hits"]:
# #     print(hit["_score"], hit["_source"].get("title"))
# from sentence_transformers import SentenceTransformer
# import json

# model = SentenceTransformer("all-MiniLM-L6-v2")

# query_vector = model.encode("economic slowdown in asia").tolist()

# print(json.dumps(query_vector))
from sentence_transformers import SentenceTransformer
import json

# موديل يعطي 384 dims
model = SentenceTransformer("all-MiniLM-L6-v2")

# ====== النص اللي بدك تحوله Vector ======
text = input("اكتب النص تبعك: ")

# توليد embedding
embedding = model.encode(text, normalize_embeddings=True)

# تحويله لقائمة عشان يطلع JSON
vector = embedding.tolist()

print("\n✅ Vector جاهز (384 dims):\n")
print(json.dumps(vector, indent=2))

print(f"\n🔢 عدد الأبعاد: {len(vector)}")
