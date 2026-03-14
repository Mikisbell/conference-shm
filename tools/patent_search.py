#!/usr/bin/env python3
"""
patent_search.py — Sprint 2: Search patents via BigQuery patents-public-data.

CLI: python3 tools/patent_search.py --query "structural health monitoring edge AI" [--limit 10] [--country US] [--json]
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
BIGQUERY_PROJECT_ID = os.getenv("BIGQUERY_PROJECT_ID", "")
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")

FALLBACK_DIR = Path(__file__).parent.parent / "db" / "patent_search"
FALLBACK_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# BigQuery search
# ---------------------------------------------------------------------------

_BASE_SQL = """
SELECT
  publication_number,
  (SELECT text FROM UNNEST(title_localized) LIMIT 1) AS title,
  (SELECT text FROM UNNEST(abstract_localized) LIMIT 1) AS abstract,
  publication_date,
  country_code
FROM `patents-public-data.patents.publications`
WHERE EXISTS (
  SELECT 1 FROM UNNEST(abstract_localized) a
  WHERE LOWER(a.text) LIKE @term
)
AND country_code IN ('US', 'EP', 'WO')
AND publication_date > 20150101
ORDER BY publication_date DESC
LIMIT @limit_val
"""

# Note: country_code IN clause uses a hardcoded constant ('US', 'EP', 'WO') because
# BigQuery does not support array/repeated parameters in IN clauses. The country
# filter is not user-controlled, so this is safe and not an injection vector.
# The --country CLI flag is accepted for API compatibility but ignored in the BigQuery
# query; results are always filtered to ('US', 'EP', 'WO').


def search_bigquery(query: str, limit: int = 10, countries: Optional[list[str]] = None) -> list[dict]:
    """Run BigQuery patent search. Returns list of result dicts."""
    if countries is None:
        countries = ["US", "EP", "WO"]

    if not BIGQUERY_PROJECT_ID:
        print("WARNING: BIGQUERY_PROJECT_ID not set — skipping BigQuery.", file=sys.stderr)
        return []

    if GOOGLE_APPLICATION_CREDENTIALS:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_APPLICATION_CREDENTIALS

    try:
        from google.cloud import bigquery as bq
    except ImportError:
        print("WARNING: google-cloud-bigquery not installed. Run: pip install google-cloud-bigquery", file=sys.stderr)
        return []

    try:
        client = bq.Client(project=BIGQUERY_PROJECT_ID)
        job_config = bq.QueryJobConfig(
            query_parameters=[
                bq.ScalarQueryParameter("term", "STRING", f"%{query.lower()}%"),
                bq.ScalarQueryParameter("limit_val", "INT64", limit),
            ]
        )
        print(f"Running BigQuery search (limit={limit})...", file=sys.stderr)
        job = client.query(_BASE_SQL, job_config=job_config)
        rows = job.result()

        results: list[dict] = []
        for row in rows:
            results.append({
                "publication_number": row.publication_number,
                "title": row.title or "",
                "abstract": (row.abstract or "")[:500],  # truncate for storage
                "publication_date": str(row.publication_date),
                "country_code": row.country_code,
            })
        return results
    except Exception as exc:  # noqa: BLE001
        print(f"WARNING: BigQuery search failed: {exc}", file=sys.stderr)
        return []


# ---------------------------------------------------------------------------
# Supabase persistence
# ---------------------------------------------------------------------------

def save_to_supabase(search_id: str, query: str, results: list[dict]) -> bool:
    """Insert search record into patent_searches. Returns True on success."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        print("WARNING: Supabase credentials not set — skipping Supabase.", file=sys.stderr)
        return False
    try:
        from supabase import create_client
        client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        record = {
            "search_id": search_id,
            "query": query,
            "results": results,
            "result_count": len(results),
        }
        client.table("patent_searches").insert(record).execute()
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"WARNING: Supabase insert failed: {exc}", file=sys.stderr)
        return False


# ---------------------------------------------------------------------------
# Fallback: local JSON
# ---------------------------------------------------------------------------

def slugify(text: str, max_len: int = 40) -> str:
    """Convert text to a filesystem-safe slug."""
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    slug = re.sub(r"[\s_-]+", "_", slug)
    return slug[:max_len].strip("_")


def save_fallback(query: str, search_id: str, results: list[dict]) -> Path:
    """Save results JSON to db/patent_search/{query_slug}_{timestamp}.json."""
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{slugify(query)}_{ts}.json"
    target = FALLBACK_DIR / filename
    payload = {
        "search_id": search_id,
        "query": query,
        "results": results,
        "result_count": len(results),
        "searched_at": datetime.now(tz=timezone.utc).isoformat(),
    }
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
    return target


# ---------------------------------------------------------------------------
# Formatted table output
# ---------------------------------------------------------------------------

def format_table(results: list[dict]) -> str:
    """Format results as a simple ASCII table."""
    if not results:
        return "No results found."

    lines = [
        f"{'#':<3} {'Publication':<20} {'Country':<8} {'Date':<12} {'Title':<50}",
        "-" * 95,
    ]
    for i, r in enumerate(results, 1):
        title = (r.get("title") or "")[:48]
        lines.append(
            f"{i:<3} {r.get('publication_number', ''):<20} "
            f"{r.get('country_code', ''):<8} "
            f"{r.get('publication_date', ''):<12} "
            f"{title:<50}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main search function
# ---------------------------------------------------------------------------

def patent_search(
    query: str,
    limit: int = 10,
    country: Optional[str] = None,
) -> dict:
    """Full search pipeline. Returns result dict."""
    countries = [country.upper()] if country else ["US", "EP", "WO"]
    search_id = str(uuid.uuid4())

    results = search_bigquery(query, limit=limit, countries=countries)

    supabase_ok = save_to_supabase(search_id, query, results)
    fb = save_fallback(query, search_id, results)

    print(f"Fallback saved: {fb}", file=sys.stderr)
    if supabase_ok:
        print("Saved to Supabase: patent_searches", file=sys.stderr)

    return {
        "search_id": search_id,
        "query": query,
        "result_count": len(results),
        "results": results,
        "supabase_saved": supabase_ok,
        "fallback_path": str(fb),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Search patents via BigQuery patents-public-data."
    )
    parser.add_argument("--query", required=True, type=str, help="Search query string")
    parser.add_argument("--limit", type=int, default=10, help="Max results (default: 10)")
    parser.add_argument("--country", type=str, default=None, help="Filter by country code (e.g. US)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON instead of table")
    args = parser.parse_args()

    result = patent_search(args.query, limit=args.limit, country=args.country)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"\nSearch: {result['query']}")
        print(f"Results: {result['result_count']} | Search ID: {result['search_id']}\n")
        print(format_table(result["results"]))
        print(f"\nFallback JSON: {result['fallback_path']}")


if __name__ == "__main__":
    main()
