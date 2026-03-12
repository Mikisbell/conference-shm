"""
tools/adapters/rest_json.py — Generic REST JSON DataAdapter
============================================================
Performs a GET request to the URL declared in source_config["url"],
optionally injecting study_params as query parameters.
Saves the JSON response to output_dir/{source_id}.json.

Retries up to 3 times with exponential back-off on transient errors.
Uses only urllib.request (stdlib) — no extra dependencies required.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from domains.base import DataAdapter

# Mathematical back-off constants (not config params — these are the retry algorithm)
_RETRY_BASE_DELAY_S = 2   # seconds — base delay for exponential back-off
_MAX_RETRIES = 3


class RestJsonAdapter(DataAdapter):
    """DataAdapter for REST APIs that return JSON.

    Reads the endpoint URL from source_config["url"].
    Maps study_params keys to query parameters if source_config["query_params"]
    lists which study_params keys to forward.
    """

    def fetch(
        self,
        source_id: str,
        source_config: dict[str, Any],
        study_params: dict[str, Any],
        output_dir: Path,
    ) -> list[Path]:
        """GET source_config["url"] and save response as {source_id}.json.

        Returns:
            List with one Path (the saved JSON file) on success, or [] on failure.

        Raises:
            OSError: If output_dir is not writable.
        """
        url = source_config.get("url", "")
        if not url:
            print(
                f"[RestJsonAdapter:{source_id}] No 'url' field in source config. "
                "Add url: <endpoint> to config/domains/<domain>.yaml.",
                file=sys.stderr,
            )
            return []

        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise OSError(
                f"[RestJsonAdapter:{source_id}] Cannot create output directory "
                f"'{output_dir}': {exc}"
            ) from exc

        # Build query string from declared params
        query_keys: list[str] = source_config.get("query_params", [])
        query: dict[str, str] = {}
        for key in query_keys:
            if key in study_params:
                query[key] = str(study_params[key])

        if query:
            url = url + "?" + urllib.parse.urlencode(query)

        out_file = output_dir / f"{source_id}.json"
        last_exc: Exception | None = None

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "belico-stack/1.0 (scientific research)"},
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    raw = resp.read()

                # Validate JSON before writing
                try:
                    json.loads(raw)
                except json.JSONDecodeError as exc:
                    print(
                        f"[RestJsonAdapter:{source_id}] Response is not valid JSON: {exc}",
                        file=sys.stderr,
                    )
                    return []

                out_file.write_bytes(raw)
                print(
                    f"[RestJsonAdapter:{source_id}] Saved {len(raw)} bytes → {out_file}"
                )
                return [out_file]

            except urllib.error.HTTPError as exc:
                print(
                    f"[RestJsonAdapter:{source_id}] HTTP {exc.code} on attempt {attempt}/{_MAX_RETRIES}: {exc.reason}",
                    file=sys.stderr,
                )
                last_exc = exc
            except urllib.error.URLError as exc:
                print(
                    f"[RestJsonAdapter:{source_id}] Network error on attempt {attempt}/{_MAX_RETRIES}: {exc.reason}",
                    file=sys.stderr,
                )
                last_exc = exc

            if attempt < _MAX_RETRIES:
                delay = _RETRY_BASE_DELAY_S ** attempt
                print(
                    f"[RestJsonAdapter:{source_id}] Retrying in {delay}s…",
                    file=sys.stderr,
                )
                time.sleep(delay)

        print(
            f"[RestJsonAdapter:{source_id}] All {_MAX_RETRIES} attempts failed. "
            f"Last error: {last_exc}",
            file=sys.stderr,
        )
        return []

    def validate(self, files: list[Path]) -> tuple[bool, list[str]]:
        """Verify each file is a non-empty, parseable JSON document.

        Returns:
            (True, []) if all files pass.
            (False, [errors]) otherwise.
        """
        if not files:
            return False, ["[RestJsonAdapter] No files to validate."]

        errors: list[str] = []
        for path in files:
            if not path.exists():
                errors.append(f"[RestJsonAdapter] File not found: {path}")
                continue
            try:
                content = path.read_bytes()
            except OSError as exc:
                errors.append(f"[RestJsonAdapter] Cannot read '{path}': {exc}")
                continue
            if not content:
                errors.append(f"[RestJsonAdapter] File is empty: {path}")
                continue
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError as exc:
                errors.append(f"[RestJsonAdapter] Invalid JSON in '{path}': {exc}")
                continue
            # Treat an empty JSON object/array as a soft warning, not a hard failure
            if parsed in ({}, []):
                errors.append(
                    f"[RestJsonAdapter] JSON in '{path}' is empty ({{}} or []). "
                    "The API may have returned no results for the given parameters."
                )

        return len(errors) == 0, errors

    def describe(self) -> dict[str, str]:
        return {
            "name": "REST JSON API",
            "requires_account": "false",
            "env_vars": "",
            "format": "json",
        }
