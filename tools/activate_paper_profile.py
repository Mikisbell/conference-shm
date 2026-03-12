#!/usr/bin/env python3
"""
activate_paper_profile.py — Activa un perfil de investigación en research_lines.yaml

Usage:
  python3 tools/activate_paper_profile.py --line structural_shm --quartile conference
  python3 tools/activate_paper_profile.py --list
"""
import argparse
import sys
from pathlib import Path
try:
    import yaml
except ImportError:
    print("[ERROR] PyYAML required: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parents[1]
RESEARCH_LINES = ROOT / "config" / "research_lines.yaml"


def list_lines(data):
    print("Available research lines:")
    for key, val in data.get("research_lines", {}).items():
        active = " ← ACTIVE" if data.get("active_profile", {}).get("research_line") == key else ""
        print(f"  {key}: {val.get('title', '?')}{active}")


def activate(data, line_key, quartile, paper_id=None):
    lines = data.get("research_lines", {})
    if line_key not in lines:
        print(f"[ERROR] Research line '{line_key}' not found.", file=sys.stderr)
        print(f"  Available: {', '.join(lines.keys())}", file=sys.stderr)
        sys.exit(1)
    line = lines[line_key]
    specs = line.get("quartile_specs", {}).get(quartile)
    if not specs:
        print(f"[WARN] No specs for {line_key}/{quartile} — using defaults", file=sys.stderr)
        specs = {}
    data["active_profile"] = {
        "research_line": line_key,
        "quartile": quartile,
        "paper_id": paper_id or f"{line_key}_{quartile}",
        "word_count_min": specs.get("word_count_min", 2500),
        "word_count_max": specs.get("word_count_max", 5000),
        "required_sections": specs.get("required_sections", []),
        "journal_target": specs.get("journal", "TBD"),
    }
    return data


def main():
    parser = argparse.ArgumentParser(description="Activate a paper profile in research_lines.yaml")
    parser.add_argument("--line", help="Research line key")
    parser.add_argument("--quartile", default="conference",
                        choices=["conference", "q4", "q3", "q2", "q1"])
    parser.add_argument("--paper-id", help="Paper identifier (optional)")
    parser.add_argument("--list", action="store_true", help="List available research lines")
    args = parser.parse_args()

    if not RESEARCH_LINES.exists():
        print(f"[ERROR] {RESEARCH_LINES} not found", file=sys.stderr)
        sys.exit(1)

    try:
        with open(RESEARCH_LINES) as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        print(f"[ERROR] Cannot parse {RESEARCH_LINES}: {e}", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"[ERROR] Cannot read {RESEARCH_LINES}: {e}", file=sys.stderr)
        sys.exit(1)

    if args.list:
        list_lines(data)
        return

    if not args.line:
        print("[ERROR] --line required. Use --list to see options.", file=sys.stderr)
        sys.exit(1)

    data = activate(data, args.line, args.quartile, args.paper_id)

    try:
        with open(RESEARCH_LINES, "w") as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False)
    except OSError as e:
        print(f"[ERROR] Cannot write {RESEARCH_LINES}: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"[OK] Active profile set: {args.line} / {args.quartile}")
    print(f"     paper_id: {data['active_profile']['paper_id']}")
    print(f"     words:    {data['active_profile']['word_count_min']}–{data['active_profile']['word_count_max']}")
    print(f"     journal:  {data['active_profile']['journal_target']}")


if __name__ == "__main__":
    main()
