#!/usr/bin/env python3
"""
tools/shadow_audit_sweep.py — Protocolo de Certificación Metrológica V1
═══════════════════════════════════════════════════════════════════════════
Ejecuta un barrido de 5 frecuencias armónicas puras sobre el emulador
de Arduino y verifica si el Scientific Narrator (FFT Skill) detecta
cada una dentro del umbral de tolerancia del 5%.

NO requiere hardware real. Opera sobre el PTY virtual + CSV.
"""
import subprocess
import sys
import time
import os
import math
import numpy as np
import pandas as pd
from pathlib import Path

# Añadir la raíz al path para el import config.paths
sys.path.append(str(Path(__file__).resolve().parent.parent))
from config.paths import get_processed_data_dir, get_drafts_dir

# ─── Configuración del Barrido ─────────────────────────────────────────
FREQUENCIES_TO_TEST = [2.0, 5.2, 8.0, 12.0, 18.0]
TOLERANCE_PCT = 5.0         # Umbral de aprobación < 5%
DT_SIMULATION = 0.01        # dt del params.yaml (100 Hz de muestreo)

def _run_battle_with_freq(f_hz: float, timeout: int = 45) -> bool:
    """Ejecuta el ciclo E2E completo a una frecuencia dada y espera al CSV."""
    csv_path = get_processed_data_dir() / "latest_abort.csv"
    
    # Borrar CSV anterior para no reusar datos viejos
    if csv_path.exists():
        csv_path.unlink()
    
    print(f"\n  ► Disparando Emulador+Bridge a {f_hz:.1f} Hz (timeout={timeout}s)...")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent)
    
    proc = subprocess.Popen(
        ["bash", "tools/run_battle_freq.sh", str(f_hz)],
        cwd=str(Path(__file__).resolve().parent.parent),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env=env
    )
    
    # Esperar hasta que el CSV aparezca (señal de que termino el análisis)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if csv_path.exists() and csv_path.stat().st_size > 100:
            break
        time.sleep(0.5)
    
    proc.terminate()
    proc.wait()
    return csv_path.exists()

def _extract_dominant_frequency(csv_path: Path) -> float:
    """FFT sobre la señal de aceleración con dt teórico del SSOT.
    
    NOTA CRÍTICA: Se usa el dt teórico de params.yaml (0.01s = 100 Hz) 
    y no el dt empírico del timestamp del CSV para evitar el sesgo del 
    jitter del PTY virtual (los timestamps heredan la variabilidad
    del reloj S.O. en milisegundos, que es desproporcionado a altas frecuencias).
    """
    if not csv_path.exists() or csv_path.stat().st_size < 100:
        return 0.0
    try:
        df = pd.read_csv(csv_path)
        if len(df) < 10:
            return 0.0
        signal = df['accel_g'].values
        signal = signal - np.mean(signal)  # Remover DC
        # Ventana de Hann para reducir Spectral Leakage
        window = np.hanning(len(signal))
        signal_w = signal * window
        # FFT con dt teórico del SSOT (100 Hz nominal)
        fft_vals = np.fft.rfft(signal_w)
        fft_freq = np.fft.rfftfreq(len(signal_w), d=DT_SIMULATION)
        # Ignorar bin DC (idx=0)
        amps = np.abs(fft_vals[1:])
        freqs = fft_freq[1:]
        dom_idx = np.argmax(amps)
        return float(freqs[dom_idx])
    except Exception as e:
        print(f"    ❌ FFT Error: {e}")
        return 0.0

def run_sweep():
    print("═" * 60)
    print("🔬 PROTOCOLO DE CERTIFICACIÓN METROLÓGICA V1")
    print("   Shadow Audit Sweep — Stack Bélico")
    print("═" * 60)
    
    results = []
    csv_path = get_processed_data_dir() / "latest_abort.csv"
    
    for f_hz in FREQUENCIES_TO_TEST:
        print(f"\n[SWEEP] Prueba: f_inyectada = {f_hz:.1f} Hz")
        
        ok = _run_battle_with_freq(f_hz)
        if not ok:
            print(f"  ⚠️  CSV no generado. Omitiendo...")
            results.append({
                "f_inyectada": f_hz, "f_detectada": None,
                "error_pct": None, "estado": "ERROR"
            })
            continue
        
        f_det = _extract_dominant_frequency(csv_path)
        if f_det == 0.0:
            results.append({
                "f_inyectada": f_hz, "f_detectada": 0.0,
                "error_pct": 100.0, "estado": "FAIL"
            })
            continue
        
        error_pct = abs(f_hz - f_det) / f_hz * 100
        estado = "PASS ✅" if error_pct < TOLERANCE_PCT else "FAIL ❌"
        
        print(f"  → f_detectada: {f_det:.2f} Hz | Error: {error_pct:.1f}% | {estado}")
        results.append({
            "f_inyectada": f_hz, "f_detectada": round(f_det, 2),
            "error_pct": round(error_pct, 1), "estado": estado
        })
    
    # ─── Tabla de Calibración ──────────────────────────────────────────
    print("\n" + "═" * 60)
    print("📋 TABLA DE CALIBRACIÓN — INSTRUMENTO BÉLICO")
    print("═" * 60)
    print(f"{'f_inyectada':>14} {'f_detectada':>13} {'Error (%)':>10} {'Estado':>12}")
    print("─" * 60)
    for r in results:
        fd  = f"{r['f_detectada']:.2f} Hz" if r['f_detectada'] is not None else "N/A"
        ep  = f"{r['error_pct']:.1f}%" if r['error_pct'] is not None else "N/A"
        print(f"{r['f_inyectada']:>12.1f} Hz {fd:>13} {ep:>10} {r['estado']:>12}")
    
    # Estadísticas globales
    validos = [r for r in results if r['error_pct'] is not None and r['estado'] != "ERROR"]
    if validos:
        errores = [r['error_pct'] for r in validos]
        promedio = np.mean(errores)
        std      = np.std(errores)
        aprobados = sum(1 for r in validos if "PASS" in r['estado'])
        print("─" * 60)
        print(f"  Promedio Error: {promedio:.1f}% | σ: {std:.1f}% | Aprobados: {aprobados}/{len(validos)}")
        print("═" * 60)
    
    # ─── Reporte Markdown ──────────────────────────────────────────────
    report_path = get_drafts_dir() / "calibration_certificate.md"
    lines = ["# 📜 Certificado de Calibración Metrológica V1\n",
             "**Sistema:** Stack Bélico v1.0 — Scientific Narrator (FFT Skill)\n",
             f"**Fecha:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}\n",
             "**Tolerancia:** < 5% de error relativo\n\n",
             "| f_inyectada | f_detectada | Error (%) | Estado |\n",
             "|---|---|---|---|\n"]
    for r in results:
        fd = f"{r['f_detectada']:.2f} Hz" if r['f_detectada'] is not None else "N/A"
        ep = f"{r['error_pct']:.1f}%" if r['error_pct'] is not None else "N/A"
        lines.append(f"| {r['f_inyectada']:.1f} Hz | {fd} | {ep} | {r['estado']} |\n")
    if validos:
        lines.append(f"\n**Error Promedio:** {promedio:.1f}% | **σ:** {std:.1f}%\n")
    
    report_path.write_text("".join(lines), encoding="utf-8")
    print(f"\n✅ Certificado guardado en: {report_path}")
    return results

if __name__ == "__main__":
    run_sweep()
