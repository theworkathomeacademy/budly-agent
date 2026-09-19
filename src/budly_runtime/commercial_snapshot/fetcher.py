"""Authenticated WooCommerce Catalog Fetcher (CCS-001 / CCS-003).

Fetches the COMPLETE commercial catalog from WooCommerce REST API v3 including:
- published, draft, pending, private products
- variable products and all child variations
- services, memberships, payment-option products
- complete pagination
"""

from __future__ import annotations

import base64
import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

logger = logging.getLogger("commercial_catalog.fetcher")


class WooCommerceCatalogFetcher:
    """Authenticated fetcher for WooCommerce REST API v3 with complete pagination."""

    def __init__(
        self,
        base_url: str | None = None,
        consumer_key: str | None = None,
        consumer_secret: str | None = None,
        opener: Callable[..., Any] | None = None,
        timeout: float = 15.0,
    ) -> None:
        self.base_url = (
            base_url
            or os.getenv("WOOCOMMERCE_API_URL", "https://cccultivate.com/wp-json/wc/v3")
        ).rstrip("/")
        self.consumer_key = consumer_key or os.getenv("WOOCOMMERCE_CONSUMER_KEY", "")
        self.consumer_secret = consumer_secret or os.getenv("WOOCOMMERCE_CONSUMER_SECRET", "")
        self.opener = opener or urllib.request.urlopen
        self.timeout = timeout

    def _build_request(self, endpoint: str, params: dict[str, Any] | None = None) -> urllib.request.Request:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        query_params = dict(params or {})
        
        # If credentials provided, attach basic auth
        headers = {
            "User-Agent": "Budly-Commercial-Catalog-Snapshot/1.0",
            "Accept": "application/json",
        }
        if self.consumer_key and self.consumer_secret:
            auth_str = f"{self.consumer_key}:{self.consumer_secret}"
            encoded_auth = base64.b64encode(auth_str.encode("utf-8")).decode("ascii")
            headers["Authorization"] = f"Basic {encoded_auth}"
        
        if query_params:
            url = f"{url}?{urllib.parse.urlencode(query_params)}"

        return urllib.request.Request(url, headers=headers, method="GET")

    def fetch_all_products(self, status: str = "any") -> list[dict[str, Any]]:
        """Fetch all products across all pages, including drafts, private, and variables."""
        all_products: list[dict[str, Any]] = []
        page = 1
        per_page = 100

        while True:
            params = {
                "page": page,
                "per_page": per_page,
                "status": status,
            }
            req = self._build_request("products", params)
            try:
                with self.opener(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
            except (urllib.error.URLError, TimeoutError, ValueError) as exc:
                logger.warning(f"Error fetching page {page} from WooCommerce API: {exc}")
                raise RuntimeError(f"WooCommerce API fetch failed on page {page}: {exc}") from exc

            if not isinstance(data, list) or not data:
                break

            all_products.extend(data)

            # If fewer than per_page returned, we reached the end
            if len(data) < per_page:
                break

            page += 1

        # Now fetch variations for variable products
        for product in list(all_products):
            if product.get("type") == "variable" and product.get("id"):
                parent_id = product["id"]
                variations = self.fetch_product_variations(parent_id)
                product["_variations"] = variations

        return all_products

    def fetch_product_variations(self, parent_id: int) -> list[dict[str, Any]]:
        """Fetch all variations for a given variable parent product."""
        variations: list[dict[str, Any]] = []
        page = 1
        per_page = 100

        while True:
            params = {"page": page, "per_page": per_page}
            req = self._build_request(f"products/{parent_id}/variations", params)
            try:
                with self.opener(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
            except (urllib.error.URLError, TimeoutError, ValueError) as exc:
                logger.warning(f"Error fetching variations for product {parent_id}: {exc}")
                break

            if not isinstance(data, list) or not data:
                break

            variations.extend(data)
            if len(data) < per_page:
                break
            page += 1

        return variations

    def fetch_single_product(self, product_id: int) -> dict[str, Any] | None:
        """Fetch a specific product record by ID using authenticated WooCommerce access."""
        req = self._build_request(f"products/{product_id}")
        try:
            with self.opener(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if isinstance(data, dict):
                    if data.get("type") == "variable" and data.get("id"):
                        data["_variations"] = self.fetch_product_variations(data["id"])
                    return data
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            logger.warning(f"Error fetching single product {product_id}: {exc}")
        return None

    def fetch_single_variation(self, parent_id: int, variation_id: int) -> dict[str, Any] | None:
        """Fetch a specific product variation by parent ID and variation ID."""
        req = self._build_request(f"products/{parent_id}/variations/{variation_id}")
        try:
            with self.opener(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if isinstance(data, dict):
                    return data
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            logger.warning(f"Error fetching variation {variation_id} for parent {parent_id}: {exc}")
        return None

    def fetch_all_coupons(self) -> list[dict[str, Any]]:
        """Fetch all coupons via authenticated WooCommerce REST API v3."""
        all_coupons: list[dict[str, Any]] = []
        page = 1
        per_page = 100

        while True:
            params = {"page": page, "per_page": per_page}
            req = self._build_request("coupons", params)
            try:
                with self.opener(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
            except (urllib.error.URLError, TimeoutError, ValueError) as exc:
                logger.warning(f"Error fetching coupons page {page}: {exc}")
                break

            if not isinstance(data, list) or not data:
                break

            all_coupons.extend(data)
            if len(data) < per_page:
                break
            page += 1

        return all_coupons

    def fetch_coupon(self, code: str) -> dict[str, Any] | None:
        """Fetch a specific coupon by code via authenticated WooCommerce REST API v3."""
        params = {"code": code}
        req = self._build_request("coupons", params)
        try:
            with self.opener(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if isinstance(data, list) and data:
                    return data[0]
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            logger.warning(f"Error fetching coupon {code}: {exc}")
        return None

