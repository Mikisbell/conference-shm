#!/usr/bin/env python3
"""AutoResearch Room 6 — Tool Chain Connectivity Evaluator.

Tests that belico-stack tools can import, read SSOT, and chain together.
No heavy dependencies required. Runs statically.

Usage:
    python3 tests/test_tool_chain.py           # human-readable report
    python3 tests/test_tool_chain.py --score   # JSON output
"""

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# ── Weights ──────────────────────────────────────────────────────────
WEIGHTS = {
    "import_chain": 0.25,
    "ssot_existence": 0.15,
    "ssot_keys": 0.25,
    "tool_cli": 0.15,
    "generate_params": 0.10,
    "data_dirs": 0.10,
}

# ── A. Import Chain ──────────────────────────────────────────────────

TOOLS_IMPORT = [
    ("tools.validate_submission", False),
    ("tools.generate_params", False),
    ("tools.generate_bibtex", False),
    ("tools.bibliography_engine", False),
    ("tools.check_novelty", False),
    ("tools.arduino_emu", False),
    ("tools.lora_emu", False),
    ("articles.scientific_narrator", False),
    ("src.physics.spectral_engine", False),
    ("src.physics.cross_validation", False),
    ("src.physics.kalman", False),
    ("src.physics.peer_adapter", True),       # scipy may be missing
    ("src.physics.torture_chamber", True),    # openseespy may be missing
]


def _run_import_chain():
    """Import each tool module. Warnings (expected failures) count as 0.5."""
    imported = 0
    warnings = 0
    failed = 0
    details = []

    for mod_name, warn_ok in TOOLS_IMPORT:
        try:
            importlib.import_module(mod_name)
            imported += 1
            details.append((mod_name, "ok"))
        except Exception as exc:
            if warn_ok:
                warnings += 1
                details.append((mod_name, f"warning: {type(exc).__name__}"))
            else:
                failed += 1
                details.append((mod_name, f"FAIL: {exc}"))

    total = len(TOOLS_IMPORT)
    score = (imported + warnings * 0.5) / total if total else 0.0
    return {
        "score": round(score, 4),
        "imported": imported,
        "warnings": warnings,
        "failed": failed,
        "_details": details,
    }


def test_import_chain():
    """All required tool modules must be importable (score >= 0.5)."""
    result = _run_import_chain()
    assert result["score"] >= 0.5, (
        f"Import chain score {result['score']} < 0.5. "
        f"Failed: {[d for d in result['_details'] if 'FAIL' in d[1]]}"
    )


# ── B. SSOT Existence ───────────────────────────────────────────────

SSOT_FILES = [
    ROOT / "config" / "params.yaml",
    ROOT / ".agent" / "specs" / "journal_specs.yaml",
    ROOT / "config" / "research_lines.yaml",
]


def _run_ssot_existence():
    found = sum(1 for p in SSOT_FILES if p.exists())
    return {
        "score": round(found / len(SSOT_FILES), 4) if SSOT_FILES else 0.0,
        "found": found,
        "total": len(SSOT_FILES),
    }


def test_ssot_existence():
    """All SSOT config files must be present (score == 1.0)."""
    result = _run_ssot_existence()
    assert result["score"] >= 1.0, (
        f"SSOT files missing: {result['found']}/{result['total']} found"
    )


# ── C. SSOT Key Validation ──────────────────────────────────────────

# Each entry: (dot-path into the YAML dict, list of accepted leaf names)
# We walk the nested dict; the key is valid if the leaf exists (plain or .value).
SSOT_KEYS = [
    ("project.domain",),
    ("structure.mass_m", "structure.mass_m.value"),
    ("structure.stiffness_k", "structure.stiffness_k.value"),
    ("damping.ratio_xi", "damping.ratio_xi.value"),
    ("material.yield_strength_fy", "material.yield_strength_fy.value"),
    ("material.elastic_modulus_E", "material.elastic_modulus_E.value"),
    ("acquisition.sample_rate_hz", "acquisition.sample_rate_hz.value"),
]


def _deep_get(d, dotpath):
    """Walk a nested dict by dotpath. Returns (True, value) or (False, None)."""
    keys = dotpath.split(".")
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return False, None
        cur = cur[k]
    return True, cur


def _run_ssot_keys():
    params_path = ROOT / "config" / "params.yaml"
    if not params_path.exists():
        return {"score": 0.0, "found": 0, "total": len(SSOT_KEYS)}

    try:
        import yaml  # noqa: F811
    except ImportError:
        # Fallback: try ruamel or skip
        return {"score": 0.0, "found": 0, "total": len(SSOT_KEYS), "error": "pyyaml not installed"}

    with open(params_path) as f:
        data = yaml.safe_load(f)

    found = 0
    for candidates in SSOT_KEYS:
        for cand in candidates:
            ok, val = _deep_get(data, cand)
            if ok and val is not None:
                found += 1
                break

    return {
        "score": round(found / len(SSOT_KEYS), 4),
        "found": found,
        "total": len(SSOT_KEYS),
    }


def test_ssot_keys():
    """All required SSOT keys must be present in params.yaml (score >= 0.8)."""
    result = _run_ssot_keys()
    assert result["score"] >= 0.8, (
        f"SSOT key score {result['score']} < 0.8: "
        f"{result['found']}/{result['total']} keys found"
    )


# ── D. Tool CLI Help ────────────────────────────────────────────────

