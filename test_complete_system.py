"""
Comprehensive Test Suite for Smart Document Retrieval System
Tests all features: Autocomplete, Text Search, Spatiotemporal Search, Georeference
"""

import requests
import json
from datetime import datetime

# Configuration
API_BASE = "http://localhost:8000"
ES_BASE = "http://localhost:9200"
INDEX_NAME = "smart-docs-ir"

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_header(text):
    print(f"\n{BLUE}{'='*70}")
    print(f"{text}")
    print(f"{'='*70}{RESET}\n")

def print_test(test_name, passed, details=""):
    status = f"{GREEN}✅ PASS{RESET}" if passed else f"{RED}❌ FAIL{RESET}"
    print(f"{status} - {test_name}")
    if details:
        print(f"    {details}")

def print_warning(text):
    print(f"{YELLOW}⚠️  {text}{RESET}")

def print_info(text):
    print(f"{BLUE}ℹ️  {text}{RESET}")


# ============================================================================
# TEST 1: ELASTICSEARCH INDEX CHECK
# ============================================================================
def test_elasticsearch_index():
    print_header("TEST 1: ELASTICSEARCH INDEX")
    
    try:
        # Check if index exists
        response = requests.get(f"{ES_BASE}/{INDEX_NAME}")
        passed = response.status_code == 200
        print_test("Index exists", passed, f"Index: {INDEX_NAME}")
        
        if not passed:
            print_warning("Index does not exist! Run your indexing script first.")
            return False
        
        # Check document count
        response = requests.get(f"{ES_BASE}/{INDEX_NAME}/_count")
        count = response.json().get('count', 0)
        passed = count > 0
        print_test("Documents indexed", passed, f"Count: {count} documents")
        
        if count == 0:
            print_warning("No documents in index! Index your data first.")
            return False
        
        # Check sample document structure
        response = requests.get(f"{ES_BASE}/{INDEX_NAME}/_search?size=1")
        data = response.json()
        if data['hits']['hits']:
            doc = data['hits']['hits'][0]['_source']
            
            # Check required fields
            required_fields = ['title', 'content', 'date', 'geopoint', 
                             'georeferences', 'temporalExpressions']
            for field in required_fields:
                has_field = field in doc
                print_test(f"Field '{field}' exists", has_field)
            
            # Show sample document
            print_info(f"Sample document title: {doc.get('title', 'N/A')}")
            print_info(f"Sample georeferences: {[g['name'] for g in doc.get('georeferences', [])[:3]]}")
        
        return True
        
    except Exception as e:
        print_test("Elasticsearch connection", False, str(e))
        return False


# ============================================================================
# TEST 2: BACKEND API HEALTH
# ============================================================================
def test_backend_health():
    print_header("TEST 2: BACKEND API HEALTH")
    
    try:
        response = requests.get(f"{API_BASE}/", timeout=5)
        passed = response.status_code == 200
        print_test("Backend is running", passed, f"Status: {response.status_code}")
        
        if passed:
            data = response.json()
            print_info(f"API Message: {data.get('message', 'N/A')}")
            print_info(f"Available endpoints: {len(data.get('endpoints', []))}")
        
        return passed
        
    except Exception as e:
        print_test("Backend connection", False, str(e))
        print_warning("Make sure FastAPI is running: uvicorn main:app --reload")
        return False


# ============================================================================
# TEST 3: AUTOCOMPLETE FUNCTIONALITY
# ============================================================================
def test_autocomplete():
    print_header("TEST 3: AUTOCOMPLETE FUNCTIONALITY")
    
    test_cases = [
        ("coc", "Should return titles starting with 'coc' (e.g., cocoa)"),
        ("ban", "Should return titles with 'ban' (e.g., bank, banking)"),
        ("tex", "Should return Texas-related documents"),
        ("oil", "Should return oil-related documents"),
    ]
    
    for query, description in test_cases:
        try:
            response = requests.get(f"{API_BASE}/autocomplete?q={query}")
            data = response.json()
            hits = data.get('hits', {}).get('hits', [])
            passed = len(hits) > 0
            
            titles = [h['_source']['title'][:50] for h in hits[:3]]
            details = f"{description}\n       Found {len(hits)} results"
            if titles:
                details += f"\n       Top result: {titles[0]}"
            
            print_test(f"Autocomplete: '{query}'", passed, details)
            
        except Exception as e:
            print_test(f"Autocomplete: '{query}'", False, str(e))


