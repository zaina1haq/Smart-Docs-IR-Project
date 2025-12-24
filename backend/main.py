from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")

def embed_query(text: str):
    return model.encode(text, normalize_embeddings=True).tolist()

from queries import (
    autocomplete_title,
    text_search,
    spatiotemporal_search
)

# --------------------------------------------------
# App initialization
# --------------------------------------------------
app = FastAPI(
    title="Smart Document Retrieval API",
    description="Backend API for textual, semantic, spatial and temporal search",
    version="1.0.0"
)

# --------------------------------------------------
# CORS (required for frontend)
# --------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # أثناء التطوير فقط
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------
# Root (optional but useful)
# --------------------------------------------------
@app.get("/")
def root():
    return {
        "message": "Smart Document Retrieval API is running",
        "endpoints": [
            "/autocomplete",
            "/search",
            "/spatiotemporal",
            "/analytics/top-georeferences",
            "/analytics/time-distribution",
            "/docs"
        ]
    }

# --------------------------------------------------
# Autocomplete (titles)
# --------------------------------------------------
@app.get("/autocomplete")
def autocomplete(q: str = Query(..., min_length=3)):
    """
    Autocomplete service for document titles.
    Starts suggesting after 3 characters and supports fuzzy matching.
    """
    return autocomplete_title(q)

# --------------------------------------------------
# Text + Semantic + Recency + Optional Localization
# --------------------------------------------------
@app.get("/search")
def search(
    q: str = Query(..., min_length=1),
    lat: float | None = None,
    lon: float | None = None,
    georef: str | None = None  # ✅ Added georeference parameter
):
    """
    Search documents with optional georeference.
    Query tuple: (query, temporal_expression, georeference)
    """
    embedding = embed_query(q)
    return text_search(q, embedding=embedding, lat=lat, lon=lon, georef=georef)


# --------------------------------------------------
# Spatio-temporal search
# --------------------------------------------------
@app.get("/spatiotemporal")
def spatiotemporal(
    q: str,
    start: str,
    end: str,
    lat: float,
    lon: float,
    distance: str = "500km",
    georef: str | None = None  # ✅ Added georeference parameter
):
    """
    Spatiotemporal search with optional georeference.
    Query tuple: (query, temporal_expression, georeference)
    """
    embedding = embed_query(q)
    return spatiotemporal_search(q, start, end, lat, lon, distance, embedding=embedding, georef=georef)