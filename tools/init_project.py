#!/usr/bin/env python3
"""
tools/init_project.py — Interactive Project Setup Wizard
=========================================================
Guides the user through creating a new config/params.yaml
by asking simple questions instead of manual YAML editing.

Usage:
  python3 tools/init_project.py              # Interactive wizard
  python3 tools/init_project.py --reset      # Start fresh (backs up existing)

After completion, automatically runs generate_params.py to propagate.
"""

import math
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
YAML_PATH = ROOT / "config" / "params.yaml"
TEMPLATE_PATH = ROOT / "config" / "params_template.yaml"
GENERATOR = ROOT / "tools" / "generate_params.py"


# ─── Utilities ──────────────────────────────────────────────────────────────

def ask(prompt: str, default=None, type_fn=str):
    """Ask user a question with optional default."""
    suffix = f" [{default}]" if default is not None else ""
    while True:
        raw = input(f"  {prompt}{suffix}: ").strip()
        if not raw and default is not None:
            return type_fn(default) if not isinstance(default, type_fn) else default
        if not raw:
            print("    (campo obligatorio, intenta de nuevo)")
            continue
        try:
            return type_fn(raw)
        except ValueError:
            print(f"    (valor invalido, se espera {type_fn.__name__})")


def ask_choice(prompt: str, options: list[str], default: str = None) -> str:
    """Ask user to pick from a list of options."""
    print(f"\n  {prompt}")
    for i, opt in enumerate(options, 1):
        marker = " <--" if opt == default else ""
        print(f"    {i}. {opt}{marker}")
    while True:
        raw = input(f"  Elige (1-{len(options)})" +
                     (f" [{options.index(default)+1}]" if default else "") +
                     ": ").strip()
        if not raw and default:
            return default
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(options):
                return options[idx]
        except ValueError:
            pass
        print(f"    (elige un numero del 1 al {len(options)})")


def banner(text: str):
    """Print a section banner."""
    width = 55
    print(f"\n{'=' * width}")
    print(f"  {text}")
    print(f"{'=' * width}")


def info(text: str):
    print(f"  >> {text}")


# ─── Domain-specific question sets ─────────────────────────────────────────

def ask_structural(cfg: dict):
    """Questions for structural engineering projects."""
    banner("MATERIAL")
    mat = cfg["material"]
    mat["name"] = ask("Nombre del material", "Concreto Liviano Reciclado C&DW")
    mat["elastic_modulus_E"]["value"] = ask(
        "Modulo elastico E (Pa)", 20e9, float)
    mat["yield_strength_fy"]["value"] = ask(
        "Resistencia fc' (Pa)", 20e6, float)
    mat["density"]["value"] = ask(
        "Densidad rho (kg/m3)", 1800.0, float)
    mat["poisson_ratio"]["value"] = ask(
        "Coeficiente de Poisson", 0.2, float)
    mat["thermal_conductivity"]["value"] = ask(
        "Conductividad termica k (W/m*K)", 0.51, float)

    banner("ESTRUCTURA")
    stru = cfg["structure"]
    stru["stiffness_k"]["value"] = ask(
        "Rigidez lateral k (N/m)", 5000.0, float)
    stru["mass_m"]["value"] = ask(
        "Masa total m (kg)", 1000.0, float)
    k_val = stru["stiffness_k"]["value"]
    m_val = stru["mass_m"]["value"]
    fn = math.sqrt(k_val / m_val) / (2 * math.pi)
    info(f"Frecuencia natural calculada: fn = {fn:.3f} Hz")

    banner("AMORTIGUAMIENTO")
    dmp = cfg["damping"]
    dmp["ratio_xi"]["value"] = ask(
        "Ratio de amortiguamiento xi", 0.05, float)

    # Update firmware nominal fn to match calculated value
    fw = cfg.setdefault("firmware", {})
    alarms = fw.setdefault("edge_alarms", {})
    alarms.setdefault("nominal_fn_hz", {})["value"] = round(fn, 3)
    info(f"nominal_fn_hz actualizado a {fn:.3f} Hz")


