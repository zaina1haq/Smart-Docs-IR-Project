import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import spacy
from dateparser import parse
from geopy.geocoders import Nominatim

# Reference year
REF_REUTERS_YEAR = 1987

#  NLP model for date extraction
_NLP = spacy.load("en_core_web_lg")

_GEOL = Nominatim(user_agent="ir-project")

# Cache
_GEO_CACHE: Dict[str, Optional[Dict[str, float]]] = {}

def parse_authors(author_raw: str) -> List[Dict[str, Optional[str]]]:
    # Return empty list if no author field
    if not author_raw:
        return []

    # Clean common prefixes and suffixes
    text = re.sub(r"(?i)^\s*by\s+|,?\s*reuters\s*$", "", author_raw.strip())
    parts = re.split(r"(?i)\s+and\s+|[;,]\s*", text)

    authors = []
    for p in parts:
        # Remove extra symbols and parentheses
        p = re.sub(r"\(.*?\)|[^\w\s\-']", " ", p)
        tokens = re.sub(r"\s+", " ", p).strip().split()
        if len(tokens) >= 2:
            authors.append({
                "first": tokens[0].title(),
                "last": " ".join(tokens[1:]).title(),
                "email": None
            })

    # Remove duplicate authors
    uniq, seen = [], set()
    for a in authors:
        key = (a["first"], a["last"])
        if key not in seen:
            seen.add(key)
            uniq.append(a)
    return uniq

@dataclass(frozen=True)
class TemporalExpr:
    text: str
    normalized: str
    has_year: bool
    is_relative: bool
    position: int
    source: str

# Regex for relative time expressions
_RELATIVE_RE = re.compile(
    r"\b(today|yesterday|tomorrow|tonight|"
    r"this\s+(week|month|year)|"
    r"last\s+(week|month|year)|"
    r"next\s+(week|month|year))\b",
    re.I
)
#regax for dates
_YEAR_RE = re.compile(r"\b(18|19|20)\d{2}\b")

_DECADE_RE = re.compile(r"\b((18|19|20)\d{2})s\b", re.I)

_MONTHNAME_RE = re.compile(
    r"\b("
    r"jan(uary)?|feb(ruary)?|mar(ch)?|apr(il)?|may|jun(e)?|jul(y)?|"
    r"aug(ust)?|sep(tember)?|sept(ember)?|oct(ober)?|nov(ember)?|dec(ember)?"
    r")\b",
    re.I
)

# standalone day numbers (1–31)
_DAY_RE = re.compile(r"\b([1-9]|[12]\d|3[01])\b")

def _is_valid_date_candidate(raw: str) -> bool:
    # Skip pure numbers and very short non-text values
    s = raw.strip()
    if s.isdigit():
        return False
    if not re.search(r"[A-Za-z]", s) and len(s) <= 2:
        return False
    return True

def _find_dates(text: str) -> List[Tuple[str, int]]:
    # Extract DATE entities using spaCy
    out = []
    for e in _NLP(text).ents:
        if e.label_ != "DATE":
            continue
        if not _is_valid_date_candidate(e.text):
            continue
        out.append((e.text, e.start_char))
    return out

def _has_year_like(raw: str) -> bool:
    # explicit year OR decade forms like "1990s"
    return bool(_YEAR_RE.search(raw) or _DECADE_RE.search(raw))

def _normalize_date(raw: str, ref: datetime) -> Optional[str]:
    has_year = bool(_YEAR_RE.search(raw))
    is_relative = bool(_RELATIVE_RE.search(raw))

    # decades like "the 1990s"
    dm = _DECADE_RE.search(raw)
    if dm:
        decade_start = int(dm.group(1))
        return datetime(decade_start, 1, 1).date().isoformat()

    month_present = bool(_MONTHNAME_RE.search(raw))
    day_present = bool(_DAY_RE.search(raw))
    year_present = bool(_YEAR_RE.search(raw))

    parsed = parse(raw, settings={"RELATIVE_BASE": ref})
    if not parsed:
        return None

    # Reuters year
    if not has_year and not is_relative:
        parsed = parsed.replace(year=ref.year)

    #  month-only  YYYY-02-01
    if month_present and not day_present and not is_relative:
        parsed = parsed.replace(day=1)

    #  year-only should become YYYY-01-01
    if year_present and not month_present and not day_present and not is_relative:
        parsed = parsed.replace(month=1, day=1)

    return parsed.date().isoformat()
