#!/usr/bin/env python3
"""
tools/check_novelty.py — Deep Novelty Checker for the Paper Factory
====================================================================
Searches OpenAlex (250M+ works) and arXiv to verify that the proposed
paper topic is original. Generates a structured novelty report.

No API key required. No MCP server needed. Runs standalone.

Usage:
  python3 tools/check_novelty.py --keywords "acoustic emission, PINNs, bolted connections"
  python3 tools/check_novelty.py                    # Extract keywords from PRD.md
  python3 tools/check_novelty.py --deep             # Extra queries + citation network
  python3 tools/check_novelty.py --save             # Save report to articles/drafts/

Sources:
  - OpenAlex API (250M+ works, Scopus/PubMed/CrossRef coverage)
  - arXiv API (preprints, STEM)
"""

import argparse
import re
import sys
import time
import urllib.parse
import urllib.request
import json
import xml.etree.ElementTree as ET
from datetime import date
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRD_PATH = ROOT / "PRD.md"
REPORT_PATH = ROOT / "articles" / "drafts" / "novelty_report.md"

OPENALEX_BASE = "https://api.openalex.org/works"
ARXIV_BASE = "http://export.arxiv.org/api/query"

# Contact email for polite pool (OpenAlex recommends it for faster responses)
MAILTO = "mailto:belico-stack@research.local"

# Noise filter for PRD keyword extraction
STOPWORDS = {
    "problema", "vision", "usuario", "pipeline", "siguiente paso", "alcance",
    "riesgos", "fuera de alcance", "documentos relacionados", "criterios de exito",
    "gap analysis", "bugs", "estado", "corregido", "funcional", "pendiente",
    "arquitectura", "producto", "requisitos", "workflow", "flujo", "instalacion",
    "dependencias", "configuracion", "notas", "componente", "archivo", "path",
    "herramienta", "tipo", "tabla", "seccion", "version", "fecha", "autor",
    "este documento", "lo que falta", "resuelto", "menor", "critico", "importante",
}


# ═══════════════════════════════════════════════════════════════════════
# API Clients
# ═══════════════════════════════════════════════════════════════════════

def _get_json(url: str, retries: int = 2) -> dict | None:
    """GET a URL and return parsed JSON, with retries."""
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": MAILTO})
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            if attempt < retries:
                time.sleep(1)
            else:
                print(f"    [WARN] Failed: {e}")
                return None


def search_openalex(query: str, per_page: int = 10) -> list[dict]:
    """Search OpenAlex for works matching the query."""
    encoded = urllib.parse.quote(query)
    url = f"{OPENALEX_BASE}?search={encoded}&per_page={per_page}&sort=relevance_score:desc"
    data = _get_json(url)
    if not data or "results" not in data:
        return []

    papers = []
    for w in data["results"]:
        source = (w.get("primary_location") or {}).get("source") or {}
        papers.append({
            "title": w.get("display_name", "Unknown"),
            "year": w.get("publication_year"),
            "journal": source.get("display_name", "Unknown"),
            "doi": w.get("doi", ""),
            "cited_by": w.get("cited_by_count", 0),
            "source": "OpenAlex",
        })
    return papers


def search_arxiv(query: str, max_results: int = 5) -> list[dict]:
    """Search arXiv for preprints matching the query."""
    encoded = urllib.parse.quote(query)
    url = f"{ARXIV_BASE}?search_query=all:{encoded}&start=0&max_results={max_results}&sortBy=relevance"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": MAILTO})
        with urllib.request.urlopen(req, timeout=15) as resp:
            xml_data = resp.read().decode("utf-8")
    except Exception as e:
        print(f"    [WARN] arXiv failed: {e}")
        return []

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError:
        return []

    papers = []
    for entry in root.findall("atom:entry", ns):
        title = entry.findtext("atom:title", "", ns).strip().replace("\n", " ")
        published = entry.findtext("atom:published", "", ns)[:4]
        papers.append({
            "title": title,
            "year": int(published) if published.isdigit() else None,
            "journal": "arXiv (preprint)",
            "doi": "",
            "cited_by": 0,
            "source": "arXiv",
        })
    return papers


