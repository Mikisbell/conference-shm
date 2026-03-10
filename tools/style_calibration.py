#!/usr/bin/env python3
"""
tools/style_calibration.py — Style Calibration via Semantic Scholar
====================================================================
Fetches 3-5 real papers from the target venue and extracts writing patterns
(voice, sentence length, citation density, intro openers) to build a Style Card.
The Style Card is saved to Engram so all batch narrators can read it before writing.

This is the anti-AI-detection step: narrators copy the voice of real published
authors at the target venue, not generic LLM prose.

No MCP server needed. Runs standalone via Semantic Scholar public API.
Optional: SEMANTIC_SCHOLAR_API_KEY in .env for higher rate limits.

Usage:
  python3 tools/style_calibration.py --venue "EWSHM" --year 2024
  python3 tools/style_calibration.py --venue "Engineering Structures" --year 2023 --n 5
  python3 tools/style_calibration.py --venue "EWSHM" --paper-id icr_shm_ae_conference
  python3 tools/style_calibration.py --dry-run   # analyze only, don't save to Engram

Outputs:
  - Style Card printed to stdout
  - Style Card saved to Engram via `engram save` CLI
  - Style Card saved to articles/drafts/style_card_{paper_id}.md (optional)
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"
STYLE_CARD_DIR = ROOT / "articles" / "drafts"

SS_SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
SS_FIELDS = "title,year,venue,abstract,authors,citationCount,openAccessPdf"

OPENALEX_URL = "https://api.openalex.org/works"

HEADERS_UA = {"User-Agent": "belico-stack/style-calibration (mailto:research@local)"}

# ── Helpers ──────────────────────────────────────────────────────────────────

def load_env():
    """Load .env file into os.environ (simple KEY=VALUE parser)."""
    if not ENV_PATH.exists():
        return
    for line in ENV_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def http_get(url, params=None, headers=None, retries=3, backoff=5):
    """Simple HTTP GET with retry and exponential backoff."""
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={**HEADERS_UA, **(headers or {})})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = backoff * (2 ** attempt)
                print(f"  [rate limit] waiting {wait}s before retry {attempt+1}/{retries}...")
                time.sleep(wait)
            else:
                print(f"  [HTTP {e.code}] {url}")
                return None
        except Exception as ex:
            print(f"  [error] {ex}")
            time.sleep(backoff)
    return None


# ── Semantic Scholar fetcher ──────────────────────────────────────────────────

def fetch_papers_semantic_scholar(venue: str, year: int, n: int, api_key: str = None) -> list[dict]:
    """Search Semantic Scholar for papers from a specific venue."""
    query = f"{venue} {year} structural health monitoring"
    headers = {}
    if api_key:
        headers["x-api-key"] = api_key

    print(f"  [semantic scholar] searching: {query!r}")
    data = http_get(SS_SEARCH_URL, {
        "query": query,
        "fields": SS_FIELDS,
        "limit": n * 3,  # fetch extra to filter
        "year": f"{year - 1}-{year + 1}",
    }, headers=headers)

    if not data or "data" not in data:
        return []

    papers = []
    for p in data["data"]:
        if not p.get("abstract"):
            continue
        title = p.get("title", "")
        abstract = p.get("abstract", "")
        venue_match = p.get("venue", "") or ""
        if len(abstract) < 100:
            continue
        papers.append({
            "title": title,
            "year": p.get("year"),
            "venue": venue_match,
            "abstract": abstract,
            "citation_count": p.get("citationCount", 0),
            "source": "semantic_scholar",
        })
        if len(papers) >= n:
            break

    print(f"  [semantic scholar] found {len(papers)} papers with abstracts")
    return papers


# ── OpenAlex fallback ─────────────────────────────────────────────────────────

def fetch_papers_openalex(venue: str, year: int, n: int, api_key: str = None) -> list[dict]:
    """Fallback: search OpenAlex for papers from a specific venue."""
    query = f"{venue} structural health monitoring"
    print(f"  [openalex fallback] searching: {query!r}")
    params = {
        "search": query,
        "filter": f"publication_year:{year - 1}-{year + 1}",
        "select": "title,publication_year,primary_location,abstract_inverted_index,cited_by_count",
        "per-page": n * 3,
        "mailto": "belico-stack@research.local",
    }
    if api_key:
        params["api_key"] = api_key
    data = http_get(OPENALEX_URL, params)

    if not data or "results" not in data:
        return []

    papers = []
    for p in data["results"]:
        abstract_inv = p.get("abstract_inverted_index") or {}
        if not abstract_inv:
            continue
        # Reconstruct abstract from inverted index
        words = {pos: word for word, positions in abstract_inv.items() for pos in positions}
        abstract = " ".join(words[i] for i in sorted(words))
        if len(abstract) < 100:
            continue
        venue_name = ""
        loc = p.get("primary_location") or {}
        src = loc.get("source") or {}
        venue_name = src.get("display_name", "")
        papers.append({
            "title": p.get("title", ""),
            "year": p.get("publication_year"),
            "venue": venue_name,
            "abstract": abstract,
            "citation_count": p.get("cited_by_count", 0),
            "source": "openalex",
        })
        if len(papers) >= n:
            break

    print(f"  [openalex] found {len(papers)} papers with abstracts")
    return papers


# ── Style analysis ────────────────────────────────────────────────────────────

def analyze_voice(text: str) -> str:
    """Detect dominant voice: active, passive, or mixed."""
    passive_markers = [
        r"\b(is|are|was|were|been|being)\s+\w+ed\b",
        r"\b(is|are|was|were)\s+(proposed|presented|evaluated|analyzed|described|shown|demonstrated)\b",
    ]
    active_markers = [
        r"\bwe\s+(propose|present|develop|evaluate|show|demonstrate|introduce|describe)\b",
        r"\bthis\s+(paper|work|study)\s+(proposes|presents|develops|evaluates|introduces)\b",
    ]
    passive_count = sum(len(re.findall(p, text, re.IGNORECASE)) for p in passive_markers)
    active_count = sum(len(re.findall(p, text, re.IGNORECASE)) for p in active_markers)
    if active_count > passive_count * 1.5:
        return "active"
    elif passive_count > active_count * 1.5:
        return "passive"
    return "mixed"


def avg_sentence_length(text: str) -> float:
    """Average words per sentence."""
    sentences = re.split(r"[.!?]+", text)
    sentences = [s.strip() for s in sentences if len(s.strip().split()) > 3]
    if not sentences:
        return 0.0
    return sum(len(s.split()) for s in sentences) / len(sentences)


def extract_intro_openers(abstracts: list[str]) -> list[str]:
    """Extract the first sentence of each abstract as intro openers."""
    openers = []
    for abstract in abstracts:
        first = re.split(r"[.!?]", abstract.strip())[0].strip()
        if len(first.split()) > 4:
            openers.append(first)
    return openers


def estimate_citation_density(abstracts: list[str]) -> float:
    """Estimate citation density: brackets [N] or (Author, Year) per paragraph."""
    total_refs = 0
    for abstract in abstracts:
        # Count [N] style citations
        total_refs += len(re.findall(r"\[\d+\]", abstract))
        # Count (Author, Year) style
        total_refs += len(re.findall(r"\([A-Z][a-z]+,?\s+\d{4}\)", abstract))
    # Abstracts rarely have citations — estimate from structure
    # Return a baseline for body text (conference papers: 1-2 per paragraph)
    return max(1.0, total_refs / max(len(abstracts), 1))


def dominant_tense(texts: list[str]) -> str:
    """Detect dominant tense used in abstracts."""
    past = sum(len(re.findall(r"\b(showed|measured|computed|evaluated|found|demonstrated|obtained|achieved)\b", t, re.I)) for t in texts)
    present = sum(len(re.findall(r"\b(shows|measures|computes|evaluates|demonstrates|presents|proposes)\b", t, re.I)) for t in texts)
    return "past" if past > present else "present"


def build_style_card(venue: str, year: int, papers: list[dict]) -> dict:
    """Extract writing patterns from a list of papers and build a Style Card."""
    abstracts = [p["abstract"] for p in papers]
    all_text = " ".join(abstracts)

    voice = analyze_voice(all_text)
    avg_sent_len = round(avg_sentence_length(all_text), 1)
    openers = extract_intro_openers(abstracts)
    citation_density = estimate_citation_density(abstracts)
    tense = dominant_tense(abstracts)

    # Extract common transition words used
    transitions = []
    transition_candidates = ["however", "moreover", "furthermore", "therefore", "thus",
                              "consequently", "in addition", "additionally", "in contrast",
                              "nevertheless", "on the other hand", "as a result"]
    for t in transition_candidates:
        count = sum(all_text.lower().count(t) for _ in [1])
        if count > 0:
            transitions.append(t)

    return {
        "venue": venue,
        "year": year,
        "papers_analyzed": len(papers),
        "voice": voice,
        "tense": tense,
        "avg_sentence_length_words": avg_sent_len,
        "citation_density_per_paragraph": round(citation_density, 1),
        "intro_openers": openers[:3],
        "transitions_used": transitions[:5],
        "paper_titles": [p["title"] for p in papers],
        "sources": list(set(p["source"] for p in papers)),
    }


def format_style_card_md(card: dict, paper_id: str) -> str:
    """Format Style Card as markdown for Engram and file output."""
    openers_block = "\n".join(f'  - "{o}"' for o in card["intro_openers"]) or "  - (none extracted)"
    transitions_block = ", ".join(card["transitions_used"]) or "(none found — avoid common AI transitions)"
    titles_block = "\n".join(f"  - {t}" for t in card["paper_titles"])

    return f"""# Style Card — {card['venue']} {card['year']}
