"""
core/api_gateway.py — Centralized API client for belico-stack
=============================================================
Single point of contact for all external HTTP APIs used across tools.
Provides: rate limiting, retry with exponential backoff, response caching,
and .env credential loading.

Replaces ad-hoc urllib calls scattered across tools/*.py.

Usage:
    from core.api_gateway import APIGateway
    gw = APIGateway()
    data = gw.get("openalex", "/works", params={"search": "deep learning"})
    data = gw.get("fred", "/series/observations", params={"series_id": "GDP"})
"""

import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# ── Root of the repository (two levels up from this file) ─────────────────────
_REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(env_path: Path) -> None:
    """Parse a .env file and populate os.environ for keys not already set.

    Only processes KEY=VALUE lines; ignores comments and blank lines.
    Does not overwrite variables that are already present in the environment.

    Args:
        env_path: absolute path to the .env file.
    """
    try:
        with open(env_path, "r", encoding="utf-8") as fh:
            for raw_line in fh:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip("'\"")
                if key and key not in os.environ:
                    os.environ[key] = value
    except FileNotFoundError:
        pass  # .env is optional


class APIGateway:
    """Centralized HTTP API client for belico-stack.

    Handles credential loading, request caching, rate limiting, and
    retry with exponential backoff for all external HTTP APIs.

    Attributes:
        cache_dir: directory where JSON response files are stored.
    """

    # Known API base URLs.
    _BASE_URLS: dict[str, str] = {
        "openalex":         "https://api.openalex.org",
        "semantic_scholar": "https://api.semanticscholar.org/graph/v1",
        "fred":             "https://api.stlouisfed.org/fred",
        "world_bank":       "https://api.worldbank.org/v2",
        "openaq":           "https://api.openaq.org/v2",
        "gbif":             "https://api.gbif.org/v1",
        "fao":              "https://fenixservices.fao.org/faostat/api/v1",
        "pubmed":           "https://eutils.ncbi.nlm.nih.gov/entrez/eutils",
    }

    # Mapping from api_name to the environment variable that holds the key.
    _API_KEY_ENV: dict[str, str] = {
        "openalex":         "OPENALEX_API_KEY",
        "semantic_scholar": "SEMANTIC_SCHOLAR_API_KEY",
        "fred":             "FRED_API_KEY",
        "pubmed":           "NCBI_API_KEY",
    }

    # Minimum seconds between consecutive requests to the same API.
    _MIN_REQUEST_INTERVAL: float = 0.1

    # Number of retry attempts on transient failures.
    _MAX_RETRIES: int = 3

    # Cache TTL in seconds (24 hours).
    _CACHE_TTL: float = 86_400.0

    def __init__(self, cache_dir: Path | None = None) -> None:
        """Initialise the gateway.

        Loads credentials from ROOT/.env (if present) and ensures the
        cache directory exists.

        Args:
            cache_dir: override the default cache location
                       (ROOT/.cache/api_gateway/).
        """
        _load_dotenv(_REPO_ROOT / ".env")

        self.cache_dir: Path = (
            cache_dir if cache_dir is not None
            else _REPO_ROOT / ".cache" / "api_gateway"
        )
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Per-api last-request timestamp for rate limiting.
        self._last_request: dict[str, float] = {}

    # ── Private helpers ───────────────────────────────────────────────────────

    def _get_base_url(self, api_name: str) -> str:
        """Return the base URL for a known API.

        Args:
            api_name: short name key (e.g. "openalex").

        Returns:
            Base URL string.

        Raises:
            KeyError: if api_name is not in the registry.
        """
        if api_name not in self._BASE_URLS:
            known = ", ".join(sorted(self._BASE_URLS))
            raise KeyError(
                f"Unknown API '{api_name}'. "
                f"Known APIs: {known}."
            )
        return self._BASE_URLS[api_name]

    def _get_api_key(self, api_name: str) -> str | None:
        """Return the API key for the given API, or None if not configured.

        Reads from os.environ (already populated from .env in __init__).

        Args:
            api_name: short name key.

        Returns:
            API key string, or None for public APIs / unconfigured keys.
        """
        env_var = self._API_KEY_ENV.get(api_name)
        if env_var is None:
            return None
        return os.environ.get(env_var)  # None if not set — never crashes

    def _cache_key(
        self,
        api_name: str,
        endpoint: str,
        params: dict | None,
    ) -> Path:
        """Derive a deterministic cache file path from the request identity.

        Args:
            api_name: short name key.
            endpoint: URL path segment (e.g. "/works").
            params:   query parameters dict (order-insensitive).

        Returns:
            Path object for the cache file (may not exist yet).
        """
        sorted_params = sorted((params or {}).items())
        raw = f"{api_name}|{endpoint}|{sorted_params}"
        digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
        return self.cache_dir / f"{api_name}_{digest}.json"

    def _read_cache(self, cache_file: Path) -> dict | list | None:
        """Return cached JSON if the file exists and is younger than TTL.

        Args:
            cache_file: path returned by _cache_key.

        Returns:
            Parsed JSON (dict or list), or None on miss/expiry.
        """
        if not cache_file.exists():
            return None
        age = time.time() - cache_file.stat().st_mtime
        if age > self._CACHE_TTL:
            return None
        try:
            with open(cache_file, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError):
            return None

    def _write_cache(self, cache_file: Path, data: dict | list) -> None:
        """Persist API response to the cache directory.

        Args:
            cache_file: destination path.
            data:       parsed JSON to serialise.
        """
        try:
            with open(cache_file, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False)
        except OSError as exc:
            print(
                f"[api_gateway] Cache write failed for {cache_file}: {exc}",
                file=sys.stderr,
            )

    def _rate_limit(self, api_name: str) -> None:
        """Sleep if the minimum inter-request interval has not elapsed.

        Args:
            api_name: short name key used as throttle bucket.
        """
        last = self._last_request.get(api_name, 0.0)
        elapsed = time.time() - last
        if elapsed < self._MIN_REQUEST_INTERVAL:
            time.sleep(self._MIN_REQUEST_INTERVAL - elapsed)
        self._last_request[api_name] = time.time()

    def _build_url(
        self,
        api_name: str,
        endpoint: str,
        params: dict | None,
    ) -> tuple[str, dict]:
        """Construct the final URL and params dict, injecting the API key.

        For semantic_scholar the key is sent as an HTTP header, not a query
        param; that header is handled in get() directly.

        Args:
            api_name: short name key.
            endpoint: URL path segment.
            params:   caller-supplied query parameters (not mutated).

        Returns:
            (url, params_with_key) tuple. params_with_key may include the
            api_key query param for APIs that use it that way.
        """
        base = self._get_base_url(api_name)
        url = base.rstrip("/") + "/" + endpoint.lstrip("/")
        merged: dict = dict(params or {})

        api_key = self._get_api_key(api_name)
        if api_key and api_name not in ("semantic_scholar",):
            merged["api_key"] = api_key

        return url, merged

    # ── Public interface ──────────────────────────────────────────────────────

    def get(
        self,
        api_name: str,
        endpoint: str,
        params: dict | None = None,
        use_cache: bool = True,
    ) -> dict | list:
        """Perform an HTTP GET request against a known API.

        Features:
        - Cache: returns stored response if file is < 24 h old.
        - Rate limit: enforces _MIN_REQUEST_INTERVAL between calls.
        - Retry: up to _MAX_RETRIES attempts with 2^n second backoff.
        - 429 handling: reads Retry-After header when present.

        Args:
            api_name:  short name key (must be in _BASE_URLS).
            endpoint:  URL path (e.g. "/works", "/series/observations").
            params:    optional query-string parameters dict.
            use_cache: set to False to bypass the cache layer.

        Returns:
            Parsed JSON response as dict or list.

        Raises:
            KeyError:              unknown api_name.
            urllib.error.URLError: network failure after all retries.
            json.JSONDecodeError:  response is not valid JSON.
        """
        cache_file = self._cache_key(api_name, endpoint, params)

        if use_cache:
            cached = self._read_cache(cache_file)
            if cached is not None:
                return cached

        url, merged_params = self._build_url(api_name, endpoint, params)
        if merged_params:
            url = url + "?" + urllib.parse.urlencode(merged_params)

        # Build request object (headers for semantic_scholar API key)
        headers: dict[str, str] = {"Accept": "application/json"}
        if api_name == "semantic_scholar":
            api_key = self._get_api_key(api_name)
            if api_key:
                headers["x-api-key"] = api_key

        last_exc: Exception | None = None
        for attempt in range(self._MAX_RETRIES):
            self._rate_limit(api_name)
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    raw = resp.read().decode("utf-8")
                    data: dict | list = json.loads(raw)
                    if use_cache:
                        self._write_cache(cache_file, data)
                    return data

            except urllib.error.HTTPError as exc:
                if exc.code == 429:
                    retry_after_raw = exc.headers.get("Retry-After", "")
                    try:
                        wait = float(retry_after_raw)
                    except (ValueError, TypeError):
                        wait = 2 ** attempt
                    time.sleep(wait)
                    last_exc = exc
                    continue
                raise  # non-429 HTTP errors are not retried

            except urllib.error.URLError as exc:
                last_exc = exc
                time.sleep(2 ** attempt)
                continue

            except json.JSONDecodeError:
                raise  # malformed JSON is not retried

        # All retries exhausted — re-raise the last network error.
        if last_exc is not None:
            raise last_exc
        raise urllib.error.URLError(  # pragma: no cover
            f"All {self._MAX_RETRIES} retries failed for {url}"
        )
