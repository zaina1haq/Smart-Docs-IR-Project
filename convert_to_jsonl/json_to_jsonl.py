import os
import json
from typing import Any, List


def convert_processed_json_to_jsonl(
    processed_dir: str = "../data_processed_with_countrykeys",  # ✅ changed
    output_dir: str = "../jsonl_output_with_countrykeys"        # ✅ changed
) -> None:
    """
    Takes all .json files from processed_dir.
    Each JSON file is expected to be a list of documents.
    Outputs one .jsonl file per input JSON into output_dir.

    If your JSON docs already include countryKeys / country_code,
    they will be preserved in the JSONL lines automatically.
    """
    os.makedirs(output_dir, exist_ok=True)

    json_files = sorted(
        f for f in os.listdir(processed_dir)
        if f.lower().endswith(".json")
    )

    if not json_files:
        print(f"No JSON files found in {processed_dir}")
        return

    print(f"Found {len(json_files)} JSON files in {processed_dir}")

    for filename in json_files:
        input_path = os.path.join(processed_dir, filename)
        output_name = os.path.splitext(filename)[0] + ".jsonl"
        output_path = os.path.join(output_dir, output_name)

        with open(input_path, "r", encoding="utf-8") as f:
            data: List[Any] = json.load(f)

        if not isinstance(data, list):
            print(f"Skipping {filename} (not a list)")
            continue

        with open(output_path, "w", encoding="utf-8") as out:
            for doc in data:
                out.write(json.dumps(doc, ensure_ascii=False) + "\n")

        print(f"Saved → {output_path}")


if __name__ == "__main__":
    convert_processed_json_to_jsonl()