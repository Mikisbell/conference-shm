#!/usr/bin/env python3
"""
tools/init_project.py — Project Bootstrapper
==============================================
Single entry point for new projects. Detects the current directory,
asks minimal questions, creates structure, installs deps, and generates
config files. Everything adapts to the project name automatically.

Usage:
  python3 tools/init_project.py              # New project setup
  python3 tools/init_project.py --reset      # Start fresh (backs up existing)
  python3 tools/init_project.py --skip-deps  # Skip dependency installation
"""

import os
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
YAML_PATH = ROOT / "config" / "params.yaml"
PRD_PATH = ROOT / "PRD.md"
GENERATOR = ROOT / "tools" / "generate_params.py"
SETUP_DEPS = ROOT / "tools" / "setup_dependencies.sh"


# ═══════════════════════════════════════════════════════════════════════════
# Utilities
# ═══════════════════════════════════════════════════════════════════════════

def ask(prompt: str, default=None) -> str:
    suffix = f" [{default}]" if default else ""
    while True:
        raw = input(f"  {prompt}{suffix}: ").strip()
        if not raw and default:
            return default
        if raw:
            return raw
        print("    (campo obligatorio)")


def ask_choice(prompt: str, options: list[dict]) -> dict:
    print(f"\n  {prompt}\n")
    for i, opt in enumerate(options, 1):
        print(f"    {i}. {opt['label']}")
        if opt.get("desc"):
            print(f"       {opt['desc']}")
    while True:
        raw = input(f"\n  Elige (1-{len(options)}): ").strip()
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(options):
                return options[idx]
        except ValueError:
            pass
        print(f"    (elige un numero del 1 al {len(options)})")


def ask_yn(prompt: str, default: bool = True) -> bool:
    hint = "S/n" if default else "s/N"
    raw = input(f"  {prompt} [{hint}]: ").strip().lower()
    if not raw:
        return default
    return raw in ("s", "si", "y", "yes")


def banner(text: str):
    w = 55
    print(f"\n{'=' * w}")
    print(f"  {text}")
    print(f"{'=' * w}")


def info(text: str):
    print(f"  >> {text}")


def detect_project_name() -> str:
    """Use the current directory name as default project name."""
    return ROOT.name


# ═══════════════════════════════════════════════════════════════════════════
# Domain definitions
# ═══════════════════════════════════════════════════════════════════════════

DOMAINS = [
    {
        "label": "structural — Analisis sismico / estructural",
        "key": "structural",
        "solver": "OpenSeesPy",
        "desc": "Columnas, porticos, muros, puentes. Sensor: acelerometro.",
        "research_hint": "Material (concreto, acero, madera), geometria, carga sismica",
    },
    {
        "label": "water — Fluidos / hidraulica",
        "key": "water",
        "solver": "FEniCSx (Navier-Stokes)",
        "desc": "Tuberias, canales, presas, flujo interno.",
        "research_hint": "Fluido (agua, aceite), geometria del dominio, condiciones de borde",
    },
    {
        "label": "air — Viento / aerodinamica",
        "key": "air",
        "solver": "FEniCSx / SU2",
        "desc": "Carga de viento en edificios, tuneles, puentes.",
        "research_hint": "Condicion atmosferica, geometria de obstaculo, velocidad de viento",
    },
]

# ═══════════════════════════════════════════════════════════════════════════
# Directory structure
# ═══════════════════════════════════════════════════════════════════════════

REQUIRED_DIRS = [
    "config",
    "src/firmware",
    "src/physics",
    "src/ai",
    "data/raw",
    "data/processed",
    "data/external",
    "articles/drafts",
    "articles/figures",
    ".agent/prompts",
    ".agent/skills",
    ".agent/specs",
    "tools",
]


def ensure_directories():
    """Create project directory structure if missing."""
    created = []
    for d in REQUIRED_DIRS:
        path = ROOT / d
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            created.append(d)
    return created


# ═══════════════════════════════════════════════════════════════════════════
# Dependency check
# ═══════════════════════════════════════════════════════════════════════════

def check_dependencies() -> dict:
    """Check which ecosystem tools are installed."""
    deps = {}
    for cmd, name in [("engram", "Engram"), ("gentle-ai", "Gentle AI"),
                      ("gga", "GGA")]:
        result = subprocess.run(["which", cmd], capture_output=True)
        deps[name] = result.returncode == 0
    # Check cloned repos
    deps["Agent Teams Lite"] = (ROOT / ".agents" / "agent-teams-lite").exists()
    return deps


def install_dependencies():
    """Run setup_dependencies.sh if available."""
    if SETUP_DEPS.exists():
        info("Instalando dependencias del ecosistema...")
        subprocess.run(["bash", str(SETUP_DEPS)], cwd=str(ROOT))
    else:
        info("setup_dependencies.sh no encontrado — instala manualmente:")
        print("    brew install gentleman-programming/tap/engram")
        print("    brew install gentleman-programming/tap/gentle-ai")
        print("    brew install gentleman-programming/tap/gga")


