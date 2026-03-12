#!/usr/bin/env python3
"""
tools/scaffold_investigation.py — Multi-Domain Project Scaffolder + Data Validator
===================================================================================
Creates a new project directory under projects/ and validates that all
required parameters are populated in config/params.yaml for the selected domain.

Supports three domains:
  structural  -> OpenSeesPy   (seismic, SHM, P-Delta)
  water       -> FEniCSx      (Navier-Stokes, hydraulics)
  air         -> FEniCSx/SU2  (wind loading, aerodynamics)

Usage:
  python3 tools/scaffold_investigation.py <project_name> [domain]
  python3 tools/scaffold_investigation.py --check [domain]

Examples:
  python3 tools/scaffold_investigation.py Bridge_Alpha structural
  python3 tools/scaffold_investigation.py Tank_Beta water
  python3 tools/scaffold_investigation.py Tower_Gamma air
  python3 tools/scaffold_investigation.py --check           # checks current domain
  python3 tools/scaffold_investigation.py --check water     # checks water params
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

VALID_DOMAINS = ("structural", "water", "air")

DOMAIN_DESCRIPTIONS = {
    "structural": "OpenSeesPy (seismic, SHM, P-Delta)",
    "water": "FEniCSx (Navier-Stokes, hydraulics, dam/pipe monitoring)",
    "air": "FEniCSx/SU2 (wind loading, aerodynamics, ventilation)",
}

DOMAIN_SOLVERS = {
    "structural": "OpenSeesPy",
    "water": "FEniCSx (pip install fenics-dolfinx)",
    "air": "FEniCSx (pip install fenics-dolfinx) or SU2",
}


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
    """Get the solver backend instance for a domain."""
    if domain == "structural":
        try:
            from src.physics.torture_chamber import StructuralBackend
        except ImportError as e:
            print(f"[SCAFFOLD] ERROR: Could not import StructuralBackend: {e}", file=sys.stderr)
            print("[SCAFFOLD] Install: pip install openseespy", file=sys.stderr)
            sys.exit(1)
        return StructuralBackend()
    elif domain in ("water", "air"):
        try:
            from src.physics.torture_chamber_fluid import FluidBackend
        except ImportError as e:
            print(f"[SCAFFOLD] ERROR: Could not import FluidBackend: {e}", file=sys.stderr)
            print("[SCAFFOLD] Install: pip install fenics-dolfinx", file=sys.stderr)
            sys.exit(1)
        return FluidBackend(domain=domain)
    else:
        raise ValueError(f"Unknown domain: {domain}. Valid: {', '.join(VALID_DOMAINS)}")


def print_checklist(missing: list[tuple[str, str]], domain: str, project_name: str = None):
    """Print a formatted checklist of missing parameters."""
    context = f" para proyecto '{project_name}'" if project_name else ""
    solver = DOMAIN_SOLVERS[domain]

    if not missing:
        print(f"\n[SCAFFOLD] TODOS los parametros del dominio '{domain}' estan configurados{context}.")
        print(f"[SCAFFOLD] Solver: {solver}")
        return

    print(f"\n{'='*70}")
    print(f"  DATOS REQUERIDOS — Dominio: {domain.upper()}{context}")
    print(f"  Solver: {solver}")
    print(f"  {DOMAIN_DESCRIPTIONS[domain]}")
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
    project_dir = ROOT / "projects" / project_name
    project_dir.mkdir(parents=True, exist_ok=True)

    belico_path = project_dir / "belico.yaml"
    if belico_path.exists():
        print(f"[SCAFFOLD] Proyecto '{project_name}' ya existe en {project_dir}")
    else:
        template = {
            "project": project_name,
            "domain": domain,
            "status": "pending_field_data",
            "solver": DOMAIN_SOLVERS[domain],
            "site": {
                "name": "TODO: nombre del sitio",
                "element": "TODO: tipo de elemento o estructura",
            },
            "orchestration": {
                "guardian_angel": True,
                "engram_notary": True,
            },
            "notes": (
                f"Proyecto creado por scaffold_investigation.py (domain={domain}). "
                "Completar parametros en config/params.yaml antes de analisis."
            ),
        }
        with open(belico_path, "w") as f:
            yaml.dump(template, f, sort_keys=False, allow_unicode=True)
        print(f"[SCAFFOLD] Proyecto '{project_name}' creado en {project_dir}")
        print(f"[SCAFFOLD] Dominio: {domain} ({DOMAIN_DESCRIPTIONS[domain]})")

    # Validate SSOT for this domain
    cfg = load_ssot()
    backend = get_backend_for_domain(domain)
    missing = backend.check_required_params(cfg)
    print_checklist(missing, domain, project_name)


def main():
    if len(sys.argv) < 2:
        print("Uso:")
        print("  python3 tools/scaffold_investigation.py <nombre_proyecto> [domain]")
        print("  python3 tools/scaffold_investigation.py --check [domain]")
        print(f"\nDominios validos: {', '.join(VALID_DOMAINS)}")
        for d, desc in DOMAIN_DESCRIPTIONS.items():
            print(f"  {d:12s} — {desc}")
        sys.exit(1)

    if sys.argv[1] == "--check":
        domain = sys.argv[2] if len(sys.argv) > 2 else None
        cfg = load_ssot()

        if domain is None:
            domain = cfg.get("project", {}).get("domain", "structural")

        if domain not in VALID_DOMAINS:
            print(f"Error: dominio '{domain}' no valido. Usar: {', '.join(VALID_DOMAINS)}")
            sys.exit(1)

        backend = get_backend_for_domain(domain)
        missing = backend.check_required_params(cfg)
        print_checklist(missing, domain)
        sys.exit(1 if missing else 0)
    else:
        project_name = sys.argv[1].replace(" ", "_")
        domain = sys.argv[2] if len(sys.argv) > 2 else "structural"

        if domain not in VALID_DOMAINS:
            print(f"Error: dominio '{domain}' no valido. Usar: {', '.join(VALID_DOMAINS)}")
            sys.exit(1)

        create_project(project_name, domain)


if __name__ == "__main__":
    main()
