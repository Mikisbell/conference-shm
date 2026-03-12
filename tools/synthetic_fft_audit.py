#!/usr/bin/env python3
"""
tools/synthetic_fft_audit.py — Protocolo de Certificación Metrológica V1 (Audit Sintético)
════════════════════════════════════════════════════════════════════════════════════════════
Valida el algoritmo FFT del Scientific Narrator de forma aislada, sin depender
del canal PTY (que introduce jitter de reloj). Genera un CSV sintético de 10 
segundos con señal armónica pura + ruido gaussiano al 10% para simular la 
respuesta de un sensor real, luego verifica que la FFT detecte la frecuencia
con Error < 5%.
"""
import sys
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime

sys.path.append(str(Path(__file__).resolve().parent.parent))
from config.paths import get_processed_data_dir, get_drafts_dir
from src.physics.params import SAMPLE_RATE_HZ

# ─── Configuración ────────────────────────────────────────────────────────────
FREQUENCIES_TO_TEST  = [2.0, 5.2, 8.0, 12.0, 18.0]
TOLERANCE_PCT        = 5.0      # Umbral de aprobación
FS                   = float(SAMPLE_RATE_HZ)  # From SSOT via params.py
T_SIGNAL             = 10.0     # Segundos de señal sintética
NOISE_RATIO          = 0.10     # ±10% de ruido gaussiano sobre la amplitud
AMPLITUDE            = 1.0      # g (máximo del sensor)

# Synthetic stress column — metrological test artifact, not a physics parameter.
# Values are arbitrary placeholders to complete the CSV schema; the FFT audit
# only reads accel_g. Not to be used in any simulation or paper.
_SYNTH_STRESS_BASE_PA  = 180e6  # Pa — nominal stress level (test scaffold only)
_SYNTH_STRESS_SCALE_PA = 15e6   # Pa/g — linear scaling factor (test scaffold only)

def _generate_synthetic_csv(f_hz: float, csv_path: Path) -> None:
    """Genera un CSV de señal armónica pura con ruido gaussiano."""
    t = np.arange(0, T_SIGNAL, 1.0 / FS)
    signal = AMPLITUDE * np.sin(2 * np.pi * f_hz * t)
    noise  = np.random.normal(0, AMPLITUDE * NOISE_RATIO, len(t))
    accel  = signal + noise
    # Stress sintético proporcional (no relevante para FFT, pero completa el CSV)
    stress = _SYNTH_STRESS_BASE_PA + accel * _SYNTH_STRESS_SCALE_PA
    df = pd.DataFrame({
        "time_s":      t,
        "accel_g":     accel,
        "stress_mpa":  stress / 1e6,
        "innovation_g": noise
    })
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(csv_path, index=False)

def _extract_dominant_frequency(csv_path: Path) -> float:
    """FFT con ventana de Hann y dt teórico del SSOT (100 Hz)."""
    df = pd.read_csv(csv_path)
    signal = df['accel_g'].values - np.mean(df['accel_g'].values)
    window = np.hanning(len(signal))
    fft_vals = np.fft.rfft(signal * window)
    fft_freq = np.fft.rfftfreq(len(signal), d=1.0/FS)
    amps = np.abs(fft_vals[1:])
    freqs = fft_freq[1:]
    return float(freqs[np.argmax(amps)])

def run_synthetic_audit():
    csv_path = get_processed_data_dir() / "synth_audit.csv"
    
    print("═" * 62)
    print("🔬 PROTOCOLO DE CERTIFICACIÓN METROLÓGICA V1 — AUDIT SINTÉTICO")
    print(f"   T={T_SIGNAL}s | fs={FS}Hz | Ruido={int(NOISE_RATIO*100)}% Gaussiano")
    print("═" * 62)
    
    results = []
    for f_hz in FREQUENCIES_TO_TEST:
        _generate_synthetic_csv(f_hz, csv_path)
        f_det = _extract_dominant_frequency(csv_path)
        error_pct = abs(f_hz - f_det) / f_hz * 100
        estado    = "PASS ✅" if error_pct < TOLERANCE_PCT else "FAIL ❌"
        print(f"  {f_hz:>5.1f} Hz → {f_det:>5.2f} Hz | Error: {error_pct:>5.1f}% | {estado}")
        results.append({"f_inyectada": f_hz, "f_detectada": round(f_det, 2),
                         "error_pct": round(error_pct, 1), "estado": estado})
    
    # ─── Estadísticas ─────────────────────────────────────────────────────────
    errores   = [r['error_pct'] for r in results]
    promedio  = np.mean(errores)
    std       = np.std(errores)
    aprobados = sum(1 for r in results if "PASS" in r['estado'])
    
    print("─" * 62)
    print(f"  Error Promedio: {promedio:.2f}% | σ: {std:.2f}% | Aprobados: {aprobados}/{len(results)}")
    veredicto = "✅ INSTRUMENTO VALIDADO" if aprobados == len(results) else f"⚠️ {aprobados}/{len(results)} PASS"
    print(f"  Veredicto: {veredicto}")
    print("═" * 62)
    
    # ─── Certificado Markdown ─────────────────────────────────────────────────
    cert_path = get_drafts_dir() / "calibration_certificate.md"
    ts = datetime.now().strftime('%Y-%m-%d %H:%M')
    lines = [
        "# 📜 Certificado de Calibración Metrológica V1\n\n",
        f"**Sistema:** Stack Bélico v1.0 — Scientific Narrator (FFT Skill)  \n",
        f"**Fecha:** {ts}  \n",
        f"**Condiciones:** Señal sintética {T_SIGNAL}s · fs={FS}Hz · Ruido={int(NOISE_RATIO*100)}% Gaussiano  \n",
        f"**Tolerancia:** Error relativo < {TOLERANCE_PCT}%  \n\n",
        "| f_inyectada | f_detectada | Error (%) | Estado |\n",
        "|---|---|---|---|\n"
    ]
    for r in results:
        lines.append(f"| {r['f_inyectada']:.1f} Hz | {r['f_detectada']:.2f} Hz | {r['error_pct']:.1f}% | {r['estado']} |\n")
    lines.append(f"\n**Error Promedio:** {promedio:.2f}% | **σ:** {std:.2f}% | **{veredicto}**\n")
    lines.append(f"\n> **Nota metodológica:** Este certificado valida el algoritmo FFT del Scientific Narrator de forma aislada.\n")
    lines.append(f"> El entorno PTY virtual tiene una ventana máxima de ~0.6s (Δf=1.67Hz), insuficiente para frecuencias > 5Hz.\n")
    lines.append(f"> Con hardware Arduino real a {int(FS)}Hz continuo, la resolución espectral es `Δf={1/T_SIGNAL:.2f}Hz` — rango operativo completo.\n")
    
    try:
        cert_path.parent.mkdir(parents=True, exist_ok=True)
        cert_path.write_text("".join(lines), encoding="utf-8")
    except OSError as e:
        print(f"[ERROR] Cannot write certificate {cert_path}: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"\n✅ Certificado final guardado en: {cert_path}")
    return aprobados, len(results), promedio

if __name__ == "__main__":
    run_synthetic_audit()
