#!/usr/bin/env python3
"""
patent_scaffold.py — Sprint 4B: Generate patent draft from gap analysis.

CLI: python3 tools/patent_scaffold.py --paper-id foo --jurisdiction US [--title "Mi Metodología"]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
import os

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
load_dotenv(Path(__file__).parent.parent / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

FALLBACK_DIR = Path(__file__).parent.parent / "db" / "patent_search"
FALLBACK_DIR.mkdir(parents=True, exist_ok=True)

PATENTS_DIR = Path(__file__).parent.parent / "articles" / "patents"
PATENTS_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Load gap analysis
# ---------------------------------------------------------------------------

def _load_gap_supabase(paper_id: str) -> Optional[dict]:
    """Load most recent gap analysis from Supabase innovation_gaps."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        return None
    try:
        from supabase import create_client
        client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        resp = (
            client.table("innovation_gaps")
            .select("*")
            .eq("paper_id", paper_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if resp.data:
            row = resp.data[0]
            analysis = row.get("analysis", {})
            analysis["novelty_verdict"] = row.get("verdict", analysis.get("novelty_verdict", "MEDIUM"))
            return analysis
        return None
    except Exception as exc:  # noqa: BLE001
        print(f"WARNING: Supabase read failed: {exc}", file=sys.stderr)
        return None


def _load_gap_fallback(paper_id: str) -> Optional[dict]:
    """Load most recent gap_{paper_id}_*.json from db/patent_search/."""
    candidates = sorted(
        FALLBACK_DIR.glob(f"gap_{paper_id}_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for path in candidates:
        try:
            data = json.loads(path.read_text())
            # Support both flat and nested analysis structures
            if "analysis" in data:
                return data["analysis"]
            if "gaps" in data:
                return data
        except Exception:  # noqa: BLE001
            continue
    return None


def load_gap_analysis(paper_id: str) -> dict:
    """Load gap analysis from Supabase or fallback. Exits if not found."""
    analysis = _load_gap_supabase(paper_id)
    if analysis is None:
        analysis = _load_gap_fallback(paper_id)
    if analysis is None:
        print(
            f"ERROR: No gap analysis found for paper_id='{paper_id}'.\n"
            f"Run: python3 tools/innovation_gap.py --paper-id {paper_id} --query '<your query>'",
            file=sys.stderr,
        )
        sys.exit(1)
    return analysis


# ---------------------------------------------------------------------------
# Template builders
# ---------------------------------------------------------------------------

_JURISDICTION_NOTE = {
    "US": (
        "This patent application is filed under 35 U.S.C. §§ 101, 102, 103, and 112 "
        "with the United States Patent and Trademark Office (USPTO)."
    ),
    "EP": (
        "This patent application is filed under the European Patent Convention (EPC) "
        "with the European Patent Office (EPO). The invention possesses technical character "
        "and is industrially applicable under Art. 57 EPC."
    ),
    "PCT": (
        "This international application is filed under the Patent Cooperation Treaty (PCT) "
        "via the World Intellectual Property Organization (WIPO). Priority is claimed "
        "under applicable national filings."
    ),
}

_LEGAL_DISCLAIMER = """
> **DISCLAIMER LEGAL / LEGAL DISCLAIMER**
>
> Este documento es un **borrador preliminar generado automáticamente** con fines de investigación
> y orientación. **NO constituye asesoría legal ni una solicitud de patente válida.**
> Requiere revisión y aprobación por un abogado especializado en propiedad intelectual con
> licencia activa en la jurisdicción correspondiente antes de cualquier presentación ante
> una oficina de patentes.
>
> *This document is a preliminary draft generated automatically for research and guidance
> purposes. It does NOT constitute legal advice or a valid patent application. It requires
> review and approval by a licensed intellectual property attorney in the relevant jurisdiction
> before any submission to a patent office.*
"""


def _format_claims(analysis: dict) -> str:
    """Format claims section from analysis dict."""
    # Use pre-generated claims if patent_agent already ran
    claims = analysis.get("claims", {})

    gaps = analysis.get("gaps", [])
    opportunities = analysis.get("innovation_opportunities", [])

    # Build Claim 1 from top gap/opportunity
    if claims.get("claim_1"):
        claim_1 = claims["claim_1"]
    else:
        top_opp = opportunities[0] if opportunities else (gaps[0] if gaps else "the disclosed method")
        # Strip "Opportunity: " prefix if present
        top_opp = top_opp.replace("Opportunity: ", "").strip()
        claim_1 = (
            f"A method comprising:\n"
            f"  receiving input data related to {top_opp[:80]};\n"
            f"  processing said input data using a computational model;\n"
            f"  generating an output indicative of a result; and\n"
            f"  applying the output to improve system performance."
        )

    # Build dependent claims from remaining gaps/opportunities
    dep_claims: list[str] = []
    for i, src in enumerate(
        list(claims.get(f"claim_{j}", "") for j in range(2, 6))
        or opportunities[1:5]
        or gaps[1:5],
        start=2,
    ):
        if not src:
            continue
        text = str(src).replace("Opportunity: ", "").strip()
        if text.lower().startswith("the method of claim"):
            dep_claims.append(f"### Claim {i} (Dependent)\n{text}")
        else:
            dep_claims.append(
                f"### Claim {i} (Dependent)\nThe method of claim 1, wherein {text[:120]}."
            )
        if len(dep_claims) >= 4:
            break

    lines = ["### Claim 1 (Independent)", claim_1, ""]
    lines.extend(dep_claims)
    return "\n".join(lines)


def _format_background(analysis: dict) -> str:
    """Build background section from assumptions and counterarguments."""
    parts: list[str] = [
        "The prior art has addressed related problems, however several limitations remain:\n"
    ]
    for a in analysis.get("assumptions", [])[:3]:
        parts.append(f"- {a}")
    for c in analysis.get("counterarguments", [])[:2]:
        parts.append(f"- {c}")
    return "\n".join(parts)


def _format_summary(analysis: dict) -> str:
    """Build summary of the invention from gaps and opportunities."""
    gaps = analysis.get("gaps", [])
    opportunities = analysis.get("innovation_opportunities", [])
    verdict = analysis.get("novelty_verdict", "MEDIUM")
    score = analysis.get("non_obviousness_score", 5)

    lines = [
        f"The present invention addresses {len(gaps)} identified gap(s) in the prior art "
        f"with a non-obviousness score of {score}/10 (verdict: {verdict}).\n",
        "Key innovation opportunities addressed:",
    ]
    for o in (opportunities or gaps)[:4]:
        lines.append(f"- {str(o).replace('Opportunity: ', '')}")
    return "\n".join(lines)


def generate_patent_draft(
    paper_id: str,
    analysis: dict,
    jurisdiction: str,
    title: Optional[str],
    today: str,
) -> str:
    """Generate full patent draft markdown content."""
    verdict = analysis.get("novelty_verdict", "MEDIUM")
    score = analysis.get("non_obviousness_score", 5)

    if title is None:
        title = f"Method and System for {paper_id.replace('_', ' ').title()}"

    jurisdiction_note = _JURISDICTION_NOTE.get(jurisdiction, _JURISDICTION_NOTE["US"])

    frontmatter = f"""---
paper_id: {paper_id}
jurisdiction: {jurisdiction}
status: draft
created: {today}
novelty_verdict: {verdict}
non_obviousness_score: {score}
disclaimer: "Este documento es un borrador preliminar. Requiere revisión por abogado de patentes."
---
"""

    background = _format_background(analysis)
    summary = _format_summary(analysis)
    claims_section = _format_claims(analysis)

    return f"""{frontmatter}
# Patent Draft: {title}

> Jurisdiction: **{jurisdiction}** | Verdict: **{verdict}** | Non-obviousness: **{score}/10**

---

## Field of the Invention

This invention relates to methods and systems for {paper_id.replace('_', ' ')}, and more
particularly to techniques addressing previously unresolved gaps in the prior art.

{jurisdiction_note}

---

## Background

{background}

---

## Summary of the Invention

{summary}

---

## Claims

{claims_section}

---

## Abstract

A method and system are disclosed that address identified gaps in the prior art related to
{paper_id.replace('_', ' ')}. The invention achieves a non-obviousness score of {score}/10
under applicable patent law standards, with a novelty verdict of **{verdict}**. The disclosed
approach overcomes limitations of existing solutions by addressing {len(analysis.get('gaps', []))}
previously unresolved technical challenge(s).

---

## Brief Description of Drawings

*(Reference figures to be included during formal prosecution. Each claim element should be
illustrated with at least one drawing reference numeral.)*

- FIG. 1 — System architecture overview
- FIG. 2 — Method flowchart (Claim 1 steps)
- FIG. 3 — Detailed view of key innovation component

---

## Detailed Description

The following detailed description is set forth to provide an understanding of the invention
as defined by the claims. This description references the accompanying drawings (FIG. 1-3).

### Embodiment 1

*(To be completed by patent counsel based on the claims and technical specification.)*

### Embodiment 2

*(Alternative configurations addressing Claims 2-5.)*

---

{_LEGAL_DISCLAIMER}
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def patent_scaffold(
    paper_id: str,
    jurisdiction: str = "US",
    title: Optional[str] = None,
) -> Path:
    """Generate patent draft markdown. Returns path to generated file."""
    jurisdiction = jurisdiction.upper()
    if jurisdiction not in ("US", "EP", "PCT"):
        print(f"WARNING: Unknown jurisdiction '{jurisdiction}', defaulting to US.", file=sys.stderr)
        jurisdiction = "US"

    print(f"Loading gap analysis for: {paper_id}", file=sys.stderr)
    analysis = load_gap_analysis(paper_id)

    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    content = generate_patent_draft(paper_id, analysis, jurisdiction, title, today)

    output_path = PATENTS_DIR / f"{paper_id}_patent_draft.md"
    output_path.write_text(content, encoding="utf-8")

    print(f"Patent draft generated: {output_path}", file=sys.stderr)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a structured patent draft from gap analysis."
    )
    parser.add_argument("--paper-id", required=True, type=str, help="Paper ID")
    parser.add_argument(
        "--jurisdiction",
        type=str,
        default="US",
        choices=["US", "EP", "PCT"],
        help="Target patent jurisdiction (default: US)",
    )
    parser.add_argument("--title", type=str, default=None, help="Optional invention title")
    args = parser.parse_args()

    path = patent_scaffold(args.paper_id, jurisdiction=args.jurisdiction, title=args.title)
    print(str(path))


if __name__ == "__main__":
    main()
