#!/usr/bin/env python3
"""
tools/blind_comparative_test.py — Fase 26: Test Ciego de Soberanía del Dato
═══════════════════════════════════════════════════════════════════════════════
Genera 3 señales sintéticas sin etiqueta y desafía al motor FFT a ordenarlas
de mayor a menor rigidez usando ÚNICAMENTE la frecuencia dominante detectada.

El Narrador NO sabe qué señal corresponde a qué estado estructural.
Si el orden recuperado coincide con la realidad física, el sistema es agnóstico
y la evidencia es soberana (no circular).

Señales inyectadas (ocultas al test):
  Señal X: fn = 8.00 Hz → estructura SANA (k nominal)
  Señal Y: fn = 7.59 Hz → MICRO-DAÑO LEVE (k-10%, fn*sqrt(0.9)=7.589)
  Señal Z: fn = 6.20 Hz → DAÑO CRÍTICO (k-40%, fn*sqrt(0.6)=6.197)

Tolerancia de detección: Δf < 0.30 Hz por señal (resolución = 0.10 Hz con T=10s)
"""
import sys
import random
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime

_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(_ROOT))
from config.paths import get_processed_data_dir, get_drafts_dir
from src.physics.params import SAMPLE_RATE_HZ

# ─── Configuración ─────────────────────────────────────────────────────────────
FS           = float(SAMPLE_RATE_HZ)  # From SSOT via params.py
T_SIGNAL     = 10.0     # segundos — Δf = 0.10 Hz (suficiente para resolver 0.26 Hz)
NOISE_RATIO  = 0.10     # ±10% ruido Gaussiano (realista para sensor de campo)
AMPLITUDE    = 0.12     # g — vibracion de servicio, no resonancia

# ─── FN_NOMINAL desde SSOT ────────────────────────────────────────────────────
def _load_fn_nominal() -> float:
    """Load nominal structural frequency from config/params.yaml (SSOT)."""
    try:
        import yaml as _yaml
        _cfg = _yaml.safe_load((_ROOT / "config" / "params.yaml").read_text(encoding="utf-8")) or {}
    except FileNotFoundError:
        print("[ERROR] blind_comparative_test: config/params.yaml not found.", file=sys.stderr)
        sys.exit(1)
    except Exception as _e:  # yaml.YAMLError or OSError
        print(f"[ERROR] blind_comparative_test: cannot read params.yaml: {_e}", file=sys.stderr)
        sys.exit(1)
    _fn = _cfg.get("structure", {}).get("fn_hz", {}).get("value")
    if _fn is None:
        print("[ERROR] blind_comparative_test: SSOT missing 'structure.fn_hz.value'", file=sys.stderr)
        sys.exit(1)
    return float(_fn)


# Señales reales (no expuestas al motor hasta el final)
FN_NOMINAL   = _load_fn_nominal()          # Hz — estructura sana, from SSOT
FN_LEVE      = FN_NOMINAL * np.sqrt(0.90)  # k-10%
FN_CRITICO   = FN_NOMINAL * np.sqrt(0.60)  # k-40%

def _generate_csv(fn: float, path: Path) -> None:
    t      = np.arange(0, T_SIGNAL, 1.0 / FS)
    signal = AMPLITUDE * np.sin(2 * np.pi * fn * t)
    # Armónico secundario (realista — las estructuras no son puramente lineales)
    signal += (AMPLITUDE * 0.15) * np.sin(2 * np.pi * fn * 2 * t)
    signal += np.random.normal(0, AMPLITUDE * NOISE_RATIO, len(t))
    df = pd.DataFrame({"time_s": t, "accel_g": signal,
                       "stress_mpa": [0.0]*len(t), "innovation_g": [0.0]*len(t)})
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(path, index=False)
    except OSError as e:
        print(f"[ERROR] Cannot write {path}: {e}", file=sys.stderr)
        raise

def _fft_dominant(path: Path) -> float:
    df     = pd.read_csv(path)
    signal = df['accel_g'].values - np.mean(df['accel_g'].values)
    window = np.hanning(len(signal))
    fft    = np.fft.rfft(signal * window)
    freq   = np.fft.rfftfreq(len(signal), d=1.0/FS)
    amps   = np.abs(fft[1:]); freqs = freq[1:]
    return float(freqs[np.argmax(amps)])