def get_citing_works(openalex_id: str, per_page: int = 5) -> list[dict]:
    """Get works that cite a given OpenAlex work (citation network)."""
    url = f"{OPENALEX_BASE}?filter=cites:{openalex_id}&per_page={per_page}&sort=relevance_score:desc"
    data = _get_json(url)
    if not data or "results" not in data:
        return []

    papers = []
    for w in data["results"]:
        source = (w.get("primary_location") or {}).get("source") or {}
        papers.append({
            "title": w.get("display_name", "Unknown"),
            "year": w.get("publication_year"),
            "journal": source.get("display_name", "Unknown"),
            "doi": w.get("doi", ""),
            "cited_by": w.get("cited_by_count", 0),
            "source": "OpenAlex (citation)",
        })
    return papers


# ═══════════════════════════════════════════════════════════════════════
# Keyword Extraction
# ═══════════════════════════════════════════════════════════════════════

def extract_keywords_from_prd(prd_path: Path) -> list[str]:
    """Extract research keywords from PRD.md, filtering noise."""
    if not prd_path.exists():
        return []

    text = prd_path.read_text(encoding="utf-8")
    keywords = set()

    for match in re.finditer(r'[Kk]eywords?[:\s]+([^\n]+)', text):
        for kw in match.group(1).split(","):
            kw = kw.strip().strip("*`\"'")
            if 2 < len(kw) < 50:
                keywords.add(kw.lower())

    for match in re.finditer(r'\*\*([^*]+)\*\*', text):
        term = match.group(1).strip()
        if (3 < len(term) < 60
                and not any(c in term for c in ['/', '\\', '(', ')', '|', '='])
                and term.lower() not in STOPWORDS):
            keywords.add(term.lower())

    filtered = set()
    for kw in keywords:
        if any(noise in kw for noise in [
            'corregido', 'funcional', 'pendiente', 'tools/', 'src/',
            '.py', '.sh', '.md', 'brew', 'git ', 'b1', 'b2', 'w1',
            '---', '|', 'resuelto', 'estado', 'gap', 'bug', 'fix',
        ]):
            continue
        if kw in STOPWORDS:
            continue
        alpha_ratio = sum(c.isalpha() or c == ' ' for c in kw) / max(len(kw), 1)
        if alpha_ratio < 0.7:
            continue
        filtered.add(kw)

    return sorted(filtered)


# ═══════════════════════════════════════════════════════════════════════
# Query Generation
# ═══════════════════════════════════════════════════════════════════════

def generate_queries(keywords: list[str], deep: bool = False) -> list[str]:
    """Generate search queries from keyword combinations."""
    queries = []
    if not keywords:
        return queries

    # Full combination (top 5)
    queries.append(" ".join(keywords[:5]))

    # Pairwise combinations
    top = keywords[:7] if deep else keywords[:5]
    for a, b in combinations(top, 2):
        queries.append(f"{a} {b}")
        if not deep and len(queries) >= 10:
            break

    # Triplets (deep mode)
    if deep and len(keywords) >= 3:
        for a, b, c in combinations(keywords[:5], 3):
            queries.append(f"{a} {b} {c}")
            if len(queries) >= 20:
                break

    return queries


# ═══════════════════════════════════════════════════════════════════════
# Deduplication & Threat Assessment
# ═══════════════════════════════════════════════════════════════════════

def deduplicate(papers: list[dict]) -> list[dict]:
    """Remove duplicate papers by title similarity."""
    seen_titles = set()
    unique = []
    for p in papers:
        normalized = p["title"].lower().strip()[:80]
        if normalized not in seen_titles:
            seen_titles.add(normalized)
            unique.append(p)
    return unique