def extract_temporal_expressions(
    title: str,
    content: str,
    dateline: str,
    reference_dt: Optional[datetime]
) -> List[TemporalExpr]:
    # Store final results and avoid duplicates
    results, seen = [], set()

    # Use given reference date or default Reuters year
    ref = reference_dt or datetime(REF_REUTERS_YEAR, 1, 1)

    def collect(src: str, text: str):
        # Find and normalize dates from a text source
        for raw, pos in _find_dates(text):
            norm = _normalize_date(raw, ref)
            if not norm:
                continue

            has_year = _has_year_like(raw)
            is_relative = bool(_RELATIVE_RE.search(raw))

            # Prevent duplicate temporal expressions
            key = (raw.lower(), norm, src)
            if key in seen:
                continue
            seen.add(key)

            results.append(
                TemporalExpr(raw, norm, has_year, is_relative, pos, src)
            )

    # Extract dates from different document parts
    collect("dateline", dateline)
    collect("title", title)
    collect("content", content)

    return results


def temporal_confidence(t: TemporalExpr) -> float:
    # Score temporal expression based on quality and position
    score = (
        (2.0 if t.has_year else 0.0) +
        (1.5 if t.source == "dateline" else 0.5) +
        (1.0 if not t.is_relative else -1.0) +
        max(0.0, 1.0 - t.position / 500.0)
    )

    # Keep score in a fixed range
    if score < 0.0:
        return 0.0
    if score > 5.0:
        return 5.0
    return score
def geo_key(name: str) -> str:
    # Create a normalized key for grouping places
    if not name:
        return ""
    return re.sub(r"[^a-z]", "", name.lower())


# names at the end of place strings
_MONTH_RE = re.compile(
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\b.*$",
    re.I
)

_WS_RE = re.compile(r"\s+")

# Remove common company
_CORP_SUFFIX_RE = re.compile(
    r"(?i)\b(inc|inc\.|co|co\.|corp|corp\.|ltd|ltd\.|plc|llc)\b\.?\s*$"
)

# Filter codes that look like product IDs
_JUNK_GEO_RE = re.compile(r"(?i)^[A-Z]{1,4}[-_/]?\d{1,4}$")


def _norm_place(s: str) -> str:

    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", s.lower())).strip()


def _clean_place(name: str) -> str:
    # Clean raw place name text
    cleaned = _MONTH_RE.sub("", name).strip()
    cleaned = _WS_RE.sub(" ", cleaned).strip()
    cleaned = _CORP_SUFFIX_RE.sub("", cleaned).strip()
    return cleaned


def _is_reasonable_place(p: str) -> bool:
    # Basic checks to drop bad place candidates
    if not p:
        return False

    if _JUNK_GEO_RE.match(p.strip()):
        return False

    digits = sum(ch.isdigit() for ch in p)
    if digits >= 2 and any(sym in p for sym in ("-", "_", "/")):
        return False

    if not re.search(r"[A-Za-z]", p):
        return False

    return True


def extract_places(text: str) -> List[str]:
    # Extract place entities from text
    places = []
    for e in _NLP(text).ents:
        if e.label_ in ("GPE", "LOC", "FAC"):
            p = _clean_place(e.text)
            if p and _is_reasonable_place(p):
                places.append(p)
    return places


def extract_dateline_place(dateline: str) -> Optional[str]:
    # Get main place from dateline
    m = re.match(r"\s*([A-Z][A-Z\s\-]+),", dateline or "")
    return m.group(1).title() if m else None


def _collapse_abbrev(s: str) -> str:
    # Convert abbreviations like U.S.A. to USA
    return re.sub(r"[^A-Za-z]", "", s or "").strip()


def _country_hint_from_places(places: List[str]) -> Optional[str]:
    # Guess country hint from Reuters place tags
    if not places:
        return None

    for p in places:
        if not isinstance(p, str):
            continue
        hint = p.strip()
        if not hint:
            continue

        collapsed = _collapse_abbrev(hint)
        if collapsed and collapsed.lower() != hint.lower():
            return collapsed

        return hint

    return None


def _norm_hint(h: str) -> str:
    # Normalize country hint text
    return re.sub(r"[\W_]+", " ", h or "").strip()


