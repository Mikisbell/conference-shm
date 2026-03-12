"""
tools/adapters/local_file.py — Local File DataAdapter
======================================================
For domains where data is already on disk (e.g. structural: PEER .AT2 records).
Does not download anything. Scans output_dir for existing files and reports what
is available. If nothing is found, prints instructions for the user.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from domains.base import DataAdapter


class LocalFileAdapter(DataAdapter):
    """DataAdapter for data sources that are already on disk.

    No network access. Treats local_path from source_config as the scan target.
    Falls back to output_dir if local_path is not declared.
    """

    def fetch(
        self,
        source_id: str,
        source_config: dict[str, Any],
        study_params: dict[str, Any],
        output_dir: Path,
    ) -> list[Path]:
        """Scan local_path (or output_dir) for existing files.

        Does not download. If the directory is empty or missing, prints
        user instructions and returns an empty list.

        Returns:
            List of Path objects for all files found on disk.

        Raises:
            OSError: If output_dir cannot be created.
        """
        # Prefer the declared local_path; fall back to output_dir
        local_path_str = source_config.get("local_path", "")
        scan_dir = Path(local_path_str) if local_path_str else output_dir

        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise OSError(
                f"[LocalFileAdapter:{source_id}] Cannot create output directory "
                f"'{output_dir}': {exc}"
            ) from exc

        if not scan_dir.exists():
            print(
                f"[LocalFileAdapter:{source_id}] Directory '{scan_dir}' does not exist.\n"
                f"  For PEER NGA-West2 records: download .AT2 files from\n"
                f"  https://ngawest2.berkeley.edu and place them in '{scan_dir}'.\n"
                f"  Then re-run: python3 tools/fetch_domain_data.py --domain structural --verify",
                file=sys.stderr,
            )
            return []

        files = [p for p in scan_dir.rglob("*") if p.is_file()]
        if not files:
            print(
                f"[LocalFileAdapter:{source_id}] Directory '{scan_dir}' is empty.\n"
                f"  Source name : {source_config.get('name', source_id)}\n"
                f"  Format      : {source_config.get('format', 'unknown')}\n"
                f"  URL         : {source_config.get('url', 'N/A')}\n"
                f"  Download data manually and place it in '{scan_dir}'.",
                file=sys.stderr,
            )
            return []

        print(
            f"[LocalFileAdapter:{source_id}] Found {len(files)} file(s) in '{scan_dir}'."
        )
        return files

    def validate(self, files: list[Path]) -> tuple[bool, list[str]]:
        """Verify that each file is non-empty and readable.

        Returns:
            (True, []) if all files are OK.
            (False, [errors]) listing any unreadable or empty files.
        """
        if not files:
            return False, [
                "[LocalFileAdapter] No files to validate. "
                "Run fetch() first or place data in the local_path directory."
            ]

        errors: list[str] = []
        for path in files:
            if not path.exists():
                errors.append(f"[LocalFileAdapter] File not found: {path}")
                continue
            try:
                size = path.stat().st_size
            except OSError as exc:
                errors.append(f"[LocalFileAdapter] Cannot stat '{path}': {exc}")
                continue
            if size == 0:
                errors.append(f"[LocalFileAdapter] File is empty: {path}")

        return len(errors) == 0, errors

    def describe(self) -> dict[str, str]:
        return {
            "name": "Local File",
            "requires_account": "false",
            "env_vars": "",
            "format": "any",
        }
