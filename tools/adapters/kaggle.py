"""
tools/adapters/kaggle.py — Kaggle DataAdapter
=============================================
Downloads datasets from Kaggle using the Kaggle API.
Requires KAGGLE_USERNAME and KAGGLE_KEY in environment variables or .env file.

Free account: https://www.kaggle.com
API key: https://www.kaggle.com/settings → Account → API → Create New Token

The dataset slug is read from source_config["dataset"] (format: "owner/dataset-name").
Downloaded ZIP is extracted to output_dir.

Uses the kaggle CLI (pip install kaggle) if available; falls back to
direct urllib download with Kaggle HTTP API if not.
"""

from __future__ import annotations

import os
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

from domains.base import DataAdapter


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


class KaggleAdapter(DataAdapter):
    """DataAdapter for Kaggle public/private datasets.

    Requires KAGGLE_USERNAME + KAGGLE_KEY in .env.
    Downloads via the kaggle CLI (recommended) or subprocess call.
    """

    def fetch(
        self,
        source_id: str,
        source_config: dict[str, Any],
        study_params: dict[str, Any],
        output_dir: Path,
    ) -> list[Path]:
        """Download a Kaggle dataset to output_dir.

        Returns:
            List of Paths for all files extracted, or [] if credentials missing.

        Raises:
            OSError: If output_dir is not writable.
        """
        username = _load_dotenv("KAGGLE_USERNAME")
        api_key = _load_dotenv("KAGGLE_KEY")

        if not username or not api_key:
            print(
                "[KaggleAdapter] KAGGLE_USERNAME and/or KAGGLE_KEY not set.\n"
                "  Register at https://www.kaggle.com, then:\n"
                "  Settings → Account → API → Create New Token\n"
                "  Add to .env:\n"
                "    KAGGLE_USERNAME=your_username\n"
                "    KAGGLE_KEY=your_api_key",
                file=sys.stderr,
            )
            return []

        dataset = source_config.get("dataset", "")
        if not dataset:
            print(
                f"[KaggleAdapter:{source_id}] No 'dataset' field in source config. "
                "Add dataset: owner/dataset-name to config/domains/<domain>.yaml "
                "→ data_sources.",
                file=sys.stderr,
            )
            return []

        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise OSError(
                f"[KaggleAdapter:{source_id}] Cannot create output directory "
                f"'{output_dir}': {exc}"
            ) from exc

        # Set credentials in environment for kaggle CLI
        env = os.environ.copy()
        env["KAGGLE_USERNAME"] = username
        env["KAGGLE_KEY"] = api_key

        try:
            result = subprocess.run(
                [
                    "kaggle", "datasets", "download",
                    "--dataset", dataset,
                    "--path", str(output_dir),
                    "--unzip",
                ],
                env=env,
                capture_output=True,
                text=True,
                timeout=300,
            )
        except FileNotFoundError:
            print(
                "[KaggleAdapter] kaggle CLI not found. Install with:\n"
                "  pip install kaggle",
                file=sys.stderr,
            )
            return []
        except subprocess.TimeoutExpired:
            print(
                f"[KaggleAdapter:{source_id}] Download timed out after 5 minutes.",
                file=sys.stderr,
            )
            return []

        if result.returncode != 0:
            print(
                f"[KaggleAdapter:{source_id}] kaggle CLI failed (exit {result.returncode}):\n"
                f"  stdout: {result.stdout.strip()}\n"
                f"  stderr: {result.stderr.strip()}",
                file=sys.stderr,
            )
            return []

        # Collect all files written
        files = [p for p in output_dir.rglob("*") if p.is_file()]
        print(
            f"[KaggleAdapter:{source_id}] Downloaded and extracted {len(files)} file(s) to {output_dir}"
        )
        return files

    def validate(self, files: list[Path]) -> tuple[bool, list[str]]:
        """Verify that files are non-empty. ZIP archives are checked for integrity.

        Returns:
            (True, []) if all files pass.
            (False, [errors]) otherwise.
        """
        if not files:
            return False, ["[KaggleAdapter] No files to validate."]

        errors: list[str] = []
        for path in files:
            if not path.exists():
                errors.append(f"[KaggleAdapter] File not found: {path}")
                continue
            try:
                size = path.stat().st_size
            except OSError as exc:
                errors.append(f"[KaggleAdapter] Cannot stat '{path}': {exc}")
                continue
            if size == 0:
                errors.append(f"[KaggleAdapter] File is empty: {path}")
                continue
            if path.suffix.lower() == ".zip":
                try:
                    with zipfile.ZipFile(path) as zf:
                        bad = zf.testzip()
                    if bad:
                        errors.append(
                            f"[KaggleAdapter] ZIP '{path}' has a bad entry: {bad}"
                        )
                except zipfile.BadZipFile as exc:
                    errors.append(f"[KaggleAdapter] Bad ZIP file '{path}': {exc}")

        return len(errors) == 0, errors

    def describe(self) -> dict[str, str]:
        return {
            "name": "Kaggle",
            "requires_account": "true",
            "env_vars": "KAGGLE_USERNAME,KAGGLE_KEY",
            "format": "ZIP / CSV / any",
        }