# ============================================================================
# TEST 4: TEXT SEARCH (Basic)
# ============================================================================
def test_text_search_basic():
    print_header("TEST 4: TEXT SEARCH (Basic)")
    
    test_cases = [
        {
            "query": "cocoa",
            "description": "Search for cocoa documents",
            "expected_min": 1
        },
        {
            "query": "bank",
            "description": "Search for banking documents",
            "expected_min": 1
        },
        {
            "query": "oil financial",
            "description": "Multi-word search",
            "expected_min": 1
        },
        {
            "query": "BAHIA COCOA REVIEW",
            "description": "Exact title match",
            "expected_min": 1
        }
    ]
    
    for test in test_cases:
        try:
            response = requests.get(f"{API_BASE}/search?q={test['query']}")
            data = response.json()
            hits = data.get('hits', {}).get('hits', [])
            passed = len(hits) >= test['expected_min']
            
            details = f"{test['description']}\n       Found {len(hits)} results"
            if hits:
                details += f"\n       Top result: {hits[0]['_source']['title'][:60]}"
                details += f"\n       Score: {hits[0]['_score']:.2f}"
            
            print_test(f"Text search: '{test['query']}'", passed, details)
            
        except Exception as e:
            print_test(f"Text search: '{test['query']}'", False, str(e))


# ============================================================================
# TEST 5: TEXT SEARCH WITH GEOREFERENCE
# ============================================================================
def test_text_search_with_georeference():
    print_header("TEST 5: TEXT SEARCH WITH GEOREFERENCE")
    
    test_cases = [
        {
            "query": "cocoa",
            "georef": "Bahia",
            "description": "Cocoa in Bahia"
        },
        {
            "query": "bank",
            "georef": "USA",
            "description": "Banks in USA"
        },
        {
            "query": "financial",
            "georef": "Cleveland",
            "description": "Financial services in Cleveland"
        },
        {
            "query": "debt",
            "georef": "Brazil",
            "description": "Debt related to Brazil"
        }
    ]
    
    for test in test_cases:
        try:
            response = requests.get(
                f"{API_BASE}/search?q={test['query']}&georef={test['georef']}"
            )
            data = response.json()
            hits = data.get('hits', {}).get('hits', [])
            passed = len(hits) > 0
            
            details = f"{test['description']}\n       Found {len(hits)} results"
            if hits:
                top_hit = hits[0]['_source']
                details += f"\n       Top result: {top_hit['title'][:60]}"
                georefs = [g['name'] for g in top_hit.get('georeferences', [])[:3]]
                details += f"\n       Georeferences: {georefs}"
            
            print_test(f"Georef search: {test['georef']}", passed, details)
            
        except Exception as e:
            print_test(f"Georef search: {test['georef']}", False, str(e))


# ============================================================================
# TEST 6: TEXT SEARCH WITH LOCATION
# ============================================================================
def test_text_search_with_location():
    print_header("TEST 6: TEXT SEARCH WITH LOCATION (LAT/LON)")
    
    test_cases = [
        {
            "query": "cocoa",
            "lat": -12.9822,
            "lon": -38.4812,
            "description": "Cocoa near Salvador, Bahia"
        },
        {
            "query": "bank",
            "lat": 29.7589,
            "lon": -95.3677,
            "description": "Banks near Houston, Texas"
        }
    ]
    
    for test in test_cases:
        try:
            response = requests.get(
                f"{API_BASE}/search?q={test['query']}&lat={test['lat']}&lon={test['lon']}"
            )
            data = response.json()
            hits = data.get('hits', {}).get('hits', [])
            passed = len(hits) > 0
            
            details = f"{test['description']}\n       Found {len(hits)} results"
            if hits:
                top_hit = hits[0]['_source']
                details += f"\n       Top result: {top_hit['title'][:60]}"
                if 'geopoint' in top_hit:
                    gp = top_hit['geopoint']
                    details += f"\n       Location: ({gp['lat']:.2f}, {gp['lon']:.2f})"
            
            print_test(f"Location search: ({test['lat']}, {test['lon']})", passed, details)
            
        except Exception as e:
            print_test(f"Location search", False, str(e))


