from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from sentence_transformers import SentenceTransformer


model = SentenceTransformer("all-MiniLM-L6-v2")


def embed_query(text: str):
    # Convert query text into a vector embedding
    return model.encode(text, normalize_embeddings=True).tolist()


from queries import (
    autocomplete_title,
    text_search,
    spatiotemporal_search
)

# Create the FastAPI app
app = FastAPI(
    title="Smart Document Retrieval API",
    description="Backend API for textual, semantic, spatial and temporal search",
    version="1.0.0"
)

# Enable CORS so the frontend can call the backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Basic health endpoint
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

# Autocomplete endpoint (titles)
@app.get("/autocomplete")
def autocomplete(q: str = Query(..., min_length=3)):
    # Return title suggestions after 3 chars
    return autocomplete_title(q)

# Text + semantic search with optional location + georef filter
@app.get("/search")
def search(
    q: str = Query(..., min_length=1),
    lat: float | None = None,
    lon: float | None = None,
    georef: str | None = None
):
    # Embed query and run search
    embedding = embed_query(q)
    return text_search(q, embedding=embedding, lat=lat, lon=lon, georef=georef)

# Spatiotemporal search endpoint
@app.get("/spatiotemporal")
def spatiotemporal(
    q: str,
    start: str,
    end: str,
    lat: float,
    lon: float,
    distance: str = "500km",
    georef: str | None = None
):
    # Embed query and run spatiotemporal search
    embedding = embed_query(q)
    return spatiotemporal_search(
        q, start, end, lat, lon, distance, embedding=embedding, georef=georef
    )
