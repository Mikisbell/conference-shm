#!/usr/bin/env python3
"""
tools/activate_domain.py — One-command domain activator
========================================================

Activates a research domain in belico-stack:
  1. Validates the domain registry YAML exists
  2. Checks Python dependency availability
  3. Updates config/params.yaml → project.domain
  4. Injects domain namespace template into params.yaml (if missing)
  5. Regenerates params.h + params.py via generate_params.py
  6. Prints a completion checklist

Usage:
    python3 tools/activate_domain.py --domain environmental
    python3 tools/activate_domain.py --domain biomedical --quartile q3
    python3 tools/activate_domain.py --list

Adding a new domain:
    1. Create config/domains/<domain>.yaml
    2. Create domains/<domain>.py extending DomainBackend
    3. Create .agent/skills/domains/<domain>.md
    4. Run: python3 tools/activate_domain.py --domain <domain>
"""

from __future__ import annotations

import argparse
import importlib
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).parent.parent

# ─── Lazy YAML import ─────────────────────────────────────────────────────────
try:
    import yaml as _yaml
except ImportError:  # pragma: no cover
    print("[activate_domain] ERROR: pyyaml not installed. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(1)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _load_registry(domain: str) -> dict:
    """Load domain YAML from config/domains/<domain>.yaml."""
    path = _ROOT / "config" / "domains" / f"{domain}.yaml"
    if not path.exists():
        available = [p.stem for p in (_ROOT / "config" / "domains").glob("*.yaml")]
        print(f"[activate_domain] ERROR: No registry for domain '{domain}'.", file=sys.stderr)
        print(f"  Available: {', '.join(available)}", file=sys.stderr)
        print(f"  To add: create config/domains/{domain}.yaml", file=sys.stderr)
        sys.exit(1)
    with path.open("r", encoding="utf-8") as fh:
        return _yaml.safe_load(fh)


def _check_deps(registry: dict) -> list[str]:
    """Check which required Python deps are missing. Returns list of missing packages."""
    deps = registry.get("dependencies", {}).get("python", [])
    missing = []
    for spec in deps:
        # Extract package name from specifier (e.g. "numpy>=1.24" → "numpy")
        pkg_name = spec.split(">=")[0].split("==")[0].split("!=")[0].strip()
        # Map pip names to importable names
        import_name = {
            "openseespy": "openseespy",
            "scikit-learn": "sklearn",
            "pyyaml": "yaml",
            "statsmodels": "statsmodels",
            "geopandas": "geopandas",
        }.get(pkg_name, pkg_name)
        try:
            importlib.import_module(import_name)
        except ImportError:
            missing.append(spec)
    return missing


def _read_params_yaml() -> tuple[dict, str]:
    """Read config/params.yaml and return (data, raw_text)."""
    path = _ROOT / "config" / "params.yaml"
    if not path.exists():
        print("[activate_domain] ERROR: config/params.yaml not found.", file=sys.stderr)
        sys.exit(1)
    raw = path.read_text(encoding="utf-8")
    data = _yaml.safe_load(raw)
    return data, raw


def _set_domain_in_params(raw: str, domain: str) -> str:
    """Replace project.domain value in raw YAML text (preserves formatting)."""
    lines = raw.splitlines(keepends=True)
    in_project = False
    result = []
    replaced = False
    for line in lines:
        stripped = line.strip()
        if stripped == "project:":
            in_project = True
            result.append(line)
            continue
        if in_project and stripped.startswith("domain:"):
            result.append(f'  domain: "{domain}"\n')
            in_project = False
            replaced = True
            continue
        # Exit project block on any non-indented key
        if in_project and stripped and not stripped.startswith("#") and not line.startswith(" "):
            in_project = False
        result.append(line)

    if not replaced:
        print("[activate_domain] WARN: Could not find 'project.domain' in params.yaml. "
              "Add it manually: project:\n  domain: \"" + domain + "\"", file=sys.stderr)

    return "".join(result)


def _build_params_template(registry: dict) -> str:
    """Generate a params.yaml section template for a domain's namespace."""
    domain = registry.get("domain", "unknown")
    display = registry.get("display_name", domain)
    namespaces = registry.get("params_namespace", [])
    if not namespaces:
        return ""

    lines = [
        f"\n# ─── {display} domain params ─────────────────────────────────────────────",
        f"# Activate with: python3 tools/activate_domain.py --domain {domain}",
        f"# Required keys declared in: config/domains/{domain}.yaml → params_namespace",
        f"{domain}:",
    ]

    for ns in namespaces:
        # e.g. "environmental.study_area.*" → key = "study_area"
        parts = ns.strip(".*").split(".")
        if len(parts) >= 2:
            key = parts[1]
            lines.append(f"  {key}:  # TODO: fill values — see config/domains/{domain}.yaml")
        else:
            lines.append(f"  # {ns}")

    return "\n".join(lines) + "\n"


def _inject_namespace_template(raw: str, registry: dict) -> tuple[str, bool]:
    """Inject domain namespace template at end of params.yaml if not present."""
    domain = registry.get("domain", "unknown")
    if f"\n{domain}:" in raw or raw.startswith(f"{domain}:"):
        return raw, False  # already present
    template = _build_params_template(registry)
    if not template:
        return raw, False
    return raw + template, True


def _list_domains() -> None:
    """Print all registered domains with status."""
    domains_dir = _ROOT / "config" / "domains"
    print("\n=== REGISTERED DOMAINS ===")
    print(f"{'Domain':<20} {'Status':<14} {'Display Name'}")
    print("-" * 70)
    for path in sorted(domains_dir.glob("*.yaml")):
        try:
            with path.open("r", encoding="utf-8") as fh:
                reg = _yaml.safe_load(fh)
            status = reg.get("status", "unknown")
            display = reg.get("display_name", "")
            domain = reg.get("domain", path.stem)
            status_icon = {"operational": "✅", "planned": "🔧", "experimental": "⚗️"}.get(status, "❓")
            print(f"  {domain:<18} {status_icon} {status:<12} {display}")
        except _yaml.YAMLError as exc:
            print(f"  {path.stem:<18} ⚠️  PARSE ERROR: {exc}")
    print()


def _print_checklist(registry: dict, missing_deps: list[str], quartile: str) -> None:
    """Print activation checklist with remaining TODOs."""
    domain = registry.get("domain", "unknown")
    status = registry.get("status", "planned")
    todos = registry.get("todo", [])
    figures = registry.get("pipeline", {}).get("figures", [])
    stats = registry.get("pipeline", {}).get("statistics", [])

    print(f"\n{'='*60}")
    print(f"  DOMAIN ACTIVATED: {domain.upper()}")
    print(f"{'='*60}")

    # Deps
    if missing_deps:
        print("\n⚠️  MISSING DEPENDENCIES (install before COMPUTE):")
        for dep in missing_deps:
            print(f"   pip install {dep}")
        print(f"\n   Or install all: pip install {' '.join(missing_deps)}")
    else:
        print("\n✅ All Python dependencies available")

    # Status
    if status == "operational":
        print(f"✅ Domain status: OPERATIONAL — compute pipeline ready")
    else:
        print(f"🔧 Domain status: {status.upper()} — implement TODOs before COMPUTE")

    # Pipeline hooks
    pipeline = registry.get("pipeline", {})
    print(f"\n📋 PIPELINE HOOKS:")
    print(f"   Narrator : python3 articles/scientific_narrator.py {pipeline.get('narrator_flag', '')}")
    print(f"   Figures  : python3 tools/plot_figures.py {pipeline.get('plot_figures_flag', '')} --quartile {quartile}")
    print(f"   Stats    : python3 tools/compute_statistics.py --domain {domain} --quartile {quartile}")

    # Figures declared
    if figures:
        print(f"\n📊 FIGURES DECLARED ({len(figures)}):")
        for fig in figures:
            req = "required" if fig.get("required") else "Q3+ required"
            print(f"   [{req:<15}] {fig['id']} — {fig['title'][:50]}")
            print(f"                     data: {fig['data_source']}")

    # Statistics declared
    if stats:
        print(f"\n📈 STATISTICAL TESTS DECLARED: {', '.join(stats)}")

    # Normative codes
    codes = pipeline.get("normative_codes", [])
    if codes:
        print(f"\n📖 NORMATIVE CODES TO CITE: {', '.join(codes)}")

    # TODOs
    if todos:
        print(f"\n⬜ TODO (implement before first paper in this domain):")
        for todo in todos:
            print(f"   [ ] {todo}")

    # Next step
    print(f"\n🚀 NEXT STEP:")
    if status == "operational":
        print(f"   python3 tools/generate_params.py    # regenerate params.h + params.py")
        print(f"   Then: start EXPLORE phase in the pipeline")
    else:
        print(f"   1. Implement TODOs above")
        print(f"   2. python3 tools/generate_params.py")
        print(f"   3. Test: python3 -c \"from domains.{domain} import *; print('OK')\"")

    print(f"{'='*60}\n")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Activate a research domain in belico-stack.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 tools/activate_domain.py --list
  python3 tools/activate_domain.py --domain environmental
  python3 tools/activate_domain.py --domain biomedical --quartile q3
  python3 tools/activate_domain.py --domain economics --dry-run
        """,
    )
    parser.add_argument(
        "--domain", "-d",
        help="Domain to activate (e.g. structural, environmental, biomedical, economics)",
    )
    parser.add_argument(
        "--quartile", "-q",
        default="q3",
        choices=["conference", "q4", "q3", "q2", "q1"],
        help="Target paper quartile (default: q3)",
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List all registered domains",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing files",
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Skip pip install even if deps are missing",
    )
    args = parser.parse_args()

    if args.list:
        _list_domains()
        return

    if not args.domain:
        parser.print_help()
        sys.exit(1)

    domain = args.domain.lower().strip()

    print(f"\n[activate_domain] Activating domain: {domain} (quartile: {args.quartile})")

    # ── STEP 1: Load registry ────────────────────────────────────────────────
    print("[activate_domain] Step 1/5 — Loading registry...")
    registry = _load_registry(domain)
    print(f"  ✅ Registry loaded: {registry.get('display_name', domain)} [{registry.get('status')}]")

    # ── STEP 2: Check dependencies ───────────────────────────────────────────
    print("[activate_domain] Step 2/5 — Checking dependencies...")
    missing = _check_deps(registry)
    if missing:
        print(f"  ⚠️  Missing: {', '.join(missing)}")
        if not args.skip_install and not args.dry_run:
            print(f"  Installing: pip install {' '.join(missing)}")
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install"] + missing,
                capture_output=False,
            )
            if result.returncode != 0:
                print(f"  ⚠️  pip install exited {result.returncode} — continuing anyway",
                      file=sys.stderr)
            missing = _check_deps(registry)  # re-check after install
            if not missing:
                print("  ✅ All dependencies installed")
        else:
            print("  (skipped — dry-run or --skip-install)")
    else:
        print("  ✅ All dependencies available")

    # ── STEP 2b: Verify backend class is importable ───────────────────────────
    backend_module = registry.get("solver", {}).get("backend_module", "")
    backend_class = registry.get("solver", {}).get("backend_class", "")
    if backend_module and backend_class:
        try:
            mod = importlib.import_module(backend_module)
            getattr(mod, backend_class)
            print(f"  ✅ Backend class importable: {backend_module}.{backend_class}")
        except ImportError as exc:
            print(
                f"  ❌ Backend module not found: {backend_module} — {exc}",
                file=sys.stderr,
            )
            print(
                f"     Fix: create domains/{domain}.py extending DomainBackend",
                file=sys.stderr,
            )
            sys.exit(1)
        except AttributeError:
            print(
                f"  ❌ Class '{backend_class}' not found in {backend_module}",
                file=sys.stderr,
            )
            print(
                f"     Fix: add class {backend_class}(DomainBackend) to domains/{domain}.py",
                file=sys.stderr,
            )
            sys.exit(1)
    else:
        print("  ⚠️  No backend_module/backend_class in registry — skipping import check")

    # ── STEP 3: Update params.yaml → project.domain ──────────────────────────
    print("[activate_domain] Step 3/5 — Updating config/params.yaml...")
    data, raw = _read_params_yaml()
    current_domain = data.get("project", {}).get("domain", "unknown")

    if current_domain == domain:
        print(f"  ✅ Already active: project.domain = '{domain}' (no change)")
    else:
        new_raw = _set_domain_in_params(raw, domain)
        if args.dry_run:
            print(f"  [DRY-RUN] Would change project.domain: '{current_domain}' → '{domain}'")
        else:
            (_ROOT / "config" / "params.yaml").write_text(new_raw, encoding="utf-8")
            print(f"  ✅ Updated project.domain: '{current_domain}' → '{domain}'")
        raw = new_raw

    # ── STEP 4: Inject namespace template if missing ─────────────────────────
    print("[activate_domain] Step 4/5 — Checking domain namespace in params.yaml...")
    new_raw, injected = _inject_namespace_template(raw, registry)
    if injected:
        if args.dry_run:
            print(f"  [DRY-RUN] Would inject '{domain}:' namespace template at end of params.yaml")
        else:
            (_ROOT / "config" / "params.yaml").write_text(new_raw, encoding="utf-8")
            print(f"  ✅ Injected '{domain}:' namespace template — fill TODO values before COMPUTE")
    else:
        print(f"  ✅ Namespace '{domain}:' already present in params.yaml")

    # ── STEP 5: Regenerate params.h + params.py ──────────────────────────────
    print("[activate_domain] Step 5/5 — Regenerating SSOT derivatives...")
    gen_params = _ROOT / "tools" / "generate_params.py"
    if gen_params.exists() and not args.dry_run:
        result = subprocess.run(
            [sys.executable, str(gen_params)],
            capture_output=True,
            text=True,
            cwd=str(_ROOT),
        )
        if result.returncode == 0:
            print("  ✅ generate_params.py OK — params.h + params.py regenerated")
        else:
            print(f"  ⚠️  generate_params.py exited {result.returncode}:", file=sys.stderr)
            if result.stderr:
                print(result.stderr[:300], file=sys.stderr)
    elif args.dry_run:
        print("  [DRY-RUN] Would run: python3 tools/generate_params.py")
    else:
        print("  ⚠️  tools/generate_params.py not found — skipping SSOT regeneration",
              file=sys.stderr)

    # ── Checklist ─────────────────────────────────────────────────────────────
    _print_checklist(registry, missing, args.quartile)


if __name__ == "__main__":
    main()
