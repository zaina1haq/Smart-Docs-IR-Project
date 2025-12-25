from es_client import es, INDEX
from typing import Optional, List


# 1. AUTOCOMPLETE (titles)
def autocomplete_title(prefix: str):
    return es.search(
        index=INDEX,
        size=10,
        query={
            "bool": {
                "should": [
                    {
                        "match_bool_prefix": {
                            "title": {
                                "query": prefix
                            }
                        }
                    },
                    {
                        "match": {
                            "title": {
                                "query": prefix,
                                "fuzziness": "AUTO"
                            }
                        }
                    }
                ],
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
    functions = []

    # Recency boost
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

    # Stage 1: Lexical retrieval (BM25)
    lexical_query = {
        "bool": {
            "should": [
                {
                    "multi_match": {
                        "query": query,
                        "fields": ["title^6", "content"],
                        "fuzziness": "AUTO"
                    }
                },
                {
                    "match_phrase": {
                        "title": {
                            "query": query,
                            "boost": 10
                        }
                    }
                },
                {
                    # Exact title match
                    "term": {
                        "title.raw": {
                            "value": query,
                            "boost": 50,
                            "case_insensitive": True
                        }
                    }
                }
            ],
            "minimum_should_match": 1
        }
    }

    # Georeference boost
    if georef is not None:
        lexical_query["bool"]["should"].append({
        "nested": {
            "path": "georeferences",
            "score_mode": "max",  #take strongest one
            "query": {
                "function_score": {
                    "query": {
                        "term": {
                            "georeferences.name": {
                                "value": georef.lower(),
                                "case_insensitive": True
                            }
                        }
                    },
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

    if embedding is not None:
        final_query = {
            "script_score": {
                "query": lexical_query,
                "script": {
                    "source": """
                        double base = _score;


                        if (doc['title.raw'].size() != 0 &&
                            doc['title.raw'].value.equalsIgnoreCase(params.q)
) {
                            base = base * 10.0;
                        }


                        double sim = cosineSimilarity(params.qv, 'content_embedding');
                        sim = Math.max(sim, 0.0);

                        return base * (1.0 + sim);
                    """,
                    "params": {
                        "qv": embedding,
                        "q": query
                    }
                }
            }
        }
    else:
        final_query = lexical_query
    # Final scoring

    return es.search(
        index=INDEX,
        size=10,
        query={
            "function_score": {
                "query": final_query,
                "functions": functions,
                "boost_mode": "multiply",
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
    base_query = {
        "bool": {
            "must": [
                {
                    "multi_match": {
                        "query": query,
                        "fields": ["title^4", "content"],
                        "fuzziness": "AUTO"
                    }
                },
                {
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

    return es.search(
        index=INDEX,
        size=10,
        query={
            "function_score": {
                "query": base_query,
                "functions": [
                    {
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
