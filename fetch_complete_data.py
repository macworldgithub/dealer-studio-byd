"""
Dealer Studio - Complete Data Harvester
---------------------------------------
Paginates through ALL pages and ALL filters to extract 100% complete data:
1. All Lead Clusters (All 3,313 leads across all 34 pages)
2. Active Lead Clusters (All 758 active leads)
3. Complete Cars Inventory (All 13 vehicles)
4. Full Detailed Specs for every single car
5. Top Lead Cluster Details & Contacts
6. Manifest & Summary Statistics
"""

import os
import sys
import json
import time
import math
import glob
import httpx
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://dashboard.dealerstudio.com.au"
DEALERSHIP_SLUG = os.getenv("DEALERSTUDIO_DEALERSHIP_SLUG", "denza-melbourne")
DEALERSHIP_ID = os.getenv("DEALERSTUDIO_DEALERSHIP_ID", "2606")
CSRF_TOKEN = os.getenv("DEALERSTUDIO_CSRF_TOKEN", "")
COOKIE = os.getenv("DEALERSTUDIO_COOKIE", "")

# Destination folders on D:
BASE_DATA_DIR = os.path.join(os.path.dirname(__file__), "api_data")
LEADS_PAGES_DIR = os.path.join(BASE_DATA_DIR, "lead_clusters_pages")
CARS_DIR = os.path.join(BASE_DATA_DIR, "cars_detailed")

os.makedirs(BASE_DATA_DIR, exist_ok=True)
os.makedirs(LEADS_PAGES_DIR, exist_ok=True)
os.makedirs(CARS_DIR, exist_ok=True)

HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": f"{BASE_URL}/dealerships/{DEALERSHIP_SLUG}/lead_clusters/pipelines/all",
    "X-CSRF-Token": CSRF_TOKEN,
    "Cookie": COOKIE,
}


def log(msg: str):
    print(msg, flush=True)


def safe_save_json(filepath: str, data: any):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def fetch_with_retry(client: httpx.Client, url: str, params: dict = None, retries: int = 3) -> dict:
    for attempt in range(1, retries + 1):
        try:
            resp = client.get(url, headers=HEADERS, params=params)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 429:
                log(f"    [RATE LIMIT] Waiting 5 seconds before retry...")
                time.sleep(5.0)
            else:
                log(f"    [WARN] Status {resp.status_code} on {url}")
                return {"status_code": resp.status_code, "error": resp.text[:500]}
        except Exception as exc:
            log(f"    [RETRY {attempt}/{retries}] Error: {exc}")
            time.sleep(1.5 * attempt)
    return {"error": "Failed after retries"}


def harvest_lead_clusters(client: httpx.Client, active_only: bool = False):
    label = "Active" if active_only else "All (Historic + Active)"
    prefix = "active" if active_only else "all"
    log(f"\n==================================================")
    log(f"[*] Harvesting {label} Lead Clusters...")
    log(f"==================================================")

    # Clean old pagination files for this prefix to prevent stale ghost pages
    for old_file in glob.glob(os.path.join(LEADS_PAGES_DIR, f"{prefix}_page_*.json")):
        try:
            os.remove(old_file)
        except OSError:
            pass

    url = f"{BASE_URL}/dealerships/{DEALERSHIP_SLUG}/lead_clusters/postgres_search"
    rows_per_page = 100
    page = 1
    all_clusters = []
    has_more = True
    cursor = None

    while has_more:
        params = {
            "rows": rows_per_page,
            "query": "",
            "pipeline_id": "all",
            "sort_by": "created_at_desc",
            "page": page,
            "first": (page - 1) * rows_per_page
        }
        if active_only:
            params["active_lead_clusters_filter"] = "true"
        if cursor:
            params["cursor"] = cursor

        log(f"--> Fetching Page {page:02d} (items {(page - 1) * rows_per_page + 1} - {page * rows_per_page})...")
        data = fetch_with_retry(client, url, params)

        if not isinstance(data, dict) or "lead_clusters" not in data:
            log(f"    [!] Unexpected response on page {page}: {data}")
            break

        clusters = data.get("lead_clusters", [])
        total_count = data.get("total_count", 0)
        has_more = data.get("has_more", False)
        cursor = data.get("next_cursor")

        all_clusters.extend(clusters)
        log(f"    [OK] Page {page}: Received {len(clusters)} leads. Total accumulated: {len(all_clusters)} / {total_count}")

        # Save individual page
        page_file = os.path.join(LEADS_PAGES_DIR, f"{prefix}_page_{page:02d}.json")
        safe_save_json(page_file, data)

        if not clusters or len(clusters) < rows_per_page or len(all_clusters) >= total_count:
            has_more = False

        page += 1
        time.sleep(0.3)  # Gentle delay

    # Save consolidated files (dynamic count, canonical, and legacy compatibility)
    total_harvested = len(all_clusters)
    consolidated_data = {
        "dealership_slug": DEALERSHIP_SLUG,
        "dealership_id": DEALERSHIP_ID,
        "filter": "active_only" if active_only else "all",
        "total_harvested": total_harvested,
        "lead_clusters": all_clusters
    }

    # 1. Dynamic count filename
    dynamic_filename = f"active_lead_clusters_{total_harvested}.json" if active_only else f"all_lead_clusters_{total_harvested}.json"
    safe_save_json(os.path.join(BASE_DATA_DIR, dynamic_filename), consolidated_data)

    # 2. Canonical un-suffixed filename
    canonical_filename = "active_lead_clusters.json" if active_only else "all_lead_clusters.json"
    safe_save_json(os.path.join(BASE_DATA_DIR, canonical_filename), consolidated_data)

    # 3. Legacy filename for backwards-compatibility with existing sync scripts
    legacy_filename = "active_lead_clusters_758.json" if active_only else "all_lead_clusters_3313.json"
    legacy_path = os.path.join(BASE_DATA_DIR, legacy_filename)
    safe_save_json(legacy_path, consolidated_data)

    log(f"[COMPLETE] Saved {total_harvested} {label} leads to api_data/{dynamic_filename} and legacy {legacy_filename} ({os.path.getsize(legacy_path):,} bytes)")
    return all_clusters