# ═══════════════════════════════════════════════════════════════════════════
# File generators
# ═══════════════════════════════════════════════════════════════════════════

def generate_skeleton(project_name: str, domain: dict) -> dict:
    return {
        "metadata": {
            "project": project_name,
            "version": "1.0.0",
            "last_updated": str(date.today()),
            "author": "",
            "config_hash": "",
        },
        "project": {
            "domain": domain["key"],
            "keywords": "",
        },
        "material": {
            "name": "",
            "elastic_modulus_E": {"value": None, "units": "Pa", "symbol": "E"},
            "yield_strength_fy": {"value": None, "units": "Pa", "symbol": "fc"},
            "poisson_ratio": {"value": None, "units": "dimensionless", "symbol": "nu"},
            "density": {"value": None, "units": "kg/m^3", "symbol": "rho"},
            "thermal_conductivity": {"value": None, "units": "W/m*K", "symbol": "k_term"},
        },
        "structure": {
            "stiffness_k": {"value": None, "units": "N/m", "symbol": "k",
                            "firmware_var": "STIFFNESS_K", "simulation_var": "k"},
            "mass_m": {"value": None, "units": "kg", "symbol": "m",
                       "firmware_var": "MASS_M", "simulation_var": "mass"},
            "natural_frequency_fn": {"value": None, "units": "Hz",
                                     "symbol": "fn", "computed": True},
        },
        "damping": {
            "method": "rayleigh",
            "ratio_xi": {"value": None, "units": "dimensionless", "symbol": "xi",
                         "firmware_var": "DAMPING_RATIO", "simulation_var": "xi"},
        },
        "acquisition": {
            "sample_rate_hz": {"value": 100, "units": "Hz",
                               "firmware_var": "SAMPLE_RATE_HZ",
                               "simulation_var": "dt"},
            "sensor_pin": {"value": "A0", "firmware_var": "SENSOR_PIN"},
            "serial_baud": {"value": 115200, "firmware_var": "SERIAL_BAUD"},
        },
        "temporal": {
            "dt_simulation": {"value": 0.01, "units": "s"},
            "max_jitter_ms": {"value": 5, "units": "ms"},
            "buffer_depth": {"value": 10, "units": "packets"},
            "handshake_token": {"value": f"SYNC_{date.today().year}"},
        },
        "signal_processing": {
            "kalman": {
                "enabled": True,
                "process_noise_q": {"value": 1e-5},
                "measurement_noise_r": {"value": 0.01},
            },
        },
        "guardrails": {
            "max_stress_ratio": {"value": 0.6},
            "convergence_tolerance": {"value": 1e-6},
            "max_sensor_outlier_sigma": {"value": 3.0},
        },
    }


