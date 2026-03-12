"""
tools/adapters/fred.py — FRED Federal Reserve Economic Data Adapter
====================================================================
Downloads time-series observations from the FRED API
(https://api.stlouisfed.org/fred/series/observations).

Requires FRED_API_KEY in environment (free registration at
https://fred.stlouisfed.org/docs/api/api_key.html).

Series IDs to download come from source_config["series_ids"] (list of str)
or study_params["series_ids"]. Each series is saved as
{output_dir}/{series_id}.csv.
"""

from __future__ import annotations

import csv
import io
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from domains.base import DataAdapter

_FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"
# Back-off constants (part of the retry algorithm, not config params)
_RETRY_BASE_DELAY_S = 2
_MAX_RETRIES = 3


def _load_dotenv_key(key: str) -> str | None:
    """Read key from os.environ first, then from .env file if present."""
    value = os.environ.get(key)
    if value:
        return value
    dotenv_path = Path(".env")
    if dotenv_path.exists():
        try:
            for line in dotenv_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith(f"{key}="):
                    return line.split("=", 1)[1].strip().strip("\"'")
        except OSError:
            pass
    return None


class FredAdapter(DataAdapter):
    """DataAdapter for FRED (Federal Reserve Economic Data).

    Fetches one CSV file per series ID. Series IDs are read from
    source_config["series_ids"] or study_params["series_ids"].
    """

    def fetch(
        self,
        source_id: str,
        source_config: dict[str, Any],
        study_params: dict[str, Any],
        output_dir: Path,
    ) -> list[Path]:
        """Download FRED series observations to output_dir.

        Returns:
            List of Path objects (one per series), or [] if API key missing.

        Raises:
            OSError: If output_dir is not writable.
        """
        api_key = _load_dotenv_key("FRED_API_KEY")
        if not api_key:
            print(
                "[FredAdapter] FRED_API_KEY not found in environment or .env file.\n"
                "  Register for a free API key at:\n"
                "  https://fred.stlouisfed.org/docs/api/api_key.html\n"
                "  Then add to .env: FRED_API_KEY=your_key_here",
                file=sys.stderr,
            )
            return []

        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise OSError(
                f"[FredAdapter:{source_id}] Cannot create output directory "
                f"'{output_dir}': {exc}"
            ) from exc

        # Series IDs: prefer source_config, then study_params
        series_ids: list[str] = (
            source_config.get("series_ids")
            or study_params.get("series_ids")
            or []
        )
        if not series_ids:
            print(
                f"[FredAdapter:{source_id}] No series_ids found in source config or study_params.\n"
                "  Add series_ids: [GDP, UNRATE, ...] to config/domains/economics.yaml "
                "→ data_sources.macro",
                file=sys.stderr,
            )
            return []

        # Optional date range from study_params
        observation_start = study_params.get("start_year", "")
        observation_end = study_params.get("end_year", "")

        written: list[Path] = []
        for series_id in series_ids:
            out_file = output_dir / f"{series_id}.csv"
            params: dict[str, str] = {
                "series_id": series_id,
                "api_key": api_key,
                "file_type": "json",
            }
            if observation_start:
                params["observation_start"] = f"{observation_start}-01-01"
            if observation_end:
                params["observation_end"] = f"{observation_end}-12-31"

            url = _FRED_BASE_URL + "?" + urllib.parse.urlencode(params)
            last_exc: Exception | None = None

            for attempt in range(1, _MAX_RETRIES + 1):
                try:
                    req = urllib.request.Request(
                        url,
                        headers={"User-Agent": "belico-stack/1.0 (scientific research)"},
                    )
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        raw = resp.read()

                    try:
                        data = json.loads(raw)
                    except json.JSONDecodeError as exc:
                        print(
                            f"[FredAdapter:{series_id}] Unexpected non-JSON response: {exc}",
                            file=sys.stderr,
                        )
                        break

                    observations = data.get("observations", [])
                    if not observations:
                        print(
                            f"[FredAdapter:{series_id}] API returned 0 observations. "
                            "Check series ID and date range.",
                            file=sys.stderr,
                        )
                        break

                    # Write as CSV with columns: date, value
                    with out_file.open("w", newline="", encoding="utf-8") as fh:
                        writer = csv.DictWriter(
                            fh, fieldnames=["date", "value", "realtime_start", "realtime_end"]
                        )
                        writer.writeheader()
                        writer.writerows(observations)

                    print(
                        f"[FredAdapter:{series_id}] {len(observations)} observations → {out_file}"
                    )
                    written.append(out_file)
                    break

                except urllib.error.HTTPError as exc:
                    print(
                        f"[FredAdapter:{series_id}] HTTP {exc.code} on attempt "
                        f"{attempt}/{_MAX_RETRIES}: {exc.reason}",
                        file=sys.stderr,
                    )
                    last_exc = exc
                except urllib.error.URLError as exc:
                    print(
                        f"[FredAdapter:{series_id}] Network error on attempt "
                        f"{attempt}/{_MAX_RETRIES}: {exc.reason}",
                        file=sys.stderr,
                    )
                    last_exc = exc

                if attempt < _MAX_RETRIES:
                    delay = _RETRY_BASE_DELAY_S ** attempt
                    print(
                        f"[FredAdapter:{series_id}] Retrying in {delay}s…",
                        file=sys.stderr,
                    )
                    time.sleep(delay)
                else:
                    print(
                        f"[FredAdapter:{series_id}] All {_MAX_RETRIES} attempts failed. "
                        f"Last error: {last_exc}",
                        file=sys.stderr,
                    )

        return written

    def validate(self, files: list[Path]) -> tuple[bool, list[str]]:
        """Verify each CSV file is non-empty and has a 'value' column.

        Returns:
            (True, []) if all files pass.
            (False, [errors]) otherwise.
        """
        if not files:
            return False, ["[FredAdapter] No files to validate."]

        errors: list[str] = []
        for path in files:
            if not path.exists():
                errors.append(f"[FredAdapter] File not found: {path}")
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except OSError as exc:
                errors.append(f"[FredAdapter] Cannot read '{path}': {exc}")
                continue
            if not content.strip():
                errors.append(f"[FredAdapter] File is empty: {path}")
                continue
            try:
                reader = csv.DictReader(io.StringIO(content))
                rows = list(reader)
            except csv.Error as exc:
                errors.append(f"[FredAdapter] CSV parse error in '{path}': {exc}")
                continue
            if not rows:
                errors.append(f"[FredAdapter] No data rows in '{path}'.")
                continue
            if "value" not in (reader.fieldnames or []):
                errors.append(
                    f"[FredAdapter] Missing 'value' column in '{path}'. "
                    f"Columns found: {reader.fieldnames}"
                )

        return len(errors) == 0, errors

    def describe(self) -> dict[str, str]:
        return {
            "name": "FRED Economic Data",
            "requires_account": "true",
            "env_vars": "FRED_API_KEY",
            "format": "csv",
        }
