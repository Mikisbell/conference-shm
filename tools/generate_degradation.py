"""
Generate Degradation — Generador de datasets sinteticos de degradacion estructural para entrenamiento LSTM.

Simula la vida util de N modulos estructurales mediante un proceso de caminata aleatoria
(Wiener process) con deriva negativa en frecuencia natural (fn_hz) y positiva en
conductividad termica (k_term), incluyendo estacionalidad termica/humedad anual. Parametros
iniciales y umbrales criticos derivados del SSOT. Produce CSV con columnas de series
temporales y etiqueta de Time-To-Failure (ttf_days) para entrenamiento supervisado.

Pipeline: COMPUTE C4 (generacion de datos sinteticos antes de entrenamiento LSTM)
CLI: python3 tools/generate_degradation.py --modules N --out data/synthetic/degradation_history.csv
Depende de: config/params.yaml (SSOT — k, mass_m, thermal_conductivity)
Produce: data/synthetic/degradation_history.csv (input de src/ai/lstm_predictor.py)
"""
import argparse
import sys
from pathlib import Path

try:
    import numpy as np
except ImportError:
    print("[DEGRADATION] numpy not installed. Run: pip install numpy", file=sys.stderr)
    sys.exit(1)

try:
    import pandas as pd
except ImportError:
    print("[DEGRADATION] pandas not installed. Run: pip install pandas", file=sys.stderr)
    sys.exit(1)

try:
    import yaml
