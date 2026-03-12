#!/usr/bin/env python3
"""
generate_compute_manifest.py — COMPUTE C5 gate auto-generator
Scans data/processed/ and db/manifest.yaml to produce COMPUTE_MANIFEST.json.

Usage:
  python3 tools/generate_compute_manifest.py [--paper-id ID] [--design-sources f1,f2]

Arguments:
  --paper-id        Paper identifier (read from db/manifest.yaml if omitted)
  --design-sources  Comma-separated list of files the design requires in data/processed/
                    (e.g. "disp_pisco_intact.csv,cv_results.json")
  --emulation       Mark emulation as ran (default: auto-detect from data/processed/)
  --guardian        Mark guardian as validated (default: auto-detect)
  --dry-run         Print the manifest without writing it

Output:
  data/processed/COMPUTE_MANIFEST.json
"""

import argparse
import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
MANIFEST_PATH = PROCESSED / "COMPUTE_MANIFEST.json"
DB_MANIFEST = ROOT / "db" / "manifest.yaml"
PARAMS_YAML = ROOT / "config" / "params.yaml"


def _load_ssot_cm_cfg():
    """Load simulation.compute_manifest section from config/params.yaml.

    Returns a dict with skip_files, emulation_signals, and guardian_results_file.
    Falls back to hardcoded defaults if the section is absent so the script keeps
    working even when params.yaml predates this feature.
    """
    _defaults = {
        "skip_files": [
            "COMPUTE_MANIFEST.json",
            "simulation_summary.json",
            "cv_results.json",
            "guardian_test_results.json",
            "ml_training_set.csv",
        ],
        "emulation_signals": [
            "latest_abort.csv",
            "guardian_test_results.json",
        ],
        "guardian_results_file": "guardian_test_results.json",
    }
    try:
        import yaml
        with open(PARAMS_YAML) as f:
            cfg = yaml.safe_load(f)
        cm = cfg.get("simulation", {}).get("compute_manifest", {})
        if not cm:
            return _defaults
        return {
            "skip_files": cm.get("skip_files", _defaults["skip_files"]),
            "emulation_signals": cm.get("emulation_signals", _defaults["emulation_signals"]),
            "guardian_results_file": cm.get("guardian_results_file", _defaults["guardian_results_file"]),
        }
    except FileNotFoundError:
        print("[WARN] config/params.yaml not found — using built-in defaults for compute_manifest", file=sys.stderr)
        return _defaults
    except yaml.YAMLError as e:
        print(f"[WARN] config/params.yaml malformed ({e}) — using built-in defaults", file=sys.stderr)
        return _defaults
    except OSError as e:
        print(f"[WARN] config/params.yaml read error ({e}) — using built-in defaults", file=sys.stderr)
        return _defaults


# Load SSOT config once at module level so all functions share the same values.
_CM_CFG = _load_ssot_cm_cfg()
SKIP_FILES = set(_CM_CFG["skip_files"])
EMULATION_SIGNALS = set(_CM_CFG["emulation_signals"])
GUARDIAN_RESULTS_FILE = _CM_CFG["guardian_results_file"]


def load_db_manifest():
    try:
        import yaml
        with open(DB_MANIFEST) as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print("[MANIFEST] db/manifest.yaml not found — running without RSN traceability", file=sys.stderr)
        return {}
    except yaml.YAMLError as e:
        print(f"[MANIFEST] db/manifest.yaml parse error: {e}", file=sys.stderr)
        return {}
    except PermissionError as e:
        print(f"[MANIFEST] db/manifest.yaml permission denied: {e}", file=sys.stderr)
        return {}
    except OSError as e:
        print(f"[MANIFEST] db/manifest.yaml read error: {e}", file=sys.stderr)
        return {}


def detect_records(db):
    """Extract record filenames from db/manifest.yaml."""
    records = []
    excitation = db.get("excitation", {})
    for r in excitation.get("records_present", []):
        if r.get("valid"):
            records.append(r.get("filename", ""))
    return [r for r in records if r]


def count_simulations(processed_dir):
    """Count CSV/NPY files that look like simulation outputs (not metadata).

    Files listed in simulation.compute_manifest.skip_files (params.yaml) are excluded.
    """
    count = 0
    for f in processed_dir.glob("*.csv"):
        if f.name not in SKIP_FILES:
            count += 1
    for f in processed_dir.glob("*.npy"):
        count += 1
    return count


def detect_emulation(processed_dir):
    """Emulation ran if any file from simulation.compute_manifest.emulation_signals exists."""
    return any((processed_dir / name).exists() for name in EMULATION_SIGNALS)


def detect_guardian(processed_dir):
    """Guardian validated if guardian_results_file exists and has all_gates_pass=true.

    The filename is read from simulation.compute_manifest.guardian_results_file (params.yaml).
    """
    gtr = processed_dir / GUARDIAN_RESULTS_FILE
    if not gtr.exists():
        return False
    try:
        with open(gtr) as f:
            data = json.load(f)
        return data.get("all_gates_pass", False)
    except (json.JSONDecodeError, KeyError, OSError) as e:
        print(f"[WARN] detect_guardian: {e}", file=sys.stderr)
        return False