def assess_threat(paper: dict, keywords: list[str]) -> str:
    """Assess threat level based on keyword overlap in title."""
    title_lower = paper["title"].lower()
    matches = sum(1 for kw in keywords if kw in title_lower)
    ratio = matches / max(len(keywords), 1)
    if ratio >= 0.6:
        return "HIGH"
    elif ratio >= 0.3:
        return "MEDIUM"
    return "LOW"


# ═══════════════════════════════════════════════════════════════════════
# Report Generation
# ═══════════════════════════════════════════════════════════════════════

def generate_report(keywords: list[str], papers: list[dict],
                    queries_run: int, verdict: str, gap: str) -> str:
    """Generate the novelty report in Markdown."""
    kw_list = ", ".join(keywords)

    rows = ""
    for i, p in enumerate(papers[:25], 1):
        threat = assess_threat(p, keywords)
        rows += (f"| {i} | {p['title'][:80]} | {p['year']} | "
                 f"{p['journal'][:30]} | {p['cited_by']} | {threat} | {p['source']} |\n")

    high = sum(1 for p in papers if assess_threat(p, keywords) == "HIGH")
    medium = sum(1 for p in papers if assess_threat(p, keywords) == "MEDIUM")
    low = sum(1 for p in papers if assess_threat(p, keywords) == "LOW")

    return f"""---
title: Novelty Check Report
status: completed
date: {date.today()}
verdict: {verdict}
keywords: [{kw_list}]
sources: OpenAlex (250M+ works), arXiv
queries_executed: {queries_run}
papers_analyzed: {len(papers)}
threat_high: {high}
threat_medium: {medium}
threat_low: {low}
---

# Novelty Check Report

## 1. Keywords

{kw_list}

## 2. Search Summary

| Metric | Value |
|--------|-------|
| Queries executed | {queries_run} |
| Total papers found | {len(papers)} (deduplicated) |
| Sources | OpenAlex (250M+ works), arXiv |
| HIGH threat | {high} |
| MEDIUM threat | {medium} |
| LOW threat | {low} |

## 3. Papers Found

| # | Title | Year | Journal | Cites | Threat | Source |
|---|-------|------|---------|-------|--------|--------|
{rows}

## 4. Gap Analysis

{gap}

## 5. Verdict: **{verdict}**

{"Proceed to PROPOSE." if verdict == "ORIGINAL" else ""}
{"Proceed to PROPOSE with explicit differentiation." if verdict == "INCREMENTAL" else ""}
{"Pivot required. See recommendations below." if verdict == "DUPLICATE" else ""}
"""


# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Deep Novelty Checker — OpenAlex + arXiv search")
    parser.add_argument("--keywords", type=str,
                        help="Manual keywords (comma-separated)")
    parser.add_argument("--deep", action="store_true",
                        help="Deep search: more queries + citation network")
    parser.add_argument("--save", action="store_true",
                        help="Save report to articles/drafts/novelty_report.md")
    args = parser.parse_args()

    print("=" * 60)
    print("  NOVELTY CHECKER — Deep Academic Search")
    print("  Sources: OpenAlex (250M+ works) + arXiv")
    print("=" * 60)

    # ── Keywords ──
    if args.keywords:
        keywords = [k.strip().lower() for k in args.keywords.split(",")]
    else:
        keywords = extract_keywords_from_prd(PRD_PATH)

    if not keywords:
        print("\n  No keywords found. Use --keywords \"term1, term2, term3\"")
        sys.exit(1)

    print(f"\n  Keywords ({len(keywords)}):")
    for kw in keywords:
        print(f"    - {kw}")

    # ── Generate queries ──
    queries = generate_queries(keywords, deep=args.deep)
    print(f"\n  Queries to execute: {len(queries)}")

    # ── Search OpenAlex ──
    all_papers = []
    queries_run = 0

    print(f"\n  Searching OpenAlex...")
    for i, q in enumerate(queries, 1):
        print(f"    [{i}/{len(queries)}] {q[:60]}...")
        results = search_openalex(q, per_page=10)
        all_papers.extend(results)
        queries_run += 1
        time.sleep(0.2)  # polite rate limiting

    # ── Search arXiv ──
    print(f"\n  Searching arXiv...")
    for q in queries[:5]:  # arXiv is slower, limit queries
        results = search_arxiv(q, max_results=5)
        all_papers.extend(results)
        queries_run += 1
        time.sleep(0.5)  # arXiv rate limit: 1 req/3s

    # ── Citation network (deep mode) ──
    if args.deep and all_papers:
        print(f"\n  Analyzing citation network...")
        # Find the most relevant paper and check who cites it
        top_paper = all_papers[0] if all_papers else None
        if top_paper and top_paper.get("doi"):
            # Extract OpenAlex ID from first result
            encoded = urllib.parse.quote(top_paper["title"][:50])
            lookup = _get_json(f"{OPENALEX_BASE}?search={encoded}&per_page=1")
            if lookup and lookup.get("results"):
                oa_id = lookup["results"][0].get("id", "").split("/")[-1]
                if oa_id:
                    citing = get_citing_works(oa_id, per_page=10)
                    all_papers.extend(citing)
                    print(f"    Found {len(citing)} citing works")

    # ── Deduplicate ──
    unique_papers = deduplicate(all_papers)
    print(f"\n  Total unique papers: {len(unique_papers)}")

    # ── Assess threats ──
    high_threat = [p for p in unique_papers if assess_threat(p, keywords) == "HIGH"]
    medium_threat = [p for p in unique_papers if assess_threat(p, keywords) == "MEDIUM"]
    low_threat = [p for p in unique_papers if assess_threat(p, keywords) == "LOW"]

    print(f"    HIGH threat:   {len(high_threat)}")
    print(f"    MEDIUM threat: {len(medium_threat)}")
    print(f"    LOW threat:    {len(low_threat)}")

    # ── Verdict ──
    if len(high_threat) >= 2:
        verdict = "DUPLICATE"
        gap = ("Multiple papers with high keyword overlap found. "
               "The proposed contribution may not be sufficiently novel.")
    elif len(high_threat) == 1:
        verdict = "INCREMENTAL"
        gap = (f"One paper with high overlap: \"{high_threat[0]['title'][:80]}\" "
               f"({high_threat[0]['year']}). Differentiation needed.")
    elif len(medium_threat) >= 5:
        verdict = "INCREMENTAL"
        gap = ("Several papers touch related topics but none combine all keywords. "
               "Explicit differentiation recommended.")
    else:
        verdict = "ORIGINAL"
        gap = ("No paper found that combines all proposed keywords. "
               "The intersection of these topics appears novel.")

    print(f"\n  {'=' * 50}")
    print(f"  VERDICT: {verdict}")
    print(f"  {'=' * 50}")
    print(f"  {gap}")

    # ── Top threats ──
    if high_threat or medium_threat:
        print(f"\n  Top threats:")
        for p in (high_threat + medium_threat)[:5]:
            threat = assess_threat(p, keywords)
            print(f"    [{threat}] {p['title'][:70]} ({p['year']}, {p['journal'][:25]})")

    # ── Save report ──
    if args.save:
        report = generate_report(keywords, unique_papers, queries_run, verdict, gap)
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(report, encoding="utf-8")
        print(f"\n  Report saved: {REPORT_PATH}")

    print(f"""
  ─────────────────────────────────────────────────
  Queries executed:  {queries_run}
  Papers analyzed:   {len(unique_papers)}
  Verdict:           {verdict}

  For deeper analysis: python3 tools/check_novelty.py --deep --save
  ─────────────────────────────────────────────────
""")

    # Exit code for pipeline integration
    if verdict == "DUPLICATE":
        sys.exit(2)
    elif verdict == "INCREMENTAL":
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