except ImportError:
    print("[DEGRADATION] PyYAML not installed. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.paths import get_params_file


def _load_ssot() -> dict:
    params_path = get_params_file()
    try:
        with open(params_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        print(f"[DEGRADATION] ERROR: params.yaml not found at {params_path}"
              " — run: python3 tools/generate_params.py", file=sys.stderr)
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"[DEGRADATION] ERROR: params.yaml malformed: {e}", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"[DEGRADATION] ERROR: cannot read params.yaml: {e}", file=sys.stderr)
        sys.exit(1)


def simulate_degradation_module(module_id, base_damage_rate, initial_fn, initial_k_term,
                        critical_fn, critical_k_term, months_max=120,
                        samples_per_month=30):
    """
    Simulate the life of a structural module.
    Degradation uses a Random Walk (Wiener process) with negative drift
    for fn and positive drift for k_term.
    """
    time_series = []
    current_fn = initial_fn
    current_k = initial_k_term

    # Manufacturing variability (75% recycled aggregate heterogeneity)
    module_resilience = np.random.normal(1.0, 0.15)

    for month in range(1, months_max + 1):
        for day in range(1, samples_per_month + 1):
            total_day = (month - 1) * samples_per_month + day

            temp_ext = 25.0 + 10.0 * np.sin(2 * np.pi * total_day / 365.0) + np.random.normal(0, 2)
            temp_int = 22.0 + 2.0 * np.sin(2 * np.pi * total_day / 365.0) + np.random.normal(0, 0.5)
            humedad = 60.0 + 20.0 * np.sin(2 * np.pi * total_day / 365.0 + np.pi / 2) + np.random.normal(0, 5)

            stress_factor = (temp_ext / 30.0) * (humedad / 80.0)

            fn_drop = np.random.exponential(base_damage_rate * stress_factor / module_resilience)
            current_fn -= fn_drop

            k_rise = np.random.exponential((base_damage_rate * 0.05) * stress_factor / module_resilience)
            current_k += k_rise

            failed = current_fn < critical_fn or current_k > critical_k_term

            time_series.append({
                "module_id": module_id,
                "month": month,
                "day": day,
                "fn_hz": current_fn,
                "k_term": current_k,
                "tmp_ext": temp_ext,
                "tmp_int": temp_int,
                "hum": humedad,
                "state": "FAILED" if failed else "OK",
            })

            if failed:
                break

        if current_fn < critical_fn or current_k > critical_k_term:
            break

    df = pd.DataFrame(time_series)
    total_life_days = len(df)
    df["ttf_days"] = total_life_days - np.arange(1, total_life_days + 1)
    return df


def generate_dataset(num_modules, output_path):
    cfg = _load_ssot()

    # Read from SSOT
    _k_raw = cfg.get("structure", {}).get("stiffness_k", {}).get("value")
    _m_raw = cfg.get("structure", {}).get("mass_m", {}).get("value")
    _k_term_raw = cfg.get("material", {}).get("thermal_conductivity", {}).get("value")
    for _name, _val in (
        ("structure.stiffness_k.value", _k_raw),
        ("structure.mass_m.value", _m_raw),
        ("material.thermal_conductivity.value", _k_term_raw),
    ):
        if _val is None:
            print(f"[DEGRADATION] ERROR: SSOT missing key '{_name}' in config/params.yaml",
                  file=sys.stderr)
            sys.exit(1)
    k = float(_k_raw)
    m = float(_m_raw)
    k_term = float(_k_term_raw)

    # Derived initial fn from SSOT
    import math
    initial_fn = math.sqrt(k / m) / (2.0 * math.pi)

    # Critical thresholds from SSOT (no hardcoded literals)
    _fn_ratio_raw = (cfg.get("firmware", {}).get("edge_alarms", {})
                     .get("fn_drop_crit_ratio", {}).get("value"))
    _kt_ratio_raw = (cfg.get("firmware", {}).get("thresholds", {})
                     .get("k_term_crit_ratio", {}).get("value"))
    for _name, _val in (
        ("firmware.edge_alarms.fn_drop_crit_ratio.value", _fn_ratio_raw),
        ("firmware.thresholds.k_term_crit_ratio.value", _kt_ratio_raw),
    ):
        if _val is None:
            print(f"[DEGRADATION] ERROR: SSOT missing key '{_name}' in config/params.yaml",
                  file=sys.stderr)
            sys.exit(1)
    fn_drop_crit_ratio = float(_fn_ratio_raw)
    k_term_crit_ratio = float(_kt_ratio_raw)
    critical_fn = initial_fn * fn_drop_crit_ratio
    critical_k_term = k_term * k_term_crit_ratio

    print(f"[DEGRADATION] SSOT loaded:")
    print(f"  initial_fn={initial_fn:.3f}Hz  critical_fn={critical_fn:.3f}Hz")
    print(f"  initial_k_term={k_term}  critical_k_term={critical_k_term}")
    print(f"  Generating {num_modules} modules...")

    all_data = []

    for i in range(1, num_modules + 1):
        base_rate = np.random.uniform(0.001, 0.005)
        df_module = simulate_degradation_module(
            f"MOD-{i:04d}", base_rate,
            initial_fn=initial_fn,
            initial_k_term=k_term,
            critical_fn=critical_fn,
            critical_k_term=critical_k_term,
        )
        all_data.append(df_module)

        if i % 100 == 0:
            print(f"  Simulated {i}/{num_modules} modules...")

    if not all_data:
        print("[DEGRADATION] ERROR: no modules were simulated — check --modules argument",
              file=sys.stderr)
        sys.exit(1)
    final_df = pd.concat(all_data, ignore_index=True)

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        final_df.to_csv(output_file, index=False)
    except OSError as e:
        print(f"[DEGRADATION] ERROR: cannot write {output_file}: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"\n[DEGRADATION] Dataset complete.")
    print(f"  Total samples: {len(final_df)}")
    print(f"  Output: {output_file}")
    print(f"  Shortest life: {final_df.groupby('module_id')['ttf_days'].max().min()} days")
    print(f"  Longest life: {final_df.groupby('module_id')['ttf_days'].max().max()} days")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Degradation Emulator (LSTM Training Data)")
    parser.add_argument("--modules", type=int, default=1000)
    parser.add_argument("--out", type=str, default="data/synthetic/degradation_history.csv")
    args = parser.parse_args()

    generate_dataset(args.modules, args.out)
