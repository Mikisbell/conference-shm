#!/usr/bin/env python3
"""
tools/scaffold_investigation.py — Multi-Domain Project Scaffolder + Data Validator
===================================================================================
Creates a new project directory under projects/ and validates that all
required parameters are populated in config/params.yaml for the selected domain.

Domain-agnostic: accepts any domain registered in config/domains/*.yaml.
For unknown domains, guides the user to the orchestrator (Claude Code) which
generates the domain configuration from a free-text research description.

Usage:
  python3 tools/scaffold_investigation.py <project_name> [domain]
  python3 tools/scaffold_investigation.py --check [domain]
  python3 tools/scaffold_investigation.py --list-domains

Examples:
  python3 tools/scaffold_investigation.py Bridge_Alpha structural
  python3 tools/scaffold_investigation.py Crop_Study_Region environmental
  python3 tools/scaffold_investigation.py ECG_Arrhythmia biomedical
  python3 tools/scaffold_investigation.py --check           # checks current domain
  python3 tools/scaffold_investigation.py --list-domains    # show all registered domains
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    import yaml
except ImportError:
    print("[SCAFFOLD] ERROR: PyYAML not installed. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(1)
YAML_PATH = ROOT / "config" / "params.yaml"


def _get_registered_domains() -> dict[str, dict]:
    """Load all domains from config/domains/*.yaml. Returns {domain: registry_dict}."""
    domains_dir = ROOT / "config" / "domains"
    result = {}
    if not domains_dir.exists():
        return result
    for path in sorted(domains_dir.glob("*.yaml")):
        try:
            with path.open("r", encoding="utf-8") as fh:
                reg = yaml.safe_load(fh)
            if reg and "domain" in reg:
                result[reg["domain"]] = reg
        except yaml.YAMLError:
            pass
    return result


def load_ssot() -> dict:
    try:
        with open(YAML_PATH) as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        print(f"[SCAFFOLD] ERROR: config/params.yaml not found at {YAML_PATH}", file=sys.stderr)
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"[SCAFFOLD] ERROR: config/params.yaml is malformed: {e}", file=sys.stderr)
        sys.exit(1)


def get_backend_for_domain(domain: str):
    """Get the solver backend instance for a domain via Domain Registry."""
    try:
        from domains.base import DomainRegistry
        return DomainRegistry.load(domain)
    except FileNotFoundError:
        registered = _get_registered_domains()
        print(
            f"[SCAFFOLD] ERROR: Domain '{domain}' not registered.\n"
            f"  Registered: {', '.join(registered.keys()) or 'none'}",
            file=sys.stderr,
        )
        _print_new_domain_guide(domain)
        sys.exit(1)
    except ImportError as exc:
        print(f"[SCAFFOLD] ERROR: Cannot load backend for '{domain}': {exc}", file=sys.stderr)
        sys.exit(1)


def _print_new_domain_guide(domain: str) -> None:
    """Guide user to generate a new domain via the orchestrator."""
    print(
        f"\n  To generate '{domain}' automatically:\n"
        f"  → Open Claude Code in this directory\n"
        f"  → Say: \"engram conectó\"\n"
        f"  → Describe your research in free text — the orchestrator generates\n"
        f"    config/domains/{domain}.yaml + domains/{domain}.py automatically\n"
        f"  → Then re-run: python3 tools/scaffold_investigation.py <name> {domain}\n",
        file=sys.stderr,
    )


def print_checklist(missing: list[tuple[str, str]], domain: str, project_name: str = None):
    """Print a formatted checklist of missing parameters."""
    context = f" para proyecto '{project_name}'" if project_name else ""
    registered = _get_registered_domains()
    reg = registered.get(domain, {})
    solver_info = reg.get("solver", {}).get("engine", "see config/domains/" + domain + ".yaml")
    display_name = reg.get("display_name", domain)

    if not missing:
        print(f"\n[SCAFFOLD] TODOS los parametros del dominio '{domain}' estan configurados{context}.")
        print(f"[SCAFFOLD] Solver: {solver_info}")
        return

    print(f"\n{'='*70}")
    print(f"  DATOS REQUERIDOS — Dominio: {domain.upper()}{context}")
    print(f"  {display_name}")
    print(f"  Solver: {solver_info}")
    print(f"{'='*70}\n")

    for i, (dotpath, desc) in enumerate(missing, 1):
        yaml_path = dotpath.replace(".", " > ")
        print(f"  [{i:2d}] {yaml_path}")
        print(f"       {desc}\n")

    print(f"{'='*70}")
    print(f"  Total: {len(missing)} parametros faltantes")
    print(f"  Editar: config/params.yaml")
    print(f"  Luego:  python3 tools/generate_params.py")
    print(f"{'='*70}\n")


def create_project(project_name: str, domain: str):
    """Create a new project directory with belico.yaml template."""
    registered = _get_registered_domains()
    reg = registered.get(domain, {})
    display_name = reg.get("display_name", domain)
    solver_info = reg.get("solver", {}).get("engine", "see registry")
    domain_status = reg.get("status", "unknown")

    project_dir = ROOT / "projects" / project_name
    project_dir.mkdir(parents=True, exist_ok=True)

    belico_path = project_dir / "belico.yaml"
    if belico_path.exists():
        print(f"[SCAFFOLD] Proyecto '{project_name}' ya existe en {project_dir}")
    else:
        template = {
            "project": project_name,
            "domain": domain,
            "domain_display": display_name,
            "domain_status": domain_status,
            "status": "pending_compute",
            "solver": solver_info,
            "site": {
                "name": "TODO: nombre del sitio o area de estudio",
                "description": "TODO: descripcion del objeto de estudio",
            },
            "orchestration": {
                "guardian_angel": domain == "structural",
                "engram_notary": True,
            },
            "registry": f"config/domains/{domain}.yaml",
            "notes": (
                f"Proyecto creado por scaffold_investigation.py (domain={domain}). "
                "Completar parametros en config/params.yaml antes de COMPUTE."
            ),
        }
        with open(belico_path, "w") as f:
            yaml.dump(template, f, sort_keys=False, allow_unicode=True)
        print(f"[SCAFFOLD] Proyecto '{project_name}' creado en {project_dir}")
        print(f"[SCAFFOLD] Dominio: {domain} — {display_name} [{domain_status}]")

    # Validate SSOT for this domain
    cfg = load_ssot()
    try:
        backend = get_backend_for_domain(domain)
        ok, errors = backend.validate_ssot()
        if ok:
            print_checklist([], domain, project_name)
        else:
            # Convert validate_ssot errors to checklist format
            missing = [(e, "") for e in errors]
            print_checklist(missing, domain, project_name)
    except SystemExit:
        raise


def _list_domains() -> None:
    """Print all registered domains."""
    registered = _get_registered_domains()
    if not registered:
        print("No domains registered in config/domains/")
        print("Run: python3 tools/activate_domain.py --list")
        return
    print("\nDominios registrados:")
    for domain, reg in registered.items():
        status = reg.get("status", "unknown")
        display = reg.get("display_name", domain)
        icon = {"operational": "✅", "planned": "🔧", "experimental": "⚗️"}.get(status, "❓")
        print(f"  {icon} {domain:20s} [{status}] — {display}")
    print()
    print("Dominio no listado? Descríbelo en Claude Code — el orquestador lo genera.")
    print()


def main():
    registered = _get_registered_domains()

    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("Uso:")
        print("  python3 tools/scaffold_investigation.py <nombre_proyecto> [domain]")
        print("  python3 tools/scaffold_investigation.py --check [domain]")
        print("  python3 tools/scaffold_investigation.py --list-domains")
        print()
        _list_domains()
        sys.exit(0 if len(sys.argv) > 1 else 1)

    if sys.argv[1] == "--list-domains":
        _list_domains()
        sys.exit(0)

    if sys.argv[1] == "--check":
        cfg = load_ssot()
        domain = sys.argv[2] if len(sys.argv) > 2 else None
        if domain is None:
            domain = cfg.get("project", {}).get("domain", "structural")

        if domain not in registered:
            print(f"[SCAFFOLD] Dominio '{domain}' no registrado.")
            _print_new_domain_guide(domain)
            sys.exit(1)

        backend = get_backend_for_domain(domain)
        ok, errors = backend.validate_ssot()
        missing = [(e, "") for e in errors]
        print_checklist(missing, domain)
        sys.exit(1 if missing else 0)

    else:
        project_name = sys.argv[1].replace(" ", "_")
        domain = sys.argv[2] if len(sys.argv) > 2 else None

        if domain is None:
            # Read from SSOT
            cfg = load_ssot()
            domain = cfg.get("project", {}).get("domain", "structural")
            print(f"[SCAFFOLD] Usando dominio activo del SSOT: {domain}")

        if domain not in registered:
            print(f"[SCAFFOLD] Dominio '{domain}' no registrado en config/domains/")
            _print_new_domain_guide(domain)
            sys.exit(1)

        create_project(project_name, domain)


if __name__ == "__main__":
    main()
