#!/usr/bin/env python3
"""
tools/check_novelty.py — Novelty Checker for the Paper Factory
===============================================================
Reads the PRD.md to extract research keywords, generates search queries
for the AI agent to run via WebSearch, and provides a structured template
for the novelty report.

This script does NOT call any API directly. It prepares the queries and
the agent executes them via WebSearch (Google Scholar / web).

Usage:
  python3 tools/check_novelty.py                # Extract from PRD.md
  python3 tools/check_novelty.py --keywords "acoustic emission, PINNs, concrete"
  python3 tools/check_novelty.py --save          # Save report template
"""

import argparse
import re
import sys
from itertools import combinations
from pathlib import Path
from datetime import date

ROOT = Path(__file__).resolve().parent.parent
PRD_PATH = ROOT / "PRD.md"
REPORT_PATH = ROOT / "articles" / "drafts" / "novelty_report.md"

# Words that are NOT useful as research keywords
STOPWORDS = {
    "problema", "vision", "usuario", "pipeline", "siguiente paso", "alcance",
    "riesgos", "fuera de alcance", "documentos relacionados", "criterios de exito",
    "gap analysis", "bugs", "estado", "corregido", "funcional", "pendiente",
    "arquitectura", "producto", "requisitos", "workflow", "flujo", "instalacion",
    "dependencias", "configuracion", "notas", "componente", "archivo", "path",
    "herramienta", "tipo", "tabla", "seccion", "version", "fecha", "autor",
    "este documento", "lo que falta", "resuelto", "menor", "critico", "importante",
}

# Patterns that indicate a line is code/config, not research content
CODE_PATTERNS = [
    r'^[\s]*[-\[\]xX]',       # checklist items
    r'^\|',                     # table rows
    r'^```',                    # code blocks
    r'^#+\s*\d+\.',            # numbered headers like "## 7. bugs"
    r'tools/',                  # tool paths
    r'src/',                    # source paths
    r'config/',                 # config paths
    r'\.py|\.sh|\.md|\.yaml',  # file extensions
    r'brew install',            # install commands
    r'git clone',               # git commands
]


def extract_keywords_from_prd(prd_path: Path) -> list[str]:
    """Extract research keywords from PRD.md, filtering noise."""
    if not prd_path.exists():
        print(f"  PRD not found: {prd_path}")
        return []

    text = prd_path.read_text(encoding="utf-8")
    keywords = set()

    # 1. Explicit keyword lines (highest priority)
    for match in re.finditer(r'[Kk]eywords?[:\s]+([^\n]+)', text):
        for kw in match.group(1).split(","):
            kw = kw.strip().strip("*`\"'")
            if 2 < len(kw) < 50:
                keywords.add(kw.lower())

    # 2. Title of the PRD (first H1)
    title_match = re.search(r'^#\s+(?:PRD\s*[-—]\s*)?(.+)', text, re.MULTILINE)
    if title_match:
        title = title_match.group(1).strip()
        if len(title) < 100:
            keywords.add(title.lower())

    # 3. Bold terms that look like research concepts (not paths/commands)
    for match in re.finditer(r'\*\*([^*]+)\*\*', text):
        term = match.group(1).strip()
        if (3 < len(term) < 60
                and not any(c in term for c in ['/', '\\', '(', ')', '|', '='])
                and term.lower() not in STOPWORDS
                and not any(re.search(p, term) for p in CODE_PATTERNS)):
            keywords.add(term.lower())

    # 4. Section headers from research-relevant sections only
    # Look for sections 1-5 (Problem, Vision, Scope, Methodology, etc.)
    for match in re.finditer(r'^##\s+\d*\.?\s*(.+)', text, re.MULTILINE):
        title = match.group(1).strip().lower()
        if (len(title) < 60
                and title not in STOPWORDS
                and not any(re.search(p, title) for p in CODE_PATTERNS)):
            keywords.add(title)

    # Filter out obvious noise
    filtered = set()
    for kw in keywords:
        # Skip if it looks like a status line, path, or command
        if any(noise in kw for noise in [
            'corregido', 'funcional', 'pendiente', 'instalado', 'verificado',
            'tools/', 'src/', '.py', '.sh', '.md', 'brew', 'git ',
            'b1', 'b2', 'b3', 'w1', 'w2', '---', '|', 'resuelto',
            'estado', 'gap', 'bug', 'fix',
        ]):
            continue
        # Skip if too generic
        if kw in STOPWORDS:
            continue
        # Skip if mostly punctuation or numbers
        alpha_ratio = sum(c.isalpha() or c == ' ' for c in kw) / max(len(kw), 1)
        if alpha_ratio < 0.7:
            continue
        filtered.add(kw)

    return sorted(filtered)


