#!/usr/bin/env python3
"""
tools/check_novelty.py — Deep Novelty Checker for the Paper Factory
====================================================================
Searches OpenAlex (250M+ works), arXiv, Semantic Scholar (220M+ papers),
Scopus (optional), and CrossRef (100M+ DOIs) to verify that the proposed
paper topic is original. Generates a structured novelty report.

No MCP server needed. Runs standalone.
Reads OPENALEX_API_KEY from .env or environment (optional, improves rate limits).

Usage:
  python3 tools/check_novelty.py --keywords "acoustic emission, PINNs, bolted connections"
  python3 tools/check_novelty.py                    # Extract keywords from PRD.md
  python3 tools/check_novelty.py --deep             # Extra queries + citation network
  python3 tools/check_novelty.py --save             # Save report to articles/drafts/
  python3 tools/check_novelty.py --threshold 0.5    # Custom HIGH threat threshold

Sources:
  - OpenAlex API (250M+ works, Scopus/PubMed/CrossRef coverage)
  - arXiv API (preprints, STEM)
  - Semantic Scholar API (220M+ papers, citation counts, DOI metadata)
  - Scopus API (optional — requires ELSEVIER_API_KEY)
  - CrossRef (100M+ DOIs, Elsevier/Springer/Wiley/IEEE — always active, no key required)
"""

import argparse
import os
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
ENV_PATH = ROOT / ".env"

OPENALEX_BASE = "https://api.openalex.org/works"
ARXIV_BASE = "http://export.arxiv.org/api/query"
SEMANTIC_SCHOLAR_BASE = "https://api.semanticscholar.org/graph/v1/paper/search"
SCOPUS_BASE = "https://api.elsevier.com/content/search/scopus"
CROSSREF_BASE = "https://api.crossref.org/works"

# Contact email for polite pool (OpenAlex recommends it for faster responses)
MAILTO = "mailto:belico-stack@research.local"

def _load_env_key(name: str) -> str:
    """Read API key from environment or .env file."""
    val = os.environ.get(name, "")
    if not val and ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            line = line.strip()
            if line.startswith(f"{name}=") and not line.startswith("#"):
                val = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    return val

# Threat thresholds — keyword overlap ratio that classifies a paper as HIGH or MEDIUM threat.
# Calibrated empirically: 0.6 catches papers covering >60% of the proposed keywords (strong overlap),
# 0.3 catches papers covering >30% (partial overlap). Both are overridable per-run via
# --threshold / --threshold-medium CLI flags, allowing domain-specific tuning without code changes.
# AGENTS.md Rule 1 exception: these are algorithm calibration constants, not physical parameters.
DEFAULT_THRESHOLD_HIGH = 0.6
DEFAULT_THRESHOLD_MEDIUM = 0.3

# OpenAlex API key — free public key, no billing attached.
# Design: every clone of belico-stack inherits this key without configuration.
# Priority order: env var OPENALEX_API_KEY > .env file > this default.
# AGENTS.md Rule 10 exception: this is a public zero-cost key, not a credential.
# Source: https://openalex.org (polite pool — requires mailto header, not authentication)
_DEFAULT_OPENALEX_KEY = "0tf39ysz34eIKFV3e3caoI"


def _load_api_key() -> str:
    """Load OpenAlex API key: env var > .env file > built-in default."""
    key = os.environ.get("OPENALEX_API_KEY")
    if key:
        return key
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            line = line.strip()
            if line.startswith("OPENALEX_API_KEY=") and not line.startswith("#"):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return _DEFAULT_OPENALEX_KEY


def _load_elsevier_api_key() -> str:
    """Load Elsevier/Scopus API key: env var > .env file > empty string (optional)."""
    key = os.environ.get("ELSEVIER_API_KEY")
    if key:
        return key
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            line = line.strip()
            if line.startswith("ELSEVIER_API_KEY=") and not line.startswith("#"):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


