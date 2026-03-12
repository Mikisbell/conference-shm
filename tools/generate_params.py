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

try:
    import yaml
except ImportError:
    print("[ERROR] PyYAML not installed. Run: pip install pyyaml", file=__import__("sys").stderr)
    raise SystemExit(1)

ROOT      = Path(__file__).resolve().parent.parent
YAML_PATH = ROOT / "config" / "params.yaml"
PY_OUT    = ROOT / "src" / "physics" / "params.py"
H_OUT     = ROOT / "src" / "firmware" / "params.h"


def compute_hash(path: Path) -> str:
    sha = hashlib.sha256()
    sha.update(path.read_bytes())
    return sha.hexdigest()


def load_yaml() -> dict:
    try:
        with open(YAML_PATH) as f:
            return yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"[ERROR] config/params.yaml is malformed: {e}", file=sys.stderr)
        sys.exit(1)


def _nl_val(cfg: dict, *keys):
    """Safely get a nonlinear parameter value, return None if missing."""
    current = cfg
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    if isinstance(current, dict):
        return current.get("value")
    return current


def _nonlinear_ready(cfg: dict) -> bool:
    """Check if all required nonlinear params are populated."""
    nl = cfg.get("nonlinear")
    if nl is None:
        return False
    for section_key in ("concrete", "steel", "section", "geometry"):
        section = nl.get(section_key, {})
        for param in section.values():
            if isinstance(param, dict) and param.get("required", False):
                if param.get("value") is None:
                    return False
    return True


def _v(section: dict, key: str, fallback="None"):
    """Extract value from SSOT section, returning fallback string for nulls.

    Fallback design: all keys this function queries ARE defined in config/params.yaml.
    The fallback values are identical to the SSOT defaults — they are safety nets for
    the template state (before a child project fills in its domain-specific values).
    They are NOT physics constants living outside the SSOT: every fallback here has a
    corresponding entry in params.yaml that takes precedence at runtime.
    AGENTS.md Rule 1 exception: fallbacks mirror SSOT defaults, not override them.
    """
    if key not in section:
        return fallback
    entry = section[key]
    if isinstance(entry, dict):
        val = entry.get("value")
    else:
        val = entry
    return fallback if val is None else val


def _c_val(section: dict, key: str):
    """Extract value for C header. Returns '0 /* TODO: pending research */' for nulls."""
    val = _v(section, key, fallback=None)
    if val is None:
        return "0  /* TODO: pending research */"
    return val


