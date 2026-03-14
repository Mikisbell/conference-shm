#!/usr/bin/env python3
"""
innovation_gap.py — Sprint 3: Challenger Protocol gap analysis for patent innovation.

CLI: python3 tools/innovation_gap.py --paper-id foo --query "structural health monitoring edge AI"
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
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


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_from_supabase(paper_id: str) -> Optional[dict]:
    """Load reference paper record from Supabase."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        return None
    try:
        from supabase import create_client
        client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        resp = (
            client.table("reference_papers")
            .select("*")
            .eq("paper_id", paper_id)
            .limit(1)
            .execute()
        )
        if resp.data:
            return resp.data[0]
        return None
    except Exception as exc:  # noqa: BLE001
        print(f"WARNING: Supabase read failed: {exc}", file=sys.stderr)
        return None


def _load_from_fallback(paper_id: str) -> Optional[dict]:
    """Load paper from db/patent_search/{paper_id}.json."""
    path = FALLBACK_DIR / f"{paper_id}.json"
    if path.exists():
        return json.loads(path.read_text())
    return None


def load_paper(paper_id: str) -> dict:
    """Load paper from Supabase or local fallback. Exits if not found."""
    record = _load_from_supabase(paper_id)
    if record is None:
        record = _load_from_fallback(paper_id)
    if record is None:
        print(
            f"ERROR: Paper '{paper_id}' not found in Supabase or {FALLBACK_DIR}/",
            file=sys.stderr,
        )
        sys.exit(1)
    return record