def generate_queries(keywords: list[str], max_queries: int = 8) -> list[str]:
    """Generate WebSearch queries from keyword combinations."""
    queries = []

    if not keywords:
        return queries

    # Query 1: All top keywords together
    top = " ".join(keywords[:5])
    queries.append(f"{top} 2024 2025 2026")

    # Query 2-5: Pairwise combinations
    for a, b in combinations(keywords[:6], 2):
        queries.append(f'"{a}" "{b}" paper')
        if len(queries) >= max_queries - 2:
            break

    # Query: Recent review/survey
    queries.append(f"{keywords[0]} review survey 2024 2025")

    # Query: Google Scholar specific
    queries.append(f"{' '.join(keywords[:3])} site:scholar.google.com")

    return queries[:max_queries]


def generate_report_template(keywords: list[str], queries: list[str]) -> str:
    """Generate the novelty report Markdown template."""
    kw_list = "\n".join(f"- {kw}" for kw in keywords)
    q_list = "\n".join(f"{i}. `{q}`" for i, q in enumerate(queries, 1))

    return f"""---
title: Novelty Check Report
status: pending
date: {date.today()}
---

# Novelty Check Report

## 1. Extracted Keywords

{kw_list}

## 2. Search Queries Executed

{q_list}

## 3. Similar Papers Found

| # | Title | Year | Journal | Overlap | Threat Level |
|---|-------|------|---------|---------|--------------|
| 1 | (pending) | | | | |
| 2 | (pending) | | | | |
| 3 | (pending) | | | | |

**Threat levels:** HIGH = same contribution, MEDIUM = same topic different angle, LOW = related but distinct

## 4. Gap Analysis

<!-- What does our paper do that NONE of the found papers do? -->

(pending — fill after WebSearch results)

## 5. Verdict

- [ ] **ORIGINAL** — No paper combines these exact elements
- [ ] **INCREMENTAL** — Similar work exists but our angle is new
- [ ] **DUPLICATE** — Too close to existing work, pivot needed

## 6. Recommended Differentiation

<!-- If INCREMENTAL, what should we emphasize to differentiate? -->

(pending)
"""


def main():
    parser = argparse.ArgumentParser(
        description="Novelty Checker — extracts keywords and generates search queries")
    parser.add_argument("--keywords", type=str,
                        help="Manual keywords (comma-separated)")
    parser.add_argument("--save", action="store_true",
                        help="Save report to articles/drafts/novelty_report.md")
    args = parser.parse_args()

    print("=" * 55)
    print("  NOVELTY CHECKER — Paper Factory")
    print("=" * 55)

    # Extract keywords
    if args.keywords:
        keywords = [k.strip().lower() for k in args.keywords.split(",")]
        print(f"\n  Keywords (manual): {len(keywords)}")
    else:
        keywords = extract_keywords_from_prd(PRD_PATH)
        print(f"\n  Keywords (from PRD.md): {len(keywords)}")

    if not keywords:
        print("\n  No keywords found. Provide them manually:")
        print("    python3 tools/check_novelty.py --keywords \"term1, term2, term3\"")
        sys.exit(1)

    for kw in keywords:
        print(f"    - {kw}")

    # Generate queries
    queries = generate_queries(keywords)
    print(f"\n  Search queries for WebSearch ({len(queries)}):")
    print()
    for i, q in enumerate(queries, 1):
        print(f"    {i}. {q}")

    # Save report
    if args.save:
        report = generate_report_template(keywords, queries)
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(report, encoding="utf-8")
        print(f"\n  Report template saved: {REPORT_PATH}")

    print(f"""
  ─────────────────────────────────────────────────
  NEXT STEP (for the AI agent):

  1. Run each query above via WebSearch
  2. Fill articles/drafts/novelty_report.md with findings
  3. Set verdict: ORIGINAL / INCREMENTAL / DUPLICATE
  4. If DUPLICATE → pivot the topic before continuing

  Shortcut with manual keywords:
    python3 tools/check_novelty.py --keywords "term1, term2" --save
  ─────────────────────────────────────────────────
""")


if __name__ == "__main__":
    main()