def geocode(place: str, country_hint: Optional[str] = None) -> Optional[Dict[str, float]]:
    # Convert place name to latitude and longitude
    if not place:
        return None

    queries = []

    if country_hint and country_hint.strip():
        hint = _norm_hint(country_hint)
        if hint and hint.lower() not in place.lower():
            queries.append(f"{place}, {hint}")

    # Fallback: place name only
    queries.append(place)

    for q in queries:
        key = _norm_place(q)
        if key in _GEO_CACHE:
            return _GEO_CACHE[key]

        try:
            loc = _GEOL.geocode(q, timeout=10)
            if loc:
                _GEO_CACHE[key] = {"lat": loc.latitude, "lon": loc.longitude}
                return _GEO_CACHE[key]
        except Exception:
            pass

        _GEO_CACHE[key] = None

    return None


def geo_confidence(place: str, title: str, dateline: str) -> float:
    # Score place importance based on where it appears
    score = 0.0
    if place in dateline:
        score += 2.0
    if place in title:
        score += 1.5
    score += title.count(place) * 0.3
    return score

def choose_best_doc_date(temporal_exprs: List[TemporalExpr]) -> Optional[str]:
    # pick the best date from extracted temporal expressions
    if not temporal_exprs:
        return None

    # prefer non-relative dates if available
    non_relative = [t for t in temporal_exprs if not t.is_relative]
    pool = non_relative if non_relative else temporal_exprs

    best = max(pool, key=temporal_confidence)
    return best.normalized


def preprocess_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    title = doc.get("title", "")
    content = doc.get("content", "")
    dateline = doc.get("dateline", "")
    ref_date = doc.get("date_published")

    # temporal expressions
    temporal_exprs = extract_temporal_expressions(
        title, content, dateline, ref_date
    )

    #  date only if original date is missing
    approx_date: Optional[str] = None
    if ref_date is None:
        approx_date = choose_best_doc_date(temporal_exprs)

    # Collect all possible place mentions
    geo_refs = (
        extract_places(dateline) +
        extract_places(title) +
        extract_places(content) +
        (doc.get("places") or [])
    )

    # Clean, filter
    seen, unique_geo = set(), []
    for g in geo_refs:
        gg = _clean_place(str(g)) if g is not None else ""
        if not gg or not _is_reasonable_place(gg):
            continue
        k = _norm_place(gg)
        if k and k not in seen:
            seen.add(k)
            unique_geo.append(gg)

    # single geopoint
    geopoint, geopoint_from = None, None
    country_hint = _country_hint_from_places(doc.get("places") or [])
    dl = extract_dateline_place(dateline)

    # dateline with a region hint
    if dl:
        region_hint = None
        for p in unique_geo:
            if p.lower() != dl.lower() and p.isalpha() and len(p) > 3:
                region_hint = p
                break

        if region_hint:
            gp = geocode(f"{dl}, {region_hint}")
            if gp:
                geopoint, geopoint_from = gp, f"{dl}, {region_hint}"

        # dateline only
        if geopoint is None:
            gp = geocode(dl)
            if gp:
                geopoint, geopoint_from = gp, dl

    # best scored place
    if geopoint is None:
        for p in sorted(
            unique_geo,
            key=lambda x: geo_confidence(x, title, dateline),
            reverse=True
        ):
            gp = geocode(p, country_hint=country_hint)
            if gp:
                geopoint, geopoint_from = gp, p
                break

    return {
        "id": doc.get("id"),
        "title": title,
        "content": content,
        "authors": parse_authors(doc.get("author_raw", "")),

        # Use real date if exists, otherwise approximated date
        "date": (
            ref_date.isoformat(timespec="seconds")
            if ref_date
            else (approx_date if approx_date else None)
        ),

        "geopoint": geopoint,

        # Store all extracted temporal expressions
        "temporalExpressions": [
            {
                "text": t.text,
                "normalized": t.normalized,
                "source": t.source,
                "has_year": t.has_year,
                "is_relative": t.is_relative,
                "confidence": temporal_confidence(t),
            }
            for t in temporal_exprs
        ],

        "georeferences": [
            {
                "name": g,
                "key": geo_key(g),
                "confidence": geo_confidence(g, title, dateline)
            }
            for g in unique_geo
        ],

        "topics": doc.get("topics") or [],
        "places": doc.get("places") or [],

        # Flags to show approximations
        "approximations": {
            "date_is_approx": (ref_date is None and approx_date is not None),
            "geopoint_is_approx": geopoint is not None,
            "geopoint_from": geopoint_from,
        },
    }
