"""HDX API client with auth and rate limiting, inspired by hdx-mcp patterns."""
from __future__ import annotations

import base64
import json
import logging
import os
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class HDXClientError(RuntimeError):
    """Raised when HDX API requests fail."""


@dataclass
class HDXClientConfig:
    api_key: str
    base_url: str = "https://hapi.humdata.org/api/v2"
    timeout: float = 30.0
    app_name: str = "alles-gut-ocha"
    app_email: str = "assistant@example.com"
    rate_limit_requests: int = 10
    rate_limit_period: float = 60.0
    debug: bool = False
    debug_payload: bool = False
    debug_payload_max_chars: int = 2000


class HDXClient:
    """Small sync client for HDX HAPI with simple token-bucket-like throttling."""

    def __init__(self, config: HDXClientConfig):
        self._config = config
        self._lock = threading.Lock()
        self._request_times: deque[float] = deque()

        self._client = httpx.Client(
            base_url=config.base_url,
            timeout=config.timeout,
            headers={
                "X-HDX-HAPI-APP-IDENTIFIER": config.api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            params={"app_identifier": self._create_app_identifier()},
        )

    @property
    def base_url(self) -> str:
        return self._config.base_url

    @property
    def rate_limit_requests(self) -> int:
        return self._config.rate_limit_requests

    @property
    def rate_limit_period(self) -> float:
        return self._config.rate_limit_period

    def _create_app_identifier(self) -> str:
        app_info = f"{self._config.app_name}:{self._config.app_email}"
        return base64.b64encode(app_info.encode("utf-8")).decode("utf-8")

    def _throttle(self) -> None:
        while True:
            sleep_seconds = 0.0
            with self._lock:
                now = time.monotonic()
                window_start = now - self._config.rate_limit_period

                while self._request_times and self._request_times[0] < window_start:
                    self._request_times.popleft()

                if len(self._request_times) < self._config.rate_limit_requests:
                    self._request_times.append(now)
                    return

                sleep_seconds = self._request_times[0] + self._config.rate_limit_period - now

            if sleep_seconds > 0:
                time.sleep(sleep_seconds)

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        if self._config.debug:
            safe_params = dict(kwargs.get("params") or {})
            if "app_identifier" in safe_params:
                safe_params["app_identifier"] = "***"
            logger.info("HDX request: method=%s path=%s params=%s", method, path, safe_params)

        self._throttle()
        try:
            response = self._client.request(method, path, **kwargs)
            response.raise_for_status()
            payload = response.json()

            if self._config.debug:
                rows = payload.get("data") if isinstance(payload, dict) else None
                row_count = len(rows) if isinstance(rows, list) else None
                logger.info(
                    "HDX response: method=%s path=%s status=%s rows=%s",
                    method,
                    path,
                    response.status_code,
                    row_count,
                )

                if self._config.debug_payload:
                    try:
                        payload_text = json.dumps(payload, default=str, ensure_ascii=True)
                    except TypeError:
                        payload_text = str(payload)

                    max_len = self._config.debug_payload_max_chars
                    if len(payload_text) > max_len:
                        payload_text = payload_text[:max_len] + " ...<truncated>"

                    logger.info(
                        "HDX response payload preview: method=%s path=%s payload=%s",
                        method,
                        path,
                        payload_text,
                    )

            return payload
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:500]
            if self._config.debug:
                logger.exception(
                    "HDX HTTP status error: method=%s path=%s status=%s body=%s",
                    method,
                    path,
                    exc.response.status_code,
                    detail,
                )
            raise HDXClientError(
                f"HDX API error {exc.response.status_code} on {path}: {detail}"
            ) from exc
        except httpx.HTTPError as exc:
            if self._config.debug:
                logger.exception("HDX transport error: method=%s path=%s", method, path)
            raise HDXClientError(f"HDX request failed on {path}: {exc}") from exc

    def get_version(self) -> dict[str, Any]:
        return self._request("GET", "/util/version")

    def get_dataset_info(self, dataset_hdx_id: str) -> dict[str, Any]:
        data = self._request(
            "GET", "/metadata/dataset", params={"dataset_hdx_id": dataset_hdx_id}
        )
        rows = data.get("data") or []
        if not rows:
            return {
                "error": "Dataset not found",
                "dataset_hdx_id": dataset_hdx_id,
            }
        return {
            "status": "success",
            "dataset_hdx_id": dataset_hdx_id,
            "dataset": rows[0],
        }

    def search_locations(
        self,
        name_pattern: str | None = None,
        has_hrp: bool | None = None,
        limit: int = 25,
    ) -> dict[str, Any]:
        data = self._request("GET", "/metadata/location")
        rows = data.get("data") or []

        if name_pattern:
            pat = name_pattern.casefold()
            rows = [r for r in rows if pat in str(r.get("name") or "").casefold()]

        if has_hrp is not None:
            rows = [r for r in rows if bool(r.get("has_hrp")) == has_hrp]

        rows = rows[:limit]
        return {
            "status": "success",
            "count": len(rows),
            "results": rows,
        }

    def _get_hapi_data(self, path: str, extra_params: dict[str, Any], limit: int) -> dict[str, Any]:
        params: dict[str, Any] = {k: v for k, v in extra_params.items() if v is not None}
        params["limit"] = limit
        data = self._request("GET", path, params=params)
        rows = data.get("data") or []
        return {
            "status": "success",
            "source": "HDX HAPI",
            "source_url": f"https://hapi.humdata.org/api/v2{path}",
            "count": len(rows),
            "results": rows,
        }

    def get_humanitarian_needs(
        self,
        location_code: str | None = None,
        year: int | None = None,
        cluster_code: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        return self._get_hapi_data(
            "/affected-people/humanitarian-needs",
            {"location_code": location_code, "year": year, "cluster_code": cluster_code},
            limit,
        )

    def get_affected_populations(
        self,
        location_code: str | None = None,
        year: int | None = None,
        population_group_code: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Routes to refugees or IDPs endpoint based on population_group_code ('IDP' or else)."""
        if population_group_code and population_group_code.upper() == "IDP":
            path = "/affected-people/idps"
            extra: dict[str, Any] = {"location_code": location_code, "year": year}
        else:
            path = "/affected-people/refugees-persons-of-concern"
            extra = {"location_code": location_code, "year": year}
            if population_group_code and population_group_code.upper() not in ("REF", "IDP"):
                extra["population_group_code"] = population_group_code
        return self._get_hapi_data(path, extra, limit)

    def get_food_security(
        self,
        location_code: str | None = None,
        year: int | None = None,
        ipc_phase: int | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """ipc_phase: 1=Minimal, 2=Stressed, 3=Crisis, 4=Emergency, 5=Famine."""
        return self._get_hapi_data(
            "/food-security-nutrition-poverty/food-security",
            {"location_code": location_code, "year": year, "ipc_phase": ipc_phase},
            limit,
        )

    def get_conflict_events(
        self,
        location_code: str | None = None,
        year: int | None = None,
        event_type: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        return self._get_hapi_data(
            "/coordination-context/conflict-events",
            {"location_code": location_code, "year": year, "event_type": event_type},
            limit,
        )

    def get_funding(
        self,
        location_code: str | None = None,
        year: int | None = None,
        cluster_code: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        return self._get_hapi_data(
            "/coordination-context/funding",
            {"location_code": location_code, "year": year, "cluster_code": cluster_code},
            limit,
        )

    def get_operational_presence(
        self,
        location_code: str | None = None,
        year: int | None = None,
        cluster_code: str | None = None,
        org_acronym: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        return self._get_hapi_data(
            "/coordination-context/operational-presence",
            {
                "location_code": location_code,
                "year": year,
                "cluster_code": cluster_code,
                "org_acronym": org_acronym,
            },
            limit,
        )

    def close(self) -> None:
        self._client.close()


def create_hdx_client_from_env() -> HDXClient | None:
    """Create an HDX client from environment variables, or None if disabled."""
    api_key = os.getenv("HDX_APP_IDENTIFIER")
    if not api_key:
        return None

    config = HDXClientConfig(
        api_key=api_key.strip(),
        base_url=os.getenv("HDX_BASE_URL", "https://hapi.humdata.org/api/v2"),
        timeout=float(os.getenv("HDX_TIMEOUT", "30.0")),
        app_name=os.getenv("HDX_APP_NAME", "alles-gut-ocha"),
        app_email=os.getenv("HDX_APP_EMAIL", "assistant@example.com"),
        rate_limit_requests=int(os.getenv("HDX_RATE_LIMIT_REQUESTS", "10")),
        rate_limit_period=float(os.getenv("HDX_RATE_LIMIT_PERIOD", "60.0")),
        debug=os.getenv("HDX_DEBUG", "false").strip().lower() in {"1", "true", "yes", "on"},
        debug_payload=os.getenv("HDX_DEBUG_PAYLOAD", "false").strip().lower()
        in {"1", "true", "yes", "on"},
        debug_payload_max_chars=int(os.getenv("HDX_DEBUG_PAYLOAD_MAX_CHARS", "2000")),
    )

    if config.debug:
        logger.info("HDX debug logging enabled")
        if config.debug_payload:
            logger.info(
                "HDX payload debug logging enabled (max chars=%s)",
                config.debug_payload_max_chars,
            )

    return HDXClient(config)
