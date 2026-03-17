#!/usr/bin/env python3
"""
tools/run_torture_chamber.py — COMPUTE C2 runner (structural domain)
=====================================================================
CLI wrapper for the structural simulation campaign.

Runs in order:
  1. CrossValidationEngine (A/B scenarios) → data/processed/cv_results.json
  2. Spectral analysis Sa(T) via research_director.run_research()
  3. compute_statistics.py (Q1/Q2 only — read from active research profile)

This is the c2_runner for config/domains/structural.yaml:
  c2_runner: "python3 tools/run_torture_chamber.py"

Quartile and topic are read automatically from config/research_lines.yaml
(active_profile). Pass --quartile / --topic to override.

Usage:
  python3 tools/run_torture_chamber.py
  python3 tools/run_torture_chamber.py --quartile Q2 --topic "SHM RC columns" --cycles 500
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _ssot_defaults() -> tuple[str, str]:
    """Read active quartile + topic from config/research_lines.yaml (SSOT).

    Falls back to config/params.yaml project name + 'Conference' if the
    research profile is not yet activated.
    """
    try:
        import yaml  # noqa: PLC0415
        rl_path = ROOT / "config" / "research_lines.yaml"
        if rl_path.exists():
            with open(rl_path, encoding="utf-8") as fh:
                rl = yaml.safe_load(fh) or {}
            active = rl.get("active_profile", {})
            quartile = str(active.get("quartile", "")).strip() or "Conference"
            topic = str(
                active.get("topic", active.get("title", "")) or ""
            ).strip()
            if topic:
                return quartile, topic
    except Exception:  # noqa: BLE001
        pass

    # Fallback: params.yaml project name
    try:
        import yaml  # noqa: PLC0415
        p = ROOT / "config" / "params.yaml"
        if p.exists():
            with open(p, encoding="utf-8") as fh:
                cfg = yaml.safe_load(fh) or {}
            topic = (
                cfg.get("metadata", {}).get("project", "")
                or cfg.get("project", {}).get("name", "")
                or "structural health monitoring"
            )
            return "Conference", str(topic)
    except Exception:  # noqa: BLE001
        pass

    return "Conference", "structural health monitoring"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="COMPUTE C2 — Structural simulation (CrossValidation + Spectral + Stats)"
    )
    parser.add_argument(
        "--quartile",
        type=str,
        default=None,
        help="Paper quartile: Conference | Q4 | Q3 | Q2 | Q1. "
             "Default: read from config/research_lines.yaml active_profile.",
    )
    parser.add_argument(
        "--topic",
        type=str,
        default=None,
        help="Research topic string. "
             "Default: read from config/research_lines.yaml active_profile.",
    )
    parser.add_argument(
        "--cycles",
        type=int,
        default=500,
        help="Simulation cycles for CrossValidationEngine (default: 500).",
    )
    args = parser.parse_args()

    ssot_quartile, ssot_topic = _ssot_defaults()
    quartile = args.quartile or ssot_quartile
    topic = args.topic or ssot_topic

    print(
        f"[C2-RUNNER] Structural COMPUTE — "
        f"quartile={quartile}  topic='{topic}'  cycles={args.cycles}"
    )

    # Delegate to research_director.run_research() — handles full campaign:
    # CrossValidationEngine → cv_results.json
    # spectral_engine → Sa(T) spectrum
    # compute_statistics.py (auto-enabled for Q1/Q2)
    try:
        from tools.research_director import run_research  # type: ignore[import]
    except ImportError:
        # Direct import fallback (when called from repo root)
        import importlib  # noqa: PLC0415
        rd = importlib.import_module("research_director")
        run_research = rd.run_research  # type: ignore[attr-defined]

    run_research(quartile, topic, args.cycles)


if __name__ == "__main__":
    main()
