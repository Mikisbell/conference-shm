"""
domains/biomedical.py — Biomedical Engineering Domain Backend
=============================================================

Concrete implementation of DomainBackend for the biomedical domain.
Data-driven: biosignal processing (ECG/EEG/EMG), ML classification,
wearable sensors, clinical data mining. No physical FEM solver.

Registered in: config/domains/biomedical.yaml
  solver.backend_module: "domains.biomedical"
  solver.backend_class:  "BiomedicalBackend"

Status: PLANNED — run_compute() is a scaffold. Implement per-paper.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from domains.base import DomainBackend

# ─── Required SSOT keys for the biomedical domain ────────────────────────────
_REQUIRED_SSOT_KEYS = [
    ("biomedical", "signal"),
    ("biomedical", "subject"),
    ("biomedical", "model"),
]


class BiomedicalBackend(DomainBackend):
    """DomainBackend for biomedical engineering & health informatics papers.

    Data pipeline: public biosignal datasets (PhysioNet, OpenNeuro) +
    feature extraction + ML classification. No physical FEM solver.
    No hardware emulator (wearables connect via their own APIs).
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
                "scikit-learn>=1.3",
            ],
            "system": [],
            "optional": [
                "mne>=1.5",       # EEG/MEG signal processing
                "neurokit2>=0.2", # physiological signal analysis (HRV, ECG features)
                "pydicom>=2.4",   # DICOM medical image I/O
                "antropy>=0.1",   # entropy features for biosignals
            ],
        }

    # ── 2. Compute ────────────────────────────────────────────────────────────

    def run_compute(self, params: dict[str, Any]) -> dict[str, Any]:
        """Run the biomedical data pipeline.

        TODO: Implement per paper. Scaffold returns converged=False with a
        clear diagnostic so the gate blocks instead of silently skipping.

        Steps to implement:
          1. Load biosignal dataset (PhysioNet WFDB, CSV, EDF)
          2. Preprocess: bandpass filter, notch filter, baseline correction
          3. Extract features (time-domain, frequency-domain, entropy)
          4. Run ML classification with cross-validation
          5. Compute AUC, sensitivity, specificity, bootstrap CI
          6. Save results to data/processed/
        """
        print(
            "[BiomedicalBackend] run_compute() is not yet implemented. "
            "Implement the biosignal processing pipeline per paper.",
            file=sys.stderr,
        )
        return {
            "converged": False,
            "error": (
                "BiomedicalBackend.run_compute() not yet implemented "
                "— domain status: planned. "
                "See domains/biomedical.py → run_compute() scaffold."
            ),
            "files": [],
            "outputs": {},
        }

    # ── 3. SSOT validation ────────────────────────────────────────────────────

    def validate_ssot(self) -> tuple[bool, list[str]]:
        """Check config/params.yaml for biomedical.* section."""
        import yaml as _yaml

        params_path = Path("config/params.yaml")
        if not params_path.exists():
            return False, ["[BiomedicalBackend] config/params.yaml not found."]

        try:
            with params_path.open("r", encoding="utf-8") as fh:
                ssot = _yaml.safe_load(fh)
        except _yaml.YAMLError as exc:
            return False, [f"[BiomedicalBackend] params.yaml parse error: {exc}"]

        bio_section = ssot.get("biomedical")
        if bio_section is None:
            return False, [
                "[BiomedicalBackend] Missing 'biomedical:' section in "
                "config/params.yaml. Add it when activating this domain "
                "(see config/domains/biomedical.yaml → params_namespace)."
            ]

        errors: list[str] = []
        for _, key in _REQUIRED_SSOT_KEYS:
            if key not in bio_section:
                errors.append(
                    f"[BiomedicalBackend] Missing SSOT key: "
                    f"biomedical.{key} in config/params.yaml"
                )

        return len(errors) == 0, errors

    # ── 4. Emulator ───────────────────────────────────────────────────────────

    def get_emulator(self) -> None:
        """No hardware emulator for the biomedical domain.

        Wearable devices (ECG patches, EEG headsets) connect via their own
        BLE/serial APIs or export CSV/EDF files. No Arduino bridge needed.
        """
        return None
