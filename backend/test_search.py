import requests
import json

API_BASE = "http://localhost:8000"

#check if backend is running
try:
    response = requests.get(f"{API_BASE}/")
    print("Backend is running")
    print(response.json())
except Exception as e:
    print(f"Backend error: {e}")
    exit()

#simple text search
print("\n" + "=" * 50)
print("Testing TEXT SEARCH...")
try:
    response = requests.get(f"{API_BASE}/search?q=cocoa")
    data = response.json()

    hits = data.get("hits", {}).get("hits", [])
    print(f"Found {len(hits)} results")

    if hits:
        print(f"First result title: {hits[0]['_source']['title']}")
except Exception as e:
    print(f"Text search error: {e}")

# spatiotemporal search
print("\n" + "=" * 50)
print("Testing SPATIOTEMPORAL SEARCH...")
try:
    params = {
        "q": "cocoa",
        "start": "1987-01-01",
        "end": "1987-12-31",
        "lat": -12.98,
        "lon": -38.48,
        "distance": "1000km",
        "georef": "Bahia"
    }

    response = requests.get(f"{API_BASE}/spatiotemporal", params=params)
    data = response.json()

    hits = data.get("hits", {}).get("hits", [])
    print(f"Found {len(hits)} results")

    if hits:
        for hit in hits[:3]:
            print(f"- {hit['_source']['title']} (score: {hit['_score']})")
    else:
        print("No results returned")
        print(json.dumps(data, indent=2))
except Exception as e:
    print(f"Spatiotemporal search error: {e}")