def _load_patent_results_supabase(query: str) -> list[dict]:
    """Load latest patent search results from Supabase for given query."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        return []
    try:
        from supabase import create_client
        client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        resp = (
            client.table("patent_searches")
            .select("results")
            .eq("query", query)
            .order("searched_at", desc=True)
            .limit(1)
            .execute()
        )
        if resp.data and resp.data[0].get("results"):
            return resp.data[0]["results"]
        return []
    except Exception as exc:  # noqa: BLE001
        print(f"WARNING: Supabase patent search read failed: {exc}", file=sys.stderr)
        return []


def _load_patent_results_fallback(query: str) -> list[dict]:
    """Load most recent patent_search JSON file matching the query slug."""
    slug = re.sub(r"[^\w]", "_", query.lower())[:40].strip("_")
    candidates = sorted(
        FALLBACK_DIR.glob(f"{slug[:20]}*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for path in candidates:
        try:
            data = json.loads(path.read_text())
            if "results" in data:
                return data["results"]
        except Exception:  # noqa: BLE001
            continue
    return []


def load_patent_results(query: str) -> list[dict]:
    """Load patent results from Supabase or local files."""
    results = _load_patent_results_supabase(query)
    if not results:
        results = _load_patent_results_fallback(query)
    return results


# ---------------------------------------------------------------------------
# Heuristic gap analysis (Challenger Protocol)
# ---------------------------------------------------------------------------

# Phrases that signal limitations / future work in academic text
_LIMITATION_SIGNALS = [
    "future work", "limitation", "does not", "cannot", "out of scope",
    "not considered", "not addressed", "remains to be", "beyond the scope",
    "further research", "not validated", "constrained by", "restricted to",
    "simplifying assumption",
]

# Phrases that signal implicit assumptions
_ASSUMPTION_SIGNALS = [
    "we assume", "assuming", "it is assumed", "we consider", "treated as",
    "approximated", "simplified", "idealized", "neglected",
]

# Phrases that signal unresolved problems
_GAP_SIGNALS = [
    "has not been", "have not been", "lacks", "lack of", "insufficient",
    "no existing", "few studies", "limited studies", "rarely", "seldom",
    "overlooked", "underexplored",
]


def _extract_sentences_with(text: str, signals: list[str], max_count: int = 5) -> list[str]:
    """Return sentences containing any of the signal phrases."""
    found: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        lower = sentence.lower()
        if any(sig in lower for sig in signals):
            cleaned = sentence.strip()
            if 20 < len(cleaned) < 400:
                found.append(cleaned)
        if len(found) >= max_count:
            break
    return found


def _compute_non_obviousness(
    assumptions: list[str],
    gaps: list[str],
    patent_count: int,
) -> int:
    """
    Heuristic non-obviousness score 0-10.
    Higher = more likely patentable under USPTO §103.
    """
    score = 5  # baseline
    score += min(len(gaps), 3)         # more gaps = higher novelty potential
    score -= min(patent_count // 3, 3) # more existing patents = lower novelty
    score += 1 if len(assumptions) > 2 else 0  # many assumptions → unexplored space
    return max(0, min(10, score))


def _determine_verdict(score: int) -> str:
    if score >= 8:
        return "HIGH"
    if score >= 5:
        return "MEDIUM"
    return "LOW"


def generate_gap_analysis(paper: dict, patent_results: list[dict], query: str) -> dict:
    """
    Apply Challenger Protocol heuristics to generate gap analysis dict.

    NOTE: Deep semantic analysis is delegated to the patent_agent sub-agent.
    This function prepares structured data for that agent.
    """
    full_text = paper.get("full_text", "") or paper.get("methodology_text", "")
    limitations_text = paper.get("limitations_text", "")

    combined_text = full_text + "\n" + limitations_text

    # --- Step 1: Assumptions (what does the paper take for granted?) ---
    assumptions = _extract_sentences_with(combined_text, _ASSUMPTION_SIGNALS, max_count=5)
    # Rule 2: if no assumptions found in text, return empty — do NOT fabricate placeholders

    # --- Step 2: Counterarguments (what would a Q1 reviewer say?) ---
    counterarguments: list[str] = []
    if patent_results:
        top_patents = patent_results[:3]
        for p in top_patents:
            title = (p.get("title") or "")[:80]
            if title:
                counterarguments.append(
                    f"Prior art '{title}' ({p.get('publication_number', '')}) "
                    f"may anticipate key claims — differentiation required."
                )
    if not counterarguments:
        # Rule 2: no patents available — return empty, do NOT fabricate reviewer comments
        print("No prior art available for counterarguments", file=sys.stderr)

    # --- Step 3: Gaps (what does the paper NOT solve?) ---
    # Rule 2: only extract gaps present in the actual text; do NOT infer by keyword absence
    gaps = _extract_sentences_with(combined_text, _GAP_SIGNALS + _LIMITATION_SIGNALS, max_count=6)
    # If no gap signals found in text, return empty — no fallback fabrication

    # --- Innovation opportunities (synthesized from gaps) ---
    innovation_opportunities = [
        f"Opportunity: {gap[:120]}" for gap in gaps[:4]
    ]
    if patent_results:
        existing_methods = {
            p.get("title", "").lower()[:40] for p in patent_results if p.get("title")
        }
        innovation_opportunities.append(
            f"Differentiation from {len(patent_results)} existing patents via novel combination."
        )

    score = _compute_non_obviousness(assumptions, gaps, len(patent_results))
    verdict = _determine_verdict(score)

    return {
        "assumptions": assumptions,
        "counterarguments": counterarguments,
        "gaps": gaps,
        "innovation_opportunities": innovation_opportunities,
        "non_obviousness_score": score,
        "novelty_verdict": verdict,
        "patent_overlap_count": len(patent_results),
        "query": query,
        "paper_id": paper.get("paper_id", "unknown"),
    }


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_to_supabase(gap_id: str, paper_id: str, query: str, analysis: dict, verdict: str) -> bool:
    """Insert gap analysis into innovation_gaps table."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        print("WARNING: Supabase credentials not set — skipping Supabase.", file=sys.stderr)
        return False
    try:
        from supabase import create_client
        client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        record = {
            "gap_id": gap_id,
            "paper_id": paper_id,
            "query": query,
            "analysis": analysis,
            "verdict": verdict,
        }
        client.table("innovation_gaps").insert(record).execute()
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"WARNING: Supabase insert failed: {exc}", file=sys.stderr)
        return False


