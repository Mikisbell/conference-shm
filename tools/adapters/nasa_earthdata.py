"""
tools/adapters/nasa_earthdata.py — NASA EarthData DataAdapter
==============================================================
Downloads datasets from NASA EarthData (https://earthdata.nasa.gov).
Requires EARTHDATA_USER and EARTHDATA_PASS environment variables.

Free account registration: https://urs.earthdata.nasa.gov

The download URL is read from source_config["download_url"] or
source_config["url"]. NASA EarthData uses HTTP Basic Auth via cookie-based
URS (Unified Registration System). We handle the auth redirect manually.
"""

from __future__ import annotations

import base64
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from domains.base import DataAdapter

_URS_AUTH_HOST = "urs.earthdata.nasa.gov"
# Back-off constants (retry algorithm, not config params)
_RETRY_BASE_DELAY_S = 2
_MAX_RETRIES = 3


def _load_dotenv(key: str) -> str | None:
    """Read key from os.environ first, then from .env file."""
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


class NasaEarthdataAdapter(DataAdapter):
    """DataAdapter for NASA EarthData (Earthdata Login required).

    Supports HTTP Basic Auth + URS redirect flow.
    Downloads the file at source_config["download_url"] (or "url") to output_dir.
    """

    def fetch(
        self,
        source_id: str,
        source_config: dict[str, Any],
        study_params: dict[str, Any],
        output_dir: Path,
    ) -> list[Path]:
        """Download from NASA EarthData with URS authentication.

        Returns:
            List with one Path on success, or [] if credentials missing / download fails.

        Raises:
            OSError: If output_dir is not writable.
        """
        user = _load_dotenv("EARTHDATA_USER")
        password = _load_dotenv("EARTHDATA_PASS")

        if not user or not password:
            print(
                "[NasaEarthdataAdapter] EARTHDATA_USER and/or EARTHDATA_PASS not set.\n"
                "  Register for a free account at:\n"
                "  https://urs.earthdata.nasa.gov\n"
                "  Then add to .env:\n"
                "    EARTHDATA_USER=your_username\n"
                "    EARTHDATA_PASS=your_password",
                file=sys.stderr,
            )
            return []

        url = source_config.get("download_url") or source_config.get("url", "")
        if not url:
            print(
                f"[NasaEarthdataAdapter:{source_id}] No 'url' or 'download_url' in source config. "
                "Add download_url: https://opendap.earthdata.nasa.gov/... to "
                "config/domains/environmental.yaml → data_sources.remote_sensing",
                file=sys.stderr,
            )
            return []

        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise OSError(
                f"[NasaEarthdataAdapter:{source_id}] Cannot create output directory "
                f"'{output_dir}': {exc}"
            ) from exc

        url_path = url.rstrip("/").split("/")[-1] or f"{source_id}.nc"
        out_file = output_dir / url_path

        # Build a password manager for NASA URS
        password_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
        password_mgr.add_password(None, _URS_AUTH_HOST, user, password)
        auth_handler = urllib.request.HTTPBasicAuthHandler(password_mgr)
        opener = urllib.request.build_opener(auth_handler)

        last_exc: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                req = urllib.request.Request(
                    url,
                    headers={"User-Agent": "belico-stack/1.0 (scientific research)"},
                )
                with opener.open(req, timeout=120) as resp:
                    raw = resp.read()

                if not raw:
                    print(
                        f"[NasaEarthdataAdapter:{source_id}] Server returned empty body.",
                        file=sys.stderr,
                    )
                    return []

                out_file.write_bytes(raw)
                print(
                    f"[NasaEarthdataAdapter:{source_id}] Downloaded {len(raw)} bytes → {out_file}"
                )
                return [out_file]

            except urllib.error.HTTPError as exc:
                print(
                    f"[NasaEarthdataAdapter:{source_id}] HTTP {exc.code} on attempt "
                    f"{attempt}/{_MAX_RETRIES}: {exc.reason}",
                    file=sys.stderr,
                )
                last_exc = exc
            except urllib.error.URLError as exc:
                print(
                    f"[NasaEarthdataAdapter:{source_id}] Network error on attempt "
                    f"{attempt}/{_MAX_RETRIES}: {exc.reason}",
                    file=sys.stderr,
                )
                last_exc = exc

            if attempt < _MAX_RETRIES:
                delay = _RETRY_BASE_DELAY_S ** attempt
                print(
                    f"[NasaEarthdataAdapter:{source_id}] Retrying in {delay}s…",
                    file=sys.stderr,
                )
                time.sleep(delay)

        print(
            f"[NasaEarthdataAdapter:{source_id}] All {_MAX_RETRIES} attempts failed. "
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
            return False, ["[NasaEarthdataAdapter] No files to validate."]

        errors: list[str] = []
        for path in files:
            if not path.exists():
                errors.append(f"[NasaEarthdataAdapter] File not found: {path}")
                continue
            try:
                size = path.stat().st_size
            except OSError as exc:
                errors.append(f"[NasaEarthdataAdapter] Cannot stat '{path}': {exc}")
                continue
            if size == 0:
                errors.append(f"[NasaEarthdataAdapter] File is empty: {path}")

        return len(errors) == 0, errors

    def describe(self) -> dict[str, str]:
        return {
            "name": "NASA EarthData",
            "requires_account": "true",
            "env_vars": "EARTHDATA_USER,EARTHDATA_PASS",
            "format": "NetCDF / HDF5 / GeoTIFF",
        }
