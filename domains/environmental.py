"""
domains/environmental.py — Environmental Engineering Domain Backend
===================================================================

Concrete implementation of DomainBackend for the environmental domain.
Data-driven: GIS, remote sensing, field campaigns — no physical FEM solver.

Registered in: config/domains/environmental.yaml
  solver.backend_module: "domains.environmental"
  solver.backend_class:  "EnvironmentalBackend"

Status: PLANNED — run_compute() is a scaffold. Implement per-paper.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from domains.base import DomainBackend

# ─── Required SSOT keys for the environmental domain ─────────────────────────
_REQUIRED_SSOT_KEYS = [
    ("environmental", "study_area"),
    ("environmental", "time_series"),
    ("environmental", "targets"),
]


class EnvironmentalBackend(DomainBackend):
    """DomainBackend for environmental engineering & ecology papers.

    Data pipeline: field datasets + public APIs (OpenAQ, GBIF, Earth Engine,
    ERA5). No physical FEM solver. No hardware emulator.
    """

    # ── 1. Dependencies ───────────────────────────────────────────────────────

    def get_dependencies(self) -> dict[str, list[str]]:
        return {
            "python": [
                "numpy>=1.24",
                "scipy>=1.10",
                "matplotlib>=3.7",
                "pandas>=2.0",
                "pyyaml>=6.0",
                "statsmodels>=0.14",
                "scikit-learn>=1.3",
            ],
            "system": [],  # gdal needed for geopandas/rasterio but optional
            "optional": [
                "geopandas>=0.14",
                "rasterio>=1.3",
                "geemap>=0.28",
                "pysal>=23.0",
                "netCDF4>=1.6",
                "xarray>=2023.0",
            ],
        }

    # ── 2. Compute ────────────────────────────────────────────────────────────

    def run_compute(self, params: dict[str, Any]) -> dict[str, Any]:
        """Run the environmental data pipeline.

        TODO: Implement per paper. Scaffold returns converged=False with
        a clear diagnostic so the gate blocks instead of silently skipping.

        Steps to implement:
          1. Download / load field data (GeoTIFF, NetCDF, CSV)
          2. Compute indices (NDVI, AQI, species richness, etc.)
          3. Run spatial / temporal statistics
          4. Save results to data/processed/
        """
        print(
            "[EnvironmentalBackend] run_compute() is not yet implemented. "
            "Create tools/fetch_environmental_data.py and wire it here.",
            file=sys.stderr,
        )
        return {
            "converged": False,
            "error": (
                "[EnvironmentalBackend] Compute pipeline not implemented. "
                "See domains/environmental.py → run_compute() scaffold."
            ),
            "files": [],
            "outputs": {},
        }

    # ── 3. SSOT validation ────────────────────────────────────────────────────

    def validate_ssot(self) -> tuple[bool, list[str]]:
        """Check config/params.yaml for environmental.* section."""
        import yaml as _yaml

        params_path = Path("config/params.yaml")
        if not params_path.exists():
            return False, ["[EnvironmentalBackend] config/params.yaml not found."]

        try:
            with params_path.open("r", encoding="utf-8") as fh:
                ssot = _yaml.safe_load(fh)
        except _yaml.YAMLError as exc:
            return False, [f"[EnvironmentalBackend] params.yaml parse error: {exc}"]

        env_section = ssot.get("environmental")
        if env_section is None:
            return False, [
                "[EnvironmentalBackend] Missing 'environmental:' section in "
                "config/params.yaml. Add it when activating this domain "
                "(see config/domains/environmental.yaml → params_namespace)."
            ]

        errors: list[str] = []
        for _, key in _REQUIRED_SSOT_KEYS:
            if key not in env_section:
                errors.append(
                    f"[EnvironmentalBackend] Missing SSOT key: "
                    f"environmental.{key} in config/params.yaml"
                )

        return len(errors) == 0, errors

    # ── 4. Emulator ───────────────────────────────────────────────────────────

    def get_emulator(self) -> None:
        """No hardware emulator for the environmental domain.

        Field sensors (meteorological stations, UAV sensors, IoT air quality
        monitors) connect via their own APIs or CSV exports.
        """
        return None
