#!/usr/bin/env python3
"""
tools/generate_params.py — Propagador SSOT del Stack Bélico
============================================================
Lee config/params.yaml (fuente única de verdad) y regenera
los archivos derivados que usan otros módulos:

  - src/physics/params.py   → Constantes Python para bridge.py
  - src/firmware/params.h   → Defines C++ para el firmware Nicla

Uso:
  python3 tools/generate_params.py
  python3 tools/generate_params.py --dry-run   # Solo verificar, no escribir
"""

import argparse
import hashlib
import sys
from pathlib import Path

import yaml

ROOT      = Path(__file__).resolve().parent.parent
YAML_PATH = ROOT / "config" / "params.yaml"
PY_OUT    = ROOT / "src" / "physics" / "params.py"
H_OUT     = ROOT / "src" / "firmware" / "params.h"


def compute_hash(path: Path) -> str:
    sha = hashlib.sha256()
    sha.update(path.read_bytes())
    return sha.hexdigest()


def load_yaml() -> dict:
    with open(YAML_PATH) as f:
        return yaml.safe_load(f)


def generate_python(cfg: dict, config_hash: str) -> str:
    mat  = cfg["material"]
    stru = cfg["structure"]
    acq  = cfg["acquisition"]
    sig  = cfg["signal_processing"]
    temp = cfg["temporal"]

    return f'''# AUTO-GENERATED — No editar manualmente.
# Fuente: config/params.yaml  |  Hash: {config_hash[:16]}
# Regenerar: python3 tools/generate_params.py

CONFIG_HASH = "{config_hash}"

# Material
MATERIAL_NAME = "{mat["name"]}"
E         = {mat["elastic_modulus_E"]["value"]}
fc        = {mat["yield_strength_fy"]["value"]}
nu        = {mat["poisson_ratio"]["value"]}
rho       = {mat["density"]["value"]}
k_term    = {mat["thermal_conductivity"]["value"]}

# Estructura
k         = {stru["stiffness_k"]["value"]}

# Adquisición
BAUD_RATE = {acq["serial_baud"]["value"]}
SAMPLE_RATE_HZ = {acq["sample_rate_hz"]["value"]}

# Kalman
KF_ENABLED = {sig["kalman"]["enabled"]}
KF_Q       = {sig["kalman"]["process_noise_q"]["value"]}
KF_R       = {sig["kalman"]["measurement_noise_r"]["value"]}

# Temporal
DT         = {temp["dt_simulation"]["value"]}
MAX_JITTER = {temp["max_jitter_ms"]["value"]}
BUFFER_DEPTH = {temp["buffer_depth"]["value"]}
'''


def generate_header(cfg: dict, config_hash: str) -> str:
    mat  = cfg["material"]
    acq  = cfg["acquisition"]
    sig  = cfg["signal_processing"]

    return f'''// AUTO-GENERATED — No editar manualmente.
// Fuente: config/params.yaml  |  Hash: {config_hash[:16]}
// Regenerar: python3 tools/generate_params.py
#pragma once

#define CONFIG_HASH     "{config_hash[:16]}"
#define MATERIAL_NAME   "{mat["name"]}"
#define E_MODULUS       {mat["elastic_modulus_E"]["value"]}
#define RHO             {mat["density"]["value"]}
#define K_TERM          {mat["thermal_conductivity"]["value"]}

#define SERIAL_BAUD     {acq["serial_baud"]["value"]}
#define SAMPLE_RATE_HZ  {acq["sample_rate_hz"]["value"]}

#define KF_Q            {sig["kalman"]["process_noise_q"]["value"]}
#define KF_R            {sig["kalman"]["measurement_noise_r"]["value"]}
'''


def main(dry_run: bool = False):
    if not YAML_PATH.exists():
        print(f"❌ No encontré {YAML_PATH}")
        sys.exit(1)

    cfg         = load_yaml()
    config_hash = compute_hash(YAML_PATH)
    py_content  = generate_python(cfg, config_hash)
    h_content   = generate_header(cfg, config_hash)

    print(f"📋 Hash SSOT: {config_hash[:16]}...")

    if dry_run:
        print("  [DRY-RUN] No se escribirán archivos.")
        print(f"  Generaría: {PY_OUT}")
        print(f"  Generaría: {H_OUT}")
        return

    PY_OUT.write_text(py_content, encoding="utf-8")
    print(f"  ✅ {PY_OUT}")

    H_OUT.parent.mkdir(parents=True, exist_ok=True)
    H_OUT.write_text(h_content, encoding="utf-8")
    print(f"  ✅ {H_OUT}")

    print("Propagación SSOT completada.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Propagador SSOT — Belico Stack")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
