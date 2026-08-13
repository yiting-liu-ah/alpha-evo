"""Conservative WorldQuant BRAIN HTTP client.

The client keeps mutating operations explicit. Simulations are never retried after an
ambiguous POST response, and alpha submission requires a separate method call.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Iterable

import requests
from requests.auth import HTTPBasicAuth


API_BASE = "https://api.worldquantbrain.com"


class BrainError(RuntimeError):
    """Raised when BRAIN returns an unusable response."""


@dataclass(frozen=True)
class BrainConfig:
    api_base: str = API_BASE
    connect_timeout: int = 10
    read_timeout: int = 90
    poll_seconds: float = 5.0
    max_get_retries: int = 4


def default_settings() -> dict[str, Any]:
    return {
        "instrumentType": "EQUITY",
        "region": "USA",
        "universe": "TOP3000",
        "delay": 1,
        "decay": 4,
        "neutralization": "SUBINDUSTRY",
        "truncation": 0.08,
        "pasteurization": "ON",
        "unitHandling": "VERIFY",
        "nanHandling": "ON",
        "language": "FASTEXPR",
        "visualization": False,
    }


def load_credentials(skill_dir: Path | None = None) -> tuple[str, str]:
    username = os.getenv("WQ_BRAIN_USERNAME")
    password = os.getenv("WQ_BRAIN_PASSWORD")
    if username and password:
        return username, password

    candidates: list[Path] = []
    if skill_dir is not None:
        candidates.append(skill_dir / "credential.txt")
    candidates.append(Path.cwd() / "credential.txt")
    for path in candidates:
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list) or len(data) != 2:
            raise BrainError(f"Invalid credential format in {path}")
        return str(data[0]), str(data[1])
    raise BrainError(
        "BRAIN credentials not found. Set WQ_BRAIN_USERNAME and "
        "WQ_BRAIN_PASSWORD or create an ignored credential.txt."
    )


def _retry_delay(response: requests.Response, attempt: int) -> float:
    value = response.headers.get("Retry-After")
    if value:
        try:
            return max(0.0, float(value))
        except ValueError:
            try:
                target = parsedate_to_datetime(value)
                now = datetime.now(target.tzinfo or timezone.utc)
                return max(0.0, (target - now).total_seconds())
            except (TypeError, ValueError):
                pass
    return min(30.0, 2.0**attempt)


class BrainClient:
    def __init__(
        self,
        username: str,
        password: str,
        config: BrainConfig | None = None,
    ) -> None:
        self.config = config or BrainConfig()
        self.request_count = 0
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(username, password)
        self.session.headers.update(
            {
                "Accept": "application/json;version=2.0",
                "Content-Type": "application/json",
                "User-Agent": "quantaalpha-wq-research/1.0",
            }
        )

    @classmethod
    def from_environment(cls, skill_dir: Path | None = None) -> "BrainClient":
        return cls(*load_credentials(skill_dir))

    def close(self) -> None:
        self.session.close()

    def authenticate(self) -> None:
        self.request_count += 1
        response = self.session.post(
            f"{self.config.api_base}/authentication",
            timeout=(self.config.connect_timeout, self.config.read_timeout),
        )
        if response.status_code != 201:
            raise BrainError(
                f"BRAIN authentication failed: {response.status_code} {response.text[:500]}"
            )

    def get(self, path_or_url: str, **kwargs: Any) -> requests.Response:
        url = (
            path_or_url
            if path_or_url.startswith("http")
            else f"{self.config.api_base}/{path_or_url.lstrip('/')}"
        )
        for attempt in range(self.config.max_get_retries):
            try:
                self.request_count += 1
                response = self.session.get(
                    url,
                    timeout=(self.config.connect_timeout, self.config.read_timeout),
                    **kwargs,
                )
            except (requests.ConnectionError, requests.Timeout):
                if attempt + 1 == self.config.max_get_retries:
                    raise
                time.sleep(min(30.0, 2.0**attempt))
                continue
            if response.status_code not in {429, 500, 502, 503, 504}:
                return response
            if attempt + 1 == self.config.max_get_retries:
                return response
            time.sleep(_retry_delay(response, attempt))
        raise BrainError(f"GET failed without response: {url}")

    def post(self, path: str, *, json_body: dict[str, Any] | None = None) -> requests.Response:
        """Issue one POST only; callers resolve ambiguous outcomes explicitly."""
        self.request_count += 1
        return self.session.post(
            f"{self.config.api_base}/{path.lstrip('/')}",
            json=json_body,
            timeout=(self.config.connect_timeout, self.config.read_timeout),
        )

    @staticmethod
    def _json(response: requests.Response, context: str) -> dict[str, Any]:
        if response.status_code >= 400:
            raise BrainError(f"{context}: {response.status_code} {response.text[:800]}")
        try:
            value = response.json()
        except ValueError as exc:
            raise BrainError(f"{context}: invalid JSON response") from exc
        if not isinstance(value, dict):
            raise BrainError(f"{context}: expected object response")
        return value

    def list_alphas(self, limit: int = 100) -> list[dict[str, Any]]:
        alphas: list[dict[str, Any]] = []
        offset = 0
        while True:
            response = self.get(
                "/users/self/alphas", params={"limit": limit, "offset": offset}
            )
            payload = self._json(response, "list alphas")
            batch = payload.get("results", payload.get("alphas", []))
            if not isinstance(batch, list):
                raise BrainError("list alphas: results is not a list")
            alphas.extend(item for item in batch if isinstance(item, dict))
            if len(batch) < limit:
                break
            offset += limit
            time.sleep(0.2)
        return alphas

    def list_data_fields(
        self,
        *,
        region: str,
        universe: str,
        delay: int,
        instrument_type: str = "EQUITY",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        fields: list[dict[str, Any]] = []
        offset = 0
        while True:
            response = self.get(
                "/data-fields",
                params={
                    "instrumentType": instrument_type,
                    "region": region,
                    "universe": universe,
                    "delay": delay,
                    "limit": limit,
                    "offset": offset,
                },
            )
            payload = self._json(response, "list data fields")
            batch = payload.get("results", payload.get("dataFields", []))
            if not isinstance(batch, list):
                raise BrainError("list data fields: results is not a list")
            fields.extend(item for item in batch if isinstance(item, dict))
            if len(batch) < limit:
                break
            offset += limit
            time.sleep(0.2)
        return fields

    def get_alpha(self, alpha_id: str) -> dict[str, Any]:
        return self._json(self.get(f"/alphas/{alpha_id}"), f"get alpha {alpha_id}")

    @staticmethod
    def _property_indexes(payload: dict[str, Any]) -> tuple[int, int]:
        properties = payload.get("schema", {}).get("properties", [])
        if isinstance(properties, list):
            names = [str(item.get("name", "")).lower() for item in properties]
            date_index = next((i for i, name in enumerate(names) if name == "date"), 0)
            pnl_index = next(
                (i for i, name in enumerate(names) if name in {"pnl", "cum_pnl", "returns", "ret"}),
                1,
            )
            return date_index, pnl_index
        if isinstance(properties, dict):
            indexes = {
                str(name).lower(): int(meta.get("index", position))
                for position, (name, meta) in enumerate(properties.items())
                if isinstance(meta, dict)
            }
            return indexes.get("date", 0), next(
                (indexes[name] for name in ("pnl", "cum_pnl", "returns", "ret") if name in indexes),
                1,
            )
        return 0, 1

    def fetch_pnl(
        self, alpha_id: str, *, empty_response_retries: int = 3
    ) -> list[dict[str, Any]]:
        """Fetch a PnL recordset without accepting BRAIN's transient 200-empty response."""
        for attempt in range(empty_response_retries + 1):
            response = self.get(f"/alphas/{alpha_id}/recordsets/pnl")
            if response.status_code != 200:
                raise BrainError(
                    f"fetch PnL {alpha_id}: HTTP {response.status_code}"
                )
            if response.text.strip():
                payload = self._json(response, f"fetch PnL {alpha_id}")
                date_index, pnl_index = self._property_indexes(payload)
                by_date: dict[str, float] = {}
                for raw in payload.get("records", []):
                    row = raw
                    if isinstance(row, list) and len(row) == 1 and isinstance(row[0], list):
                        row = row[0]
                    if not isinstance(row, list) or max(date_index, pnl_index) >= len(row):
                        continue
                    try:
                        date = str(row[date_index])
                        value = float(row[pnl_index])
                    except (TypeError, ValueError):
                        continue
                    by_date[date] = value
                if by_date:
                    return [
                        {"date": date, "pnl": by_date[date]}
                        for date in sorted(by_date)
                    ]
            if attempt < empty_response_retries:
                # BRAIN can soft-throttle this endpoint with HTTP 200 and an
                # empty HTML body. Treat it as retryable GET state, not as an
                # Alpha with no PnL.
                time.sleep(min(8.0, 1.5 * (attempt + 1)))
        raise BrainError(
            f"fetch PnL {alpha_id}: empty or unparseable recordset after "
            f"{empty_response_retries + 1} attempts"
        )

    def simulate(
        self,
        expression: str,
        settings: dict[str, Any],
        *,
        timeout_seconds: int = 1800,
    ) -> tuple[str, dict[str, Any]]:
        payload = {"type": "REGULAR", "settings": settings, "regular": expression}
        started_at = datetime.now(timezone.utc)
        response = self.post("/simulations", json_body=payload)
        if response.status_code != 201:
            raise BrainError(f"simulation start failed: {response.status_code} {response.text[:800]}")
        location = response.headers.get("Location")
        if not location:
            raise BrainError("simulation start succeeded without Location header")

        deadline = time.monotonic() + timeout_seconds
        next_account_scan = time.monotonic() + 30
        while time.monotonic() < deadline:
            poll = self.get(location)
            data = self._json(poll, "simulation poll")
            status = str(data.get("status", "")).upper()
            alpha = data.get("alpha")
            if alpha:
                alpha_id = alpha.get("id") if isinstance(alpha, dict) else str(alpha)
                if status in {"COMPLETE", "COMPLETED", "DONE"}:
                    return str(alpha_id), data
                # BRAIN can expose a fully populated Alpha before the simulation
                # endpoint switches to a terminal status. Treat complete IS
                # metrics as authoritative instead of polling until timeout.
                resolved = self.get_alpha(str(alpha_id))
                is_metrics = resolved.get("is") if isinstance(resolved, dict) else None
                if isinstance(is_metrics, dict) and is_metrics.get("sharpe") is not None:
                    data["status"] = "RECOVERED_FROM_ALPHA_DETAILS"
                    return str(alpha_id), data
            if status in {"ERROR", "FAILED", "CANCELLED"}:
                raise BrainError(f"simulation {status}: {json.dumps(data)[:1000]}")
            # The account Alpha index and the Simulation resource can become
            # temporarily inconsistent: the UI already shows a completed Alpha
            # while Location still has no terminal status or Alpha ID. Recover
            # only an exact-expression Alpha created by this POST window.
            if time.monotonic() >= next_account_scan:
                next_account_scan = time.monotonic() + 30
                try:
                    for item in self.list_alphas():
                        regular = item.get("regular") if isinstance(item, dict) else None
                        code = regular.get("code") if isinstance(regular, dict) else None
                        if str(code or "") != expression:
                            continue
                        created_raw = str(item.get("dateCreated") or "")
                        try:
                            created_at = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
                        except ValueError:
                            continue
                        if created_at.astimezone(timezone.utc) < started_at:
                            continue
                        recovered_id = str(item.get("id") or "")
                        if not recovered_id:
                            continue
                        resolved = self.get_alpha(recovered_id)
                        is_metrics = resolved.get("is") if isinstance(resolved, dict) else None
                        if isinstance(is_metrics, dict) and is_metrics.get("sharpe") is not None:
                            data["status"] = "RECOVERED_FROM_ACCOUNT_INDEX"
                            data["alpha"] = recovered_id
                            return recovered_id, data
                except (BrainError, requests.RequestException):
                    pass
            time.sleep(max(self.config.poll_seconds, _retry_delay(poll, 0) if poll.status_code == 429 else 0))
        raise TimeoutError(f"simulation did not finish within {timeout_seconds} seconds")

    def submit_alpha(self, alpha_id: str) -> requests.Response:
        return self.post(f"/alphas/{alpha_id}/submit")

    def wait_for_alpha_status(
        self,
        alpha_id: str,
        terminal: Iterable[str] = ("ACTIVE",),
        *,
        timeout_seconds: int = 900,
    ) -> dict[str, Any]:
        terminal_set = {value.upper() for value in terminal}
        deadline = time.monotonic() + timeout_seconds
        last: dict[str, Any] = {}
        while time.monotonic() < deadline:
            last = self.get_alpha(alpha_id)
            status = str(last.get("status", "")).upper()
            checks = last.get("is", {}).get("checks", []) if isinstance(last.get("is"), dict) else []
            any_failed = any(
                isinstance(item, dict)
                and str(item.get("result") or "").upper() == "FAIL"
                for item in checks
            )
            if status in terminal_set or status in {"REJECTED", "ERROR", "FAILED"} or any_failed:
                return last
            time.sleep(10)
        return last