def ask_fluid(cfg: dict):
    """Questions for water/fluid projects."""
    banner("PROPIEDADES DEL FLUIDO")
    fl = cfg.setdefault("fluid", {}).setdefault("properties", {})
    fl.setdefault("viscosity_mu", {})["value"] = ask(
        "Viscosidad dinamica mu (Pa.s)", 1e-3, float)
    fl["viscosity_mu"]["units"] = "Pa.s"
    fl.setdefault("density_rho", {})["value"] = ask(
        "Densidad del fluido (kg/m3)", 1000.0, float)
    fl["density_rho"]["units"] = "kg/m3"

    banner("GEOMETRIA DEL DOMINIO")
    geo = cfg["fluid"].setdefault("geometry", {})
    geo.setdefault("length", {})["value"] = ask("Longitud del dominio (m)", 10.0, float)
    geo["length"]["units"] = "m"
    geo.setdefault("height", {})["value"] = ask("Altura del dominio (m)", 2.0, float)
    geo["height"]["units"] = "m"
    geo.setdefault("width", {})["value"] = ask("Ancho (m, 0 para 2D)", 0.0, float)
    geo["width"]["units"] = "m"

    banner("CONDICIONES DE BORDE")
    bnd = cfg["fluid"].setdefault("boundary", {})
    bnd.setdefault("inlet_velocity", {})["value"] = ask(
        "Velocidad de entrada (m/s)", 1.0, float)
    bnd["inlet_velocity"]["units"] = "m/s"
    bnd.setdefault("outlet_pressure", {})["value"] = ask(
        "Presion de salida (Pa, gauge)", 0.0, float)
    bnd["outlet_pressure"]["units"] = "Pa"

    banner("MALLA Y ANALISIS")
    mesh = cfg["fluid"].setdefault("mesh", {})
    mesh.setdefault("resolution", {})["value"] = ask(
        "Resolucion de malla (elem/m)", 20, int)
    mesh["resolution"]["units"] = "elem/m"
    ana = cfg["fluid"].setdefault("analysis", {})
    ana.setdefault("time_step", {})["value"] = ask("Paso temporal (s)", 0.001, float)
    ana["time_step"]["units"] = "s"
    ana.setdefault("total_time", {})["value"] = ask("Tiempo total (s)", 10.0, float)
    ana["total_time"]["units"] = "s"


def ask_air(cfg: dict):
    """Questions for wind/air projects."""
    banner("PROPIEDADES DEL AIRE")
    air = cfg.setdefault("air", {}).setdefault("properties", {})
    air.setdefault("viscosity_mu", {})["value"] = ask(
        "Viscosidad dinamica mu (Pa.s)", 1.8e-5, float)
    air["viscosity_mu"]["units"] = "Pa.s"
    air.setdefault("density_rho", {})["value"] = ask(
        "Densidad del aire (kg/m3)", 1.225, float)
    air["density_rho"]["units"] = "kg/m3"

    banner("GEOMETRIA DEL DOMINIO")
    geo = cfg["air"].setdefault("geometry", {})
    geo.setdefault("length", {})["value"] = ask("Longitud del dominio (m)", 30.0, float)
    geo["length"]["units"] = "m"
    geo.setdefault("height", {})["value"] = ask("Altura del dominio (m)", 15.0, float)
    geo["height"]["units"] = "m"
    geo.setdefault("width", {})["value"] = ask("Ancho (m, 0 para 2D)", 0.0, float)
    geo["width"]["units"] = "m"
    geo.setdefault("obstacle_width", {})["value"] = ask(
        "Ancho del edificio/obstaculo (m)", 1.0, float)
    geo["obstacle_width"]["units"] = "m"
    geo.setdefault("obstacle_height", {})["value"] = ask(
        "Altura del edificio/obstaculo (m)", 3.0, float)
    geo["obstacle_height"]["units"] = "m"

    banner("CONDICIONES DE BORDE")
    bnd = cfg["air"].setdefault("boundary", {})
    bnd.setdefault("inlet_velocity", {})["value"] = ask(
        "Velocidad del viento (m/s)", 15.0, float)
    bnd["inlet_velocity"]["units"] = "m/s"
    bnd.setdefault("turbulence_intensity", {})["value"] = ask(
        "Intensidad de turbulencia (0-1)", 0.15, float)
    bnd["turbulence_intensity"]["units"] = "-"

    banner("MALLA Y ANALISIS")
    mesh = cfg["air"].setdefault("mesh", {})
    mesh.setdefault("resolution", {})["value"] = ask(
        "Resolucion de malla (elem/m)", 10, int)
    mesh["resolution"]["units"] = "elem/m"
    ana = cfg["air"].setdefault("analysis", {})
    ana.setdefault("time_step", {})["value"] = ask("Paso temporal (s)", 0.005, float)
    ana["time_step"]["units"] = "s"
    ana.setdefault("total_time", {})["value"] = ask("Tiempo total (s)", 30.0, float)
    ana["total_time"]["units"] = "s"


