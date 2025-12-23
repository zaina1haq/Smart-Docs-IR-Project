"""
Smart Document Retrieval System - Backend API
Flask-based REST API for spatiotemporal document search and analytics
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from elasticsearch import Elasticsearch
from sentence_transformers import SentenceTransformer
from dateparser import parse as date_parse
from typing import Optional, List, Dict, Any, Tuple
import re

app = Flask(__name__)
CORS(app)

# =========================
# Config / Clients
# =========================
ES_URL = "http://localhost:9200"
INDEX_NAME = "smart-docs-ir"

es = Elasticsearch(ES_URL)
model = SentenceTransformer("all-MiniLM-L6-v2")


# =========================
# Utility Functions
# =========================
def embed_text(text: str) -> List[float]:
    """Generate embedding vector for semantic search"""
    return model.encode(text, normalize_embeddings=True).tolist()


def parse_temporal_expression(temporal_expr: Optional[str]) -> Optional[str]:
    """Parse temporal expression to ISO date format (YYYY-MM-DD)"""
    if not temporal_expr:
        return None
    parsed = date_parse(temporal_expr)
    if parsed:
        return parsed.date().isoformat()
    return None


def parse_iso_or_natural_date(value: Optional[str]) -> Optional[str]:
    """Parse ISO or natural language date to ISO date string (YYYY-MM-DD)."""
    if not value:
        return None
    parsed = date_parse(value)
    if parsed:
        return parsed.date().isoformat()
    return None


def parse_georeference(geo_expr: Optional[str]) -> Optional[str]:
    """Clean and normalize georeference expression"""
    if not geo_expr:
        return None
    cleaned = re.sub(r"\s+", " ", geo_expr.strip())
    return cleaned if cleaned else None


def geo_key(name: str) -> str:
    """Match the indexing tool's key normalization (for georeferences.key)"""
    if not name:
        return ""
    return re.sub(r"[^a-z]", "", name.lower())


def safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        v = str(value).strip()
        if not v:
            return None
        return float(v)
    except Exception:
        return None


def build_geo_origin(lat: Optional[float], lon: Optional[float]) -> Optional[Dict[str, float]]:
    if lat is None or lon is None:
        return None
    return {"lat": lat, "lon": lon}


def km_to_es_distance(km: float) -> str:
    # Elasticsearch accepts "10km"
    if km <= 0:
        km = 1.0
    # keep it clean
    return f"{km:g}km"


# =========================
# API Endpoints
# =========================
@app.route("/", methods=["GET"])
def index():
    return jsonify(
        {
            "name": "Smart Document Retrieval System API",
            "version": "1.1.0",
            "status": "running",
            "endpoints": {
                "health": "/health",
                "autocomplete": "/api/autocomplete?q=<query>&size=10",
                "search": "/api/search (POST)",
                "top_georeferences": "/api/analytics/top-georeferences?size=10",
                "temporal_distribution": "/api/analytics/temporal-distribution?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD",
                "document": "/api/document/<doc_id>",
                "stats": "/api/stats",
            },
            "search_body_example": {
                "query": "economy inflation",
                "temporal_expression": "1996-02-10",
                "georeference": "Paris",
                "size": 10,
                "use_semantic": True,
                "date_from": "1996-01-01",
                "date_to": "1996-03-01",
                "lat": 48.8566,
                "lon": 2.3522,
                "radius_km": 150
            }
        }
    ), 200


@app.route("/health", methods=["GET"])
def health_check():
    try:
        ok = es.ping()
        if not ok:
            return jsonify({"status": "unhealthy", "elasticsearch": "not responding"}), 500

        exists = es.indices.exists(index=INDEX_NAME)
        if not exists:
            return jsonify(
                {
                    "status": "unhealthy",
                    "elasticsearch": "connected",
                    "index": INDEX_NAME,
                    "error": "index does not exist",
                }
            ), 500

        return jsonify({"status": "healthy", "elasticsearch": "connected", "index": INDEX_NAME}), 200
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500