# ============================================================================
# TEST 7: SPATIOTEMPORAL SEARCH (Full)
# ============================================================================
def test_spatiotemporal_search():
    print_header("TEST 7: SPATIOTEMPORAL SEARCH")
    
    test_cases = [
        {
            "query": "cocoa",
            "start": "1987-02-01",
            "end": "1987-02-28",
            "lat": -12.98,
            "lon": -38.48,
            "distance": "1000km",
            "georef": "Bahia",
            "description": "Cocoa in Bahia, February 1987"
        },
        {
            "query": "bank",
            "start": "1987-02-20",
            "end": "1987-02-28",
            "lat": 29.76,
            "lon": -95.37,
            "distance": "1000km",
            "georef": "USA",
            "description": "Banking in USA, late February 1987"
        },
        {
            "query": "oil",
            "start": "1987-01-01",
            "end": "1987-12-31",
            "lat": 41.50,
            "lon": -81.69,
            "distance": "500km",
            "georef": "Cleveland",
            "description": "Oil industry in Cleveland, 1987"
        },
        {
            "query": "debt",
            "start": "1987-01-01",
            "end": "1987-03-31",
            "lat": -20.54,
            "lon": -48.59,
            "distance": "2000km",
            "georef": "Brazil",
            "description": "Debt crisis in Brazil, Q1 1987"
        }
    ]
    
    for test in test_cases:
        try:
            params = {
                "q": test["query"],
                "start": test["start"],
                "end": test["end"],
                "lat": test["lat"],
                "lon": test["lon"],
                "distance": test["distance"],
                "georef": test["georef"]
            }
            
            response = requests.get(f"{API_BASE}/spatiotemporal", params=params)
            data = response.json()
            hits = data.get('hits', {}).get('hits', [])
            passed = len(hits) > 0
            
            details = f"{test['description']}\n       Found {len(hits)} results"
            if hits:
                top_hit = hits[0]['_source']
                details += f"\n       Top result: {top_hit['title'][:60]}"
                details += f"\n       Date: {top_hit.get('date', 'N/A')[:10]}"
                georefs = [g['name'] for g in top_hit.get('georeferences', [])[:3]]
                details += f"\n       Georeferences: {georefs}"
            
            print_test(f"Spatiotemporal: {test['georef']}", passed, details)
            
        except Exception as e:
            print_test(f"Spatiotemporal: {test['georef']}", False, str(e))


# ============================================================================
# TEST 8: SPATIOTEMPORAL WITHOUT LOCATION (Georeference only)
# ============================================================================
def test_spatiotemporal_georef_only():
    print_header("TEST 8: SPATIOTEMPORAL (Georeference Only, No Location)")
    
    test_cases = [
        {
            "query": "cocoa",
            "start": "1987-01-01",
            "end": "1987-12-31",
            "georef": "Bahia",
            "description": "Cocoa in Bahia using georeference only"
        },
        {
            "query": "bank",
            "start": "1987-02-01",
            "end": "1987-03-01",
            "georef": "Houston",
            "description": "Banks in Houston using georeference only"
        }
    ]
    
    print_info("Testing spatiotemporal with default coordinates (location not provided)")
    
    for test in test_cases:
        try:
            params = {
                "q": test["query"],
                "start": test["start"],
                "end": test["end"],
                "lat": 32.2211,  # Default: Nablus
                "lon": 35.2544,
                "distance": "20000km",  # Very large to not filter anything
                "georef": test["georef"]
            }
            
            response = requests.get(f"{API_BASE}/spatiotemporal", params=params)
            data = response.json()
            hits = data.get('hits', {}).get('hits', [])
            passed = len(hits) > 0
            
            details = f"{test['description']}\n       Found {len(hits)} results (georeference-based)"
            if hits:
                top_hit = hits[0]['_source']
                details += f"\n       Top result: {top_hit['title'][:60]}"
            
            print_test(f"Georef-only: {test['georef']}", passed, details)
            
        except Exception as e:
            print_test(f"Georef-only: {test['georef']}", False, str(e))


