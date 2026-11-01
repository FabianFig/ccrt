"""Bounded, token-authenticated UCDP GED client. No network access on import."""

from __future__ import annotations

import math
import os
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import httpx

from ccrt.loaders.base import parse_date
from ccrt.loaders.ucdp import check_version, from_api_records


class UCDPError(RuntimeError):
    """A sanitized error: response bodies, headers and tokens are never included."""


class UCDPClient:
    def __init__(self, api_key=None, *, timeout=30.0, retries=3, transport=None):
        self._api_key = api_key if api_key is not None else os.environ.get("UCDP_API_KEY", "")
        if not self._api_key or not self._api_key.strip():
            raise UCDPError("Set UCDP_API_KEY or pass api_key to UCDPClient")
        if not math.isfinite(timeout) or timeout <= 0 or type(retries) is not int or not 0 <= retries <= 5:
            raise ValueError("timeout must be finite and positive; retries must be an integer from 0 to 5")
        self._retries = retries
        self._client = httpx.Client(timeout=timeout, transport=transport, follow_redirects=False)

    def close(self):
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _page(self, version, params):
        for attempt in range(self._retries + 1):
            delay = min(2**attempt, 30)
            try:
                response = self._client.get(
                    f"https://ucdpapi.pcr.uu.se/api/gedevents/{version}",
                    params=params,
                    headers={"x-ucdp-access-token": self._api_key},
                )
            except httpx.TransportError:
                if attempt == self._retries:
                    raise UCDPError("UCDP connection failed after bounded retries") from None
            else:
                status = response.status_code
                if status in {401, 403}:
                    raise UCDPError("UCDP rejected the access token (authentication/authorization)")
                if status == 200:
                    try:
                        payload = response.json()
                    except ValueError:
                        raise UCDPError("UCDP returned invalid JSON") from None
                    if not isinstance(payload, dict):
                        raise UCDPError("UCDP returned an invalid response object")
                    return payload
                if status not in {429, 500, 502, 503, 504}:
                    raise UCDPError(f"UCDP request failed (HTTP {status})")
                if attempt == self._retries:
                    raise UCDPError(f"UCDP request exhausted retries (HTTP {status})")
                retry_after = response.headers.get("Retry-After")
                if retry_after:
                    try:
                        delay = max(0, float(retry_after))
                    except ValueError:
                        try:
                            when = parsedate_to_datetime(retry_after)
                            delay = max(0, (when - datetime.now(timezone.utc)).total_seconds())
                        except (TypeError, ValueError, OverflowError):
                            delay = min(2**attempt, 30)
                    if not math.isfinite(delay) or delay > 30:
                        raise UCDPError("UCDP requested a longer retry delay; try again later")
            time.sleep(delay)
        raise AssertionError("unreachable")

    def fetch(
        self,
        *,
        version,
        countries=None,
        start_date=None,
        end_date=None,
        types_of_violence=None,
        page_size=1000,
        max_pages=5000,
    ):
        """Fetch a complete bounded query. Date filters apply to UCDP date_end.

        Country values are UCDP/Gleditsch-Ward numeric IDs, not ISO codes.
        A partial response is never returned as a complete Dataset.
        """
        check_version(version)
        if type(page_size) is not int or not 1 <= page_size <= 1000:
            raise ValueError("page_size must be an integer from 1 to 1000")
        if type(max_pages) is not int or not 1 <= max_pages <= 5000:
            raise ValueError("max_pages must be an integer from 1 to 5000")
        params = {"pagesize": page_size}
        for name, values in (("Country", countries), ("TypeOfViolence", types_of_violence)):
            if values is not None:
                values = list(values)
                if not values or any(type(v) is not int or v < 1 for v in values):
                    raise ValueError(f"{name} must contain positive integer IDs")
                if name == "TypeOfViolence" and any(v not in {1, 2, 3} for v in values):
                    raise ValueError("TypeOfViolence must contain 1, 2, or 3")
                params[name] = ",".join(str(v) for v in sorted(set(values)))
        dates = []
        for name, value in (("StartDate", start_date), ("EndDate", end_date)):
            parsed = parse_date(value) if value is not None else None
            dates.append(parsed)
            if parsed:
                params[name] = parsed.isoformat()
        if all(dates) and dates[0] > dates[1]:
            raise ValueError("start_date exceeds end_date")
        rows, expected, seen_ids = [], None, set()
        # The live GED endpoint indexes pages from zero. Starting at one silently
        # skips the first page, even though its documentation examples use page=1.
        page = 0
        while True:
            payload = self._page(version, {**params, "page": page})
            total, pages, results = (
                payload.get("TotalCount"),
                payload.get("TotalPages"),
                payload.get("Result"),
            )
            if (
                type(total) is not int
                or total < 0
                or type(pages) is not int
                or pages < 0
                or not isinstance(results, list)
                or any(not isinstance(r, dict) for r in results)
            ):
                raise UCDPError("UCDP response has invalid pagination or records")
            if (total > 0 and pages == 0) or (total == 0 and pages > 1):
                raise UCDPError("UCDP response has inconsistent pagination")
            if expected is None:
                expected = (total, pages)
                if pages > max_pages:
                    raise UCDPError("Query exceeds max_pages; narrow the query or increase the bound")
            elif expected != (total, pages):
                raise UCDPError("UCDP result count changed during pagination; retry the query")
            if page < pages and not results:
                raise UCDPError("UCDP returned an empty intermediate page")
            for row in results:
                identifier = str(row.get("id", ""))
                if identifier in seen_ids:
                    raise UCDPError("UCDP repeated a record during pagination; retry the query")
                seen_ids.add(identifier)
            rows.extend(results)
            if page + 1 >= pages:
                break
            page += 1
        if len(rows) != expected[0]:
            raise UCDPError("UCDP result count does not match retrieved records")
        return from_api_records(
            rows,
            version=version,
            metadata={"query": params, "retrieved_at": datetime.now(timezone.utc).isoformat()},
        )