paper_id: {paper_id}
generated: {__import__('datetime').date.today()}

## Writing Patterns (extracted from {card['papers_analyzed']} real papers)

| Pattern | Value |
|---------|-------|
| Voice | {card['voice']} |
| Tense | {card['tense']} |
| Avg sentence length | {card['avg_sentence_length_words']} words |
| Citation density | {card['citation_density_per_paragraph']} refs/paragraph |
| Data source | {", ".join(card['sources'])} |

## Intro Openers (copy this rhythm, not these words)
{openers_block}

## Transitions found in venue papers
{transitions_block}

## Papers analyzed
{titles_block}

## Instructions for narrators
- Match the voice: **{card['voice']}**
- Match the tense: **{card['tense']}**
- Keep sentences ≤ {int(card['avg_sentence_length_words']) + 3} words on average
- Cite ~{card['citation_density_per_paragraph']} sources per paragraph
- Study the intro openers above — match the rhythm and specificity, not the wording
- Avoid transitions NOT found in the venue list above
- Every claim needs a number from data/processed/ — no vague adjectives
"""


# ── Engram save ───────────────────────────────────────────────────────────────

def save_to_engram(paper_id: str, venue: str, card: dict, dry_run: bool = False):
    """Save Style Card to Engram via CLI."""
    title = f"style: {paper_id} — venue={venue}, voice={card['voice']}, tense={card['tense']}, avg_sent={card['avg_sentence_length_words']}w, citation_density={card['citation_density_per_paragraph']}/para"
    content = (
        f"Venue: {venue} {card['year']}. "
        f"Papers analyzed: {card['papers_analyzed']}. "
        f"Voice: {card['voice']}. Tense: {card['tense']}. "
        f"Avg sentence: {card['avg_sentence_length_words']} words. "
        f"Citation density: {card['citation_density_per_paragraph']}/paragraph. "
        f"Transitions: {', '.join(card['transitions_used'][:3]) or 'none common'}. "
        f"Sources: {', '.join(card['sources'])}."
    )

    if dry_run:
        print(f"\n[dry-run] Would save to Engram:")
        print(f"  title: {title}")
        print(f"  content: {content}")
        return True

    try:
        result = subprocess.run(
            ["engram", "save", title, content, "--type", "decision", "--project", "belico-stack"],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            print(f"  [engram] saved: style card for {paper_id}")
            return True
        else:
            print(f"  [engram] error: {result.stderr.strip()}")
            return False
    except FileNotFoundError:
        print("  [engram] CLI not found — skipping Engram save (MCP tools will work)")
        return False
    except Exception as ex:
        print(f"  [engram] unexpected error: {ex}")
        return False


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Style Calibration — fetch real papers from target venue and build Style Card"
    )
    parser.add_argument("--venue", default="EWSHM", help="Target journal or conference name")
    parser.add_argument("--year", type=int, default=2024, help="Target year (searches ±1 year)")
    parser.add_argument("--n", type=int, default=5, help="Number of papers to analyze (3-10)")
    parser.add_argument("--paper-id", default="active_paper", help="Paper ID for Engram key")
    parser.add_argument("--save-md", action="store_true", help="Save Style Card as .md file")
    parser.add_argument("--dry-run", action="store_true", help="Analyze only, don't save to Engram")
    parser.add_argument("--no-fallback", action="store_true", help="Don't fall back to OpenAlex")
    args = parser.parse_args()

    load_env()
    ss_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "")
    oa_key = os.environ.get("OPENALEX_API_KEY", "")

    print(f"\n=== STYLE CALIBRATION ===")
    print(f"Venue: {args.venue} ({args.year})")
    print(f"Target papers: {args.n}")
    print(f"Semantic Scholar key: {'present' if ss_key else 'not set (rate limits apply)'}")
    print(f"OpenAlex key: {'present' if oa_key else 'not set'}")
    print()

    # 1. Fetch papers — Semantic Scholar first, OpenAlex fallback
    papers = fetch_papers_semantic_scholar(args.venue, args.year, args.n, ss_key or None)

    if len(papers) < 2 and not args.no_fallback:
        print("  [fallback] insufficient results from Semantic Scholar — trying OpenAlex...")
        time.sleep(2)
        papers = fetch_papers_openalex(args.venue, args.year, args.n, oa_key or None)

    if not papers:
        print("\n[ERROR] No papers found. Suggestions:")
        print("  - Try a broader venue name: 'structural health monitoring'")
        print("  - Set SEMANTIC_SCHOLAR_API_KEY in .env for higher rate limits")
        print("  - Try --year with a different year")
        sys.exit(1)

    print(f"\nAnalyzing {len(papers)} papers...")

    # 2. Build Style Card
    card = build_style_card(args.venue, args.year, papers)
    md = format_style_card_md(card, args.paper_id)

    # 3. Print Style Card
    print("\n" + "=" * 60)
    print(md)
    print("=" * 60)

    # 4. Save to Engram
    engram_ok = save_to_engram(args.paper_id, args.venue, card, dry_run=args.dry_run)

    # 5. Save .md file (optional or if explicitly requested)
    if args.save_md or args.dry_run:
        STYLE_CARD_DIR.mkdir(parents=True, exist_ok=True)
        out_path = STYLE_CARD_DIR / f"style_card_{args.paper_id}.md"
        out_path.write_text(md)
        print(f"\n[saved] {out_path}")

    # 6. Summary
    print(f"\n--- STYLE CALIBRATION COMPLETE ---")
    print(f"Papers analyzed: {card['papers_analyzed']} ({', '.join(card['sources'])})")
    print(f"Voice:           {card['voice']}")
    print(f"Tense:           {card['tense']}")
    print(f"Avg sent len:    {card['avg_sentence_length_words']} words")
    print(f"Citation density:{card['citation_density_per_paragraph']}/paragraph")
    print(f"Engram:          {'saved' if engram_ok else 'skipped'}")
    print(f"\nNarrators: read style_card_{args.paper_id}.md or search Engram 'style: {args.paper_id}' before writing.")
    print()


if __name__ == "__main__":
    main()