def ask_sensors(cfg: dict):
    """Sensor and acquisition questions (common to all domains)."""
    banner("SENSORES Y ADQUISICION")
    acq = cfg["acquisition"]
    acq["sample_rate_hz"]["value"] = ask(
        "Frecuencia de muestreo (Hz)", 100, int)
    acq["serial_baud"]["value"] = ask(
        "Baudrate serial (debug)", 115200, int)

    sig = cfg["signal_processing"]
    info("Filtro de Kalman (suaviza ruido del sensor)")
    sig["kalman"]["process_noise_q"]["value"] = ask(
        "Ruido de proceso Q (mas bajo = mas suave)", 1e-5, float)
    sig["kalman"]["measurement_noise_r"]["value"] = ask(
        "Ruido de medicion R (mas alto = mas suave)", 0.01, float)


def ask_lora(cfg: dict):
    """LoRa/telemetry questions."""
    use_lora = ask_choice(
        "Usaras telemetria LoRa?",
        ["si", "no"], default="si")

    if use_lora == "si":
        fw = cfg.setdefault("firmware", {})
        common = fw.setdefault("edge_common", {})
        common.setdefault("lora_baud", {})["value"] = ask(
            "Baudrate LoRa UART", 9600, int)
        common["lora_baud"]["units"] = "baud"
        common.setdefault("window_size_samples", {})["value"] = ask(
            "Ventana FFT (potencia de 2)", 256, int)
        common["window_size_samples"]["units"] = "samples"
        common.setdefault("sleep_interval_ms", {})["value"] = ask(
            "Intervalo de sueño entre bursts (ms)", 5000, int)
        common["sleep_interval_ms"]["units"] = "ms"


# ─── Base template ──────────────────────────────────────────────────────────

def load_base_template() -> dict:
    """Load template or create minimal base config."""
    if TEMPLATE_PATH.exists():
        with open(TEMPLATE_PATH) as f:
            return yaml.safe_load(f)

    # If no template exists, load the current params.yaml as base
    if YAML_PATH.exists():
        with open(YAML_PATH) as f:
            return yaml.safe_load(f)

    # Minimal skeleton
    return {
        "metadata": {
            "project": "belico-stack",
            "version": "1.0.0",
            "last_updated": "",
            "author": "",
            "config_hash": "",
        },
        "project": {"domain": "structural"},
        "material": {
            "name": "",
            "elastic_modulus_E": {"value": None, "units": "Pa", "symbol": "E"},
            "yield_strength_fy": {"value": None, "units": "Pa", "symbol": "fc"},
            "poisson_ratio": {"value": None, "units": "dimensionless", "symbol": "nu"},
            "density": {"value": None, "units": "kg/m^3", "symbol": "rho"},
            "thermal_conductivity": {"value": None, "units": "W/m·K", "symbol": "k_term"},
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
            "ratio_xi": {"value": 0.05, "units": "dimensionless", "symbol": "xi",
                         "firmware_var": "DAMPING_RATIO", "simulation_var": "xi"},
            "alpha_mass": {"value": None, "computed": True},
            "beta_stiff": {"value": None, "computed": True},
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
            "handshake_token": {"value": "BELICO_SYNC_2026"},
            "clock_drift_warning_ms": {"value": 2, "units": "ms"},
            "prediction_mode": {
                "enabled": False,
                "trigger_threshold_g": {"value": 0.3, "units": "g"},
            },
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
            "max_slenderness": {"value": 120},
            "eccentricity_ratio": {"value": 0.10},
            "mass_participation_min": {"value": 0.90},
            "max_sensor_outlier_sigma": {"value": 3.0},
            "abort_jitter_ms": {"value": 10.0},
            "abort_jitter_consec": {"value": 3},
            "stress_ratio_abort": {"value": 0.85},
            "lora_stale_timeout_s": {"value": 15.0},
        },
    }


