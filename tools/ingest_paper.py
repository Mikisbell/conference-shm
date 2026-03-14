#!/usr/bin/env python3
"""
ingest_paper.py — Sprint 1: Ingest PDF paper into Supabase reference_papers table.

CLI: python3 tools/ingest_paper.py --pdf articles/references/paper.pdf [--paper-id foo]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
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
# PDF extraction
# ---------------------------------------------------------------------------

def extract_pdf_text(path: Path) -> str:
    """Extract full text from a PDF using pdfminer.six."""
    from pdfminer.high_level import extract_text

    text = extract_text(str(path))
    if not text or not text.strip():
        raise ValueError(f"PDF produced empty text: {path}")
    return text


# ---------------------------------------------------------------------------
# IMRaD section parser
# ---------------------------------------------------------------------------

# Ordered list of section labels with their canonical key.
_IMRAD_PATTERNS: list[tuple[str, str]] = [
    (r"introduction", "introduction"),
    (r"related\s+work", "related_work"),
    (r"method(?:ology|s)?", "methodology"),
    (r"material(?:s)?\s+and\s+method(?:s)?", "methodology"),
    (r"result(?:s)?", "results"),
    (r"discussion", "discussion"),
    (r"conclusion(?:s)?", "conclusion"),
    (r"limitation(?:s)?", "limitations"),
    (r"future\s+work", "future_work"),
    (r"abstract", "abstract"),
]


def _build_section_regex() -> re.Pattern[str]:
    """Build a single regex that matches any IMRaD header line."""
    # Matches lines like "1. Introduction", "## Methods", "RESULTS", etc.
    alternation = "|".join(
        rf"(?P<{key.replace(' ', '_')}_{i}>{pattern})"
        for i, (pattern, key) in enumerate(_IMRAD_PATTERNS)
    )
    return re.compile(
        rf"(?im)^(?:#+\s*|(?:\d+\.?\s+))?(?:{alternation})\s*$"
    )


_HEADER_RE = re.compile(
    r"(?im)^(?:#+\s*|\d+[\.\d]*\s+)?("
    + "|".join(p for p, _ in _IMRAD_PATTERNS)
    + r")\s*$"
)


def parse_imrad_sections(text: str) -> dict[str, str]:
    """Split text into IMRaD sections. Returns dict key → section_text."""
    lines = text.splitlines(keepends=True)
    sections: dict[str, list[str]] = {}
    current_key: Optional[str] = None

    for line in lines:
        stripped = line.strip()
        match = _HEADER_RE.match(stripped)
        if match:
            header_text = match.group(1).lower()
            # Map header_text to canonical key
            canonical = None
            for pattern, key in _IMRAD_PATTERNS:
                if re.fullmatch(pattern, header_text, re.IGNORECASE):
                    canonical = key
                    break
            if canonical is None:
                canonical = re.sub(r"\s+", "_", header_text)
            current_key = canonical
            if current_key not in sections:
                sections[current_key] = []
        elif current_key is not None:
            sections[current_key].append(line)

    return {k: "".join(v).strip() for k, v in sections.items() if "".join(v).strip()}


def extract_limitations_text(sections: dict[str, str], full_text: str) -> str:
    """Return limitations text: dedicated section or heuristic extraction."""
    if "limitations" in sections:
        return sections["limitations"]
    # Heuristic: grab sentences containing limitation keywords
    candidates: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+", full_text):
        lower = sentence.lower()
        if any(kw in lower for kw in ["limitation", "future work", "does not", "cannot",
                                       "out of scope", "not considered", "not addressed"]):
            candidates.append(sentence.strip())
    return " ".join(candidates[:20])  # cap at ~20 sentences


def extract_methodology_text(sections: dict[str, str]) -> str:
    """Return methodology text from parsed sections."""
    for key in ("methodology", "material_and_methods", "materials_and_methods"):
        if key in sections:
            return sections[key]
    return ""


# ---------------------------------------------------------------------------
# Title extractor (best-effort from first 500 chars)
# ---------------------------------------------------------------------------

def extract_title(text: str) -> str:
    """Heuristic: first non-empty non-numeric line that looks like a title."""
    for line in text.splitlines():
        line = line.strip()
        if len(line) > 10 and not line.isdigit():
            return line[:200]
    return "Unknown Title"


# ---------------------------------------------------------------------------
# Supabase persistence
# ---------------------------------------------------------------------------

def save_to_supabase(record: dict) -> bool:
    """Upsert record into reference_papers. Returns True on success."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        print("WARNING: SUPABASE_URL or SUPABASE_SERVICE_KEY not set — skipping Supabase.", file=sys.stderr)
        return False
    try:
        from supabase import create_client
        client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        # Upsert by paper_id
        client.table("reference_papers").upsert(record, on_conflict="paper_id").execute()
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"WARNING: Supabase upsert failed: {exc}", file=sys.stderr)
        return False


# ---------------------------------------------------------------------------
# Fallback: local JSON
# ---------------------------------------------------------------------------

def save_fallback(paper_id: str, result: dict) -> Path:
    """Save result JSON to db/patent_search/{paper_id}.json."""
    target = FALLBACK_DIR / f"{paper_id}.json"
    target.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    return target


# ---------------------------------------------------------------------------
# Main ingest function
# ---------------------------------------------------------------------------

def ingest_paper(pdf_path: Path, paper_id: Optional[str] = None) -> dict:
    """Full ingest pipeline. Returns result dict."""
    if not pdf_path.exists():
        print(f"ERROR: PDF not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    # Derive paper_id from filename hash if not provided
    if paper_id is None:
        sha = hashlib.sha256(pdf_path.read_bytes()).hexdigest()[:8]
        paper_id = f"{pdf_path.stem}_{sha}"

    print(f"Extracting text from: {pdf_path}", file=sys.stderr)
    full_text = extract_pdf_text(pdf_path)
    char_count = len(full_text)

    print(f"Parsing IMRaD sections ({char_count:,} chars)...", file=sys.stderr)
    sections = parse_imrad_sections(full_text)
    found_sections = list(sections.keys())

    title = extract_title(full_text)
    methodology_text = extract_methodology_text(sections)
    limitations_text = extract_limitations_text(sections, full_text)

    record = {
        "paper_id": paper_id,
        "title": title,
        "pdf_path": str(pdf_path),
        "full_text": full_text,
        "methodology_text": methodology_text,
        "limitations_text": limitations_text,
    }

    supabase_ok = save_to_supabase(record)
    fallback_path: Optional[str] = None

    if not supabase_ok:
        fb = save_fallback(paper_id, record)
        fallback_path = str(fb)
        print(f"Fallback saved: {fb}", file=sys.stderr)
    else:
        print("Saved to Supabase: reference_papers", file=sys.stderr)

    result = {
        "paper_id": paper_id,
        "title": title,
        "sections_found": found_sections,
        "char_count": char_count,
        "supabase_saved": supabase_ok,
        "fallback_path": fallback_path,
    }

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest a PDF paper into Supabase reference_papers table."
    )
    parser.add_argument("--pdf", required=True, type=Path, help="Path to PDF file")
    parser.add_argument("--paper-id", type=str, default=None, help="Optional explicit paper_id")
    args = parser.parse_args()

    result = ingest_paper(args.pdf, paper_id=args.paper_id)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