# ============================================================================
# TEST 9: EDGE CASES AND ERROR HANDLING
# ============================================================================
def test_edge_cases():
    print_header("TEST 9: EDGE CASES AND ERROR HANDLING")
    
    # Test 1: Empty query
    try:
        response = requests.get(f"{API_BASE}/search?q=")
        passed = response.status_code in [200, 422]
        print_test("Empty query handling", passed, f"Status: {response.status_code}")
    except Exception as e:
        print_test("Empty query handling", False, str(e))
    
    # Test 2: Very short autocomplete (< 3 chars)
    try:
        response = requests.get(f"{API_BASE}/autocomplete?q=ab")
        passed = response.status_code == 422
        print_test("Short autocomplete rejection", passed, "Should reject queries < 3 chars")
    except Exception as e:
        print_test("Short autocomplete rejection", False, str(e))
    
    # Test 3: Non-existent georeference
    try:
        response = requests.get(f"{API_BASE}/search?q=test&georef=NonExistentPlace12345")
        data = response.json()
        # Should return results (even if no georef match, text search should work)
        passed = response.status_code == 200
        print_test("Non-existent georeference", passed, "Should handle gracefully")
    except Exception as e:
        print_test("Non-existent georeference", False, str(e))
    
    # Test 4: Invalid date range
    try:
        response = requests.get(
            f"{API_BASE}/spatiotemporal?q=test&start=2025-01-01&end=2020-01-01&lat=0&lon=0&distance=100km&georef=test"
        )
        passed = response.status_code in [200, 400, 422]
        print_test("Invalid date range", passed, f"Status: {response.status_code}")
    except Exception as e:
        print_test("Invalid date range", False, str(e))


# ============================================================================
# TEST 10: RESPONSE STRUCTURE VALIDATION
# ============================================================================
def test_response_structure():
    print_header("TEST 10: RESPONSE STRUCTURE VALIDATION")
    
    try:
        response = requests.get(f"{API_BASE}/search?q=cocoa")
        data = response.json()
        
        # Check Elasticsearch response structure
        has_hits = 'hits' in data
        print_test("Response has 'hits' field", has_hits)
        
        if has_hits and data['hits']['hits']:
            hit = data['hits']['hits'][0]
            
            # Check hit structure
            print_test("Hit has '_score'", '_score' in hit)
            print_test("Hit has '_source'", '_source' in hit)
            
            source = hit['_source']
            
            # Check required fields in source
            required_fields = {
                'title': 'Title field',
                'content': 'Content field',
                'date': 'Date field',
                'geopoint': 'Geopoint field',
                'georeferences': 'Georeferences array',
                'temporalExpressions': 'Temporal expressions array'
            }
            
            for field, description in required_fields.items():
                has_field = field in source
                print_test(description, has_field)
            
            # Check nested structures
            if 'georeferences' in source and source['georeferences']:
                georef = source['georeferences'][0]
                print_test("Georeference has 'name'", 'name' in georef)
                print_test("Georeference has 'key'", 'key' in georef)
            
            if 'temporalExpressions' in source and source['temporalExpressions']:
                temporal = source['temporalExpressions'][0]
                print_test("Temporal has 'text'", 'text' in temporal)
                print_test("Temporal has 'normalized'", 'normalized' in temporal)
        
    except Exception as e:
        print_test("Response structure validation", False, str(e))


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================
def run_all_tests():
    print(f"{BLUE}")
    print("╔════════════════════════════════════════════════════════════════════╗")
    print("║    SMART DOCUMENT RETRIEVAL SYSTEM - COMPREHENSIVE TEST SUITE     ║")
    print("╚════════════════════════════════════════════════════════════════════╝")
    print(f"{RESET}")
    
    print_info(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print_info(f"API Base URL: {API_BASE}")
    print_info(f"Elasticsearch URL: {ES_BASE}")
    print_info(f"Index Name: {INDEX_NAME}")
    
    # Run all tests
    tests = [
        ("Elasticsearch Index", test_elasticsearch_index),
        ("Backend API Health", test_backend_health),
        ("Autocomplete", test_autocomplete),
        ("Text Search (Basic)", test_text_search_basic),
        ("Text Search with Georeference", test_text_search_with_georeference),
        ("Text Search with Location", test_text_search_with_location),
        ("Spatiotemporal Search", test_spatiotemporal_search),
        ("Spatiotemporal (Georef Only)", test_spatiotemporal_georef_only),
        ("Edge Cases", test_edge_cases),
        ("Response Structure", test_response_structure)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"{RED}Error running {test_name}: {e}{RESET}")
            results.append((test_name, False))
    
    # Summary
    print_header("TEST SUMMARY")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = f"{GREEN}✅ PASS{RESET}" if result else f"{RED}❌ FAIL{RESET}"
        print(f"{status} - {test_name}")
    
    print(f"\n{BLUE}{'='*70}")
    print(f"TOTAL: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    print(f"{'='*70}{RESET}\n")
    
    if passed == total:
        print(f"{GREEN}🎉 ALL TESTS PASSED! Your system is working correctly!{RESET}")
    else:
        print(f"{YELLOW}⚠️  Some tests failed. Please review the output above.{RESET}")


if __name__ == "__main__":
    run_all_tests()