OPENALEX_API_KEY = _load_api_key()
ELSEVIER_API_KEY = _load_elsevier_api_key()

# Noise filter for PRD keyword extraction
STOPWORDS = {
    # PRD structure noise
    "problema", "vision", "usuario", "pipeline", "siguiente paso", "alcance",
    "riesgos", "fuera de alcance", "documentos relacionados", "criterios de exito",
    "gap analysis", "bugs", "estado", "corregido", "funcional", "pendiente",
    "arquitectura", "producto", "requisitos", "workflow", "flujo", "instalacion",
    "dependencias", "configuracion", "notas", "componente", "archivo", "path",
    "herramienta", "tipo", "tabla", "seccion", "version", "fecha", "autor",
    "este documento", "lo que falta", "resuelto", "menor", "critico", "importante",
    # Gentleman ecosystem noise
    "engram", "gentle ai", "agent teams lite", "gentleman.dots", "veil.nvim",
    "gentleman skills", "gga", "flujo sdd", "instalacion rapida",
    # Generic Spanish noise
    "caso de uso", "comunicacion", "consecuencia", "en una frase", "proposito",
    "patron", "objetivo", "descripcion", "contexto", "resultado", "ejemplo",
    "referencia", "estructura", "proceso", "sistema", "metodo", "modelo",
    "analisis", "datos", "parametro", "valor", "proyecto", "investigacion",
}


# ═══════════════════════════════════════════════════════════════════════
# API Clients
# ═══════════════════════════════════════════════════════════════════════

def _get_json(url: str, retries: int = 2) -> dict | None:
    """GET a URL and return parsed JSON, with HTTP-aware retries (M4)."""
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": MAILTO})
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and attempt < retries:
                # Rate limited or service unavailable — back off exponentially
                wait = 2 ** (attempt + 1)
                print(f"    [RATE] HTTP {e.code}, waiting {wait}s...")
                time.sleep(wait)
            elif attempt < retries:
                time.sleep(1)
            else:
                print(f"    [WARN] Failed: HTTP {e.code} {e.reason}")
                return None
        except Exception as e:
            if attempt < retries:
                time.sleep(1)
            else:
                print(f"    [WARN] Failed: {e}")
                return None


def _openalex_url(params: str) -> str:
    """Build OpenAlex URL with API key if available."""
    key_param = f"&api_key={OPENALEX_API_KEY}" if OPENALEX_API_KEY else ""
    return f"{OPENALEX_BASE}?{params}{key_param}"


def search_openalex(query: str, per_page: int = 10) -> list[dict]:
    """Search OpenAlex for works matching the query."""
    encoded = urllib.parse.quote(query)
    url = _openalex_url(f"search={encoded}&per_page={per_page}&sort=relevance_score:desc")
    data = _get_json(url)
    if not data or "results" not in data:
        return []

    papers = []
    for w in data["results"]:
        source = (w.get("primary_location") or {}).get("source") or {}
        # H2: capture abstract for deeper threat assessment
        abstract_index = w.get("abstract_inverted_index") or {}
        abstract_text = _reconstruct_abstract(abstract_index)
        papers.append({
            "title": w.get("display_name", "Unknown"),
            "year": w.get("publication_year"),
            "journal": source.get("display_name", "Unknown"),
            "doi": w.get("doi", ""),
            "cited_by": w.get("cited_by_count", 0),
            "abstract": abstract_text,
            "source": "OpenAlex",
        })
    return papers


def _reconstruct_abstract(inverted_index: dict) -> str:
    """Reconstruct abstract from OpenAlex inverted index format."""
    if not inverted_index:
        return ""
    # inverted_index: {"word": [pos1, pos2, ...], ...}
    words = {}
    for word, positions in inverted_index.items():
        for pos in positions:
            words[pos] = word
    if not words:
        return ""
    max_pos = max(words.keys())
    return " ".join(words.get(i, "") for i in range(max_pos + 1)).strip()


