"""
tools/adapters/physionet.py — PhysioNet DataAdapter
====================================================
Downloads datasets from PhysioNet (https://physionet.org) using direct
HTTP download. PhysioNet provides many datasets publicly without authentication.

The URL to download from is read from source_config["url"] or
source_config["download_url"]. The file is saved as-is to output_dir.

No account required for public datasets (MIT-BIH, PTB-XL, etc.).
"""

from __future__ import annotations

import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from domains.base import DataAdapter

# Back-off constants (retry algorithm, not config params)
_RETRY_BASE_DELAY_S = 2
_MAX_RETRIES = 3


class PhysioNetAdapter(DataAdapter):
    """DataAdapter for PhysioNet public datasets.

    Downloads a single file (or a listing page) from PhysioNet.
    For WFDB multi-file datasets, the download_url should point to a
    zip archive or a specific record. Individual WFDB record parsing
    is delegated to the caller (e.g. via the mne or wfdb library).
    """

    def fetch(
        self,
        source_id: str,
        source_config: dict[str, Any],
        study_params: dict[str, Any],
        output_dir: Path,
    ) -> list[Path]:
        """Download from PhysioNet to output_dir.

        Uses source_config["download_url"] if present, otherwise
        falls back to source_config["url"].

        Returns:
            List with one Path on success, [] on failure.

        Raises:
            OSError: If output_dir is not writable.
        """
        url = source_config.get("download_url") or source_config.get("url", "")
        if not url:
            print(
                f"[PhysioNetAdapter:{source_id}] No 'url' or 'download_url' in source config. "
                "Add download_url: https://physionet.org/files/<db>/<version>/<record>.zip "
                "to config/domains/biomedical.yaml → data_sources.",
                file=sys.stderr,
            )
            return []

        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise OSError(
                f"[PhysioNetAdapter:{source_id}] Cannot create output directory "
                f"'{output_dir}': {exc}"
            ) from exc

        # Derive filename from URL
        url_path = url.rstrip("/").split("/")[-1] or f"{source_id}.dat"
        out_file = output_dir / url_path
        last_exc: Exception | None = None

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "belico-stack/1.0 (scientific research)"},
                )
                with urllib.request.urlopen(req, timeout=60) as resp:
                    raw = resp.read()

                if not raw:
                    print(
                        f"[PhysioNetAdapter:{source_id}] Server returned empty body for '{url}'.",
                        file=sys.stderr,
                    )
                    return []

                out_file.write_bytes(raw)
                print(
                    f"[PhysioNetAdapter:{source_id}] Downloaded {len(raw)} bytes → {out_file}"
                )
                return [out_file]

            except urllib.error.HTTPError as exc:
                print(
                    f"[PhysioNetAdapter:{source_id}] HTTP {exc.code} on attempt "
                    f"{attempt}/{_MAX_RETRIES}: {exc.reason}",
                    file=sys.stderr,
                )
                last_exc = exc
            except urllib.error.URLError as exc:
                print(
                    f"[PhysioNetAdapter:{source_id}] Network error on attempt "
                    f"{attempt}/{_MAX_RETRIES}: {exc.reason}",
                    file=sys.stderr,
                )
                last_exc = exc

            if attempt < _MAX_RETRIES:
                delay = _RETRY_BASE_DELAY_S ** attempt
                print(
                    f"[PhysioNetAdapter:{source_id}] Retrying in {delay}s…",
                    file=sys.stderr,
                )
                time.sleep(delay)

        print(
            f"[PhysioNetAdapter:{source_id}] All {_MAX_RETRIES} attempts failed. "
            f"Last error: {last_exc}",
            file=sys.stderr,
        )
        return []

    def validate(self, files: list[Path]) -> tuple[bool, list[str]]:
        """Verify each downloaded file is non-empty.

        Returns:
            (True, []) if all files are OK.
            (False, [errors]) otherwise.
        """
        if not files:
            return False, ["[PhysioNetAdapter] No files to validate."]

        errors: list[str] = []
        for path in files:
            if not path.exists():
                errors.append(f"[PhysioNetAdapter] File not found: {path}")
                continue
            try:
                size = path.stat().st_size
            except OSError as exc:
                errors.append(f"[PhysioNetAdapter] Cannot stat '{path}': {exc}")
                continue
            if size == 0:
                errors.append(f"[PhysioNetAdapter] File is empty: {path}")

        return len(errors) == 0, errors

    def describe(self) -> dict[str, str]:
        return {
            "name": "PhysioNet",
            "requires_account": "false",
            "env_vars": "",
            "format": "WFDB / CSV / ZIP",
        }
