"""
Dealer Studio - Comprehensive Authenticated GET Runner
------------------------------------------------------
Tests all GET APIs for Dealership 'denza-melbourne' (ID: 2606) using session auth,
and saves full response data to d:\\new-proj\\results.json.
"""

import os
import json
import httpx
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://dashboard.dealerstudio.com.au"
DEALERSHIP_SLUG = os.getenv("DEALERSTUDIO_DEALERSHIP_SLUG", "denza-melbourne")
DEALERSHIP_ID = os.getenv("DEALERSTUDIO_DEALERSHIP_ID", "2606")
CSRF_TOKEN = os.getenv("DEALERSTUDIO_CSRF_TOKEN", "")
COOKIE = os.getenv("DEALERSTUDIO_COOKIE", "")

HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": f"{BASE_URL}/dealerships/{DEALERSHIP_SLUG}/lead_clusters/pipelines/all",
    "X-CSRF-Token": CSRF_TOKEN,
    "Cookie": COOKIE,
}

ENDPOINTS = [
    {
        "category": "Lead Clusters",
        "name": "Search Lead Clusters (Postgres Search)",
        "url": f"{BASE_URL}/dealerships/{DEALERSHIP_SLUG}/lead_clusters/postgres_search",
        "params": {
            "rows": 10,
            "active_lead_clusters_filter": "true",
            "query": "",
            "pipeline_id": "all",
            "sort_by": "created_at_desc",
            "page": 1,
            "first": 0
        }
    },
    {
        "category": "Lead Clusters",
        "name": "Get Specific Lead Cluster Details",
        "url": f"{BASE_URL}/dealerships/{DEALERSHIP_SLUG}/lead_clusters/2848219",
        "params": {}
    },
    {
        "category": "Vehicles & Inventory",
        "name": "List Dealership Cars",
        "url": f"{BASE_URL}/dealerships/{DEALERSHIP_SLUG}/cars",
        "params": {"page": 1, "per_page": 5}
    },
    {
        "category": "Vehicles & Inventory",
        "name": "Get Specific Car Details (ID: 1672689)",
        "url": f"{BASE_URL}/dealerships/{DEALERSHIP_SLUG}/cars/1672689",
        "params": {}
    },
    {
        "category": "Contacts",
        "name": "Get Contact Details (ID: 2636665)",
        "url": f"{BASE_URL}/dealerships/{DEALERSHIP_SLUG}/contacts/2636665",
        "params": {}
    },
    {
        "category": "Dealership Structure",
        "name": "List Dealership Locations",
        "url": f"{BASE_URL}/dealerships/{DEALERSHIP_SLUG}/locations",
        "params": {}
    },
    {
        "category": "Dealership Structure",
        "name": "List Dealership Users / Staff",
        "url": f"{BASE_URL}/dealerships/{DEALERSHIP_SLUG}/users",
        "params": {}
    },
    {
        "category": "API v1 REST",
        "name": "API v1 Cars List",
        "url": f"{BASE_URL}/api/v1/cars",
        "params": {"page": 1, "per_page": 5}
    }
]

def main():
    results = {}
    print("=" * 70)
    print(f"DEALER STUDIO LIVE API AUDIT & RUNNER")
    print(f"Dealership: {DEALERSHIP_SLUG} (ID: {DEALERSHIP_ID})")
    print("=" * 70)

    with httpx.Client(timeout=15.0, follow_redirects=True) as client:
        for idx, ep in enumerate(ENDPOINTS, 1):
            category = ep["category"]
            name = ep["name"]
            url = ep["url"]
            params = ep.get("params", {})

            print(f"[{idx}/{len(ENDPOINTS)}] Checking {name}...")

            entry = {
                "category": category,
                "url": url,
                "params": params,
                "status_code": None,
                "data": None,
                "error": None
            }

            try:
                r = client.get(url, headers=HEADERS, params=params)
                entry["status_code"] = r.status_code
                print(f"    --> Status: {r.status_code} {r.reason_phrase}")

                try:
                    data = r.json()
                    entry["data"] = data
                    if isinstance(data, list):
                        print(f"    --> Received list of {len(data)} items")
                    elif isinstance(data, dict):
                        print(f"    --> Received object with keys: {list(data.keys())[:5]}")
                except Exception:
                    entry["raw_preview"] = r.text[:200]
                    print(f"    --> Received non-JSON response ({len(r.text)} bytes)")

            except Exception as exc:
                entry["error"] = str(exc)
                print(f"    --> Error: {exc}")

            results[name] = entry

    output_path = os.path.join(os.path.dirname(__file__), "results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n[OK] All results saved successfully to {output_path}")

if __name__ == "__main__":
    main()
