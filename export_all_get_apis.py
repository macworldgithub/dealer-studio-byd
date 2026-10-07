"""
Dealer Studio - Export All GET APIs to Separate JSON Files
----------------------------------------------------------
Executes all GET endpoints using active credentials from .env
and saves each response into a separate .json file in the 'api_data' folder.
"""

import os
import json
import logging
from typing import Dict, Any
import httpx
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://dashboard.dealerstudio.com.au"
DEALERSHIP_SLUG = os.getenv("DEALERSTUDIO_DEALERSHIP_SLUG", "denza-melbourne")
DEALERSHIP_ID = os.getenv("DEALERSTUDIO_DEALERSHIP_ID", "2606")
CSRF_TOKEN = os.getenv("DEALERSTUDIO_CSRF_TOKEN", "")
COOKIE = os.getenv("DEALERSTUDIO_COOKIE", "")
API_KEY = os.getenv("DEALERSTUDIO_API_KEY", "")

# Directory where individual JSON files will be stored
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "api_data")
os.makedirs(OUTPUT_DIR, exist_ok=True)

HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": f"{BASE_URL}/dealerships/{DEALERSHIP_SLUG}/lead_clusters/pipelines/all",
    "X-CSRF-Token": CSRF_TOKEN,
    "Cookie": COOKIE,
}

if API_KEY:
    HEADERS["Authorization"] = f"Bearer {API_KEY}"


def save_json(filename: str, data: Any):
    filepath = os.path.join(OUTPUT_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"    [SAVED] -> api_data/{filename} ({os.path.getsize(filepath):,} bytes)")


def fetch_and_save(client: httpx.Client, name: str, url: str, filename: str, params: Dict[str, Any] = None):
    print(f"\n[*] Fetching: {name}")
    print(f"    URL: {url}")
    if params:
        print(f"    Params: {params}")

    try:
        resp = client.get(url, headers=HEADERS, params=params)
        print(f"    Status: {resp.status_code} {resp.reason_phrase}")

        try:
            data = resp.json()
        except Exception:
            data = {
                "status_code": resp.status_code,
                "raw_text": resp.text[:2000],
                "content_type": resp.headers.get("content-type")
            }

        save_json(filename, data)
        return resp.status_code, data
    except Exception as e:
        print(f"    [ERROR]: {e}")
        error_payload = {"error": str(e), "url": url}
        save_json(filename, error_payload)
        return None, error_payload


