# import os
# import json
# from test import count_core_attributes

# DATA_DIR = "../data_processed"

# all_docs = []

# for file in os.listdir(DATA_DIR):
#     if file.endswith(".json"):
#         with open(os.path.join(DATA_DIR, file), "r", encoding="utf-8") as f:
#             docs = json.load(f)
#             all_docs.extend(docs)

# count_core_attributes(all_docs)