def generate_prd(project_name: str, domain: dict, author: str,
                 keywords: str = "") -> str:
    return f"""# PRD — {project_name}
# Version: 1.0.0 | Autor: {author} | Fecha: {date.today()}

---

## 1. Problema

<!-- Describe el problema de investigacion que quieres resolver -->

(Por definir durante la sesion de investigacion)

---

## 2. Vision

<!-- En una frase: que va a lograr este proyecto? -->

(Por definir)

---

## 3. Usuario

**{author}** — Investigador.
- Dominio: {domain['label']}
- Solver: {domain['solver']}

---

## 4. Research Keywords

Keywords: {keywords}

---

## 5. Alcance del Paper

| Aspecto | Valor |
|---------|-------|
| Tipo | (Conference / Q4 / Q3 / Q2 / Q1) |
| Target journal | (Por definir) |
| Datos requeridos | (Sinteticos / Campo / Laboratorio) |

---

## 6. Parametros a Investigar

El agente AI te guiara para completar estos parametros durante la sesion:

- **Material**: {domain['research_hint']}
- **Config**: `config/params.yaml` (valores null = pendiente de investigacion)
- **Propagacion**: `python3 tools/generate_params.py`

---

## 7. Pipeline

```
config/params.yaml (SSOT)
    |
    v
src/firmware/params.h  +  src/physics/params.py
    |                          |
    v                          v
Sensor (campo)          Simulacion ({domain['solver']})
    |                          |
    v                          v
data/raw/               data/processed/
    |                          |
    +----------+---------------+
               |
               v
        articles/drafts/  -->  PDF
```

---

## 8. Siguiente Paso

Abre Claude Code en este directorio y di: `Engram conecto`
"""


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Project Bootstrapper — configures a new research project")
    parser.add_argument("--reset", action="store_true",
                        help="Backup existing config and start fresh")
    parser.add_argument("--skip-deps", action="store_true",
                        help="Skip dependency installation")
    args = parser.parse_args()

    # Detect project context
    default_name = detect_project_name()

    banner(f"NUEVO PROYECTO — {default_name}")
    print(f"  Directorio: {ROOT}")
    print(f"  Solo necesito 3 cosas. El resto lo investigamos juntos en Claude.")

    # Backup if needed
    if args.reset:
        for f in [YAML_PATH, PRD_PATH]:
            if f.exists():
                backup = f.with_suffix(f"{f.suffix}.bak.{date.today()}")
                shutil.copy2(f, backup)
                info(f"Backup: {backup.name}")

    # ── 1. Project name (default = folder name) ──
    banner("NOMBRE DEL PROYECTO")
    project_name = ask("Como se llama tu proyecto?", default_name)

    # ── 2. Domain ──
    banner("DOMINIO")
    domain = ask_choice("En que area trabajas?", DOMAINS)
    info(f"Dominio: {domain['key']} ({domain['solver']})")

    # ── 3. Research keywords ──
    banner("TEMA DE INVESTIGACION")
    print("  Escribe las keywords de tu investigacion separadas por comas.")
    print("  Ejemplo: digital twin, seismic, reinforced concrete, SHM")
    research_keywords = ask("Keywords de investigacion")

    # ── 4. Author ──
    author = ask("Tu nombre (autor)", "")

    # ── 4. Create directory structure ──
    banner("ESTRUCTURA DE DIRECTORIOS")
    created = ensure_directories()
    if created:
        for d in created:
            info(f"Creado: {d}/")
    else:
        info("Estructura completa (todos los directorios existen)")

    # ── 5. Dependencies ──
    if not args.skip_deps:
        banner("DEPENDENCIAS")
        deps = check_dependencies()
        all_ok = True
        for name, installed in deps.items():
            status = "OK" if installed else "FALTA"
            print(f"    {name}: {status}")
            if not installed:
                all_ok = False

        if not all_ok:
            if ask_yn("Instalar dependencias faltantes?"):
                install_dependencies()
            else:
                info("Saltando instalacion. Puedes correr despues:")
                print("    bash tools/setup_dependencies.sh")
        else:
            info("Todas las dependencias instaladas")

    # ── 6. Generate config files ──
    banner("GENERANDO ARCHIVOS")

    # params.yaml
    YAML_PATH.parent.mkdir(parents=True, exist_ok=True)
    cfg = generate_skeleton(project_name, domain)
    cfg["metadata"]["author"] = author
    cfg["project"]["keywords"] = research_keywords

    class CustomDumper(yaml.SafeDumper):
        pass

    def float_representer(dumper, value):
        if value != value:
            return dumper.represent_scalar("tag:yaml.org,2002:float", ".nan")
        if abs(value) >= 1e6 or (0 < abs(value) < 1e-3):
            return dumper.represent_scalar(
                "tag:yaml.org,2002:float", f"{value:.6e}")
        return dumper.represent_scalar(
            "tag:yaml.org,2002:float", f"{value:g}")

    CustomDumper.add_representer(float, float_representer)

    with open(YAML_PATH, "w") as f:
        f.write(f"# SSOT — {project_name}\n")
        f.write(f"# Generado por init_project.py el {date.today()}\n")
        f.write("# Valores null = pendiente de investigacion\n")
        f.write("# Regenerar derivados: python3 tools/generate_params.py\n\n")
        yaml.dump(cfg, f, Dumper=CustomDumper, default_flow_style=False,
                  allow_unicode=True, sort_keys=False)
    info("config/params.yaml (esqueleto con nulls)")

    # PRD
    prd_content = generate_prd(project_name, domain, author, research_keywords)
    with open(PRD_PATH, "w") as f:
        f.write(prd_content)
    info("PRD.md (plantilla lista para investigar)")

    # Propagate
    if GENERATOR.exists():
        result = subprocess.run(
            [sys.executable, str(GENERATOR)],
            capture_output=True, text=True)
        if result.returncode == 0:
            info("params.h + params.py propagados")
        else:
            info("Propagacion pendiente (params.yaml tiene valores null)")

    # ── Done ──
    banner(f"PROYECTO LISTO: {project_name}")
    print(f"""
  Proyecto:  {project_name}
  Dominio:   {domain['key']} ({domain['solver']})
  Directorio: {ROOT}

  Archivos generados:
    config/params.yaml  — SSOT (valores pendientes de investigacion)
    PRD.md              — Roadmap del paper (por llenar con Claude)
    src/firmware/params.h  — Header C (con placeholders)
    src/physics/params.py  — Constantes Python (con None)

  SIGUIENTE PASO:
  Abre Claude Code en este directorio y di:

    Engram conecto

  El sistema te preguntara que tipo de articulo quieres desarrollar
  (Conference/Q4/Q3/Q2/Q1) y te guiara con la investigacion.
""")


if __name__ == "__main__":
    main()