def run_all_exports():
    print("=" * 75)
    print(f"DEALER STUDIO API EXPORTER")
    print(f"Target Dealership: {DEALERSHIP_SLUG} (ID: {DEALERSHIP_ID})")
    print(f"Output Directory: {OUTPUT_DIR}")
    print("=" * 75)

    summary_manifest = {
        "dealership_slug": DEALERSHIP_SLUG,
        "dealership_id": DEALERSHIP_ID,
        "files_generated": []
    }

    with httpx.Client(timeout=25.0, follow_redirects=True) as client:
        # 1. Lead Clusters Postgres Search
        status, search_data = fetch_and_save(
            client=client,
            name="Lead Clusters (Postgres Search)",
            url=f"{BASE_URL}/dealerships/{DEALERSHIP_SLUG}/lead_clusters/postgres_search",
            filename="1_lead_clusters_search.json",
            params={
                "rows": 25,
                "active_lead_clusters_filter": "true",
                "query": "",
                "pipeline_id": "all",
                "sort_by": "created_at_desc",
                "page": 1,
                "first": 0
            }
        )
        summary_manifest["files_generated"].append({
            "file": "1_lead_clusters_search.json",
            "endpoint": "/lead_clusters/postgres_search",
            "status": status,
            "total_count": search_data.get("total_count") if isinstance(search_data, dict) else None
        })

        # Extract top lead cluster IDs & contact IDs if available
        sample_cluster_id = None
        sample_contact_id = None
        if isinstance(search_data, dict) and "lead_clusters" in search_data:
            clusters = search_data["lead_clusters"]
            if clusters and isinstance(clusters, list):
                sample_cluster_id = clusters[0].get("id")
                sample_contact_id = clusters[0].get("contact_id")

        sample_cluster_id = sample_cluster_id or 2848219
        sample_contact_id = sample_contact_id or 2636665

        # 2. Specific Lead Cluster Details
        status, _ = fetch_and_save(
            client=client,
            name=f"Lead Cluster Details (ID: {sample_cluster_id})",
            url=f"{BASE_URL}/dealerships/{DEALERSHIP_SLUG}/lead_clusters/{sample_cluster_id}",
            filename=f"2_lead_cluster_{sample_cluster_id}_details.json"
        )
        summary_manifest["files_generated"].append({
            "file": f"2_lead_cluster_{sample_cluster_id}_details.json",
            "endpoint": f"/lead_clusters/{sample_cluster_id}",
            "status": status
        })

        # 3. Cars / Vehicle Inventory List
        status, cars_data = fetch_and_save(
            client=client,
            name="Cars / Vehicle Inventory List",
            url=f"{BASE_URL}/dealerships/{DEALERSHIP_SLUG}/cars",
            filename="3_cars_inventory.json",
            params={"page": 1, "per_page": 25}
        )
        summary_manifest["files_generated"].append({
            "file": "3_cars_inventory.json",
            "endpoint": f"/dealerships/{DEALERSHIP_SLUG}/cars",
            "status": status,
            "items_count": len(cars_data) if isinstance(cars_data, list) else None
        })

        # Extract sample car ID
        sample_car_id = 1672689
        if isinstance(cars_data, list) and len(cars_data) > 0:
            sample_car_id = cars_data[0].get("id", sample_car_id)

        # 4. Specific Car Details
        status, _ = fetch_and_save(
            client=client,
            name=f"Car Details (ID: {sample_car_id})",
            url=f"{BASE_URL}/dealerships/{DEALERSHIP_SLUG}/cars/{sample_car_id}",
            filename=f"4_car_{sample_car_id}_details.json"
        )
        summary_manifest["files_generated"].append({
            "file": f"4_car_{sample_car_id}_details.json",
            "endpoint": f"/dealerships/{DEALERSHIP_SLUG}/cars/{sample_car_id}",
            "status": status
        })

        # 5. Contact Details
        status, _ = fetch_and_save(
            client=client,
            name=f"Contact Details (ID: {sample_contact_id})",
            url=f"{BASE_URL}/dealerships/{DEALERSHIP_SLUG}/contacts/{sample_contact_id}",
            filename=f"5_contact_{sample_contact_id}_details.json"
        )
        summary_manifest["files_generated"].append({
            "file": f"5_contact_{sample_contact_id}_details.json",
            "endpoint": f"/dealerships/{DEALERSHIP_SLUG}/contacts/{sample_contact_id}",
            "status": status
        })

        # 6. Dealership Users / Staff
        status, users_data = fetch_and_save(
            client=client,
            name="Dealership Users / Staff",
            url=f"{BASE_URL}/dealerships/{DEALERSHIP_SLUG}/users",
            filename="6_dealership_users.json"
        )
        summary_manifest["files_generated"].append({
            "file": "6_dealership_users.json",
            "endpoint": f"/dealerships/{DEALERSHIP_SLUG}/users",
            "status": status
        })

        # 7. API v1 Cars Endpoint
        status, _ = fetch_and_save(
            client=client,
            name="API v1 Public Cars Endpoint",
            url=f"{BASE_URL}/api/v1/cars",
            filename="7_api_v1_cars.json",
            params={"page": 1, "per_page": 10}
        )
        summary_manifest["files_generated"].append({
            "file": "7_api_v1_cars.json",
            "endpoint": "/api/v1/cars",
            "status": status
        })

        # 8. Dealership Service Booking Workshops
        status, _ = fetch_and_save(
            client=client,
            name="Service Booking Workshops",
            url=f"{BASE_URL}/api/v1/dealerships/{DEALERSHIP_SLUG}/service_booking/workshops",
            filename="8_service_booking_workshops.json"
        )
        summary_manifest["files_generated"].append({
            "file": "8_service_booking_workshops.json",
            "endpoint": f"/api/v1/dealerships/{DEALERSHIP_SLUG}/service_booking/workshops",
            "status": status
        })

        # 9. Dealership Valuation Settings
        status, _ = fetch_and_save(
            client=client,
            name="Valuation Settings",
            url=f"{BASE_URL}/api/v1/dealerships/{DEALERSHIP_ID}/valuations/settings",
            filename="9_valuations_settings.json"
        )
        summary_manifest["files_generated"].append({
            "file": "9_valuations_settings.json",
            "endpoint": f"/api/v1/dealerships/{DEALERSHIP_ID}/valuations/settings",
            "status": status
        })

        # Save manifest
        save_json("0_manifest.json", summary_manifest)

    print("\n" + "=" * 75)
    print("ALL GET APIS EXECUTED & STORED IN SEPARATE JSON FILES!")
    print(f"Location: {OUTPUT_DIR}")
    print("=" * 75)


if __name__ == "__main__":
    run_all_exports()
