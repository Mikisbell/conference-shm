#!/usr/bin/env python3
"""
supabase_migrations.py — Create required tables for the Innovation Engine.

Run: python3 tools/supabase_migrations.py

Creates (if not exist):
  - reference_papers
  - patent_searches
  - innovation_gaps

Uses Supabase REST API with service key. If that fails, prints SQL for manual execution.
"""

from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv
import os

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
load_dotenv(Path(__file__).parent.parent / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

# ---------------------------------------------------------------------------
# SQL definitions
# ---------------------------------------------------------------------------

SQL_REFERENCE_PAPERS = """
CREATE TABLE IF NOT EXISTS reference_papers (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  paper_id text UNIQUE NOT NULL,
  title text,
  pdf_path text,
  full_text text,
  methodology_text text,
  limitations_text text,
  created_at timestamptz DEFAULT now()
);
"""

SQL_PATENT_SEARCHES = """
CREATE TABLE IF NOT EXISTS patent_searches (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  search_id text,
  query text NOT NULL,
  results jsonb,
  result_count int DEFAULT 0,
  searched_at timestamptz DEFAULT now()
);
"""

SQL_INNOVATION_GAPS = """
CREATE TABLE IF NOT EXISTS innovation_gaps (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  gap_id text,
  paper_id text REFERENCES reference_papers(paper_id),
  query text,
  analysis jsonb,
  verdict text,
  created_at timestamptz DEFAULT now()
);
"""

MIGRATIONS: list[tuple[str, str]] = [
    ("reference_papers", SQL_REFERENCE_PAPERS),
    ("patent_searches", SQL_PATENT_SEARCHES),
    ("innovation_gaps", SQL_INNOVATION_GAPS),
]


# ---------------------------------------------------------------------------
# Execution via Supabase REST API (pg_rpc)
# ---------------------------------------------------------------------------

def _run_sql_via_rest(sql: str, table_name: str) -> bool:
    """
    Execute raw SQL via Supabase REST API using service role key.
    Uses POST /rest/v1/rpc/exec_sql if the function exists.
    Falls back to a direct HTTP request to /pg endpoint.
    """
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        return False

    import urllib.request
    import urllib.error
    import json

    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }

    # Try via pg_meta (Supabase internal)
    url = f"{SUPABASE_URL}/rest/v1/rpc/exec_sql"
    payload = json.dumps({"query": sql}).encode()

    try:
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status in (200, 204):
                return True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            pass  # RPC function not found — try supabase client
        else:
            print(f"  HTTP {e.code}: {e.reason}", file=sys.stderr)

    # Try via supabase-py execute (some versions support raw SQL)
    try:
        from supabase import create_client
        client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        # Attempt to check if table exists by querying it
        client.table(table_name).select("id").limit(1).execute()
        return True  # Table already exists
    except Exception as exc:  # noqa: BLE001
        print(f"[supabase_migrations] Fallback check failed: {exc}", file=sys.stderr)
        return False


# ---------------------------------------------------------------------------
# Main migration runner
# ---------------------------------------------------------------------------

def run_migrations() -> None:
    """Run all migrations. Print SQL for manual execution if API fails."""
    if not SUPABASE_URL:
        print("ERROR: SUPABASE_URL not set in .env", file=sys.stderr)
        sys.exit(1)

    print(f"Supabase URL: {SUPABASE_URL}")
    print(f"Service key:  {'set' if SUPABASE_SERVICE_KEY else 'MISSING'}")
    print()

    all_ok = True
    failed_tables: list[tuple[str, str]] = []

    for table_name, sql in MIGRATIONS:
        print(f"Creating table: {table_name} ... ", end="", flush=True)
        ok = _run_sql_via_rest(sql.strip(), table_name)
        if ok:
            print("OK")
        else:
            print("FAILED (see below)")
            all_ok = False
            failed_tables.append((table_name, sql))

    if failed_tables:
        print()
        print("=" * 70)
        print("MIGRATIONS FAILED — Execute the following SQL manually in the")
        print("Supabase SQL Editor: https://supabase.com/dashboard/project/*/sql")
        print("=" * 70)
        for table_name, sql in failed_tables:
            print(f"\n-- Table: {table_name}")
            print(sql.strip())
        print()
        print("Steps:")
        print("  1. Open your Supabase project dashboard")
        print("  2. Go to SQL Editor (left sidebar)")
        print("  3. Paste each CREATE TABLE statement above and run it")
        print()
        sys.exit(1)
    else:
        print()
        print("All migrations completed successfully.")


# ---------------------------------------------------------------------------
# Print-only mode (for documentation)
# ---------------------------------------------------------------------------

def print_sql() -> None:
    """Print all migration SQL to stdout."""
    for table_name, sql in MIGRATIONS:
        print(f"-- Table: {table_name}")
        print(sql.strip())
        print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Create Innovation Engine tables in Supabase."
    )
    parser.add_argument(
        "--print-sql",
        action="store_true",
        help="Print SQL statements only (do not execute)",
    )
    args = parser.parse_args()

    if args.print_sql:
        print_sql()
    else:
        run_migrations()


if __name__ == "__main__":
    main()