def generate_python(cfg: dict, config_hash: str) -> str:
    mat  = cfg.get("material", {})
    stru = cfg.get("structure", {})
    dmp  = cfg.get("damping", {})
    acq  = cfg.get("acquisition", {})
    sig  = cfg.get("signal_processing", {})
    temp = cfg.get("temporal", {})
    grd  = cfg.get("guardrails", {})
    des  = cfg.get("design", {})

    lines = f'''# AUTO-GENERATED — Do not edit manually.
# Source: config/params.yaml  |  Hash: {config_hash[:16]}
# Regenerate: python3 tools/generate_params.py
# For runtime YAML access (always fresh), use src/physics/models/params.py instead.

CONFIG_HASH = "{config_hash}"

# Material
MATERIAL_NAME = "{_v(mat, "name", "")}"
E         = {_v(mat, "elastic_modulus_E")}
fc        = {_v(mat, "yield_strength_fy")}
nu        = {_v(mat, "poisson_ratio")}
rho       = {_v(mat, "density")}
k_term    = {_v(mat, "thermal_conductivity")}

# Estructura
k         = {_v(stru, "stiffness_k")}
MASS_M    = {_v(stru, "mass_m")}

# Damping
DAMPING_RATIO = {_v(dmp, "ratio_xi")}

# Adquisición
BAUD_RATE = {_v(acq, "serial_baud", 115200)}
SAMPLE_RATE_HZ = {_v(acq, "sample_rate_hz", 100)}

# Kalman
KF_ENABLED = {sig.get("kalman", {}).get("enabled", True)}
KF_Q       = {_v(sig.get("kalman", {}), "process_noise_q", 1e-5)}
KF_R       = {_v(sig.get("kalman", {}), "measurement_noise_r", 0.01)}

# Temporal
DT         = {_v(temp, "dt_simulation", 0.01)}
MAX_JITTER = {_v(temp, "max_jitter_ms", 5)}
BUFFER_DEPTH = {_v(temp, "buffer_depth", 10)}

# Design (E.030)
DESIGN_Z  = {_v(des, "Z", 0.45)}

# Guardrails
MAX_STRESS_RATIO       = {_v(grd, "max_stress_ratio", 0.6)}
CONVERGENCE_TOLERANCE  = {_v(grd, "convergence_tolerance", 1e-6)}
MAX_SLENDERNESS        = {_v(grd, "max_slenderness", 120)}
ECCENTRICITY_RATIO     = {_v(grd, "eccentricity_ratio", 0.10)}
MASS_PARTICIPATION_MIN = {_v(grd, "mass_participation_min", 0.90)}
MAX_SENSOR_SIGMA       = {_v(grd, "max_sensor_outlier_sigma", 3.0)}
ABORT_JITTER_MS        = {_v(grd, "abort_jitter_ms", 10.0)}
ABORT_JITTER_CONSEC    = {_v(grd, "abort_jitter_consec", 3)}
STRESS_RATIO_ABORT     = {_v(grd, "stress_ratio_abort", 0.85)}
LORA_STALE_TIMEOUT_S   = {_v(grd, "lora_stale_timeout_s", 15.0)}

# Nonlinear model status
NONLINEAR_READY = {_nonlinear_ready(cfg)}
'''

    if _nonlinear_ready(cfg):
        nl = cfg["nonlinear"]
        lines += f'''
# Nonlinear — Concrete (Concrete02)
NL_EPSC0           = {nl["concrete"]["epsc0"]["value"]}
NL_FPCU_RATIO      = {nl["concrete"]["fpcu_ratio"]["value"]}
NL_EPSU            = {nl["concrete"]["epsU"]["value"]}
NL_FT_RATIO        = {nl["concrete"]["ft_ratio"]["value"]}
NL_ETS             = {nl["concrete"]["Ets"]["value"]}
NL_CONFINEMENT     = {nl["concrete"]["confinement_ratio"]["value"]}

# Nonlinear — Steel (Steel02)
NL_FY_STEEL        = {nl["steel"]["fy"]["value"]}
NL_ES_STEEL        = {nl["steel"]["Es"]["value"]}
NL_B_HARDENING     = {nl["steel"]["b_hardening"]["value"]}

# Nonlinear — Section
NL_COVER           = {nl["section"]["cover"]["value"]}
NL_N_BARS_FACE     = {nl["section"]["n_bars_face"]["value"]}
NL_BAR_DIA         = {nl["section"]["bar_diameter"]["value"]}

# Nonlinear — Geometry
NL_COLUMN_L        = {nl["geometry"]["L"]["value"]}
NL_COLUMN_B        = {nl["geometry"]["b"]["value"]}
NL_N_ELEMENTS      = {nl["geometry"]["n_elements"]["value"]}
'''

    return lines


