#!/usr/bin/env python3
"""
tools/validate_submission.py — Pre-Submission Validator for EIU Papers
=======================================================================
Checks that a draft meets all requirements before submission to a journal.

Checks:
  1. YAML frontmatter present and complete
  2. AI_Assist markers in all AI-generated sections
  3. HV (Human Validation) markers with initials
  4. All referenced figures exist in articles/figures/
  5. Bibliography references resolved (no broken [?])
  6. Word count within target range
  7. Required IMRaD sections present
  8. No TODO markers remaining
  9. Journal specs quality gates (from .agent/specs/journal_specs.yaml)

Usage:
  python3 tools/validate_submission.py articles/drafts/paper_Q2_xxx.md
  python3 tools/validate_submission.py articles/drafts/*.md   # batch check
  python3 tools/validate_submission.py articles/drafts/paper.md --diagnose
"""

import re
import sys
from pathlib import Path

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

ROOT = Path(__file__).resolve().parent.parent
FIG_DIR = ROOT / "articles" / "figures"
SPECS_PATH = ROOT / ".agent" / "specs" / "journal_specs.yaml"

IMRAD_SECTIONS = ["Abstract", "Introduction", "Methodology", "Results",
                  "Discussion", "Conclusion"]


def _load_journal_specs() -> dict:
    """Load journal quality gates from specs file."""
    if not HAS_YAML or not SPECS_PATH.exists():
        return {}
    with open(SPECS_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _extract_quartile(text: str) -> str:
    """Extract quartile from frontmatter."""
    m = re.search(r"quartile:\s*[\"']?(\w+)[\"']?", text)
    return m.group(1) if m else ""


def validate_draft(draft_path: Path) -> list[dict]:
    """Validate a single draft. Returns list of issues."""
    issues = []
    text = draft_path.read_text(encoding="utf-8")
    lines = text.split("\n")

    # 1. YAML frontmatter
    if not text.startswith("---"):
        issues.append({"severity": "ERROR", "check": "frontmatter",
                        "msg": "Missing YAML frontmatter (must start with ---)"})
    else:
        fm_end = text.find("---", 3)
        if fm_end == -1:
            issues.append({"severity": "ERROR", "check": "frontmatter",
                            "msg": "Unclosed YAML frontmatter"})
        else:
            fm = text[3:fm_end]
            for field in ["title", "domain", "quartile", "status", "version"]:
                if field + ":" not in fm:
                    issues.append({"severity": "WARN", "check": "frontmatter",
                                    "msg": f"Missing frontmatter field: {field}"})
            if 'status: draft' in fm:
                issues.append({"severity": "INFO", "check": "frontmatter",
                                "msg": "Status is still 'draft' -- update before submission"})

    # 2. AI_Assist markers
    ai_count = text.count("<!-- AI_Assist -->")
    if ai_count == 0:
        issues.append({"severity": "ERROR", "check": "ai_markers",
                        "msg": "No <!-- AI_Assist --> markers found (required for transparency)"})

    # 3. HV markers
    hv_matches = re.findall(r"<!-- HV: (.+?) -->", text)
    unsigned = [m for m in hv_matches if "INICIALES" in m or not m.strip()]
    if not hv_matches:
        issues.append({"severity": "ERROR", "check": "hv_markers",
                        "msg": "No <!-- HV: --> markers found (human validation required)"})
    elif unsigned:
        issues.append({"severity": "WARN", "check": "hv_markers",
                        "msg": f"{len(unsigned)} HV markers still unsigned (contain 'INICIALES')"})

    # 4. Figure references
    fig_refs = re.findall(r"!\[.*?\]\((.+?)\)", text)
    for fig_ref in fig_refs:
        fig_path = ROOT / fig_ref if not Path(fig_ref).is_absolute() else Path(fig_ref)
        if not fig_path.exists():
            issues.append({"severity": "ERROR", "check": "figures",
                            "msg": f"Referenced figure not found: {fig_ref}"})

    # Also check inline Fig. N references
    fig_nums = re.findall(r"Fig\.?\s*(\d+)", text)
    # Just count them for info
    if fig_nums:
        issues.append({"severity": "INFO", "check": "figures",
                        "msg": f"References {len(set(fig_nums))} figures (Fig. {', '.join(sorted(set(fig_nums)))})"})

    # 5. Broken references
    broken_refs = text.count("[?]")
    if broken_refs:
        issues.append({"severity": "ERROR", "check": "bibliography",
                        "msg": f"{broken_refs} broken reference(s) found ([?])"})

    # 6. Word count
    # Strip markdown syntax for word count
    clean = re.sub(r"---.*?---", "", text, count=1, flags=re.DOTALL)
    clean = re.sub(r"[#*|`\[\]()!<>-]", " ", clean)
    clean = re.sub(r"\$.*?\$", "MATH", clean)
    words = len(clean.split())

    # Get target from frontmatter
    target_match = re.search(r"word_count_target:\s*(\d+)", text)
    target = int(target_match.group(1)) if target_match else 6000
    pct = (words / target) * 100 if target else 0

    if pct < 30:
        issues.append({"severity": "WARN", "check": "word_count",
                        "msg": f"Word count: {words}/{target} ({pct:.0f}%) -- very incomplete"})
    elif pct < 80:
        issues.append({"severity": "INFO", "check": "word_count",
                        "msg": f"Word count: {words}/{target} ({pct:.0f}%) -- in progress"})
    else:
        issues.append({"severity": "OK", "check": "word_count",
                        "msg": f"Word count: {words}/{target} ({pct:.0f}%)"})

    # 7. IMRaD sections
    for section in IMRAD_SECTIONS:
        if section.lower() not in text.lower():
            issues.append({"severity": "WARN", "check": "structure",
                            "msg": f"Missing IMRaD section: {section}"})

    # 8. TODO markers
    todos = re.findall(r"\[TODO.*?\]", text, re.IGNORECASE)
    if todos:
        issues.append({"severity": "WARN", "check": "completeness",
                        "msg": f"{len(todos)} TODO markers remaining"})

    # 9. Journal specs quality gates
    quartile = _extract_quartile(text)
    specs = _load_journal_specs()
    spec = specs.get(quartile, specs.get(quartile.lower(), {}))

    if spec:
        # Reference count
        # Count both pandoc [@key] and numbered [N] reference formats
        cite_keys = re.findall(r"\[@([\w_]+)\]", text)
        numbered_refs = re.findall(r"^\[(\d+)\]\s+\S", text, re.MULTILINE)
        ref_count = max(len(set(cite_keys)), len(numbered_refs))
        ref_min = spec.get("references", {}).get("min", 0)
        ref_max = spec.get("references", {}).get("max", 999)
        if ref_count < ref_min:
            issues.append({"severity": "WARN", "check": "journal_spec",
                            "msg": f"References: {ref_count} < min {ref_min} for {quartile}"})
        elif ref_count > ref_max:
            issues.append({"severity": "WARN", "check": "journal_spec",
                            "msg": f"References: {ref_count} > max {ref_max} for {quartile}"})

        # Figure count
        fig_count = len(set(fig_nums)) if fig_nums else 0
        fig_min = spec.get("figures", {}).get("min", 0)
        if fig_count < fig_min:
            issues.append({"severity": "WARN", "check": "journal_spec",
                            "msg": f"Figures: {fig_count} < min {fig_min} for {quartile}"})

        # Word count range from spec
        wc_min = spec.get("word_count", {}).get("min", 0)
        wc_max = spec.get("word_count", {}).get("max", 99999)
        if words < wc_min:
            issues.append({"severity": "WARN", "check": "journal_spec",
                            "msg": f"Word count {words} < min {wc_min} for {quartile}"})
        elif words > wc_max:
            issues.append({"severity": "WARN", "check": "journal_spec",
                            "msg": f"Word count {words} > max {wc_max} for {quartile}"})

        # Required sections from spec
        for section in spec.get("required_sections", []):
            if section.lower() not in text.lower():
                issues.append({"severity": "WARN", "check": "journal_spec",
                                "msg": f"Missing required section for {quartile}: {section}"})

        # Novelty gate
        if spec.get("novelty_gate") and "novelty" not in text.lower():
            issues.append({"severity": "WARN", "check": "journal_spec",
                            "msg": f"{quartile} requires explicit novelty statement"})

    return issues


def print_report(draft_path: Path, issues: list[dict]):
    """Print formatted validation report."""
    print(f"\n{'='*60}")
    print(f"  VALIDATION: {draft_path.name}")
    print(f"{'='*60}")

    severity_icons = {"ERROR": "[X]", "WARN": "[!]", "INFO": "[i]", "OK": "[+]"}
    errors = sum(1 for i in issues if i["severity"] == "ERROR")
    warns = sum(1 for i in issues if i["severity"] == "WARN")

    for issue in issues:
        icon = severity_icons.get(issue["severity"], "[ ]")
        print(f"  {icon} [{issue['check']:14s}] {issue['msg']}")

    print(f"{'='*60}")
    if errors:
        print(f"  RESULT: BLOCKED -- {errors} error(s), {warns} warning(s)")
    elif warns:
        print(f"  RESULT: REVIEW NEEDED -- {warns} warning(s)")
    else:
        print(f"  RESULT: READY FOR SUBMISSION")
    print(f"{'='*60}\n")

    return errors == 0


def diagnose(draft_path: Path, issues: list[dict]):
    """DAG diagnostic: map each failure to a fix action and pipeline step."""
    fix_map = {
        "frontmatter": "Edit draft YAML header → loop back to DESIGN step",
        "ai_markers": "Add <!-- AI_Assist --> to AI-generated paragraphs → IMPLEMENT step",
        "hv_markers": "Request human validation from the researcher → VERIFY step (blocked)",
        "figures": "Run: python3 tools/plot_figures.py --domain X → IMPLEMENT step",
        "bibliography": "Run: python3 tools/generate_bibtex.py → IMPLEMENT step",
        "word_count": "Expand sections with scientific_narrator.py → IMPLEMENT step",
        "structure": "Add missing IMRaD sections → DESIGN step",
        "completeness": "Resolve all TODO markers → IMPLEMENT step",
        "journal_spec": "Review .agent/specs/journal_specs.yaml gates → SPEC step",
    }

    errors_and_warns = [i for i in issues if i["severity"] in ("ERROR", "WARN")]
    if not errors_and_warns:
        print("\n  [DAG] All checks passed. Ready for next step: compile PDF")
        return

    print(f"\n{'='*60}")
    print(f"  DAG DIAGNOSTIC: {draft_path.name}")
    print(f"{'='*60}")
    print(f"  Failures: {len(errors_and_warns)} — Loop back required\n")

    for issue in errors_and_warns:
        fix = fix_map.get(issue["check"], "Manual investigation needed")
        print(f"  [{issue['severity']:5s}] {issue['msg']}")
        print(f"         FIX → {fix}\n")

    # Determine furthest loop-back step
    steps = {"SPEC": 0, "DESIGN": 1, "IMPLEMENT": 2, "VERIFY": 3}
    furthest = "VERIFY"
    for issue in errors_and_warns:
        fix = fix_map.get(issue["check"], "")
        for step in ("SPEC", "DESIGN", "IMPLEMENT"):
            if step in fix and steps.get(step, 99) < steps.get(furthest, 99):
                furthest = step

    print(f"  LOOP BACK TO: {furthest} step")
    print(f"{'='*60}\n")


def main():
    diagnose_mode = "--diagnose" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    if not args:
        print("Usage: python3 tools/validate_submission.py <draft.md> [--diagnose]")
        sys.exit(1)

    all_pass = True
    for arg in args:
        path = Path(arg)
        if not path.exists():
            print(f"[ERROR] File not found: {path}")
            all_pass = False
            continue
        issues = validate_draft(path)
        passed = print_report(path, issues)
        if diagnose_mode:
            diagnose(path, issues)
        if not passed:
            all_pass = False

    sys.exit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
