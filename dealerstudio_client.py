"""
Dealer Studio API Client (Python)
---------------------------------
Comprehensive client supporting both:
1. REST API Authentication (Bearer Token)
2. Dashboard Session Authentication (Cookie + CSRF Token)

Supports:
- Lead Clusters (Postgres Search, Pipeline stages, Lead details)
- Inventory / Cars Management (dealership cars, stock details, specs)
- Contacts & Customers
- Service Bookings & DMS Integration
- Custom Dealership Endpoints
"""

import os
import json
import logging
from typing import Optional, Dict, Any, List, Union
import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("DealerStudio")


# ==========================================
# Custom Exceptions
# ==========================================

class DealerStudioError(Exception):
    """Base exception for Dealer Studio errors."""
    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[Any] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_data = response_data


class AuthenticationError(DealerStudioError):
    """Raised when authentication fails (HTTP 401/403)."""
    pass


class ValidationError(DealerStudioError):
    """Raised when payload validation fails (HTTP 422)."""
    pass


class NotFoundError(DealerStudioError):
    """Raised when a requested resource is not found (HTTP 404)."""
    pass


class RateLimitError(DealerStudioError):
    """Raised when request rate limit is exceeded (HTTP 429)."""
    pass


# ==========================================
# Resource Namespaces
# ==========================================