def save_fallback(paper_id: str, gap_id: str, analysis: dict) -> Path:
    """Save gap analysis to db/patent_search/gap_{paper_id}_{timestamp}.json."""
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    target = FALLBACK_DIR / f"gap_{paper_id}_{ts}.json"
    target.write_text(json.dumps(analysis, indent=2, ensure_ascii=False))
    return target


# ---------------------------------------------------------------------------
# Report formatter
# ---------------------------------------------------------------------------

def format_report(analysis: dict) -> str:
    """Format gap analysis as a readable report."""
    lines = [
        "=" * 70,
        "INNOVATION GAP ANALYSIS — CHALLENGER PROTOCOL",
        "=" * 70,
        f"Paper ID : {analysis.get('paper_id', 'N/A')}",
        f"Query    : {analysis.get('query', 'N/A')}",
        f"Verdict  : {analysis.get('novelty_verdict', 'N/A')}  "
        f"(Non-obviousness: {analysis.get('non_obviousness_score', 0)}/10)",
        f"Overlapping patents: {analysis.get('patent_overlap_count', 0)}",
        "",
        "--- STEP 1: ASSUMPTIONS (qué da por sentado el paper) ---",
    ]
    for i, a in enumerate(analysis.get("assumptions", []), 1):
        lines.append(f"  {i}. {a}")

    lines += ["", "--- STEP 2: COUNTERARGUMENTS (reviewer Q1) ---"]
    for i, c in enumerate(analysis.get("counterarguments", []), 1):
        lines.append(f"  {i}. {c}")

    lines += ["", "--- STEP 3: GAPS (qué NO resuelve el paper) ---"]
    for i, g in enumerate(analysis.get("gaps", []), 1):
        lines.append(f"  {i}. {g}")

    lines += ["", "--- INNOVATION OPPORTUNITIES ---"]
    for i, o in enumerate(analysis.get("innovation_opportunities", []), 1):
        lines.append(f"  {i}. {o}")

    lines += ["", "=" * 70]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def innovation_gap(paper_id: str, query: str) -> dict:
    """Full gap analysis pipeline. Returns result dict."""
    print(f"Loading paper: {paper_id}", file=sys.stderr)
    paper = load_paper(paper_id)

    print(f"Loading patent results for: {query}", file=sys.stderr)
    patent_results = load_patent_results(query)
    print(f"Found {len(patent_results)} patent result(s).", file=sys.stderr)

    print("Generating gap analysis...", file=sys.stderr)
    analysis = generate_gap_analysis(paper, patent_results, query)

    gap_id = str(uuid.uuid4())
    verdict = analysis["novelty_verdict"]

    supabase_ok = save_to_supabase(gap_id, paper_id, query, analysis, verdict)
    fb = save_fallback(paper_id, gap_id, analysis)

    print(f"Fallback saved: {fb}", file=sys.stderr)
    if supabase_ok:
        print("Saved to Supabase: innovation_gaps", file=sys.stderr)

    return {
        "gap_id": gap_id,
        "paper_id": paper_id,
        "query": query,
        "verdict": verdict,
        "analysis": analysis,
        "supabase_saved": supabase_ok,
        "fallback_path": str(fb),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate innovation gap analysis using Challenger Protocol."
    )
    parser.add_argument("--paper-id", required=True, type=str, help="Paper ID (from ingest_paper)")
    parser.add_argument("--query", required=True, type=str, help="Patent search query used")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    args = parser.parse_args()

    result = innovation_gap(args.paper_id, args.query)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(format_report(result["analysis"]))
        print(f"\nGap ID : {result['gap_id']}")
        print(f"Saved  : {result['fallback_path']}")


if __name__ == "__main__":
    main()