CLI_TOOLS = [
    "tools/validate_submission.py",
    "tools/generate_params.py",
    "tools/check_novelty.py",
    "tools/arduino_emu.py",
    "tools/lora_emu.py",
]


def _run_tool_cli():
    passed = 0
    total = len(CLI_TOOLS)
    details = []

    for tool in CLI_TOOLS:
        tool_path = ROOT / tool
        if not tool_path.exists():
            details.append((tool, "MISSING"))
            continue
        try:
            r = subprocess.run(
                [sys.executable, str(tool_path), "--help"],
                capture_output=True,
                timeout=10,
                cwd=str(ROOT),
            )
            if r.returncode == 0:
                passed += 1
                details.append((tool, "ok"))
            else:
                details.append((tool, f"exit {r.returncode}"))
        except subprocess.TimeoutExpired:
            details.append((tool, "TIMEOUT"))
        except Exception as exc:
            details.append((tool, f"ERROR: {exc}"))

    return {
        "score": round(passed / total, 4) if total else 0.0,
        "passed": passed,
        "total": total,
        "_details": details,
    }


def test_tool_cli():
    """CLI tools are reachable; at least half must respond successfully."""
    result = _run_tool_cli()
    assert isinstance(result, dict), "Expected dict result from _run_tool_cli"
    assert "score" in result, "Result missing 'score' key"
    assert result["score"] >= 0.5, (
        f"Tool CLI score {result['score']} < 0.5: "
        f"{result['passed']}/{result['total']} passed. "
        f"Details: {[d for d in result['_details'] if d[1] != 'ok']}"
    )


# ── E. Generate Params Chain ────────────────────────────────────────

def _run_generate_params():
    params_py = ROOT / "src" / "physics" / "models" / "params.py"
    if not params_py.exists():
        return {"score": 0.0, "error": "params.py not found"}

    try:
        # Attempt import of the generated module
        spec = importlib.util.spec_from_file_location("params_generated", str(params_py))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        # Check it exposes something meaningful
        if hasattr(mod, "P") or hasattr(mod, "PARAMS") or hasattr(mod, "SAMPLE_RATE_HZ"):
            return {"score": 1.0}
        return {"score": 0.5, "note": "imported but no expected symbols found"}
    except Exception as exc:
        return {"score": 0.0, "error": str(exc)}


def test_generate_params():
    """Generated params.py must import successfully and expose expected symbols."""
    result = _run_generate_params()
    assert result["score"] >= 0.5, (
        f"generate_params score {result['score']} < 0.5: "
        + result.get("error", result.get("note", "unknown"))
    )


# ── F. Data Directories ─────────────────────────────────────────────

DATA_DIRS = [
    ROOT / "data" / "raw",
    ROOT / "data" / "processed",
    ROOT / "articles" / "drafts",
    ROOT / "articles" / "figures",
    ROOT / "config",
]


def _run_data_dirs():
    found = sum(1 for d in DATA_DIRS if d.is_dir())
    return {
        "score": round(found / len(DATA_DIRS), 4) if DATA_DIRS else 0.0,
        "found": found,
        "total": len(DATA_DIRS),
    }


def test_data_dirs():
    """All required data directories must exist (score == 1.0)."""
    result = _run_data_dirs()
    assert result["score"] >= 1.0, (
        f"Data dirs score {result['score']} < 1.0: "
        f"{result['found']}/{result['total']} found"
    )


# ── Runner ───────────────────────────────────────────────────────────

def run_all():
    results = {
        "import_chain": _run_import_chain(),
        "ssot_existence": _run_ssot_existence(),
        "ssot_keys": _run_ssot_keys(),
        "tool_cli": _run_tool_cli(),
        "generate_params": _run_generate_params(),
        "data_dirs": _run_data_dirs(),
    }

    chain_score = sum(
        WEIGHTS[k] * results[k]["score"] for k in WEIGHTS
    )

    # Strip internal details from JSON output
    clean = {}
    for k, v in results.items():
        clean[k] = {kk: vv for kk, vv in v.items() if not kk.startswith("_")}

    return round(chain_score, 4), clean, results


def main():
    score_mode = "--score" in sys.argv
    chain_score, clean_details, raw = run_all()

    if score_mode:
        out = {"chain_score": chain_score, "details": clean_details}
        print(json.dumps(out, indent=2))
        sys.exit(0 if chain_score >= 0.70 else 1)

    # Human-readable report
    print("=" * 60)
    print("  BELICO STACK — Tool Chain Connectivity Report")
    print("=" * 60)

    for cat, data in raw.items():
        s = data["score"]
        marker = "PASS" if s >= 0.8 else ("WARN" if s >= 0.5 else "FAIL")
        print(f"\n[{marker}] {cat}: {s:.2%}")
        if "_details" in data:
            for name, status in data["_details"]:
                icon = "+" if status == "ok" else ("-" if "warning" in status else "x")
                print(f"  {icon} {name}: {status}")
        for k, v in data.items():
            if k not in ("score", "_details"):
                print(f"      {k}: {v}")

    print(f"\n{'=' * 60}")
    print(f"  CHAIN SCORE: {chain_score:.2%}")
    verdict = "CONNECTED" if chain_score >= 0.80 else (
        "DEGRADED" if chain_score >= 0.50 else "BROKEN"
    )
    print(f"  VERDICT: {verdict}")
    print("=" * 60)
    sys.exit(0 if chain_score >= 0.70 else 1)


if __name__ == "__main__":
    main()