class LeadClustersResource:
    """Manages Dealer Studio Lead Clusters and Pipelines."""

    def __init__(self, client: "DealerStudioClient"):
        self._client = client

    def postgres_search(
        self,
        rows: int = 25,
        active_lead_clusters_filter: bool = True,
        query: str = "",
        pipeline_id: str = "all",
        sort_by: str = "created_at_desc",
        page: int = 1,
        first: int = 0,
        dealership_slug: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Search and filter lead clusters using the dashboard Postgres search engine.
        Returns: {'lead_clusters': [...], 'has_more': bool, 'next_cursor': ..., 'total_count': int}
        """
        slug = dealership_slug or self._client.dealership_slug
        if not slug:
            raise ValueError("Dealership slug required (e.g. 'denza-melbourne')")

        params = {
            "rows": rows,
            "active_lead_clusters_filter": "true" if active_lead_clusters_filter else "false",
            "query": query,
            "pipeline_id": pipeline_id,
            "sort_by": sort_by,
            "page": page,
            "first": first
        }
        return self._client.request("GET", f"/dealerships/{slug}/lead_clusters/postgres_search", params=params)

    def get(self, cluster_id: Union[int, str], dealership_slug: Optional[str] = None) -> Dict[str, Any]:
        """
        Retrieve details and history for a specific lead cluster.
        """
        slug = dealership_slug or self._client.dealership_slug
        return self._client.request("GET", f"/dealerships/{slug}/lead_clusters/{cluster_id}")


class CarsResource:
    """Manages Dealership Vehicles and Inventory."""

    def __init__(self, client: "DealerStudioClient"):
        self._client = client

    def list(
        self,
        page: int = 1,
        per_page: int = 25,
        dealership_slug: Optional[str] = None,
        **filters
    ) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
        """
        List cars in dealership stock. Uses dealership-scoped inventory if slug available.
        """
        slug = dealership_slug or self._client.dealership_slug
        params = {"page": page, "per_page": per_page, **filters}

        if slug:
            return self._client.request("GET", f"/dealerships/{slug}/cars", params=params)
        return self._client.request("GET", "/api/v1/cars", params=params)

    def get(self, car_id: Union[int, str], dealership_slug: Optional[str] = None) -> Dict[str, Any]:
        """
        Retrieve details for a single vehicle by ID.
        """
        slug = dealership_slug or self._client.dealership_slug
        if slug:
            return self._client.request("GET", f"/dealerships/{slug}/cars/{car_id}")
        return self._client.request("GET", f"/api/v1/cars/{car_id}")


class ContactsResource:
    """Manages Customer Contacts."""

    def __init__(self, client: "DealerStudioClient"):
        self._client = client

    def get(self, contact_id: Union[int, str], dealership_slug: Optional[str] = None) -> Dict[str, Any]:
        """
        Retrieve details for a customer contact by ID.
        """
        slug = dealership_slug or self._client.dealership_slug
        return self._client.request("GET", f"/dealerships/{slug}/contacts/{contact_id}")


class LeadsResource:
    """Manages standard CRM leads."""

    def __init__(self, client: "DealerStudioClient"):
        self._client = client

    def create(
        self,
        name: str,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        brand: Optional[str] = None,
        model: Optional[str] = None,
        dealership_id: Optional[Union[int, str]] = None,
        **extra
    ) -> Dict[str, Any]:
        lead_payload: Dict[str, Any] = {"name": name}
        did = dealership_id or self._client.dealership_id
        if did:
            lead_payload["dealership_id"] = did
        if email:
            lead_payload["email"] = email
        if phone:
            lead_payload["phone"] = phone
        if brand:
            lead_payload["brand"] = brand
        if model:
            lead_payload["model"] = model
        lead_payload.update(extra)

        return self._client.request("POST", "/api/v1/leads", json_data={"lead": lead_payload})


class DealershipsResource:
    """Manages Dealership profile, staff, and service bookings."""

    def __init__(self, client: "DealerStudioClient"):
        self._client = client

    def get_users(self, dealership_slug: Optional[str] = None) -> List[Dict[str, Any]]:
        slug = dealership_slug or self._client.dealership_slug
        return self._client.request("GET", f"/dealerships/{slug}/users")


# ==========================================
# Main Client Class
# ==========================================

class DealerStudioClient:
    """
    Dealer Studio Unified Client.

    Supports both REST API keys and Browser Session cookies.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        cookie: Optional[str] = None,
        csrf_token: Optional[str] = None,
        dealership_slug: Optional[str] = None,
        dealership_id: Optional[Union[int, str]] = None,
        base_url: str = "https://dashboard.dealerstudio.com.au",
        timeout: float = 20.0
    ):
        self.api_key = api_key or os.getenv("DEALERSTUDIO_API_KEY", "")
        self.cookie = cookie or os.getenv("DEALERSTUDIO_COOKIE", "")
        self.csrf_token = csrf_token or os.getenv("DEALERSTUDIO_CSRF_TOKEN", "")
        self.dealership_slug = dealership_slug or os.getenv("DEALERSTUDIO_DEALERSHIP_SLUG", "denza-melbourne")
        self.dealership_id = dealership_id or os.getenv("DEALERSTUDIO_DEALERSHIP_ID", "2606")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

        # Namespaces
        self.lead_clusters = LeadClustersResource(self)
        self.cars = CarsResource(self)
        self.contacts = ContactsResource(self)
        self.leads = LeadsResource(self)
        self.dealerships = DealershipsResource(self)

        self._http = httpx.Client(timeout=self.timeout, follow_redirects=True)

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Referer": f"{self.base_url}/dealerships/{self.dealership_slug}/lead_clusters/pipelines/all"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if self.csrf_token:
            headers["X-CSRF-Token"] = self.csrf_token
        if self.cookie:
            headers["Cookie"] = self.cookie
        return headers

    def request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None
    ) -> Any:
        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = self._get_headers()
        cleaned_params = {k: v for k, v in (params or {}).items() if v is not None}

        try:
            resp = self._http.request(
                method=method,
                url=url,
                headers=headers,
                params=cleaned_params,
                json=json_data
            )
        except httpx.RequestError as exc:
            raise DealerStudioError(f"HTTP Connection Error: {exc}") from exc

        try:
            data = resp.json() if resp.content else {}
        except Exception:
            data = {"raw_text": resp.text}

        if resp.status_code in (200, 201, 204):
            return data

        msg = f"API Error {resp.status_code}: {resp.reason_phrase}"
        if isinstance(data, dict):
            if "error" in data:
                msg = f"{msg} - {data['error']}"
            elif "message" in data:
                msg = f"{msg} - {data['message']}"

        if resp.status_code in (401, 403):
            raise AuthenticationError(msg, resp.status_code, data)
        elif resp.status_code == 404:
            raise NotFoundError(msg, resp.status_code, data)
        elif resp.status_code == 422:
            raise ValidationError(msg, resp.status_code, data)
        elif resp.status_code == 429:
            raise RateLimitError(msg, resp.status_code, data)
        else:
            raise DealerStudioError(msg, resp.status_code, data)

    def close(self):
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


if __name__ == "__main__":
    client = DealerStudioClient()
    print("Testing Lead Clusters Postgres Search:")
    res = client.lead_clusters.postgres_search(rows=5)
    print(f"Total Count: {res.get('total_count')}")
    print(f"Clusters Returned: {len(res.get('lead_clusters', []))}")
    print("Testing Cars List:")
    cars = client.cars.list()
    print(f"Cars Returned: {len(cars) if isinstance(cars, list) else 'N/A'}")