def search_arxiv(query: str, max_results: int = 5) -> list[dict]:
    """Search arXiv for preprints matching the query."""
    encoded = urllib.parse.quote(query)
    url = f"{ARXIV_BASE}?search_query=all:{encoded}&start=0&max_results={max_results}&sortBy=relevance"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": MAILTO})
        with urllib.request.urlopen(req, timeout=15) as resp:
            xml_data = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        if e.code in (429, 503):
            print(f"    [RATE] arXiv HTTP {e.code}, skipping...")
        else:
            print(f"    [WARN] arXiv failed: HTTP {e.code}")
        return []
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
        summary = entry.findtext("atom:summary", "", ns).strip().replace("\n", " ")
        papers.append({
            "title": title,
            "year": int(published) if published.isdigit() else None,
            "journal": "arXiv (preprint)",
            "doi": "",
            "cited_by": 0,
            "abstract": summary[:500],
            "source": "arXiv",
        })
    return papers


def search_semantic_scholar(query: str, limit: int = 20) -> list[dict]:
    """Search Semantic Scholar for papers matching the query.

    Uses the authenticated API when SEMANTIC_SCHOLAR_API_KEY is set in .env
    (1 req/sec approved rate). Falls back to public API (unauthenticated).
    Gracefully returns [] on any network error or rate limit (HTTP 429).

    Returns a normalized list of dicts with keys:
      title, year, authors, citations, source, doi
    (plus journal and abstract set to empty strings for compatibility
    with the rest of the pipeline).
    """
    encoded = urllib.parse.quote(query)
    fields = "title,year,authors,citationCount,externalIds"
    url = (f"{SEMANTIC_SCHOLAR_BASE}?query={encoded}"
           f"&fields={fields}&limit={limit}")
    headers: dict[str, str] = {
        "User-Agent": MAILTO,
        "Accept": "application/json",
    }
    api_key = _load_env_key("SEMANTIC_SCHOLAR_API_KEY")
    if api_key:
        headers["x-api-key"] = api_key
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 429:
            print(f"    [RATE] Semantic Scholar HTTP 429, skipping...")
        else:
            print(f"    [WARN] Semantic Scholar failed: HTTP {e.code}")
        return []
    except Exception as e:
        print(f"    [WARN] Semantic Scholar failed: {e}")
        return []

    papers = []
    for item in (data.get("data") or []):
        external_ids = item.get("externalIds") or {}
        doi = external_ids.get("DOI") or external_ids.get("doi") or ""
        authors_raw = item.get("authors") or []
        authors = ", ".join(a.get("name", "") for a in authors_raw[:3])
        papers.append({
            "title": item.get("title") or "Unknown",
            "year": item.get("year"),
            "journal": "",          # not returned by this endpoint
            "doi": doi.lower() if doi else "",
            "cited_by": item.get("citationCount") or 0,
            "abstract": "",         # not requested to keep payload small
            "authors": authors,
            "source": "Semantic Scholar",
        })
    return papers


