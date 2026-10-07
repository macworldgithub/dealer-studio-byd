# Dealer Studio Complete Data Harvester & API Toolkit

Complete dataset extracted for Dealership **DENZA Melbourne** (`denza-melbourne`, ID: `2606`) from `dashboard.dealerstudio.com.au`.

---

## Complete Data Harvest Summary

| Resource | Count | Master File | Detailed Files Folder |
| :--- | :---: | :--- | :--- |
| **All Historic & Active Leads** | **3,313** | [all_lead_clusters_3313.json](file:///d:/new-proj/api_data/all_lead_clusters_3313.json) (7.9 MB) | [lead_clusters_pages/](file:///d:/new-proj/api_data/lead_clusters_pages/) (34 pages) |
| **Active Pipeline Leads** | **758** | [active_lead_clusters_758.json](file:///d:/new-proj/api_data/active_lead_clusters_758.json) (1.8 MB) | [lead_clusters_pages/](file:///d:/new-proj/api_data/lead_clusters_pages/) (8 pages) |
| **Complete Car Inventory** | **13** | [all_cars_inventory_13.json](file:///d:/new-proj/api_data/all_cars_inventory_13.json) (223 KB) | — |
| **Full Car Specifications** | **13** | [all_cars_detailed_specs.json](file:///d:/new-proj/api_data/all_cars_detailed_specs.json) (223 KB) | [cars_detailed/](file:///d:/new-proj/api_data/cars_detailed/) (13 vehicle JSONs) |
| **Manifest** | — | [COMPLETE_DATA_MANIFEST.json](file:///d:/new-proj/api_data/COMPLETE_DATA_MANIFEST.json) | Full execution statistics |

---

## Directory Structure

```text
d:\new-proj\api_data\
├── COMPLETE_DATA_MANIFEST.json      <- Harvest metadata & statistics
├── all_lead_clusters_3313.json      <- All 3,313 leads (all pages combined)
├── active_lead_clusters_758.json    <- All 758 active leads
├── all_cars_inventory_13.json       <- Complete 13 vehicles in stock
├── all_cars_detailed_specs.json     <- Full vehicle specs, options & pricing
├── lead_clusters_pages/             <- 42 individual pagination JSON files:
│   ├── all_page_01.json ... all_page_34.json
│   └── active_page_01.json ... active_page_08.json
└── cars_detailed/                   <- 13 individual car JSON files:
    ├── car_1620089_B5.json
    ├── car_1672689_B8.json
    └── ...
```

---

## Scripts Available

1. **Complete Harvest (All Pages & Filters)**:
   ```powershell
   python fetch_complete_data.py
   ```
2. **Individual GET API Runner**:
   ```powershell
   python export_all_get_apis.py
   ```
3. **Python Client Library**:
   ```powershell
   python dealerstudio_client.py
   ```
