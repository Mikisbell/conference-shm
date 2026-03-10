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


def load_db_manifest():
    try:
        import yaml
        with open(DB_MANIFEST) as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"[WARN] Could not read db/manifest.yaml: {e}", file=sys.stderr)
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
    """Count CSV/NPY files that look like simulation outputs (not metadata)."""
    skip = {"COMPUTE_MANIFEST.json", "simulation_summary.json", "cv_results.json",
            "guardian_test_results.json", "ml_training_set.csv"}
    count = 0
    for f in processed_dir.glob("*.csv"):
        if f.name not in skip:
            count += 1
    for f in processed_dir.glob("*.npy"):
        count += 1
    return count


def detect_emulation(processed_dir):
    """Emulation ran if latest_abort.csv or guardian_test_results.json exist."""
    return (
        (processed_dir / "latest_abort.csv").exists()
        or (processed_dir / "guardian_test_results.json").exists()
    )


def detect_guardian(processed_dir):
    """Guardian validated if guardian_test_results.json exists and has pass=true."""
    gtr = processed_dir / "guardian_test_results.json"
    if not gtr.exists():
        return False
    try:
        with open(gtr) as f:
            data = json.load(f)
        return data.get("all_gates_pass", False)
    except Exception:
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

    PROCESSED.mkdir(parents=True, exist_ok=True)

    records = detect_records(db)
    sim_count = count_simulations(PROCESSED)
    emulation_ran = args.emulation or detect_emulation(PROCESSED)
    guardian_ok = args.guardian or detect_guardian(PROCESSED)

    design_sources = [s for s in args.design_sources.split(",") if s.strip()]
    missing = check_design_sources(design_sources, PROCESSED)
    all_exist = len(missing) == 0

    files_generated = [f.name for f in sorted(PROCESSED.iterdir())
                       if f.is_file() and f.suffix in {".csv", ".npy", ".json", ".svg", ".png"}
                       and f.name != "COMPUTE_MANIFEST.json"]

    manifest = {
        "compute_date": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "paper_id": paper_id,
        "records_used": records,
        "simulations_run": sim_count,
        "files_generated": files_generated,
        "emulation_ran": emulation_ran,
        "guardian_validated": guardian_ok,
        "all_design_sources_exist": all_exist,
        "is_template_demo": False,
    }

    if missing:
        manifest["missing_design_sources"] = missing

    output = json.dumps(manifest, indent=2)

    if args.dry_run:
        print(output)
        return

    with open(MANIFEST_PATH, "w") as f:
        f.write(output + "\n")

    print(f"[OK] COMPUTE_MANIFEST.json written to {MANIFEST_PATH}")
    print(f"     paper_id:           {paper_id}")
    print(f"     records_used:       {records}")
    print(f"     simulations_run:    {sim_count}")
    print(f"     emulation_ran:      {emulation_ran}")
    print(f"     guardian_validated: {guardian_ok}")
    print(f"     all_sources_exist:  {all_exist}")

    if missing:
        print(f"\n[WARN] Missing design sources:", file=sys.stderr)
        for m in missing:
            print(f"       - {m}", file=sys.stderr)
        print("[WARN] all_design_sources_exist=false — IMPLEMENT remains BLOCKED", file=sys.stderr)
        sys.exit(1)

    if sim_count == 0:
        print("[ERROR] 0 simulations detected in data/processed/. Re-run COMPUTE C2.", file=sys.stderr)
        sys.exit(1)

    print("[COMPUTE C5] Gate PASSED — IMPLEMENT is unblocked.")


if __name__ == "__main__":
    main()
