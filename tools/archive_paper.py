#!/usr/bin/env python3
"""
tools/archive_paper.py — ARCHIVE phase closer for the paper pipeline
=====================================================================
Updates draft frontmatter status, saves the paper event to Engram, and
prints the next-step menu for the user.

Part of the SDD pipeline: FINALIZE → ARCHIVE → (user chooses next step)

Usage:
  python3 tools/archive_paper.py articles/drafts/paper_Q1_Espectro.md
  python3 tools/archive_paper.py articles/drafts/paper_Q1_Espectro.md --status submitted
  python3 tools/archive_paper.py --list    # show all drafts with their status
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Status flow documented in CLAUDE.md
VALID_STATUSES = ["draft", "review", "submitted", "accepted", "archived"]

_ESCALERA: dict[str, str] = {
    "Conference": "Q4",
    "Q4": "Q3",
    "Q3": "Q2",
    "Q2": "Q1",
    "Q1": "(peak — consider next project or submission)",
}


# ── Frontmatter helpers ───────────────────────────────────────────────────────

def _read_frontmatter(content: str) -> tuple[dict[str, str], str]:
    """Parse YAML frontmatter from markdown. Returns (fields_dict, body)."""
    fields: dict[str, str] = {}
    body = content
    if not content.startswith("---"):
        return fields, body
    end = content.find("\n---", 3)
    if end == -1:
        return fields, body
    fm_block = content[3:end].strip()
    body = content[end + 4:].lstrip("\n")
    for line in fm_block.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fields[k.strip()] = v.strip().strip('"').strip("'")
    return fields, body


def _write_frontmatter(fields: dict[str, str], body: str) -> str:
    """Reconstruct markdown with updated frontmatter."""
    lines: list[str] = []
    for k, v in fields.items():
        needs_quotes = " " in v or ":" in v or not v
        lines.append(f'{k}: "{v}"' if needs_quotes else f"{k}: {v}")
    fm = "\n".join(lines)
    return f"---\n{fm}\n---\n\n{body}"


# ── Engram save (via CLI — MCP also saves during session) ────────────────────

def _save_to_engram(paper_id: str, title: str, journal: str, quartile: str, status: str) -> None:
    msg = (
        f"paper: archived {paper_id} — "
        f"title='{title}' journal={journal} quartile={quartile} status={status} "
        f"— ready for submission"
    )
    try:
        subprocess.run(
            ["engram", "save", msg],
            check=True,
            capture_output=True,
            timeout=10,
        )
        print(f"[OK] Engram save: {msg[:90]}...")
    except FileNotFoundError:
        print("[WARN] engram CLI not found — Engram MCP will handle this during the session")
    except subprocess.CalledProcessError as exc:
        print(f"[WARN] Engram save returned non-zero ({exc.returncode}) — check engram status")
    except subprocess.TimeoutExpired:
        print("[WARN] Engram save timed out — will retry on next session")


# ── List mode ────────────────────────────────────────────────────────────────

def _list_drafts(drafts_dir: Path) -> None:
    drafts = sorted(drafts_dir.glob("*.md"))
    if not drafts:
        print("[INFO] No drafts found in articles/drafts/")
        return
    print(f"\n  {'File':<48} {'Status':<12} {'Quartile':<10} Domain")
    print("  " + "-" * 84)
    for draft in drafts:
        try:
            content = draft.read_text(encoding="utf-8")
            fields, _ = _read_frontmatter(content)
            status = fields.get("status", "unknown")
            quartile = fields.get("quartile", "?")
            domain = fields.get("domain", "?")
        except OSError:
            status = quartile = domain = "?"
        print(f"  {draft.name:<48} {status:<12} {quartile:<10} {domain}")
    print()


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="ARCHIVE — Close the paper pipeline cycle and update draft status"
    )
    parser.add_argument("draft", nargs="?", help="Path to the draft .md file")
    parser.add_argument(
        "--status",
        default="archived",
        choices=VALID_STATUSES,
        help="Target status to write into frontmatter (default: archived)",
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List all drafts with their current status and exit",
    )
    args = parser.parse_args()

    drafts_dir = ROOT / "articles" / "drafts"

    if args.list:
        _list_drafts(drafts_dir)
        return

    if not args.draft:
        print("[ERROR] Specify a draft file or use --list to see available drafts")
        parser.print_usage()
        sys.exit(1)

    draft_path = Path(args.draft)
    if not draft_path.is_absolute():
        draft_path = ROOT / draft_path

    if not draft_path.exists():
        print(f"[ERROR] Draft not found: {draft_path}")
        print(f"  Tip: python3 tools/archive_paper.py --list")
        sys.exit(1)

    try:
        content = draft_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"[ERROR] Cannot read draft: {exc}")
        sys.exit(1)

    fields, body = _read_frontmatter(content)

    if not fields:
        print(f"[ERROR] No YAML frontmatter found in {draft_path.name}")
        print("  Expected format at top of file:")
        print("  ---")
        print("  title: My Paper Title")
        print("  domain: structural")
        print("  quartile: Conference")
        print("  status: review")
        print("  ---")
        sys.exit(1)

    title = fields.get("title", draft_path.stem)
    domain = fields.get("domain", "unknown")
    quartile = fields.get("quartile", "Conference")
    journal = fields.get("journal", "TBD")
    current_status = fields.get("status", "draft")
    paper_id = fields.get("paper_id", draft_path.stem)

    print(f"\n{'=' * 58}")
    print(f"  ARCHIVE — {draft_path.name}")
    print(f"{'=' * 58}")
    print(f"  Title    : {title}")
    print(f"  Domain   : {domain}  |  Quartile: {quartile}")
    print(f"  Journal  : {journal}")
    print(f"  Status   : {current_status}  →  {args.status}")
    print()

    fields["status"] = args.status
    try:
        draft_path.write_text(_write_frontmatter(fields, body), encoding="utf-8")
    except OSError as exc:
        print(f"[ERROR] Cannot write draft: {exc}")
        sys.exit(1)

    print(f"[OK] Frontmatter updated: status = {args.status}")
    print(f"[OK] Draft saved: {draft_path.relative_to(ROOT)}")

    _save_to_engram(paper_id, title, journal, quartile, args.status)

    next_q = _ESCALERA.get(quartile, "Q4")

    print(f"\n{'=' * 58}")
    print(f"  PAPER ARCHIVADO")
    print(f"  {title[:50]}")
    print(f"  Para: {journal} ({quartile})")
    print(f"{'=' * 58}")
    print()
    print("  Qué sigue?")
    print(f"  1. Enviar a {journal}")
    if journal and journal != "TBD":
        print(f"     → python3 tools/generate_cover_letter.py {draft_path.relative_to(ROOT)}")
    print(f"  2. Iniciar el siguiente paper (escalera obligatoria: {next_q})")
    print("     → Abre Claude Code y di 'engram conectó'")
    print("  3. AutoResearch (optimizar el stack automáticamente)")
    print("     → python3 tools/autoresearch.py --experiments 5 --room validator")
    print()
    print("  Solo después de que el usuario elija se puede iniciar un nuevo EXPLORE.")
    print()


if __name__ == "__main__":
    main()