def generate_header(cfg: dict, config_hash: str) -> str:
    mat  = cfg.get("material", {})
    stru = cfg.get("structure", {})
    dmp  = cfg.get("damping", {})
    acq  = cfg.get("acquisition", {})
    sig  = cfg.get("signal_processing", {})
    temp = cfg.get("temporal", {})
    grd  = cfg.get("guardrails", {})
    fw   = cfg.get("firmware", {})
    fw_common = fw.get("edge_common", {})
    fw_alarm  = fw.get("edge_alarms", {})
    fw_ga     = fw.get("guardian_angel", {})

    kal = sig.get("kalman", {})
    htoken = temp.get("handshake_token", {})
    htoken_val = htoken.get("value", "BELICO_SYNC") if isinstance(htoken, dict) else htoken

    header = f'''// AUTO-GENERATED — No editar manualmente.
// Fuente: config/params.yaml  |  Hash: {config_hash[:16]}
// Regenerar: python3 tools/generate_params.py
#pragma once

#define CONFIG_HASH     "{config_hash[:16]}"

// ── Material ──
#define MATERIAL_NAME   "{_v(mat, "name", "")}"
#define E_MODULUS       {_c_val(mat, "elastic_modulus_E")}
#define YIELD_STRENGTH  {_c_val(mat, "yield_strength_fy")}
#define RHO             {_c_val(mat, "density")}
#define K_TERM          {_c_val(mat, "thermal_conductivity")}

// ── Structure ──
#define STIFFNESS_K     {_c_val(stru, "stiffness_k")}
#define MASS_M          {_c_val(stru, "mass_m")}

// ── Damping ──
#define DAMPING_RATIO   {_c_val(dmp, "ratio_xi")}

// ── Acquisition ──
#define SERIAL_BAUD     {_v(acq, "serial_baud", 115200)}
#define SAMPLE_RATE_HZ  {_v(acq, "sample_rate_hz", 100)}

// ── Kalman Filter ──
#define KF_Q            {_v(kal, "process_noise_q", 1e-5)}
#define KF_R            {_v(kal, "measurement_noise_r", 0.01)}

// ── Temporal Sync ──
#define HANDSHAKE_TOKEN "{htoken_val}"
#define MAX_JITTER_MS   {_v(temp, "max_jitter_ms", 5)}

// ── Guardrails ──
#define MAX_STRESS_RATIO  {_v(grd, "max_stress_ratio", 0.6)}
#define MAX_SENSOR_SIGMA  {_v(grd, "max_sensor_outlier_sigma", 3.0)}
'''

    # Firmware edge constants (if firmware section exists in SSOT)
    if fw_common:
        header += f'''
// ── Firmware Edge Common ──
#define WINDOW_SIZE_SAMPLES  {_v(fw_common, "window_size_samples", 0)}
#define ACCEL_THRESHOLD_G    {_v(fw_common, "accel_threshold_g", 0.0)}f
#define SLEEP_INTERVAL_MS    {_v(fw_common, "sleep_interval_ms", 0)}
#define LORA_BAUD            {_v(fw_common, "lora_baud", 0)}
'''

    if fw_alarm:
        nom_fn = _v(fw_alarm, "nominal_fn_hz", None)
        fn_warn = _v(fw_alarm, "fn_drop_warn_ratio", 0.0)
        fn_crit = _v(fw_alarm, "fn_drop_crit_ratio", 0.0)
        max_g = _v(fw_alarm, "max_g_alarm", 0.0)
        header += f'''
// ── Firmware Edge Alarms ──
#define NOMINAL_FN_HZ        {f"{nom_fn}f" if nom_fn is not None else "0.0f  // TODO: set after field calibration"}
#define FN_DROP_WARN_RATIO   {fn_warn}f
#define FN_DROP_CRIT_RATIO   {fn_crit}f
#define MAX_G_ALARM          {max_g}f
'''

    if fw_ga:
        header += f'''
// ── Guardian Angel Gates ──
#define GA_RIGIDEZ_TOL_HZ    {_v(fw_ga, "rigidez_tolerance_hz", 0.0)}
#define GA_RIGIDEZ_EXT_HZ    {_v(fw_ga, "rigidez_extreme_hz", 0.0)}
#define GA_TEMP_MIN_C         {_v(fw_ga, "temp_min_c", 0.0)}
#define GA_TEMP_MAX_C         {_v(fw_ga, "temp_max_c", 0.0)}
#define GA_TEMP_EXT_MIN_C     {_v(fw_ga, "temp_extreme_min_c", 0.0)}
#define GA_TEMP_EXT_MAX_C     {_v(fw_ga, "temp_extreme_max_c", 0.0)}
#define GA_GRAD_EXT_C         {_v(fw_ga, "grad_extreme_c", 0.0)}
#define GA_GRAD_IMP_C         {_v(fw_ga, "grad_impossible_c", 0.0)}
#define GA_BAT_UNRELIABLE_V   {_v(fw_ga, "bat_unreliable_v", 0.0)}
#define GA_BAT_CRITICAL_V     {_v(fw_ga, "bat_critical_v", 0.0)}
'''

    return header


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
