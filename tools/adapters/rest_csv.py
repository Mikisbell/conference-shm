"""
tools/adapters/rest_csv.py — Generic REST CSV DataAdapter
==========================================================
Performs a GET request to source_config["url"] and saves the CSV response
to output_dir/{source_id}.csv. Validates using csv.reader.

Uses only urllib.request (stdlib) — no extra dependencies.
Retries up to 3 times with exponential back-off.
"""

from __future__ import annotations

import csv
import io
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from domains.base import DataAdapter

# Mathematical back-off constants (not config params)
_RETRY_BASE_DELAY_S = 2
_MAX_RETRIES = 3


class RestCsvAdapter(DataAdapter):
    """DataAdapter for REST APIs that return CSV.

    Reads endpoint from source_config["url"].
    Forwards study_params keys listed in source_config["query_params"] as
    query string parameters.
    """

    def fetch(
        self,
        source_id: str,
        source_config: dict[str, Any],
        study_params: dict[str, Any],
        output_dir: Path,
    ) -> list[Path]:
        """GET source_config["url"] and save response as {source_id}.csv.

        Returns:
            List with one Path on success, [] on failure.

        Raises:
            OSError: If output_dir is not writable.
        """
        url = source_config.get("url", "")
        if not url:
            print(
                f"[RestCsvAdapter:{source_id}] No 'url' field in source config. "
                "Add url: <endpoint> to config/domains/<domain>.yaml.",
                file=sys.stderr,
            )
            return []

        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise OSError(
                f"[RestCsvAdapter:{source_id}] Cannot create output directory "
                f"'{output_dir}': {exc}"
            ) from exc

        query_keys: list[str] = source_config.get("query_params", [])
        query: dict[str, str] = {}
        for key in query_keys:
            if key in study_params:
                query[key] = str(study_params[key])

        if query:
            url = url + "?" + urllib.parse.urlencode(query)

        out_file = output_dir / f"{source_id}.csv"
        last_exc: Exception | None = None

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "belico-stack/1.0 (scientific research)"},
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    raw = resp.read()

                # Quick CSV sanity check before writing
                try:
                    sample = raw[:4096].decode("utf-8", errors="replace")
                    list(csv.reader(io.StringIO(sample)))
                except csv.Error as exc:
                    print(
                        f"[RestCsvAdapter:{source_id}] Response does not look like CSV: {exc}",
                        file=sys.stderr,
                    )
                    return []

                out_file.write_bytes(raw)
                print(
                    f"[RestCsvAdapter:{source_id}] Saved {len(raw)} bytes → {out_file}"
                )
                return [out_file]

            except urllib.error.HTTPError as exc:
                print(
                    f"[RestCsvAdapter:{source_id}] HTTP {exc.code} on attempt {attempt}/{_MAX_RETRIES}: {exc.reason}",
                    file=sys.stderr,
                )
                last_exc = exc
            except urllib.error.URLError as exc:
                print(
                    f"[RestCsvAdapter:{source_id}] Network error on attempt {attempt}/{_MAX_RETRIES}: {exc.reason}",
                    file=sys.stderr,
                )
                last_exc = exc

            if attempt < _MAX_RETRIES:
                delay = _RETRY_BASE_DELAY_S ** attempt
                print(
                    f"[RestCsvAdapter:{source_id}] Retrying in {delay}s…",
                    file=sys.stderr,
                )
                time.sleep(delay)

        print(
            f"[RestCsvAdapter:{source_id}] All {_MAX_RETRIES} attempts failed. "
            f"Last error: {last_exc}",
            file=sys.stderr,
        )
        return []

    def validate(self, files: list[Path]) -> tuple[bool, list[str]]:
        """Verify each file is non-empty and parseable as CSV.

        Returns:
            (True, []) if all files pass.
            (False, [errors]) otherwise.
        """
        if not files:
            return False, ["[RestCsvAdapter] No files to validate."]

        errors: list[str] = []
        for path in files:
            if not path.exists():
                errors.append(f"[RestCsvAdapter] File not found: {path}")
                continue
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                errors.append(f"[RestCsvAdapter] Cannot read '{path}': {exc}")
                continue
            if not content.strip():
                errors.append(f"[RestCsvAdapter] File is empty: {path}")
                continue
            try:
                rows = list(csv.reader(io.StringIO(content)))
            except csv.Error as exc:
                errors.append(f"[RestCsvAdapter] CSV parse error in '{path}': {exc}")
                continue
            # Header + at least one data row
            if len(rows) < 2:
                errors.append(
                    f"[RestCsvAdapter] '{path}' has fewer than 2 rows "
                    "(header + data). The API may have returned no results."
                )

        return len(errors) == 0, errors

    def describe(self) -> dict[str, str]:
        return {
            "name": "REST CSV API",
            "requires_account": "false",
            "env_vars": "",
            "format": "csv",
        }
