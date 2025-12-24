import requests
import json

API_BASE = "http://localhost:8000"

# Test 1: Check if backend is running
try:
    response = requests.get(f"{API_BASE}/")
    print("✅ Backend is running")
    print(response.json())
except Exception as e:
    print(f"❌ Backend error: {e}")
    exit()

# Test 2: Simple text search
print("\n" + "="*50)
print("Testing TEXT SEARCH...")
try:
    response = requests.get(f"{API_BASE}/search?q=cocoa")
    data = response.json()
    print(f"✅ Found {len(data.get('hits', {}).get('hits', []))} results")
    if data.get('hits', {}).get('hits'):
        print(f"   First result: {data['hits']['hits'][0]['_source']['title']}")
except Exception as e:
    print(f"❌ Text search error: {e}")

# Test 3: Spatiotemporal search
print("\n" + "="*50)
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
    print(f"✅ Found {len(data.get('hits', {}).get('hits', []))} results")
    if data.get('hits', {}).get('hits'):
        for hit in data['hits']['hits'][:3]:
            print(f"   - {hit['_source']['title']} (score: {hit['_score']})")
    else:
        print("   ⚠️ No results - checking query...")
        print(f"   Response: {json.dumps(data, indent=2)}")
except Exception as e:
    print(f"❌ Spatiotemporal search error: {e}")