from es_client import es, INDEX
from typing import Optional, List

# 1. AUTOCOMPLETE (TITLE SUGGESTIONS)

def autocomplete_title(prefix: str):
    # This function returns title suggestions while the user is typing
    # It is used by the frontend autocomplete dropdown

    return es.search(
        index=INDEX,
        size=10,  # return at most 10 suggestions
        query={
            "bool": {
                "should": [
                    {
                        # Prefix-based autocomplete
                        # Example: "eco" → "economy", "economic growth"
                        "match_bool_prefix": {
                            "title": {
                                "query": prefix
                            }
                        }
                    },
                    {
                        # Fuzzy matching to handle small typos
                        # Example: "econmy" → "economy"
                        "match": {
                            "title": {
                                "query": prefix,
                                "fuzziness": "AUTO"
                            }
                        }
                    }
                ],
                # At least one of the above conditions must match
                "minimum_should_match": 1
            }
        }
    )


# 2. TEXT + SEMANTIC + RECENCY + OPTIONAL LOCATION
def text_search(
    query: str,
    embedding: Optional[List[float]] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    georef: Optional[str] = None
):
    # This is the main search used for normal text queries
    # It combines:
    # - lexical search (BM25)
    # - exact / phrase title matching
    # - semantic similarity (embeddings)
    # - recency boost
    # - optional geographic boost

    # List of function_score boosts (recency, distance, etc.)
    functions = []
    # Recency boost
    # Newer documents get higher score
    # scale = 3650d → slow decay (up to ~10 years)
    functions.append({
        "gauss": {
            "date": {
                "origin": "now",
                "scale": "3650d",
                "decay": 0.7
            }
        }
    })
    # Localization boost
    # If user provides lat/lon, boost documents closer to that location
    if lat is not None and lon is not None:
        functions.append({
            "gauss": {
                "geopoint": {
                    "origin": {"lat": lat, "lon": lon},
                    "scale": "300km",
                    "decay": 0.6
                }
            }
        })

    # Stage 1: Lexical retrieval (BM25-based)

    # This stage finds candidate documents based on text matching
    lexical_query = {
        "bool": {
            "should": [
                {
                    # Regular text search on title + content
                    # Title is boosted higher than content
                    "multi_match": {
                        "query": query,
                        "fields": ["title^6", "content"],
                        "fuzziness": "AUTO"
                    }
                },
                {
                    # Phrase match on title
                    # Stronger signal than normal match
                    "match_phrase": {
                        "title": {
                            "query": query,
                            "boost": 10
                        }
                    }
                },
                {
                    # Exact title match (very strong signal)
                    # Uses keyword field (title.raw)
                    "term": {
                        "title.raw": {
                            "value": query,
                            "boost": 50,
                            "case_insensitive": True
                        }
                    }
                }
            ],
            # At least one of the above lexical matches must succeed
            "minimum_should_match": 1
        }
    }

    # Georeference boost
    # Boost documents that mention a specific place name
    # Uses nested georeferences field
    if georef is not None:
        lexical_query["bool"]["should"].append({
            "nested": {
                "path": "georeferences",
                "score_mode": "max",  # take strongest matching georeference
                "query": {
                    "function_score": {
                        "query": {
                            # Match georeference name
                            "term": {
                                "georeferences.name": {
                                    "value": georef.lower(),
                                    "case_insensitive": True
                                }
                            }
                        },
                        # Boost score based on georeference confidence
                        "script_score": {
                            "script": {
                                "source": """
                                    double conf = doc['georeferences.confidence'].value;
                                    return _score * conf * 5.0;
                                """
                            }
                        }
                    }
                }
            }
        })

    # Stage 2: Semantic re-ranking
    # improves ranking using vector similarity
    if embedding is not None:
        final_query = {
            "script_score": {
                "query": lexical_query,
                "script": {
                    "source": """
                        double base = _score;

                        // Extra boost if title exactly matches the query
                        if (doc['title.raw'].size() != 0 &&
                            doc['title.raw'].value.equalsIgnoreCase(params.q)
                        ) {
                            base = base * 10.0;
                        }

                        // Compute cosine similarity with content embedding
                        double sim = cosineSimilarity(params.qv, 'content_embedding');
                        sim = Math.max(sim, 0.0);

                        // Combine lexical score with semantic similarity
                        return base * (1.0 + sim);
                    """,
                    "params": {
                        "qv": embedding,  # query embedding
                        "q": query        # raw query text
                    }
                }
            }
        }
    else:
        # If embeddings are not provided, use lexical query only
        final_query = lexical_query

    # Final scoring
    # function_score combines:
    # - lexical + semantic score
    # - recency boost
    # - location boost
    return es.search(
        index=INDEX,
        size=10,
        query={
            "function_score": {
                "query": final_query,
                "functions": functions,
                "boost_mode": "multiply",  # multiply boosts with base score
                "score_mode": "sum"
            }
        }
    )


# 3. SPATIOTEMPORAL SEARCH
def spatiotemporal_search(
    query: str,
    start: str,
    end: str,
    lat: float,
    lon: float,
    dist: str,
    embedding: Optional[List[float]] = None,
    georef: Optional[str] = None
):
    # This search enforces BOTH:
    # - text relevance
    # - time range
    # And boosts by:
    # - distance
    # - recency
    # - optional semantic similarity

    # Base query: text + time
    base_query = {
        "bool": {
            "must": [
                {
                    # Text search on title + content
                    "multi_match": {
                        "query": query,
                        "fields": ["title^4", "content"],
                        "fuzziness": "AUTO"
                    }
                },
                {
                    # Date range filter (hard constraint)
                    "range": {
                        "date": {
                            "gte": start,
                            "lte": end
                        }
                    }
                }
            ],
            "should": []
        }
    }

    # Optional georeference boost
    # Boost documents mentioning a place name
    if georef is not None:
        base_query["bool"]["should"].append({
            "nested": {
                "path": "georeferences",
                "query": {
                    "match": {
                        "georeferences.name": {
                            "query": georef,
                            "boost": 5
                        }
                    }
                }
            }
        })

    # Optional semantic scoring
    # Re-rank results using embedding similarity
    if embedding is not None:
        base_query = {
            "script_score": {
                "query": base_query,
                "script": {
                    "source": """
                        cosineSimilarity(params.query_vector, 'content_embedding') + 1.0
                    """,
                    "params": {
                        "query_vector": embedding
                    }
                }
            }
        }

    # Final spatiotemporal scoring

    return es.search(
        index=INDEX,
        size=10,
        query={
            "function_score": {
                "query": base_query,
                "functions": [
                    {
                        # Boost newer documents
                        "gauss": {
                            "date": {
                                "origin": "now",
                                "scale": "365d",
                                "decay": 0.5
                            }
                        },
                        "weight": 1
                    },
                    {
                        # Boost documents closer to the given location
                        "gauss": {
                            "geopoint": {
                                "origin": {"lat": lat, "lon": lon},
                                "scale": "500km",
                                "decay": 0.5
                            }
                        },
                        "weight": 1
                    }
                ],
                "boost_mode": "sum",
                "score_mode": "sum"
            }
        }
    )
