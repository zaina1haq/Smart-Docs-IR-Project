from es_client import es, INDEX
from typing import Optional, List

# This function is used for title autocomplete
# It helps the user while typing a title
def autocomplete_title(prefix: str):
    return es.search(
        index=INDEX,
        size=10,              # Return only 10 suggestions
        query={
            "bool": {
                "should": [
                    {
                        # This allows prefix matching
                        #auto suggest
                        "match_bool_prefix": {
                            "title": {
                                "query": prefix
                            }
                        }
                    },
                    {
                        # This allows fuzzy matching

                        "match": {
                            "title": {
                                "query": prefix,
                                "fuzziness": "AUTO"
                            }
                        }
                    }
                ],
                # At least one of the above should match
                "minimum_should_match": 1
            }
        }
    )


#function handles normal text search
# It combines text search + semantic search + time boost + location boost
def text_search(
    query: str,
    embedding: Optional[List[float]] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    georef: Optional[str] = None
):
    #list stores scoring functions
    functions = []

    # boosts newer documents
    # Recent documents get higher score
    functions.append({
        "gauss": {
            "date": {
                "origin": "now",
                "scale": "3650d",
                "decay": 0.7
            }
        }
    })

    # boosts documents close to user location
    # Only applied if latitude and longitude exist
    if lat is not None and lon is not None:
        functions.append({
            "gauss": {
                "geopoint": {
                    "origin": {"lat": lat, "lon": lon},
                    "scale": "300km",  # Nearby locations score higher
                    "decay": 0.6
                }
            }
        })

    # main lexical (text) search
    # Elasticsearch BM25 scoring
    lexical_query = {
        "bool": {
            "should": [
                {
                    # Search query in title and content
                    # Title is more important (^6)
                    "multi_match": {
                        "query": query,
                        "fields": ["title^6", "content"],
                        "fuzziness": "AUTO"
                    }
                },
                {
                    # Phrase match in title
                    # Exact phrase gives higher score
                    "match_phrase": {
                        "title": {
                            "query": query,
                            "boost": 10
                        }
                    }
                },
                {
                    # Exact title match using keyword field
                    # This gives very strong boost
                    "term": {
                        "title.raw": {
                            "value": query,
                            "boost": 50,
                            "case_insensitive": True
                        }
                    }
                }
            ],
            # At least one text condition must match
            "minimum_should_match": 1
        }
    }

    # boosts documents that mention a specific place
    # It searches inside nested georeferences
    if georef is not None:
        lexical_query["bool"]["should"].append({
            "nested": {
                "path": "georeferences",   # Nested field
                "score_mode": "max",       # Use strongest match
                "query": {
                    "function_score": {
                        "query": {
                            # Match place name
                            "term": {
                                "georeferences.name": {
                                    "value": georef.lower(),
                                    "case_insensitive": True
                                }
                            }
                        },
                        # Multiply score by confidence value
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

    # If semantic embedding exists, apply semantic re-ranking
    if embedding is not None:
        final_query = {
            "script_score": {
                "query": lexical_query,
                "script": {
                    "source": """
                        double base = _score;

                        // If title exactly matches the query, boost strongly
                        if (doc['title.raw'].size() != 0 &&
                            doc['title.raw'].value.equalsIgnoreCase(params.q)
                        ) {
                            base = base * 10.0;
                        }

                        // Compute cosine similarity with document embedding
                        double sim = cosineSimilarity(params.qv, 'content_embedding');

                        // Avoid negative similarity
                        sim = Math.max(sim, 0.0);

                        // Combine lexical score and semantic similarity
                        return base * (1.0 + sim);
                    """,
                    "params": {
                        "qv": embedding,  # Query vector
                        "q": query        # Query text
                    }
                }
            }
        }
    else:
        # If no embedding, use lexical search only
        final_query = lexical_query

    # Final Elasticsearch search call
    # Combines query score with time and location boosts
    return es.search(
        index=INDEX,
        size=10,
        query={
            "function_score": {
                "query": final_query,
                "functions": functions,
                "boost_mode": "multiply",  # Multiply query score with boosts
                "score_mode": "sum"        # Sum all boost functions
            }
        }
    )


# This function handles spatiotemporal search
# It searches by text + date range + location
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
    # Base query with text and date filtering
    base_query = {
        "bool": {
            "must": [
                {
                    # Text search
                    "multi_match": {
                        "query": query,
                        "fields": ["title^4", "content"],
                        "fuzziness": "AUTO"
                    }
                },
                {
                    # Date range filter
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

    # Boost documents that mention a specific place
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

    # Apply semantic similarity if embedding exists
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

    # Final spatiotemporal search with time and distance boosting
    return es.search(
        index=INDEX,
        size=10,
        query={
            "function_score": {
                "query": base_query,
                "functions": [
                    {
                        # Boost recent documents
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
                        # Boost documents close to given location
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
