# Dealer Studio Complete Data Harvester & API Toolkit

Complete dataset extracted for Dealership **DENZA Melbourne** (`denza-melbourne`, ID: `2606`) from `dashboard.dealerstudio.com.au`.

---

## Complete Data Harvest Summary

| Resource | Count | Master File | Detailed Files Folder |
| :--- | :---: | :--- | :--- |
| **All Historic & Active Leads** | **3,369** | [all_lead_clusters_3369.json](file:///d:/sales-floor/denza-data/dealer-studio-byd/api_data/all_lead_clusters_3369.json) (8.2 MB) | [lead_clusters_pages/](file:///d:/sales-floor/denza-data/dealer-studio-byd/api_data/lead_clusters_pages/) (34 pages) |
| **Active Pipeline Leads** | **695** | [active_lead_clusters_695.json](file:///d:/sales-floor/denza-data/dealer-studio-byd/api_data/active_lead_clusters_695.json) (1.7 MB) | [lead_clusters_pages/](file:///d:/sales-floor/denza-data/dealer-studio-byd/api_data/lead_clusters_pages/) (7 pages) |
| **Complete Car Inventory** | **12** | [all_cars_inventory_12.json](file:///d:/sales-floor/denza-data/dealer-studio-byd/api_data/all_cars_inventory_12.json) (197 KB) | — |
| **Full Car Specifications** | **12** | [all_cars_detailed_specs.json](file:///d:/sales-floor/denza-data/dealer-studio-byd/api_data/all_cars_detailed_specs.json) (197 KB) | [cars_detailed/](file:///d:/sales-floor/denza-data/dealer-studio-byd/api_data/cars_detailed/) (12 vehicle JSONs) |
| **Manifest** | — | [COMPLETE_DATA_MANIFEST.json](file:///d:/sales-floor/denza-data/dealer-studio-byd/api_data/COMPLETE_DATA_MANIFEST.json) | Full execution statistics |

---

## Directory Structure

```text
d:\sales-floor\denza-data\dealer-studio-byd\api_data\
├── COMPLETE_DATA_MANIFEST.json      <- Harvest metadata & statistics
├── all_lead_clusters_3369.json      <- All 3,369 leads (all pages combined)
├── active_lead_clusters_695.json    <- All 695 active leads
├── all_cars_inventory_12.json       <- Complete 12 vehicles in stock
├── all_cars_detailed_specs.json     <- Full vehicle specs, options & pricing
├── lead_clusters_pages/             <- 41 individual pagination JSON files:
│   ├── all_page_01.json ... all_page_34.json
│   └── active_page_01.json ... active_page_07.json
└── cars_detailed/                   <- 12 individual car JSON files:
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
