# Dealer Studio Complete Data Harvester & API Toolkit

## Hourly server deployment

The server checkout is `/var/www/dealer-studio-byd`, with its own `.venv` and private
`.env`/`.runtime` session files. `run_hourly.py` fetches all data, calls the guarded
`shaun-backend/scripts/import_dealerstudio.py` dry run, makes a compressed database
backup, applies the upsert and verifies it before publishing the canonical export.

Systemd units in `deploy/` run the data import hourly and renew the authenticated
session every five minutes, including after reboot. Configure
`DEALERSTUDIO_BACKEND_ROOT=/var/www/shaun-backend`. Install both units and the backend's
updated SalesLogs unit so they share the `clients-sync.lock` for database work.
Use `systemctl start dealerstudio-sync.service` for manual production runs too.

Server runtime files:

- `.runtime/sync/data/`: latest verified data export.
- `.runtime/sync/data.previous/`: previous successful export.
- `.runtime/sync/last-run.json`: fetch/database result and counts.
- `.runtime/sync/backups/`: pre-import gzip EJSON backups, retained for seven days.
- `.runtime/last-command-error.json`: private details of a failed child command.

Database models and mapping are documented in `shaun-backend/DEALERSTUDIO_SYNC.md`.
Full leads/inventory are stored separately; delivery clients are projected only
from actual ordered/delivered records. Staff workflow fields and other sites are
preserved. Generated snapshots and credentials are kept outside code deployments.

## Session renewal and two-step login

The harvester and Python API client use `dealerstudio_session.py`. It keeps the
server's rotated cookies and fresh CSRF tokens in private `.runtime/session.json`,
independently of the original `.env` seed. No passwords or cookies are returned
in status output. `.env` and `.runtime/` are excluded from Git.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe dealerstudio_session.py
.\.venv\Scripts\python.exe fetch_complete_data.py
```

Configure `DEALERSTUDIO_EMAIL` and `DEALERSTUDIO_PASSWORD` privately in `.env` for
normal re-login. If Dealer Studio requests MFA, use
`.\.venv\Scripts\python.exe dealerstudio_session.py --verify` and enter a current
authenticator/email/SMS code at the hidden prompt. To request a code from Dealer
Studio explicitly use `--send-code email` or `--send-code sms`. The challenge is
saved between commands; the timer does not repeatedly submit a pending password.

For unattended authenticator verification, the account owner's real TOTP secret
can be configured privately as `DEALERSTUDIO_TOTP_SECRET`. Passwords and expired
cookies cannot generate that secret or a valid verification code. The normal MFA
requirement remains enabled; this code does not change account security settings
or trust the device to skip MFA.

On Windows, run `.\install-session-task.ps1` to register
`DealerStudio-Session-Renewal` every five minutes while the current user is logged
in. It uses this project's `.venv`; no Windows password is stored in the task.
The task skips overlapping harvests using a shared session file lock. Its last
authentication result is in `.runtime/session-status.json`. Explicit logout,
revocation, or an MFA challenge without a configured authenticator secret may
require verification again. Invalid login credentials are not repeatedly retried.

Harvests are staged and checked for complete, unique lead/inventory pages before
replacing `api_data`. Failed authentication or incomplete responses preserve the
last good dataset. Previous datasets are retained under `.runtime/api-data-before-*`.
Current counts and timestamps are recorded in `api_data/COMPLETE_DATA_MANIFEST.json`.
The background task's credential-free execution receipt is `.runtime/task-status.json`.

Run isolated regression checks with
`.\.venv\Scripts\python.exe -m unittest test_session.py -v`.

Complete dataset extracted for Dealership **DENZA Melbourne** (`denza-melbourne`, ID: `2606`) from `dashboard.dealerstudio.com.au`.

---

## Complete Data Harvest Summary

| Resource | Count | Master File | Detailed Files Folder |
| :--- | :---: | :--- | :--- |
| **All Historic & Active Leads** | From manifest | [all_lead_clusters.json](api_data/all_lead_clusters.json) | [lead_clusters_pages/](api_data/lead_clusters_pages/) |
| **Active Pipeline Leads** | From manifest | [active_lead_clusters.json](api_data/active_lead_clusters.json) | [lead_clusters_pages/](api_data/lead_clusters_pages/) |
| **Complete Car Inventory** | From manifest | [all_cars_inventory.json](api_data/all_cars_inventory.json) | — |
| **Full Car Specifications** | From manifest | [all_cars_detailed_specs.json](api_data/all_cars_detailed_specs.json) | [cars_detailed/](api_data/cars_detailed/) |
| **Manifest** | — | [COMPLETE_DATA_MANIFEST.json](api_data/COMPLETE_DATA_MANIFEST.json) | Current execution statistics |

---

## Directory Structure

```text
d:\sales-floor\denza-data\dealer-studio-byd\api_data\
├── COMPLETE_DATA_MANIFEST.json      <- Harvest metadata & statistics
├── all_lead_clusters.json           <- All leads (all pages combined)
├── active_lead_clusters.json        <- All active leads
├── all_cars_inventory.json          <- Complete inventory
├── all_cars_detailed_specs.json     <- Full vehicle specs, options & pricing
├── lead_clusters_pages/             <- Individual pagination JSON files:
│   ├── all_page_*.json
│   └── active_page_*.json
└── cars_detailed/                   <- Individual car JSON files:
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
