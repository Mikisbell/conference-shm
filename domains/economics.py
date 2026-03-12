"""
domains/economics.py — Economics & Quantitative Social Sciences Domain Backend
==============================================================================

Concrete implementation of DomainBackend for the economics domain.
Data-driven: econometrics, time-series forecasting, causal inference,
panel data, policy evaluation. No physical FEM solver.

Registered in: config/domains/economics.yaml
  solver.backend_module: "domains.economics"
  solver.backend_class:  "EconomicsBackend"

Status: PLANNED — run_compute() is a scaffold. Implement per-paper.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from domains.base import DomainBackend

# ─── Required SSOT keys for the economics domain ─────────────────────────────
_REQUIRED_SSOT_KEYS = [
    ("economics", "model"),
    ("economics", "data"),
    ("economics", "thresholds"),
]


class EconomicsBackend(DomainBackend):
    """DomainBackend for economics & quantitative social science papers.

    Data pipeline: FRED, World Bank, IPUMS panel/time-series data +
    econometric estimation (OLS, IV, panel data, diff-in-diff).
    No physical FEM solver. No hardware emulator.
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
            "system": [],
            "optional": [
                "linearmodels>=5.3",       # panel data, IV estimation, GMM
                "fredapi>=0.5",            # FRED macroeconomic data
                "pandas-datareader>=0.10", # World Bank, OECD, Yahoo Finance
                "pymc>=5.0",               # Bayesian econometrics
                "causalml>=0.14",          # causal inference, heterogeneous treatment effects
            ],
        }

    # ── 2. Compute ────────────────────────────────────────────────────────────

    def run_compute(self, params: dict[str, Any]) -> dict[str, Any]:
        """Run the econometric estimation pipeline.

        TODO: Implement per paper. Scaffold returns converged=False with a
        clear diagnostic so the gate blocks instead of silently skipping.

        Steps to implement:
          1. Load panel/time-series dataset (FRED CSV, World Bank CSV, IPUMS)
          2. Construct outcome, treatment, and control variables
          3. Run baseline OLS / IV / panel estimator (statsmodels / linearmodels)
          4. Compute clustered SEs, Wald test, bootstrap CI
          5. Run robustness checks and heterogeneity analysis
          6. Save results to data/processed/ (panel_data.csv, event_study.csv, etc.)
        """
        print(
            "[EconomicsBackend] run_compute() is not yet implemented. "
            "Implement the econometric pipeline per paper.",
            file=sys.stderr,
        )
        return {
            "converged": False,
            "error": (
                "EconomicsBackend.run_compute() not yet implemented "
                "— domain status: planned. "
                "See domains/economics.py → run_compute() scaffold."
            ),
            "files": [],
            "outputs": {},
        }

    # ── 3. SSOT validation ────────────────────────────────────────────────────

    def validate_ssot(self) -> tuple[bool, list[str]]:
        """Check config/params.yaml for economics.* section."""
        import yaml as _yaml

        params_path = Path("config/params.yaml")
        if not params_path.exists():
            return False, ["[EconomicsBackend] config/params.yaml not found."]

        try:
            with params_path.open("r", encoding="utf-8") as fh:
                ssot = _yaml.safe_load(fh)
        except _yaml.YAMLError as exc:
            return False, [f"[EconomicsBackend] params.yaml parse error: {exc}"]

        econ_section = ssot.get("economics")
        if econ_section is None:
            return False, [
                "[EconomicsBackend] Missing 'economics:' section in "
                "config/params.yaml. Add it when activating this domain "
                "(see config/domains/economics.yaml → params_namespace)."
            ]

        errors: list[str] = []
        for _, key in _REQUIRED_SSOT_KEYS:
            if key not in econ_section:
                errors.append(
                    f"[EconomicsBackend] Missing SSOT key: "
                    f"economics.{key} in config/params.yaml"
                )

        return len(errors) == 0, errors

    # ── 4. Emulator ───────────────────────────────────────────────────────────

    def get_emulator(self) -> None:
        """No hardware emulator for the economics domain.

        Domain uses panel and time-series datasets from public APIs
        (FRED, World Bank, IPUMS). No real-time sensor bridge required.
        """
        return None