# ─── Main wizard ────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Belico Stack — Setup Wizard")
    parser.add_argument("--reset", action="store_true",
                        help="Backup existing config and start fresh")
    args = parser.parse_args()

    print()
    banner("BELICO STACK — SETUP WIZARD")
    print("  Te guiare paso a paso para configurar tu proyecto.")
    print("  Presiona Enter para aceptar el valor por defecto [entre corchetes].")

    # Handle existing config
    if YAML_PATH.exists() and not args.reset:
        action = ask_choice(
            "Ya existe config/params.yaml. Que quieres hacer?",
            ["Editar el existente", "Empezar de cero (backup automatico)"],
            default="Editar el existente")
        if "cero" in action:
            backup = YAML_PATH.with_suffix(f".yaml.bak.{date.today()}")
            shutil.copy2(YAML_PATH, backup)
            info(f"Backup guardado en {backup.name}")
            cfg = load_base_template()
        else:
            with open(YAML_PATH) as f:
                cfg = yaml.safe_load(f)
    elif args.reset and YAML_PATH.exists():
        backup = YAML_PATH.with_suffix(f".yaml.bak.{date.today()}")
        shutil.copy2(YAML_PATH, backup)
        info(f"Backup guardado en {backup.name}")
        cfg = load_base_template()
    else:
        cfg = load_base_template()

    # ── Step 1: Domain ──
    banner("TIPO DE PROYECTO")
    print("  Que tipo de proyecto vas a analizar?\n")
    domain = ask_choice(
        "Dominio de simulacion:",
        ["structural — Analisis sismico/estructural (OpenSeesPy)",
         "water — Fluidos/hidraulica (FEniCSx Navier-Stokes)",
         "air — Viento/aerodinamica (FEniCSx/SU2)"],
        default="structural — Analisis sismico/estructural (OpenSeesPy)")
    domain_key = domain.split(" — ")[0].strip()
    cfg["project"]["domain"] = domain_key
    info(f"Dominio seleccionado: {domain_key}")

    # ── Step 2: Metadata ──
    banner("INFORMACION DEL PROYECTO")
    meta = cfg["metadata"]
    meta["project"] = ask("Nombre del proyecto", meta.get("project", "belico-stack"))
    meta["author"] = ask("Autor", meta.get("author", ""))
    meta["version"] = ask("Version", meta.get("version", "1.0.0"))
    meta["last_updated"] = str(date.today())

    # ── Step 3: Domain-specific questions ──
    if domain_key == "structural":
        ask_structural(cfg)
    elif domain_key == "water":
        ask_fluid(cfg)
    elif domain_key == "air":
        ask_air(cfg)

    # ── Step 4: Sensors ──
    ask_sensors(cfg)

    # ── Step 5: LoRa (optional) ──
    ask_lora(cfg)

    # ── Step 6: Write YAML ──
    banner("GUARDANDO CONFIGURACION")
    YAML_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Custom YAML dumper to handle scientific notation nicely
    class CustomDumper(yaml.SafeDumper):
        pass

    def float_representer(dumper, value):
        if value != value:  # NaN
            return dumper.represent_scalar("tag:yaml.org,2002:float", ".nan")
        if abs(value) >= 1e6 or (0 < abs(value) < 1e-3):
            return dumper.represent_scalar(
                "tag:yaml.org,2002:float", f"{value:.6e}")
        return dumper.represent_scalar(
            "tag:yaml.org,2002:float", f"{value:g}")

    CustomDumper.add_representer(float, float_representer)

    with open(YAML_PATH, "w") as f:
        f.write("# SSOT — Single Source of Truth: Parametros del Gemelo Digital\n")
        f.write(f"# Generado por init_project.py el {date.today()}\n")
        f.write("# Regenerar derivados: python3 tools/generate_params.py\n\n")
        yaml.dump(cfg, f, Dumper=CustomDumper, default_flow_style=False,
                  allow_unicode=True, sort_keys=False)

    info(f"Escrito: {YAML_PATH}")

    # ── Step 7: Propagate ──
    print()
    info("Propagando a params.h y params.py...")
    result = subprocess.run(
        [sys.executable, str(GENERATOR)],
        capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(f"  ERROR en propagacion:\n{result.stderr}")
        sys.exit(1)

    banner("PROYECTO CONFIGURADO")
    print(f"  Dominio:  {domain_key}")
    print(f"  Config:   config/params.yaml")
    print(f"  Header:   src/firmware/params.h")
    print(f"  Python:   src/physics/params.py")
    print(f"\n  Siguiente paso: revisa config/params.yaml y ajusta valores avanzados.")
    print(f"  Para re-propagar: python3 tools/generate_params.py")
    print()


if __name__ == "__main__":
    main()
