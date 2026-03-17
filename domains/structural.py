"""
domains/structural.py — Structural Engineering Domain Backend
=============================================================

Concrete implementation of DomainBackend for the structural domain.
Wraps src/physics/torture_chamber.py (OpenSeesPy) + arduino_emu.py.

Registered in: config/domains/structural.yaml
  solver.backend_module: "domains.structural"
  solver.backend_class:  "StructuralBackend"
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from domains.base import DomainBackend

# ─── Required SSOT keys for the structural domain ────────────────────────────
_REQUIRED_SSOT_KEYS = [
    ("structure", "mass_m"),
    ("structure", "stiffness_k"),
    ("nonlinear", "steel"),
    ("nonlinear", "concrete"),
    ("damping", "ratio_xi"),
    ("acquisition", "sample_rate_hz"),
]


class StructuralBackend(DomainBackend):
    """DomainBackend for structural / SHM / seismic papers.

    Uses OpenSeesPy (torture_chamber.py) for FEM simulation and
    arduino_emu.py for hardware-in-the-loop emulation.
    """

    # ── 1. Dependencies ───────────────────────────────────────────────────────

    def get_dependencies(self) -> dict[str, list[str]]:
        return {
            "python": [
                "openseespy>=3.4",
                "numpy>=1.24",
                "scipy>=1.10",
                "matplotlib>=3.7",
                "pandas>=2.0",
                "pyyaml>=6.0",
            ],
            "system": [],
            "optional": [],
        }

    # ── 2. Compute ────────────────────────────────────────────────────────────

    def run_compute(self, params: dict[str, Any]) -> dict[str, Any]:
        """Run structural simulation via CrossValidationEngine.

        Delegates to src/physics/cross_validation.CrossValidationEngine which
        runs the A/B scenario comparison and writes data/processed/cv_results.json.

        For the full campaign (spectral engine + statistics), use:
          python3 tools/run_torture_chamber.py  [c2_runner CLI]
        """
        import json  # noqa: PLC0415
        from pathlib import Path  # noqa: PLC0415

        try:
            from src.physics.cross_validation import CrossValidationEngine  # type: ignore[import]
        except ImportError as exc:
            return {
                "converged": False,
                "error": (
                    f"[StructuralBackend] Cannot import CrossValidationEngine: {exc}. "
                    "Run: pip install openseespy scipy numpy"
                ),
                "files": [],
                "outputs": {},
            }

        try:
            cycles = int(
                (params or {})
                .get("simulation", {})
                .get("cycles", {})
                .get("value", 500)
            )
            engine = CrossValidationEngine(cycles=cycles)
            results = engine.execute_validation_suite()

            cv_out = Path("data/processed/cv_results.json")
            cv_out.parent.mkdir(parents=True, exist_ok=True)
            with open(cv_out, "w", encoding="utf-8") as fh:
                json.dump(results, fh)

            return {
                "converged": True,
                "files": [str(cv_out)],
                "outputs": results,
            }
        except Exception as exc:  # noqa: BLE001 — catch-all for solver errors
            return {
                "converged": False,
                "error": f"[StructuralBackend] Solver error: {exc}",
                "files": [],
                "outputs": {},
            }

    # ── 3. SSOT validation ────────────────────────────────────────────────────

    def validate_ssot(self) -> tuple[bool, list[str]]:
        """Check that config/params.yaml has required structural keys."""
        import yaml as _yaml

        params_path = Path("config/params.yaml")
        if not params_path.exists():
            return False, ["[StructuralBackend] config/params.yaml not found."]

        try:
            with params_path.open("r", encoding="utf-8") as fh:
                ssot = _yaml.safe_load(fh)
        except _yaml.YAMLError as exc:
            return False, [f"[StructuralBackend] params.yaml parse error: {exc}"]

        errors: list[str] = []
        for section, key in _REQUIRED_SSOT_KEYS:
            section_data = ssot.get(section, {})
            if not isinstance(section_data, dict) or key not in section_data:
                errors.append(
                    f"[StructuralBackend] Missing SSOT key: {section}.{key} "
                    f"in config/params.yaml"
                )

        return len(errors) == 0, errors

    # ── 4. Emulator ───────────────────────────────────────────────────────────

    def get_emulator(self) -> dict[str, Any]:
        """Return arduino_emu.py emulator configuration."""
        return {
            "tool": "tools/arduino_emu.py",
            "modes": [
                "sano", "resonance", "dano_leve",
                "dano_critico", "presa", "dropout",
                "nicla_sano", "nicla_dano", "nicla_critico",
            ],
            "launch": "python3 tools/arduino_emu.py {mode} {freq_hz}",
        }