def run_blind_test():
    proc_dir = get_processed_data_dir()
    out_dir  = get_drafts_dir()

    print("═" * 64)
    print("🕵️  BLIND COMPARATIVE TEST — Soberanía del Dato")
    print(f"   T={T_SIGNAL}s | fs={FS}Hz | Ruido={int(NOISE_RATIO*100)}% | Δf={1/T_SIGNAL:.2f}Hz")
    print("═" * 64)

    # 1. Generar 3 CSVs con IDs anónimos (aleatorizar orden para el test)
    real = {"X": FN_NOMINAL, "Y": FN_LEVE, "Z": FN_CRITICO}
    paths = {k: proc_dir / f"blind_{k}.csv" for k in real}
    for key, fn in real.items():
        _generate_csv(fn, paths[key])

    # 2. El motor FFT analiza SOLO los archivos — sin saber qué es cada uno
    print("\n📡 Analizando señales anónimas...")
    detected = {}
    for key, path in paths.items():
        detected[key] = _fft_dominant(path)
        print(f"   Señal {key}: fn_detectada = {detected[key]:.2f} Hz")

    # 3. El motor ordena por frecuencia (mayor fn = mayor rigidez)
    ranking_detectado = sorted(detected.items(), key=lambda x: -x[1])
    ranking_real      = sorted(real.items(),     key=lambda x: -x[1])

    print("\n📋 Ranking detectado (sin etiquetas):")
    for i, (k, f) in enumerate(ranking_detectado):
        print(f"   #{i+1} → Señal {k}: {f:.2f} Hz")

    print("\n📋 Ranking real (oculto al test):")
    for i, (k, f) in enumerate(ranking_real):
        print(f"   #{i+1} → Señal {k}: {f:.2f} Hz  ← fn real: {real[k]:.3f} Hz")

    # 4. Verificar error por señal
    print("\n📐 Verificación de precisión:")
    TOLERANCIA = 0.30  # Hz — 3 bins de resolución
    all_pass = True
    rows = []
    for key in real:
        f_real = real[key]
        f_det  = detected[key]
        error  = abs(f_real - f_det)
        estado = "PASS ✅" if error <= TOLERANCIA else "FAIL ❌"
        if error > TOLERANCIA:
            all_pass = False
        print(f"   Señal {key}: real={f_real:.3f}Hz | detectada={f_det:.2f}Hz | Δ={error:.3f}Hz | {estado}")
        rows.append({"Señal": key, "fn_real (Hz)": f_real, "fn_detectada (Hz)": f_det,
                     "Error (Hz)": round(error, 3), "Estado": estado})

    # 5. Verificar si el ranking fue correcto
    orden_correcto = ([k for k, _ in ranking_detectado] ==
                      [k for k, _ in ranking_real])
    veredicto_orden = "✅ CORRECTO" if orden_correcto else "❌ INCORRECTO"

    print(f"\n🏁 Orden de rigidez recuperado: {veredicto_orden}")
    print(f"   {'✅ LA IA ORDENÓ CORRECTAMENTE: mayor→menor rigidez sin etiquetas.' if orden_correcto else '❌ El orden no coincide con la realidad física.'}")
    veredicto_final = "✅ SOBERANÍA DEL DATO CONFIRMADA" if (all_pass and orden_correcto) else "⚠️ VERIFICACIÓN INCOMPLETA"
    print(f"\n   {veredicto_final}")
    print("═" * 64)

    # 6. Reporte Markdown
    ts = datetime.now().strftime('%Y-%m-%d %H:%M')
    report = (
        f"# 🕵️ Blind Comparative Test — Soberanía del Dato\n\n"
        f"**Fecha:** {ts} | **T:** {T_SIGNAL}s | **fs:** {FS}Hz | **Ruido:** {int(NOISE_RATIO*100)}% Gaussiano | **Δf:** {1/T_SIGNAL:.2f}Hz\n\n"
        f"El motor FFT recibió 3 archivos CSV anónimos y debía ordenarlos de mayor a menor rigidez **sin etiquetas**.\n\n"
        f"| Señal | fn_real (Hz) | fn_detectada (Hz) | Error (Hz) | Estado |\n"
        f"|---|---|---|---|---|\n"
    )
    for r in rows:
        report += f"| {r['Señal']} | {r['fn_real (Hz)']:.3f} | {r['fn_detectada (Hz)']:.2f} | {r['Error (Hz)']:.3f} | {r['Estado']} |\n"

    report += f"\n**Orden recuperado:** {' → '.join(k for k,_ in ranking_detectado)}\n"
    report += f"**Orden real:**       {' → '.join(k for k,_ in ranking_real)}\n"
    report += f"\n**Veredicto de orden:** {veredicto_orden}  \n**{veredicto_final}**\n"
    report += (
        f"\n> **Nota:** Las señales X, Y, Z corresponden a:\n"
        f"> - **X** = Estructura Sana (fn={FN_NOMINAL:.2f} Hz, k nominal)\n"
        f"> - **Y** = Micro-Daño Leve (fn={FN_LEVE:.3f} Hz, k-10%)\n"
        f"> - **Z** = Daño Crítico (fn={FN_CRITICO:.3f} Hz, k-40%)\n"
        f"> Esta correspondencia es revelada DESPUÉS del test para proteger la independencia de la evidencia.\n"
    )

    rpath = out_dir / "blind_test_report.md"
    try:
        rpath.write_text(report, encoding="utf-8")
    except OSError as e:
        print(f"[ERROR] Cannot write report {rpath}: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"\n✅ Reporte guardado en: {rpath}")

if __name__ == "__main__":
    random.seed()
    run_blind_test()