def check_design_sources(design_sources, processed_dir):
    """Verify that each planned data file exists in data/processed/."""
    missing = []
    for name in design_sources:
        name = name.strip()
        if name and not (processed_dir / name).exists():
            missing.append(name)
    return missing


def main():
    parser = argparse.ArgumentParser(description="Generate COMPUTE_MANIFEST.json for COMPUTE C5")
    parser.add_argument("--paper-id", help="Paper identifier (overrides db/manifest.yaml)")
    parser.add_argument("--design-sources", default="",
                        help="Comma-separated list of required files in data/processed/")
    parser.add_argument("--emulation", action="store_true",
                        help="Force emulation_ran=true")
    parser.add_argument("--guardian", action="store_true",
                        help="Force guardian_validated=true")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print manifest without writing to disk")
    args = parser.parse_args()

    db = load_db_manifest()

    paper_id = args.paper_id or db.get("paper_id", "")
    if not paper_id:
        print("[ERROR] paper_id not set. Pass --paper-id or fix db/manifest.yaml", file=sys.stderr)
        sys.exit(1)

    try:
        PROCESSED.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"[ERROR] Cannot create data/processed/: {e}", file=sys.stderr)
        sys.exit(1)

    records = detect_records(db)
    sim_count = count_simulations(PROCESSED)
    emulation_ran = args.emulation or detect_emulation(PROCESSED)
    guardian_ok = args.guardian or detect_guardian(PROCESSED)

    design_sources = [s for s in args.design_sources.split(",") if s.strip()]
    missing = check_design_sources(design_sources, PROCESSED)
    all_exist = not missing

    files_generated = [f.name for f in sorted(PROCESSED.iterdir())
                       if f.is_file() and f.suffix in {".csv", ".npy", ".json", ".svg", ".png"}
                       and f.name != "COMPUTE_MANIFEST.json"]

    # gate_passed starts False; only set True after all validations pass (M3).
    # validate_submission.py can check this field explicitly to detect stale manifests
    # written mid-run (e.g. process killed between write and final gate evaluation).
    manifest = {
        "compute_date": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "paper_id": paper_id,
        "records_used": records,
        "simulations_run": sim_count,
        "files_generated": files_generated,
        "emulation_ran": emulation_ran,
        "guardian_validated": guardian_ok,
        "all_design_sources_exist": all_exist,
        # always False in production — set True manually for demo/test manifests
        "is_template_demo": False,
        # gate_passed is False until all C5 checks below pass (set to True at end)
        "gate_passed": False,
    }

    if missing:
        manifest["missing_design_sources"] = missing

    output = json.dumps(manifest, indent=2)

    if args.dry_run:
        print(output)
        return

    # Write manifest early so validate_submission.py can read it even if we exit(1).
    # gate_passed=False signals that C5 did not complete successfully.
    try:
        with open(MANIFEST_PATH, "w") as f:
            f.write(output + "\n")
    except OSError as e:
        print(f"[ERROR] Cannot write COMPUTE_MANIFEST.json: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"[OK] COMPUTE_MANIFEST.json written to {MANIFEST_PATH}")
    print(f"     paper_id:           {paper_id}")
    print(f"     records_used:       {records}")
    print(f"     simulations_run:    {sim_count}")
    print(f"     emulation_ran:      {emulation_ran}")
    print(f"     guardian_validated: {guardian_ok}")
    print(f"     all_sources_exist:  {all_exist}")

    # Collect ALL blocking errors before exiting so the user sees everything at once (L3).
    blocking_errors = []

    if missing:
        print(f"\n[WARN] Missing design sources:", file=sys.stderr)
        for m in missing:
            print(f"       - {m}", file=sys.stderr)
        print("[WARN] all_design_sources_exist=false — IMPLEMENT remains BLOCKED", file=sys.stderr)
        blocking_errors.append("missing_design_sources")

    if sim_count == 0:
        print("[ERROR] 0 simulations detected in data/processed/. Re-run COMPUTE C2.", file=sys.stderr)
        blocking_errors.append("no_simulations")

    if blocking_errors:
        sys.exit(1)

    # All checks passed — update gate_passed to True and rewrite manifest.
    manifest["gate_passed"] = True
    try:
        with open(MANIFEST_PATH, "w") as f:
            f.write(json.dumps(manifest, indent=2) + "\n")
    except OSError as e:
        print(f"[ERROR] Cannot finalize COMPUTE_MANIFEST.json: {e}", file=sys.stderr)
        sys.exit(1)

    print("[COMPUTE C5] Gate PASSED — IMPLEMENT is unblocked.")


if __name__ == "__main__":
    main()