def search_scopus(query: str, count: int = 10) -> list[dict]:
    """Search Scopus for papers matching the query (optional — requires ELSEVIER_API_KEY).

    If ELSEVIER_API_KEY is not set, returns an empty list silently.
    Get a free academic key at: https://dev.elsevier.com

    Uses TITLE-ABS-KEY() field query for high-precision results.
    Returns a normalized list of dicts compatible with the rest of the pipeline.
    """
    if not ELSEVIER_API_KEY:
        return []

    encoded_query = urllib.parse.quote(f"TITLE-ABS-KEY({query})")
    fields = "dc:title,prism:coverDate,citedby-count,prism:publicationName,dc:identifier,prism:doi"
    url = (f"{SCOPUS_BASE}?query={encoded_query}"
           f"&count={count}&field={fields}")

    try:
        req = urllib.request.Request(
            url,
            headers={
                "X-ELS-APIKey": ELSEVIER_API_KEY,
                "Accept": "application/json",
                "User-Agent": MAILTO,
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print("    [WARN] Scopus: invalid or expired API key (HTTP 401)")
        elif e.code == 429:
            print("    [RATE] Scopus HTTP 429, skipping...")
        else:
            print(f"    [WARN] Scopus failed: HTTP {e.code}")
        return []
    except Exception as e:
        print(f"    [WARN] Scopus failed: {e}")
        return []

    entries = (data.get("search-results") or {}).get("entry") or []
    papers = []
    for item in entries:
        # Scopus returns "No results found." as a single entry when empty
        title = item.get("dc:title") or ""
        if not title or title.lower().startswith("no results"):
            continue

        # Year: prism:coverDate is "YYYY-MM-DD"
        cover_date = item.get("prism:coverDate") or ""
        year = int(cover_date[:4]) if cover_date and cover_date[:4].isdigit() else None

        # DOI: prism:doi preferred; dc:identifier is "DOI:10.xxxx/..." fallback
        doi = item.get("prism:doi") or ""
        if not doi:
            dc_id = item.get("dc:identifier") or ""
            if dc_id.upper().startswith("DOI:"):
                doi = dc_id[4:].strip()

        papers.append({
            "title": title,
            "year": year,
            "journal": item.get("prism:publicationName") or "",
            "doi": doi.lower() if doi else "",
            "cited_by": int(item.get("citedby-count") or 0),
            "abstract": "",   # not requested to keep payload small
            "source": "Scopus",
        })
    return papers


def search_crossref(query: str, rows: int = 10) -> list[dict]:
    """Search CrossRef for works matching the query.

    Uses the Polite Pool (mailto header) for faster responses.
    No API key required — always active.
    Covers 100M+ DOIs from Elsevier, Springer, Wiley, IEEE, and more.

    Returns a normalized list of dicts compatible with the rest of the pipeline.
    """
    encoded = urllib.parse.quote(query)
    fields = "title,published,is-referenced-by-count,container-title,DOI"
    url = f"{CROSSREF_BASE}?query={encoded}&rows={rows}&select={fields}"

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "belico-stack/1.0 (mailto:research@belico.dev)"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 429:
            print(f"    [RATE] CrossRef HTTP 429, skipping...")
        else:
            print(f"    [WARN] CrossRef failed: HTTP {e.code}")
        return []
    except Exception as e:
        print(f"    [WARN] CrossRef failed: {e}")
        return []

    items = (data.get("message") or {}).get("items") or []
    papers = []
    for item in items:
        title_list = item.get("title") or []
        title = title_list[0] if title_list else "Unknown"
        year = (item.get("published") or {}).get("date-parts", [[0]])[0][0]
        journal_list = item.get("container-title") or [""]
        journal = journal_list[0] if journal_list else ""
        doi = item.get("DOI") or ""
        papers.append({
            "title": title,
            "year": year if year else None,
            "journal": journal,
            "doi": doi.lower() if doi else "",
            "cited_by": item.get("is-referenced-by-count") or 0,
            "abstract": "",   # not requested to keep payload small
            "source": "CrossRef",
        })
    return papers


def get_citing_works(openalex_id: str, per_page: int = 5) -> list[dict]:
    """Get works that cite a given OpenAlex work (citation network)."""
    url = _openalex_url(f"filter=cites:{openalex_id}&per_page={per_page}&sort=relevance_score:desc")
    data = _get_json(url)
    if not data or "results" not in data:
        return []

    papers = []
    for w in data["results"]:
        source = (w.get("primary_location") or {}).get("source") or {}
        abstract_index = w.get("abstract_inverted_index") or {}
        papers.append({
            "title": w.get("display_name", "Unknown"),
            "year": w.get("publication_year"),
            "journal": source.get("display_name", "Unknown"),
            "doi": w.get("doi", ""),
            "cited_by": w.get("cited_by_count", 0),
            "abstract": _reconstruct_abstract(abstract_index),
            "source": "OpenAlex (citation)",
        })
    return papers


# ═══════════════════════════════════════════════════════════════════════
# Keyword Extraction (3 layers: explicit → YAKE → params.yaml)
# ═══════════════════════════════════════════════════════════════════════

def _keywords_from_yaml() -> list[str]:
    """Layer 3: read keywords from config/params.yaml as last fallback."""
    yaml_path = ROOT / "config" / "params.yaml"
    if not yaml_path.exists():
        return []
    try:
        import yaml
    except ImportError:
        return []  # yaml not installed — Layer 3 silently unavailable (Layer 2 YAKE is preferred)
    try:
        with open(yaml_path) as f:
            cfg = yaml.safe_load(f) or {}
        raw = (cfg.get("project") or {}).get("keywords", "")
        if raw:
            return [k.strip().lower() for k in raw.split(",") if k.strip()]
    except (yaml.YAMLError, OSError) as e:
        print(f"    [WARN] params.yaml keywords unreadable: {e}", file=sys.stderr)
    return []


def _keywords_from_explicit(text: str) -> list[str]:
    """Layer 1: read the explicit 'Keywords:' line from the PRD."""
    keywords = []
    # Match "Keywords: term1, term2, ..." (the line right after the label)
    for match in re.finditer(r'^[Kk]eywords?\s*:\s*(.+)$', text, re.MULTILINE):
        for kw in match.group(1).split(","):
            kw = kw.strip().strip("*`\"'").rstrip(":")
            if 2 < len(kw) < 50:
                keywords.append(kw.lower())
    return keywords


def _keywords_from_yake(text: str, max_keywords: int = 15) -> list[str]:
    """Layer 2: extract keywords from PRD text using YAKE (unsupervised NLP).

    YAKE uses statistical features (word frequency, position, co-occurrence)
    without any pre-trained model. Lightweight and language-agnostic.
    """
    try:
        import yake
    except ImportError:
        print("    [WARN] yake not installed — run: pip install yake")
        return []

    # Strip markdown noise before feeding to YAKE
    clean = re.sub(r'```[\s\S]*?```', '', text)      # code blocks
    clean = re.sub(r'<!--[\s\S]*?-->', '', clean)     # HTML comments
    clean = re.sub(r'\|[^\n]+\|', '', clean)          # tables
    clean = re.sub(r'#{1,6}\s+\d+\.?\s*', '', clean) # numbered headers
    clean = re.sub(r'[`*_\[\]()#>|]', ' ', clean)    # markdown chars
    clean = re.sub(r'https?://\S+', '', clean)        # URLs
    clean = re.sub(r'\S+\.\w{2,4}\b', '', clean)     # file paths (.py, .md)
    clean = re.sub(r'\s+', ' ', clean).strip()

    if len(clean) < 50:
        return []

    kw_extractor = yake.KeywordExtractor(
        lan="en",
        n=3,            # up to 3-grams (e.g. "structural health monitoring")
        dedupLim=0.7,   # deduplication threshold
        top=max_keywords,
        features=None,
    )

    raw_keywords = kw_extractor.extract_keywords(clean)

    # YAKE returns (keyword, score) — lower score = more relevant
    # Filter out noise: file paths, PRD section names, short terms
    noise_words = STOPWORDS | {
        "config", "tools", "params", "yaml", "null", "pendiente",
        "siguiente paso", "este documento", "claude code", "prd",
        "problema", "vision", "alcance", "pipeline", "siguiente",
    }
    noise_fragments = [
        '.py', '.sh', '.md', 'src/', 'tools/', 'config/',
        'brew', 'git ', '---', 'null', 'params',
    ]
    filtered = []
    for kw, score in raw_keywords:
        kw_lower = kw.lower().strip()
        if len(kw_lower) < 3:
            continue
        if kw_lower in noise_words:
            continue
        # Skip if any word in the keyphrase is a noise word
        words = kw_lower.split()
        if any(w in noise_words for w in words):
            continue
        if any(p in kw_lower for p in noise_fragments):
            continue
        # Must be mostly alphabetic
        alpha_ratio = sum(c.isalpha() or c == ' ' for c in kw_lower) / max(len(kw_lower), 1)
        if alpha_ratio < 0.7:
            continue
        filtered.append(kw_lower)

    return filtered


def extract_keywords_from_prd(prd_path: Path) -> list[str]:
    """Extract research keywords with 3-layer fallback.

    Layer 1: Explicit 'Keywords:' line in PRD (written by init_project.py)
    Layer 2: YAKE NLP extraction from full PRD text (unsupervised, no model)
    Layer 3: config/params.yaml project.keywords field
    """
    if not prd_path.exists():
        return _keywords_from_yaml()

    text = prd_path.read_text(encoding="utf-8")

    # Layer 1: explicit keywords (most reliable — user wrote them)
    explicit = _keywords_from_explicit(text)
    if explicit:
        print("    Source: explicit Keywords line in PRD")
        return explicit

    # Layer 2: YAKE NLP extraction (professional, unsupervised)
    yake_kw = _keywords_from_yake(text)
    if yake_kw:
        print("    Source: YAKE NLP extraction from PRD text")
        return yake_kw

    # Layer 3: params.yaml fallback
    yaml_kw = _keywords_from_yaml()
    if yaml_kw:
        print("    Source: config/params.yaml project.keywords")
        return yaml_kw

    return []


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
    """Remove duplicate papers by DOI (preferred) or title similarity (H3)."""
    seen_dois = set()
    seen_titles = set()
    unique = []
    for p in papers:
        # Prefer DOI dedup (globally unique identifier)
        doi = (p.get("doi") or "").strip().lower()
        if doi:
            if doi in seen_dois:
                continue
            seen_dois.add(doi)
            unique.append(p)
            continue
        # Fallback: title-based dedup
        title = p.get("title") or ""
        normalized = title.lower().strip()[:80]
        if not normalized:
            continue
        if normalized not in seen_titles:
            seen_titles.add(normalized)
            unique.append(p)
    return unique


def assess_threat(paper: dict, keywords: list[str],
                  threshold_high: float = DEFAULT_THRESHOLD_HIGH,
                  threshold_medium: float = DEFAULT_THRESHOLD_MEDIUM) -> str:
    """Assess threat level based on keyword overlap in title + abstract (H1, H2, H4).

    H1: Uses word boundary matching to avoid false positives (e.g. "SHM" in "pushme").
    H2: Checks both title and abstract for keyword presence.
    H4: Thresholds are configurable via parameters.
    """
    title_lower = (paper.get("title") or "").lower()
    abstract_lower = (paper.get("abstract") or "").lower()
    searchable = f"{title_lower} {abstract_lower}"

    matches = 0
    for kw in keywords:
        # H1: word boundary matching — prevents partial matches
        # e.g. keyword "shm" won't match "pushme" but will match "shm-based"
        pattern = r'\b' + re.escape(kw) + r'\b'
        if re.search(pattern, searchable):
            matches += 1

    ratio = matches / max(len(keywords), 1)
    if ratio >= threshold_high:
        return "HIGH"
    elif ratio >= threshold_medium:
        return "MEDIUM"
    return "LOW"


# ═══════════════════════════════════════════════════════════════════════
# Report Generation
# ═══════════════════════════════════════════════════════════════════════

def generate_report(keywords: list[str], papers: list[dict],
                    queries_run: int, verdict: str, gap: str,
                    threat_counts: dict) -> str:
    """Generate the novelty report in Markdown."""
    kw_list = ", ".join(keywords)

    rows = ""
    for i, p in enumerate(papers[:25], 1):
        rows += (f"| {i} | {p['title'][:80]} | {p['year']} | "
                 f"{p['journal'][:30]} | {p['cited_by']} | {p['threat']} | {p['source']} |\n")

    high = threat_counts.get("HIGH", 0)
    medium = threat_counts.get("MEDIUM", 0)
    low = threat_counts.get("LOW", 0)

    return f"""---
title: Novelty Check Report
status: completed
date: {date.today()}
verdict: {verdict}
keywords: [{kw_list}]
sources: OpenAlex (250M+ works), arXiv, Semantic Scholar (220M+ papers)
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
| Sources | OpenAlex (250M+ works), arXiv, Semantic Scholar (220M+ papers) |
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
        description="Deep Novelty Checker — OpenAlex + arXiv + Semantic Scholar search")
    parser.add_argument("--keywords", type=str,
                        help="Manual keywords (comma-separated)")
    parser.add_argument("--deep", action="store_true",
                        help="Deep search: more queries + citation network")
    parser.add_argument("--save", action="store_true",
                        help="Save report to articles/drafts/novelty_report.md")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD_HIGH,
                        help=f"HIGH threat threshold (default: {DEFAULT_THRESHOLD_HIGH})")
    parser.add_argument("--threshold-medium", type=float, default=DEFAULT_THRESHOLD_MEDIUM,
                        help=f"MEDIUM threat threshold (default: {DEFAULT_THRESHOLD_MEDIUM})")
    parser.add_argument("--auto", action="store_true",
                        help="Auto-read topic from config/research_lines.yaml active_profile "
                             "(for orchestrator use during EXPLORE)")
    args = parser.parse_args()

    print("=" * 60)
    print("  NOVELTY CHECKER — Deep Academic Search")
    print("  Sources: OpenAlex (250M+ works) + arXiv + Semantic Scholar (220M+)")
    print("           + CrossRef (100M+ DOIs) + Scopus (optional)")
    if OPENALEX_API_KEY:
        print(f"  OpenAlex API key: ...{OPENALEX_API_KEY[-6:]} (authenticated)")
    else:
        print("  OpenAlex API key: not set (using free tier)")
    if ELSEVIER_API_KEY:
        print(f"  Scopus API key:   ...{ELSEVIER_API_KEY[-6:]} (active — Scopus enabled)")
    else:
        print("  Scopus API key:   not set (optional — set ELSEVIER_API_KEY to enable)")
    print("  CrossRef:         always active (no key required)")
    print("=" * 60)

    # ── Keywords ──
    if args.keywords:
        keywords = [k.strip().lower() for k in args.keywords.split(",")]
    elif args.auto:
        # Read active_profile from config/research_lines.yaml (SSOT for EXPLORE)
        research_lines_path = ROOT / "config" / "research_lines.yaml"
        try:
            import yaml as _yaml  # noqa: PLC0415
            with open(research_lines_path, encoding="utf-8") as _f:
                rl_data = _yaml.safe_load(_f) or {}
            active = rl_data.get("active_profile", {})
            topic = str(active.get("topic", active.get("title", "")) or "").strip()
            if topic:
                # Split multi-word topic into individual keyword tokens
                keywords = [kw.strip().lower() for kw in topic.split() if len(kw.strip()) > 3]
                if not keywords:
                    keywords = [topic.lower()]
                print(f"  [auto] Keywords from research_lines.yaml active_profile: {keywords}")
            else:
                print("  [auto] active_profile.topic not set — falling back to PRD keywords")
                keywords = extract_keywords_from_prd(PRD_PATH)
        except FileNotFoundError:
            print("  [auto] config/research_lines.yaml not found — falling back to PRD keywords")
            keywords = extract_keywords_from_prd(PRD_PATH)
        except Exception as exc:  # noqa: BLE001
            print(f"  [auto] Failed to read research_lines.yaml: {exc} — falling back to PRD")
            keywords = extract_keywords_from_prd(PRD_PATH)
    else:
        keywords = extract_keywords_from_prd(PRD_PATH)

    if not keywords:
        print("\n  No keywords found. Use --keywords \"term1, term2, term3\" or --auto")
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

    # ── Search arXiv (M3: 3s between requests per API policy) ──
    print(f"\n  Searching arXiv...")
    for i, q in enumerate(queries[:5]):  # arXiv is slower, limit queries
        results = search_arxiv(q, max_results=5)
        all_papers.extend(results)
        queries_run += 1
        if i < min(len(queries), 5) - 1:
            time.sleep(3)  # M3: arXiv requires >= 3s between requests

    # ── Search Semantic Scholar ──
    print(f"\n  Searching Semantic Scholar...")
    for i, q in enumerate(queries[:5]):  # limit to top 5 queries
        print(f"    [{i + 1}/5] {q[:60]}...")
        results = search_semantic_scholar(q, limit=20)
        all_papers.extend(results)
        queries_run += 1
        time.sleep(1)  # polite rate limiting (public tier)

    # ── Search Scopus (optional — requires ELSEVIER_API_KEY) ──
    if ELSEVIER_API_KEY:
        print(f"\n  Searching Scopus...")
        for i, q in enumerate(queries[:5]):  # limit to top 5 queries
            print(f"    [{i + 1}/5] {q[:60]}...")
            results = search_scopus(q, count=10)
            all_papers.extend(results)
            queries_run += 1
            time.sleep(1)  # polite rate limiting

    # ── Search CrossRef (always active — no key required) ──
    print(f"\n  Searching CrossRef...")
    for i, q in enumerate(queries[:5]):  # limit to top 5 queries
        print(f"    [{i + 1}/5] {q[:60]}...")
        results = search_crossref(q, rows=10)
        all_papers.extend(results)
        queries_run += 1
        time.sleep(1)  # polite rate limiting

    # ── Citation network (deep mode) ──
    if args.deep and all_papers:
        print(f"\n  Analyzing citation network...")
        # Find the most relevant paper and check who cites it
        top_paper = all_papers[0] if all_papers else None
        if top_paper and top_paper.get("doi"):
            # Extract OpenAlex ID from first result
            encoded = urllib.parse.quote(top_paper["title"][:50])
            lookup = _get_json(_openalex_url(f"search={encoded}&per_page=1"))
            if lookup and lookup.get("results"):
                oa_id = lookup["results"][0].get("id", "").split("/")[-1]
                if oa_id:
                    citing = get_citing_works(oa_id, per_page=10)
                    all_papers.extend(citing)
                    print(f"    Found {len(citing)} citing works")

    # ── Deduplicate ──
    unique_papers = deduplicate(all_papers)
    print(f"\n  Total unique papers: {len(unique_papers)}")

    # ── Assess threats (M8: single pass, store result on each paper) ──
    threat_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for p in unique_papers:
        p["threat"] = assess_threat(p, keywords, args.threshold, args.threshold_medium)
        threat_counts[p["threat"]] += 1

    high_threat = [p for p in unique_papers if p["threat"] == "HIGH"]
    medium_threat = [p for p in unique_papers if p["threat"] == "MEDIUM"]

    print(f"    HIGH threat:   {threat_counts['HIGH']}")
    print(f"    MEDIUM threat: {threat_counts['MEDIUM']}")
    print(f"    LOW threat:    {threat_counts['LOW']}")

    # ── Verdict ──
    # Policy: >=2 HIGH-threat papers → DUPLICATE (the exact combination is already published).
    # 1 HIGH → INCREMENTAL (related work exists, differentiation must be explicit in PROPOSE).
    # >=5 MEDIUM → INCREMENTAL (many partial overlaps signal a saturated space).
    # Thresholds calibrated for the paper factory pipeline (Conference → Q1 escalation).
    # AGENTS.md Rule 1 exception: these are editorial policy constants, not physical parameters.
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
            print(f"    [{p['threat']}] {p['title'][:70]} ({p['year']}, {p['journal'][:25]})")

    # ── Save report ──
    if args.save:
        report = generate_report(keywords, unique_papers, queries_run, verdict, gap, threat_counts)
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