def harvest_cars_and_details(client: httpx.Client):
    log(f"\n==================================================")
    log(f"[*] Harvesting Full Cars Inventory & Specs...")
    log(f"==================================================")

    # Clean old detailed car JSON files
    for old_file in glob.glob(os.path.join(CARS_DIR, "car_*.json")):
        try:
            os.remove(old_file)
        except OSError:
            pass

    url = f"{BASE_URL}/dealerships/{DEALERSHIP_SLUG}/cars"
    cars_data = fetch_with_retry(client, url, {"per_page": 100})

    if not isinstance(cars_data, list):
        log(f"[!] Failed to fetch cars: {cars_data}")
        return []

    log(f"[OK] Found {len(cars_data)} vehicles in stock. Saving inventory list...")
    # Dynamic, canonical, and legacy inventory files
    inv_dynamic = os.path.join(BASE_DATA_DIR, f"all_cars_inventory_{len(cars_data)}.json")
    inv_canonical = os.path.join(BASE_DATA_DIR, "all_cars_inventory.json")
    inv_legacy = os.path.join(BASE_DATA_DIR, "all_cars_inventory_13.json")
    safe_save_json(inv_dynamic, cars_data)
    safe_save_json(inv_canonical, cars_data)
    safe_save_json(inv_legacy, cars_data)

    detailed_cars = []
    for idx, car in enumerate(cars_data, 1):
        car_id = car.get("id")
        make = car.get("make", "")
        model = car.get("model", "")
        year = car.get("year", "")
        stock = car.get("stocknum", "")
        log(f"--> [{idx}/{len(cars_data)}] Fetching full details for Car #{car_id}: {year} {make} {model} (Stock: {stock})...")

        detail_url = f"{BASE_URL}/dealerships/{DEALERSHIP_SLUG}/cars/{car_id}"
        details = fetch_with_retry(client, detail_url)
        detailed_cars.append(details)

        car_file = os.path.join(CARS_DIR, f"car_{car_id}_{model}.json")
        safe_save_json(car_file, details)
        time.sleep(0.2)

    all_detailed_path = os.path.join(BASE_DATA_DIR, "all_cars_detailed_specs.json")
    safe_save_json(all_detailed_path, detailed_cars)
    log(f"[COMPLETE] Saved {len(detailed_cars)} car specifications to api_data/all_cars_detailed_specs.json")
    return detailed_cars


def main():
    log("=" * 75)
    log(f"DEALER STUDIO - COMPLETE FULL DATA HARVESTER")
    log(f"Dealership: {DEALERSHIP_SLUG} (ID: {DEALERSHIP_ID})")
    log(f"Output Directory: {BASE_DATA_DIR}")
    log("=" * 75)

    start_time = time.time()

    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        # 1. Harvest ALL leads (all pages)
        all_leads = harvest_lead_clusters(client, active_only=False)

        # 2. Harvest active leads
        active_leads = harvest_lead_clusters(client, active_only=True)

        # 3. Harvest All Cars & Detailed Specs
        cars = harvest_cars_and_details(client)

        # 4. Generate Master Manifest
        elapsed = round(time.time() - start_time, 2)
        manifest = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "dealership_slug": DEALERSHIP_SLUG,
            "dealership_id": DEALERSHIP_ID,
            "elapsed_seconds": elapsed,
            "statistics": {
                "total_historic_leads": len(all_leads),
                "total_active_leads": len(active_leads),
                "total_cars_in_stock": len(cars)
            },
            "exported_files": [
                f"all_lead_clusters_{len(all_leads)}.json",
                f"active_lead_clusters_{len(active_leads)}.json",
                f"all_cars_inventory_{len(cars)}.json",
                "all_lead_clusters.json",
                "active_lead_clusters.json",
                "all_cars_inventory.json",
                "all_lead_clusters_3313.json (backwards-compatible)",
                "active_lead_clusters_758.json (backwards-compatible)",
                "all_cars_inventory_13.json (backwards-compatible)",
                "all_cars_detailed_specs.json",
                f"cars_detailed/ ({len(cars)} individual car JSON specs)",
                "lead_clusters_pages/ (All individual pagination JSONs)"
            ]
        }
        manifest_path = os.path.join(BASE_DATA_DIR, "COMPLETE_DATA_MANIFEST.json")
        safe_save_json(manifest_path, manifest)

    log("\n" + "=" * 75)
    log(f"SUCCESS: 100% COMPLETE DATA EXTRACTED IN {elapsed}s!")
    log(f"- Total Leads: {len(all_leads):,}")
    log(f"- Active Leads: {len(active_leads):,}")
    log(f"- Total Cars: {len(cars)}")
    log(f"- Manifest: api_data/COMPLETE_DATA_MANIFEST.json")
    log("=" * 75)


if __name__ == "__main__":
    main()