@app.route("/api/autocomplete", methods=["GET"])
def autocomplete():
    """
    Autocomplete service for document titles
    Requirements:
      - Start suggesting after the 3rd typed character
      - Return top-10 titles
      - Consider misspellings
    Query params:
      - q: query string (minimum 3 characters)
      - size: number of results (default: 10)
    """
    query_text = request.args.get("q", "").strip()
    size = int(request.args.get("size", 10))

    if len(query_text) < 3:
        return jsonify(
            {"query": query_text, "suggestions": [], "message": "Query must be at least 3 characters"}
        ), 200

    try:
        # Mapping uses edge_ngram analyzer on title, so a match query works as autocomplete.
        # Add fuzziness to tolerate misspellings.
        search_query = {
            "size": size,
            "_source": ["id", "title", "date"],
            "query": {
                "bool": {
                    "should": [
                        {
                            "match": {
                                "title": {
                                    "query": query_text,
                                    "fuzziness": "AUTO",
                                    "prefix_length": 2,
                                    "boost": 3,
                                }
                            }
                        },
                        {
                            "match_phrase_prefix": {
                                "title": {
                                    "query": query_text,
                                    "boost": 4
                                }
                            }
                        },
                    ],
                    "minimum_should_match": 1,
                }
            },
            "highlight": {"fields": {"title": {}}},
        }

        response = es.search(index=INDEX_NAME, body=search_query)

        suggestions = []
        for hit in response.get("hits", {}).get("hits", []):
            src = hit.get("_source", {})
            suggestions.append(
                {
                    "id": src.get("id"),
                    "title": src.get("title"),
                    "date": src.get("date"),
                    "score": hit.get("_score"),
                    "highlight": hit.get("highlight", {}).get("title", []),
                }
            )

        return jsonify({"query": query_text, "suggestions": suggestions, "total": len(suggestions)}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/search", methods=["POST"])
def search_documents():
    """
    Lexical and semantic search with spatiotemporal filtering + analytics-friendly output

    Required by spec:
      - tuple(query, temporal_expression, georeference)
      - lexical + semantic over title + content (title emphasized)
      - consider recency + localization factors

    Request body (keeps tuple fields + adds OPTIONAL advanced filters without breaking requirements):
      - query: search text (required)
      - temporal_expression: date/time expression (optional)
      - georeference: place name (optional)
      - size: number of results (default: 10)
      - use_semantic: enable semantic search (default: true)

      OPTIONAL (extra, helps match "spatio" strictly):
      - date_from: ISO or natural language (optional)
      - date_to: ISO or natural language (optional)
      - lat: float (optional)
      - lon: float (optional)
      - radius_km: float (optional)  -> filters within distance if provided
    """
    data = request.get_json(silent=True) or {}

    query_text = (data.get("query") or "").strip()
    temporal_expr = data.get("temporal_expression")
    geo_expr = data.get("georeference")
    size = int(data.get("size", 10))
    use_semantic = bool(data.get("use_semantic", True))

    # Optional: strict temporal range
    date_from = parse_iso_or_natural_date(data.get("date_from"))
    date_to = parse_iso_or_natural_date(data.get("date_to"))

    # Optional: strict spatial / localization
    lat = safe_float(data.get("lat"))
    lon = safe_float(data.get("lon"))
    radius_km = safe_float(data.get("radius_km"))
    geo_origin = build_geo_origin(lat, lon)

    if not query_text:
        return jsonify({"error": "Query text is required"}), 400

    try:
        should_clauses: List[Dict[str, Any]] = []
        filter_clauses: List[Dict[str, Any]] = []
        functions: List[Dict[str, Any]] = []

        # 1) Lexical (title boosted + content)
        should_clauses.extend(
            [
                {
                    "match": {
                        "title": {
                            "query": query_text,
                            "boost": 4,
                            "fuzziness": "AUTO",
                        }
                    }
                },
                {"match": {"content": {"query": query_text, "boost": 1}}},
            ]
        )

        # 2) Semantic (dense_vector cosine) - contributes to should score
        if use_semantic:
            query_vector = embed_text(query_text)
            should_clauses.append(
                {
                    "script_score": {
                        "query": {"match_all": {}},
                        "script": {
                            "source": "cosineSimilarity(params.query_vector, 'content_embedding') + 1.0",
                            "params": {"query_vector": query_vector},
                        },
                        "boost": 1.6,
                    }
                }
            )

        # 3) Temporal filtering
        # If date_from/date_to provided -> use strict range
        if date_from or date_to:
            dr: Dict[str, Any] = {}
            if date_from:
                dr["gte"] = date_from
            if date_to:
                dr["lte"] = date_to
            filter_clauses.append({"range": {"date": dr}})
        else:
            # Else use temporal_expression ±30 days (keeps your original behavior)
            parsed_date = parse_temporal_expression(temporal_expr)
            if parsed_date:
                filter_clauses.append(
                    {
                        "range": {
                            "date": {
                                "gte": f"{parsed_date}||-30d/d",
                                "lte": f"{parsed_date}||+30d/d",
                            }
                        }
                    }
                )

        # 4) Georeference (name-based) + (optional) geo_point localization
        cleaned_geo = parse_georeference(geo_expr)
        if cleaned_geo:
            k = geo_key(cleaned_geo)
            if k:
                should_clauses.append(
                    {
                        "nested": {
                            "path": "georeferences",
                            "query": {
                                "term": {"georeferences.key": {"value": k}}
                            },
                            "boost": 2.2,
                        }
                    }
                )

            # places is keyword -> exact match (keeps your original)
            should_clauses.append({"term": {"places": {"value": cleaned_geo, "boost": 1.6}}})

        # 5) Recency factor (ranking) - required
        functions.append(
            {
                "gauss": {
                    "date": {
                        "origin": "now",
                        "scale": "365d",
                        "decay": 0.5,
                    }
                },
                "weight": 0.6,
            }
        )

        # 6) Localization factor (ranking + optional filter)
        # If lat/lon provided and documents contain geopoint, boost closer documents.
        if geo_origin:
            # Optional filter within radius_km
            if radius_km and radius_km > 0:
                filter_clauses.append(
                    {
                        "geo_distance": {
                            "distance": km_to_es_distance(radius_km),
                            "geopoint": geo_origin
                        }
                    }
                )

            # Always add distance-based score boost when origin exists
            # Scale: if radius specified use it, otherwise a reasonable default
            scale_km = radius_km if (radius_km and radius_km > 0) else 250.0
            functions.append(
                {
                    "gauss": {
                        "geopoint": {
                            "origin": geo_origin,
                            "scale": km_to_es_distance(scale_km),
                            "decay": 0.5
                        }
                    },
                    "weight": 0.7,
                }
            )

        # ✅ function_score wraps bool query
        search_query = {
            "size": size,
            "query": {
                "function_score": {
                    "query": {
                        "bool": {
                            "should": should_clauses,
                            "filter": filter_clauses,
                            "minimum_should_match": 1,
                        }
                    },
                    "functions": functions,
                    "score_mode": "sum",
                    "boost_mode": "multiply",
                }
            },
            "_source": {"excludes": ["content_embedding"]},
            "highlight": {
                "fields": {
                    "title": {},
                    "content": {"fragment_size": 150, "number_of_fragments": 3},
                }
            },
        }

        response = es.search(index=INDEX_NAME, body=search_query)

        results = []
        for hit in response.get("hits", {}).get("hits", []):
            doc = hit.get("_source", {}) or {}
            snippet_list = hit.get("highlight", {}).get("content")
            if isinstance(snippet_list, list) and snippet_list:
                snippet = snippet_list[0]
            else:
                content = doc.get("content", "") or ""
                snippet = (content[:200] + "...") if content else ""

            results.append(
                {
                    "id": doc.get("id"),
                    "title": doc.get("title"),
                    "content_snippet": snippet,
                    "date": doc.get("date"),
                    "geopoint": doc.get("geopoint"),
                    "authors": doc.get("authors", []),
                    "temporalExpressions": doc.get("temporalExpressions", []),
                    "georeferences": doc.get("georeferences", []),
                    "topics": doc.get("topics", []),
                    "places": doc.get("places", []),
                    "countryKeys": doc.get("countryKeys", []),
                    "approximations": doc.get("approximations", {}),
                    "score": hit.get("_score"),
                    "highlight": hit.get("highlight", {}),
                }
            )

        total = response.get("hits", {}).get("total", {}).get("value", len(results))
        max_score = response.get("hits", {}).get("max_score")

        return jsonify(
            {
                "query": query_text,
                "temporal_expression": temporal_expr,
                "georeference": geo_expr,

                # echo optional strict filters for transparency
                "date_from": date_from,
                "date_to": date_to,
                "lat": lat,
                "lon": lon,
                "radius_km": radius_km,

                "results": results,
                "total": total,
                "max_score": max_score,
            }
        ), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/analytics/top-georeferences", methods=["GET"])
def top_georeferences():
    """
    Return top-10 mentioned georeferences across the entire index
    Query params:
      - size: number of results (default: 10)
    """
    size = int(request.args.get("size", 10))

    try:
        agg_query = {
            "size": 0,
            "aggs": {
                "top_georeferences": {
                    "nested": {"path": "georeferences"},
                    "aggs": {
                        "by_key": {
                            "terms": {
                                "field": "georeferences.key",
                                "size": size,
                                "order": {"_count": "desc"},
                            },
                            "aggs": {
                                "top_name": {
                                    "terms": {
                                        "field": "georeferences.name",
                                        "size": 1,
                                        "order": {"_count": "desc"},
                                    }
                                },
                                "avg_confidence": {"avg": {"field": "georeferences.confidence"}},
                                "top_country": {
                                    "terms": {
                                        "field": "georeferences.country_code",
                                        "size": 1,
                                        "order": {"_count": "desc"},
                                    }
                                },
                            },
                        }
                    },
                }
            },
        }

        response = es.search(index=INDEX_NAME, body=agg_query)

        buckets = (
            response.get("aggregations", {})
            .get("top_georeferences", {})
            .get("by_key", {})
            .get("buckets", [])
        )

        top_refs = []
        for b in buckets:
            name_buckets = b.get("top_name", {}).get("buckets", [])
            name = name_buckets[0]["key"] if name_buckets else None

            cc_buckets = b.get("top_country", {}).get("buckets", [])
            country_code = cc_buckets[0]["key"] if cc_buckets else None

            avg_conf = b.get("avg_confidence", {}).get("value")

            top_refs.append(
                {
                    "key": b.get("key"),
                    "name": name,
                    "country_code": country_code,
                    "count": b.get("doc_count"),
                    "avg_confidence": round(avg_conf, 2) if isinstance(avg_conf, (int, float)) else None,
                }
            )

        return jsonify({"top_georeferences": top_refs, "total": len(top_refs)}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/analytics/temporal-distribution", methods=["GET"])
def temporal_distribution():
    """
    Return distribution of documents over time with 1-day aggregation
    Query params:
      - start_date: filter start date (optional, ISO format or natural language)
      - end_date: filter end date (optional, ISO format or natural language)
    """
    start_date = parse_iso_or_natural_date(request.args.get("start_date"))
    end_date = parse_iso_or_natural_date(request.args.get("end_date"))

    try:
        query: Dict[str, Any] = {"match_all": {}}
        if start_date or end_date:
            date_range: Dict[str, Any] = {}
            if start_date:
                date_range["gte"] = start_date
            if end_date:
                date_range["lte"] = end_date
            query = {"bool": {"filter": [{"range": {"date": date_range}}]}}

        agg_query = {
            "size": 0,
            "query": query,
            "aggs": {
                "docs_over_time": {
                    "date_histogram": {
                        "field": "date",
                        "calendar_interval": "1d",
                        "format": "yyyy-MM-dd",
                        "min_doc_count": 0,
                    }
                },
                "date_stats": {"stats": {"field": "date"}},
            },
        }

        response = es.search(index=INDEX_NAME, body=agg_query)

        buckets = response.get("aggregations", {}).get("docs_over_time", {}).get("buckets", [])
        stats = response.get("aggregations", {}).get("date_stats", {})

        distribution = [{"date": b.get("key_as_string"), "count": b.get("doc_count")} for b in buckets]
        total_documents = response.get("hits", {}).get("total", {}).get("value", 0)

        return jsonify(
            {
                "distribution": distribution,
                "total_documents": total_documents,
                "date_range": {
                    "min": stats.get("min_as_string") if stats.get("min") is not None else None,
                    "max": stats.get("max_as_string") if stats.get("max") is not None else None,
                },
                "interval": "1 day",
                "filters": {"start_date": start_date, "end_date": end_date},
            }
        ), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/document/<doc_id>", methods=["GET"])
def get_document(doc_id: str):
    try:
        response = es.get(index=INDEX_NAME, id=doc_id)
        doc = response.get("_source", {}) or {}
        doc.pop("content_embedding", None)
        return jsonify({"id": doc_id, "document": doc}), 200
    except Exception as e:
        msg = str(e)
        if "NotFoundError" in msg or "404" in msg:
            return jsonify({"error": "Document not found"}), 404
        return jsonify({"error": msg}), 500


@app.route("/api/stats", methods=["GET"])
def index_statistics():
    try:
        stats = es.indices.stats(index=INDEX_NAME)
        count = es.count(index=INDEX_NAME)

        sample_query = {
            "size": 0,
            "aggs": {
                "authors": {
                    "nested": {"path": "authors"},
                    "aggs": {"count": {"cardinality": {"field": "authors.last"}}},
                },
                "places_count": {"cardinality": {"field": "places"}},
                "topics_count": {"cardinality": {"field": "topics"}},
            },
        }

        agg_response = es.search(index=INDEX_NAME, body=sample_query)

        index_size = (
            stats.get("indices", {})
            .get(INDEX_NAME, {})
            .get("total", {})
            .get("store", {})
            .get("size_in_bytes")
        )

        unique_authors = (
            agg_response.get("aggregations", {})
            .get("authors", {})
            .get("count", {})
            .get("value", 0)
        )

        return jsonify(
            {
                "total_documents": count.get("count", 0),
                "index_size": index_size,
                "unique_authors": unique_authors,
                "unique_places": agg_response.get("aggregations", {}).get("places_count", {}).get("value", 0),
                "unique_topics": agg_response.get("aggregations", {}).get("topics_count", {}).get("value", 0),
            }
        ), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =========================
# Run Application
# =========================
if __name__ == "__main__":
    print("Starting Smart Document Retrieval Backend...")
    print(f"Elasticsearch Index: {INDEX_NAME}")
    print("Available endpoints:")
    print("  GET  /health")
    print("  GET  /api/autocomplete?q=<query>&size=10")
    print("  POST /api/search")
    print("  GET  /api/analytics/top-georeferences")
    print("  GET  /api/analytics/temporal-distribution")
    print("  GET  /api/document/<doc_id>")
    print("  GET  /api/stats")
    print("\nServer running on http://localhost:5000")

    app.run(debug=True, host="0.0.0.0", port=5000)
