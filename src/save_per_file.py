import os
import json
from tqdm import tqdm

from parse_reuters import parse_reuters_file
from preprocess import preprocess_doc


DATA_RAW_DIR = "../data_raw"
DATA_PROCESSED_DIR = "../data_processed"


def save_per_sgm_file(data_raw_dir: str, data_processed_dir: str) -> None:
    os.makedirs(data_processed_dir, exist_ok=True)

    sgm_files = sorted(
        f for f in os.listdir(data_raw_dir)
        if f.lower().endswith(".sgm")
    )

    print(f"Found {len(sgm_files)} SGM files")

    for sgm_file in sgm_files:
        sgm_path = os.path.join(data_raw_dir, sgm_file)
        out_name = os.path.splitext(sgm_file)[0] + ".json"
        out_path = os.path.join(data_processed_dir, out_name)

        raw_docs = parse_reuters_file(sgm_path)
        processed_docs = []

        for doc in tqdm(
            raw_docs,
            desc=f"Processing {sgm_file}",
            leave=True
        ):
            processed_docs.append(preprocess_doc(doc))

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(processed_docs, f, ensure_ascii=False, indent=2)

        print(f"Saved → {out_path}")


if __name__ == "__main__":
    save_per_sgm_file(DATA_RAW_DIR, DATA_PROCESSED_DIR)
