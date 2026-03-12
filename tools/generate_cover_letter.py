#!/usr/bin/env python3
"""
tools/generate_cover_letter.py — Cover Letter & Reviewer Response Generator
=============================================================================
Generates parametric cover letters for journal submissions and structured
templates for responding to reviewer comments.

Usage:
  python3 tools/generate_cover_letter.py cover --draft articles/drafts/paper_Q2_xxx.md
  python3 tools/generate_cover_letter.py cover --journal "Engineering Structures" --editor "Prof. Smith"
  python3 tools/generate_cover_letter.py response --draft articles/drafts/paper_Q2_xxx.md --round 1
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent


def _extract_frontmatter(draft_path: Path) -> dict:
    """Extract YAML frontmatter fields from a draft."""
    try:
        text = draft_path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"[COVER] WARNING: Could not read draft {draft_path}: {e} — using defaults", file=sys.stderr)
        return {}
    if not text.startswith("---"):
        return {}
    fm_end = text.find("---", 3)
    if fm_end == -1:
        return {}
    fm_text = text[3:fm_end]
    result = {}
    for line in fm_text.strip().split("\n"):
        if ":" in line:
            key, _, val = line.partition(":")
            result[key.strip()] = val.strip().strip('"').strip("'")
    return result


def generate_cover_letter(draft_path: Path = None, journal: str = "",
                          editor: str = "", highlights: list = None) -> str:
    """Generate a cover letter for journal submission."""
    fm = _extract_frontmatter(draft_path) if draft_path else {}
    title = fm.get("title", "[PAPER TITLE]")
    domain = fm.get("domain", "structural")
    quartile = fm.get("quartile", "Q2")
    authors = fm.get("authors", "[AUTHOR NAMES]")

    if not journal:
        journal = {
            "Q1": "Engineering Structures",
            "Q2": "Structural Control and Health Monitoring",
            "Q3": "Journal of Civil Structural Health Monitoring",
            "Q4": "Infrastructures",
            "conference": "Conference Proceedings",
        }.get(quartile, "[JOURNAL NAME]")

    if not editor:
        editor = "the Editor-in-Chief"

    if not highlights:
        highlights = [
            "Novel integration of [TODO: key contribution 1]",
            "Validated against [TODO: dataset/benchmark]",
            "Open-source implementation available at [TODO: repo URL]",
        ]

    date_str = datetime.now().strftime("%B %d, %Y")

    letter = f"""---
type: cover_letter
journal: "{journal}"
paper_title: "{title}"
date: "{date_str}"
status: draft
---

{date_str}

Dear {editor},

We are pleased to submit our manuscript entitled **"{title}"** for consideration
for publication in *{journal}*.

## Summary

[TODO: 2-3 sentence summary of the paper's main contribution and significance]

## Key Highlights

"""
    for i, h in enumerate(highlights, 1):
        letter += f"{i}. {h}\n"

    letter += f"""
## Novelty Statement

This work is novel because [TODO: explain what distinguishes this from existing literature].
To our knowledge, no previous study has [TODO: specific gap filled].

## Relevance to {journal}

This manuscript aligns with the scope of *{journal}* because [TODO: explain relevance
to the journal's focus areas and readership].

## Declarations

- This manuscript has not been published previously and is not under consideration
  by another journal.
- All authors have approved the manuscript and agree with its submission.
- [TODO: Funding acknowledgment]
- [TODO: Conflict of interest statement]
- Data and code availability: [TODO: repository link]

## Suggested Reviewers

1. [TODO: Name, Affiliation, Email — expertise in ...]
2. [TODO: Name, Affiliation, Email — expertise in ...]
3. [TODO: Name, Affiliation, Email — expertise in ...]

We believe this work makes a significant contribution to the field and look
forward to hearing from you.

Sincerely,

[TODO: Corresponding author name]
[TODO: Affiliation]
[TODO: Email]
"""
    return letter


def generate_reviewer_response(draft_path: Path = None, round_num: int = 1) -> str:
    """Generate a structured template for responding to reviewer comments."""
    fm = _extract_frontmatter(draft_path) if draft_path else {}
    title = fm.get("title", "[PAPER TITLE]")
    date_str = datetime.now().strftime("%B %d, %Y")

    response = f"""---
type: reviewer_response
paper_title: "{title}"
revision_round: {round_num}
date: "{date_str}"
status: draft
---

# Response to Reviewers — Revision Round {round_num}

**Manuscript:** {title}
**Date:** {date_str}

---

Dear Editor and Reviewers,

We thank the reviewers for their constructive comments and careful reading of our
manuscript. We have addressed all comments point-by-point as detailed below.
Changes in the revised manuscript are highlighted in **blue**.

---

## Reviewer 1

### Comment 1.1
> [TODO: Paste reviewer comment here]

**Response:** [TODO: Your response]

**Action taken:** [TODO: Describe specific changes made, with page/line numbers]

---

### Comment 1.2
> [TODO: Paste reviewer comment here]

**Response:** [TODO: Your response]

**Action taken:** [TODO: Describe specific changes made]

---

## Reviewer 2

### Comment 2.1
> [TODO: Paste reviewer comment here]

**Response:** [TODO: Your response]

**Action taken:** [TODO: Describe specific changes made]

---

### Comment 2.2
> [TODO: Paste reviewer comment here]

**Response:** [TODO: Your response]

**Action taken:** [TODO: Describe specific changes made]

---

## Summary of Changes

| Section | Change | Motivation |
|---|---|---|
| [TODO] | [TODO] | Reviewer 1, Comment 1.1 |
| [TODO] | [TODO] | Reviewer 2, Comment 2.1 |

---

We believe the revised manuscript addresses all concerns raised by the reviewers
and hope it is now suitable for publication in [TODO: Journal Name].

Sincerely,
[TODO: Authors]
"""
    return response


def main():
    parser = argparse.ArgumentParser(description="Cover Letter & Reviewer Response Generator")
    sub = parser.add_subparsers(dest="command")

    cover = sub.add_parser("cover", help="Generate cover letter")
    cover.add_argument("--draft", type=str, help="Draft .md file path")
    cover.add_argument("--journal", type=str, default="", help="Target journal name")
    cover.add_argument("--editor", type=str, default="", help="Editor name")

    resp = sub.add_parser("response", help="Generate reviewer response template")
    resp.add_argument("--draft", type=str, help="Draft .md file path")
    resp.add_argument("--round", type=int, default=1, help="Revision round number")

    args = parser.parse_args()

    if args.command == "cover":
        draft = Path(args.draft) if args.draft else None
        letter = generate_cover_letter(draft, args.journal, args.editor)
        # Output
        out_name = f"cover_letter_{datetime.now().strftime('%Y%m%d')}.md"
        out_path = ROOT / "articles" / out_name
        try:
            out_path.write_text(letter, encoding="utf-8")
        except OSError as e:
            print(f"[COVER] ERROR: Could not write {out_path}: {e}", file=sys.stderr)
            sys.exit(1)
        print(f"[COVER] Generated: {out_path}")

    elif args.command == "response":
        draft = Path(args.draft) if args.draft else None
        response = generate_reviewer_response(draft, args.round)
        out_name = f"reviewer_response_R{args.round}_{datetime.now().strftime('%Y%m%d')}.md"
        out_path = ROOT / "articles" / out_name
        try:
            out_path.write_text(response, encoding="utf-8")
        except OSError as e:
            print(f"[COVER] ERROR: Could not write {out_path}: {e}", file=sys.stderr)
            sys.exit(1)
        print(f"[RESPONSE] Generated: {out_path}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
