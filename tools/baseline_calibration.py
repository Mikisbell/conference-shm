#!/usr/bin/env python3
"""
tools/baseline_calibration.py — Calibración de Línea Base del Nodo de Campo
═══════════════════════════════════════════════════════════════════════════════
Ejecutar el PRIMER DÍA en your monitoring site, antes de cualquier medición.

Procedimiento:
  1. Instala el nodo Nicla+E32 en la columna de referencia.
  2. No toques la estructura durante 30 minutos.
  3. Este script escucha los paquetes LoRa y calcula el "silencio real"
     del lugar: la vibración ambiente de fondo (tráfico, viento, maquinaria).
  4. Los valores calculados se guardan en config/field_baseline.yaml
     y el Guardian Angel los carga como referencia para esa instalación.

Uso:
  python3 tools/baseline_calibration.py --port /dev/ttyUSB0 --duration 1800
"""

import argparse
import time
import sys
import statistics
from pathlib import Path

try:
    import yaml
except ImportError:
    print("[ERROR] PyYAML not installed. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

try:
    import serial
except ImportError:
    print("[ERROR] pyserial not installed. Run: pip install pyserial", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from src.physics.bridge import parse_packet

BASELINE_OUTPUT = ROOT / "config" / "field_baseline.yaml"

_GUARDIAN_SIGMA_THRESHOLD = 3    # dimensionless — 3σ confidence interval (Gauss, classical statistics)
_DRY_RUN_FN_BASE_HZ    = 8.0    # Hz — approximate fn for dry-run synthetic data (nominal RC structure)
_DRY_RUN_TMP_BASE_C    = 24.0   # °C — nominal ambient temperature for dry-run synthetic data
_DRY_RUN_MAXG_BASE     = 0.04   # g — nominal acceleration amplitude for dry-run synthetic data
_DRY_RUN_RSSI_DBM      = -85    # dBm — typical indoor LoRa RSSI for dry-run synthetic data

def collect_baseline(port: str, baud: int, duration_s: int, dry_run: bool = False):
    fn_samples   = []
    tmp_samples  = []
    maxg_samples = []
    rssi_samples = []

    print("=" * 60)
    print("  BELICO STACK — Calibración de Línea Base de Campo")
    print("=" * 60)

    if dry_run:
        print("  [DRY RUN] Generando baseline SINTÉTICO (NO usar como datos reales)...")
        print("  ⚠️  Estos valores son SOLO para testing del pipeline, no para calibración.")
        fn_samples   = [_DRY_RUN_FN_BASE_HZ + (i * 0.01) for i in range(20)]
        tmp_samples  = [_DRY_RUN_TMP_BASE_C + (i * 0.05) for i in range(20)]
        maxg_samples = [_DRY_RUN_MAXG_BASE + (i * 0.001) for i in range(20)]
        rssi_samples = [_DRY_RUN_RSSI_DBM] * 20
    else:
        print(f"  Escuchando en {port} durante {duration_s}s ({duration_s//60} min)...")
        print("  NO tocar la estructura durante este tiempo.\n")

        deadline = time.time() + duration_s
        try:
            with serial.Serial(port, baud, timeout=5) as ser:
                while time.time() < deadline:
                    remaining = int(deadline - time.time())
                    raw = ser.readline().decode(errors='ignore').strip()
                    if not raw:
                        continue

                    pkt = parse_packet(raw)
                    # pkt["tmp"] can be None if LoRa packet lacked TMP field (see bridge.parse_packet)
                    if pkt and pkt.get("is_lora") and pkt["stat"] in ("OK", "WARN") and pkt.get("tmp") is not None:
                        fn_samples.append(pkt["fn"])
                        tmp_samples.append(pkt["tmp"])
                        maxg_samples.append(pkt["max_g"])
                        rssi_samples.append(pkt.get("rssi", -80))

                        print(f"  [{len(fn_samples):>4} pkts | {remaining:>4}s restantes] "
                              f"fn={pkt['fn']:.2f}Hz  max_g={pkt['max_g']:.3f}  "
                              f"T={pkt['tmp']:.1f}°C  RSSI={pkt.get('rssi','?')}dBm")
        except serial.SerialException as e:
            print(f"\n  ❌ Error de puerto: {e}")
            sys.exit(1)

    if len(fn_samples) < 5:
        print("\n  ❌ Datos insuficientes. Verificar conexión del nodo.")
        sys.exit(1)

    # Calcular estadísticas de baseline
    baseline = {
        "site": "",
        "calibration_date": time.strftime("%Y-%m-%d %H:%M"),
        "samples_n": len(fn_samples),
        "fn_baseline_hz":         round(statistics.mean(fn_samples), 3),
        "fn_std_hz":              round(statistics.stdev(fn_samples) if len(fn_samples) > 1 else 0, 3),
        "tmp_ambient_c":          round(statistics.mean(tmp_samples), 1),
        "max_g_ambient":          round(statistics.mean(maxg_samples), 4),
        "max_g_std":              round(statistics.stdev(maxg_samples) if len(maxg_samples) > 1 else 0, 4),
        "rssi_median_dbm":        int(statistics.median(rssi_samples)),
        # Umbrales derivados automáticamente (3σ sobre el ruido de fondo)
        "guardian_fn_tolerance_hz": round(_GUARDIAN_SIGMA_THRESHOLD * (statistics.stdev(fn_samples) if len(fn_samples) > 1 else 0.1), 3),
        "guardian_maxg_threshold":  round(statistics.mean(maxg_samples) + _GUARDIAN_SIGMA_THRESHOLD * (statistics.stdev(maxg_samples) if len(maxg_samples) > 1 else 0.01), 4),
    }

    if dry_run:
        output_path = BASELINE_OUTPUT.parent / "field_baseline_DRYRUN.yaml"
        baseline["_warning"] = "SYNTHETIC DATA — generated by --dry-run, NOT real calibration"
    else:
        output_path = BASELINE_OUTPUT

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            yaml.dump(baseline, f, default_flow_style=False, allow_unicode=True)
    except OSError as e:
        print(f"\n  ❌ Cannot write baseline file {output_path}: {e}", file=sys.stderr)
        sys.exit(1)

    print("\n" + "=" * 60)
    print(f"  ✅ Baseline guardado en: {BASELINE_OUTPUT}")
    print(f"  fn_baseline  = {baseline['fn_baseline_hz']} Hz  (±{baseline['fn_std_hz']} Hz)")
    print(f"  Temperatura  = {baseline['tmp_ambient_c']} °C")
    print(f"  max_g ruido  = {baseline['max_g_ambient']} g  (±{baseline['max_g_std']} g)")
    print(f"  RSSI mediana = {baseline['rssi_median_dbm']} dBm")
    print(f"\n  Umbrales Guardian Angel ajustados al sitio:")
    print(f"  fn_tolerance = ±{baseline['guardian_fn_tolerance_hz']} Hz")
    print(f"  max_g alarm  = {baseline['guardian_maxg_threshold']} g")
    print("=" * 60)

    return baseline

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Calibrador de Línea Base de Campo — Belico Stack")
    parser.add_argument("--port",     default="/dev/ttyUSB0", help="Puerto serial del gateway LoRa")
    parser.add_argument("--baud",     type=int, default=9600)
    parser.add_argument("--duration", type=int, default=1800, help="Duración de calibración en segundos")
    parser.add_argument("--dry-run",  action="store_true",   help="Simular con datos sintéticos")
    args = parser.parse_args()
    collect_baseline(args.port, args.baud, args.duration, dry_run=args.dry_run)
