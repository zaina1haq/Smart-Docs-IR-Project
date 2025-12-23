import os
import json
import re
from typing import Optional, Set, Any, Dict, List

import pycountry


# Make paths stable no matter where you run from
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PROCESSED_DIR = os.path.join(BASE_DIR, "..", "data_processed")
OUT_DIR = os.path.join(BASE_DIR, "..", "data_processed_with_countrykeys")


def _norm_name(s: str) -> str:
    """Normalize for matching country names (keep letters/spaces, collapse spaces, lowercase)."""
    s = s or ""
    s = re.sub(r"[^A-Za-z\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


# Build a lookup dict of exact country names from pycountry (no manual synonym table)
# Includes name + official_name + common_name when available.
_NAME_TO_ALPHA2: Dict[str, str] = {}
for c in pycountry.countries:
    variants = [getattr(c, "name", None), getattr(c, "official_name", None), getattr(c, "common_name", None)]
    for v in variants:
        if isinstance(v, str) and v.strip():
            key = _norm_name(v)
            _NAME_TO_ALPHA2.setdefault(key, c.alpha_2.lower())


def canonical_country_key(text: str) -> Optional[str]:
    """
    Reliable mapping:
    - Handles codes: US / USA / UAE / U.S. / U.S.A. -> us, ae, etc.
    - Handles exact country names from pycountry: Uruguay -> uy
    - Handles multi-word country names: United States of America -> us, El Salvador -> sv
    - Avoids fuzzy mistakes like "Salvador" -> El Salvador
    """
    if not text or not isinstance(text, str):
        return None

    s = text.strip()
    if not s:
        return None

    collapsed = re.sub(r"[^A-Za-z]", "", s).upper()  # "U.S.A." -> "USA"

    # Common alias: UK -> GB
    if collapsed == "UK":
        return "gb"

    # Codes
    if 2 <= len(collapsed) <= 3:
        if len(collapsed) == 2:
            c = pycountry.countries.get(alpha_2=collapsed)
            return c.alpha_2.lower() if c else None
        else:
            c = pycountry.countries.get(alpha_3=collapsed)
            return c.alpha_2.lower() if c else None

    # Exact name matching (NO fuzzy)
    key = _norm_name(s)

    # If it's a single word, ONLY accept if it exactly matches a country name (e.g., "Uruguay").
    # This prevents "Salvador" from being treated as "El Salvador".
    if " " not in key:
        return _NAME_TO_ALPHA2.get(key)

    # Multi-word: allow exact match against known country names
    return _NAME_TO_ALPHA2.get(key)


def enrich_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(doc)
    country_keys: Set[str] = set()

    # From places tags
    places = out.get("places") or []
    if isinstance(places, list):
        for p in places:
            if isinstance(p, str):
                cc = canonical_country_key(p)
                if cc:
                    country_keys.add(cc)

    # From georeferences
    georefs = out.get("georeferences") or []
    if isinstance(georefs, list):
        new_georefs: List[Dict[str, Any]] = []
        for g in georefs:
            if not isinstance(g, dict):
                continue

            name = g.get("name")
            gg = dict(g)

            if isinstance(name, str):
                cc = canonical_country_key(name)
                if cc:
                    country_keys.add(cc)
                    # Optional: only set if missing
                    gg.setdefault("country_code", cc)

            new_georefs.append(gg)

        out["georeferences"] = new_georefs

    out["countryKeys"] = sorted(country_keys)
    return out


def main(start_idx: int = 0, end_idx: int = 21) -> None:
    os.makedirs(OUT_DIR, exist_ok=True)

    json_files = sorted(
        f for f in os.listdir(DATA_PROCESSED_DIR)
        if f.lower().endswith(".json")
    )

    if not json_files:
        raise RuntimeError(f"No .json files found in {DATA_PROCESSED_DIR}")

    if start_idx < 0 or start_idx >= len(json_files):
        raise ValueError(f"start_idx={start_idx} out of range (0..{len(json_files)-1})")
    end_idx = min(end_idx, len(json_files) - 1)

    target_files = json_files[start_idx:end_idx + 1]
    print(f"Found {len(json_files)} JSON files total")
    print(f"Processing indices [{start_idx}..{end_idx}] ({len(target_files)} files):")
    for f in target_files:
        print(" -", f)

    for filename in target_files:
        in_path = os.path.join(DATA_PROCESSED_DIR, filename)
        out_path = os.path.join(OUT_DIR, filename)

        with open(in_path, "r", encoding="utf-8") as f:
            docs = json.load(f)

        if not isinstance(docs, list):
            raise ValueError(f"{filename} is not a list of documents (expected list)")

        enriched = [enrich_doc(d) if isinstance(d, dict) else d for d in docs]

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(enriched, f, ensure_ascii=False, indent=2)

        print(f"Saved → {out_path}")


if __name__ == "__main__":
    main(0, 21)