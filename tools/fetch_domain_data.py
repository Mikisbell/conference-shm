#!/usr/bin/env python3
"""
tools/fetch_domain_data.py — Generic domain data fetcher (COMPUTE C1)
======================================================================
Reads config/domains/{domain}.yaml → data_sources, dispatches each
source to the correct DataAdapter, downloads to data/external/{domain}/,
and reports what was fetched.

Usage:
    python3 tools/fetch_domain_data.py --domain environmental
    python3 tools/fetch_domain_data.py --domain environmental --source air_quality
    python3 tools/fetch_domain_data.py --domain structural --verify
    python3 tools/fetch_domain_data.py --list-sources --domain economics
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml


def _load_yaml(path: Path) -> dict:
    """Load a YAML file and return its parsed content.

    Raises:
        FileNotFoundError: If path does not exist.
        yaml.YAMLError: If file is malformed.
    """
    if not path.exists():
        raise FileNotFoundError(f"[fetch_domain_data] File not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _load_study_params(domain: str, params_path: Path) -> dict:
    """Extract the domain namespace from config/params.yaml.

    Returns an empty dict (not an error) if the section is absent —
    the domain may not yet be active in this project.
    """
    try:
        ssot = _load_yaml(params_path)
    except FileNotFoundError:
        print(
            f"[fetch_domain_data] WARNING: {params_path} not found. "
            "study_params will be empty.",
            file=sys.stderr,
        )
        return {}
    return ssot.get(domain, {})


def _list_sources(domain_cfg: dict, domain: str) -> None:
    """Print a table of available data sources for a domain."""
    data_sources = domain_cfg.get("data_sources", {})
    if not data_sources:
        print(f"[{domain}] No data_sources declared in config/domains/{domain}.yaml.")
        return

    print(f"\nData sources for domain '{domain}':")
    print(f"  {'Source ID':<25} {'Adapter':<18} {'Account?':<10} Name")
    print("  " + "-" * 72)
    for source_id, cfg in data_sources.items():
        if not isinstance(cfg, dict):
            # benchmarks list entries, etc.
            continue
        adapter = cfg.get("adapter", "(not set)")
        requires = "yes" if cfg.get("requires_account") else "no"
        name = cfg.get("name", "")
        print(f"  {source_id:<25} {adapter:<18} {requires:<10} {name}")
    print()


def _run_fetch(
    domain: str,
    domain_cfg: dict,
    study_params: dict,
    source_filter: str | None,
    verify_only: bool,
) -> int:
    """Dispatch each data_source to its adapter. Returns 0 if all OK, 1 if any failed."""
    # Import here so the registry is available after sys.path is set
    try:
        from tools.adapters import get_adapter
    except ImportError as exc:
        print(
            f"[fetch_domain_data] Cannot import tools.adapters: {exc}\n"
            "  Ensure tools/adapters/__init__.py exists and domains/base.py is importable.",
            file=sys.stderr,
        )
        return 1

    data_sources: dict = domain_cfg.get("data_sources", {})
    if not data_sources:
        print(
            f"[fetch_domain_data] No data_sources in config/domains/{domain}.yaml.",
            file=sys.stderr,
        )
        return 1

    ok_count = 0
    fail_count = 0

    for source_id, source_config in data_sources.items():
        if not isinstance(source_config, dict):
            # Skip list entries (e.g. benchmarks list in structural.yaml)
            continue
        if source_filter and source_id != source_filter:
            continue

        adapter_type = source_config.get("adapter", "")
        if not adapter_type:
            print(
                f"  [{source_id}] SKIP — no 'adapter' field in config. "
                "Add adapter: <type> to config/domains/{domain}.yaml → data_sources.{source_id}",
                file=sys.stderr,
            )
            continue

        print(f"\n--- Source: {source_id} (adapter={adapter_type}) ---")

        try:
            adapter_cls = get_adapter(adapter_type)
        except KeyError as exc:
            print(f"  [{source_id}] ERROR — {exc}", file=sys.stderr)
            fail_count += 1
            continue

        adapter = adapter_cls()
        output_dir = Path("data") / "external" / domain / source_id

        if verify_only:
            # Validate what is already on disk
            existing_files = [p for p in output_dir.rglob("*") if p.is_file()] if output_dir.exists() else []
            ok, errors = adapter.validate(existing_files)
            if ok:
                print(f"  [{source_id}] VALID — {len(existing_files)} file(s) on disk.")
                ok_count += 1
            else:
                for err in errors:
                    print(f"  [{source_id}] INVALID — {err}", file=sys.stderr)
                fail_count += 1
            continue

        # Full fetch + validate
        try:
            files = adapter.fetch(source_id, source_config, study_params, output_dir)
        except OSError as exc:
            print(f"  [{source_id}] OSError during fetch: {exc}", file=sys.stderr)
            fail_count += 1
            continue
        except RuntimeError as exc:
            print(f"  [{source_id}] RuntimeError during fetch: {exc}", file=sys.stderr)
            fail_count += 1
            continue

        if not files:
            print(
                f"  [{source_id}] No files returned by adapter. "
                "Check the messages above for instructions.",
                file=sys.stderr,
            )
            fail_count += 1
            continue

        ok, errors = adapter.validate(files)
        if ok:
            print(f"  [{source_id}] OK — {len(files)} file(s) validated.")
            ok_count += 1
        else:
            for err in errors:
                print(f"  [{source_id}] VALIDATION ERROR — {err}", file=sys.stderr)
            fail_count += 1

    return 0 if fail_count == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generic domain data fetcher (COMPUTE C1)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--domain",
        required=True,
        help="Domain name (e.g. environmental, structural, biomedical, economics)",
    )
    parser.add_argument(
        "--source",
        default=None,
        help="Fetch only this data source (by source_id). Fetches all if omitted.",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Validate existing local files only — do not download.",
    )
    parser.add_argument(
        "--list-sources",
        action="store_true",
        help="List available data sources for the domain and exit.",
    )

    args = parser.parse_args()
    domain: str = args.domain

    # Load domain registry
    domain_cfg_path = Path("config") / "domains" / f"{domain}.yaml"
    try:
        domain_cfg = _load_yaml(domain_cfg_path)
    except FileNotFoundError:
        print(
            f"[fetch_domain_data] Domain registry not found: {domain_cfg_path}\n"
            f"  Available: {[p.stem for p in Path('config/domains').glob('*.yaml')]}",
            file=sys.stderr,
        )
        return 1
    except yaml.YAMLError as exc:
        print(f"[fetch_domain_data] YAML parse error in {domain_cfg_path}: {exc}", file=sys.stderr)
        return 1

    if args.list_sources:
        _list_sources(domain_cfg, domain)
        return 0

    # Load study params from SSOT
    study_params = _load_study_params(domain, Path("config") / "params.yaml")

    exit_code = _run_fetch(
        domain=domain,
        domain_cfg=domain_cfg,
        study_params=study_params,
        source_filter=args.source,
        verify_only=args.verify,
    )

    # Summary
    print(f"\n{'='*40}")
    if exit_code == 0:
        print(f"[fetch_domain_data] All sources fetched and validated for domain '{domain}'.")
    else:
        print(
            f"[fetch_domain_data] One or more sources failed for domain '{domain}'. "
            "See messages above.",
            file=sys.stderr,
        )
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
