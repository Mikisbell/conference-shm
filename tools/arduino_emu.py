"""
Arduino Emulator — Emulador de firmware Arduino via PTY (puerto serial virtual del SO).

Crea un Pseudo-Terminal (PTY) que imita el comportamiento del hardware Arduino sin necesidad
de conexion fisica. bridge.py se conecta al PTY sin distinguir si es emulador o hardware real.
Soporta 9 modos: 6 para Nano 33 BLE Sense Rev2 (raw T/A/D @ 100Hz: sano, resonance,
dano_leve, dano_critico, presa, dropout) y 3 para Nicla Sense ME (edge AI FN/PK/ST/CONF
cada 2.56s: nicla_sano, nicla_dano, nicla_critico). Migracion a hardware real = cero cambios.

Pipeline: COMPUTE C3 (emulacion de hardware para validacion del Guardian Angel)
CLI: python3 tools/arduino_emu.py [modo] [fn_hz]
Depende de: config/params.yaml (SSOT — token handshake, dt, fn nominal)
Produce: stream serial via PTY consumido por src/physics/bridge.py
"""
import time
import math
import hashlib
import random
import select
import sys
import pty
import os
from pathlib import Path

try:
    import yaml
except ImportError:
    print("[EMU] PyYAML not installed. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
from config.paths import get_params_file

# ---------------------------------------------------------------------------
# Documented fallback constants — AGENTS.md Rule 12
# Used ONLY when optional SSOT keys are absent (warning logged to stderr).
# ---------------------------------------------------------------------------
_DEFAULT_LEVE_K_RATIO        = 0.90  # k_leve/k_nominal — micro-damage 10% stiffness loss
_DEFAULT_CRITICO_K_RATIO     = 0.60  # k_critico/k_nominal — critical 40% stiffness loss
_DEFAULT_NICLA_DANO_K_RATIO  = 0.75  # k_dano/k_nominal — Nicla moderate damage ~25%
_DEFAULT_NICLA_CRIT_K_RATIO  = 0.55  # k_critico/k_nominal — Nicla critical damage ~45%
_DEFAULT_PRESA_SOIL_FREQ_HZ  = 2.5   # Hz — soft soil predominant frequency (Kanai-Tajimi)
_DEFAULT_PRESA_SOIL_DAMPING  = 0.60  # dimensionless — soft soil damping ratio

_JITTER_STD_MS           = 2     # ms — Gaussian jitter std dev (Arduino serial Tx jitter)
_RESONANCE_AMP_MAX       = 1.5   # dimensionless — resonance amplitude cap (simulation limit)
_RESONANCE_GROWTH_RATE   = 0.1   # per-packet amplitude growth rate in resonance mode
_NICLA_FFT_WINDOW_S      = 2.56  # s — Nicla Sense ME inference window (Edge Impulse DSP default)

# ─────────────────────────────────────────────────────────
# EMULADOR ARDUINO BÉLICO (Ingeniería del Caos)
# ─────────────────────────────────────────────────────────
# Crea un PTY (puerto serial virtual real del SO) y emula el
# firmware de Arduino. bridge.py se conecta sin saber que es virtual.
#
# MODOS DISPONIBLES:
#
#   Nano 33 BLE Sense Rev2 (raw accel @ 100Hz → bridge.py):
#     sano          — vibración nominal, estructura intacta
#     resonance     — frecuencia forzada creciente (activa RL-2)
#     dano_leve     — rigidez -10%, fn cae ~5%
#     dano_critico  — rigidez -40%, fn cae ~37%, amplitud creciente
#     presa         — perfil sísmico Kanai-Tajimi (suelo blando)
#     dropout       — simula desconexión USB abrupta tras 15 paquetes
#
#   Nicla Sense ME (FFT on-board → 1 paquete/2.56s, formato FN/PK/ST/CONF):
#     nicla_sano    — estructura intacta, clasificador: INTACT, conf >0.92
#     nicla_dano    — rigidez -25%, clasificador: DAMAGE, conf 0.78-0.93
#     nicla_critico — rigidez -45%, clasificador: CRITICAL, conf >0.85
#
# Uso: python3 tools/arduino_emu.py [modo] [fn_hz]
#   Ejemplo Nano 33: python3 tools/arduino_emu.py sano 5.2
#   Ejemplo Nicla:   python3 tools/arduino_emu.py nicla_dano 5.2

PARAMS_PATH = get_params_file()


def load_config() -> dict:
    try:
        with open(PARAMS_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        print(f"[EMU] ERROR: params.yaml not found: {PARAMS_PATH}", file=sys.stderr)
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"[EMU] ERROR: params.yaml malformed: {e}", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"[EMU] ERROR: cannot read params.yaml: {e}", file=sys.stderr)
        sys.exit(1)

def run_emulator(chaos_mode="resonance", f_hz=None):
    """
    Crea un PTY (Pseudo-Terminal) y actúa como el Arduino.
    Imprime el nombre del puerto que el bridge.py debe escuchar.
    """
    master, slave = pty.openpty()
    port_name = os.ttyname(slave)
    
    cfg = load_config()
    with open(PARAMS_PATH, 'rb') as f:
        master_hash = hashlib.sha256(f.read()).hexdigest()

    # Load nominal fn from SSOT — required, no fallback
    if f_hz is None:
        _fw = cfg.get("firmware", {}).get("edge_alarms", {})
        _fn_entry = _fw.get("nominal_fn_hz", {})
        f_hz = _fn_entry.get("value") if isinstance(_fn_entry, dict) else _fn_entry
        if f_hz is None:
            print("[EMU] ERROR: SSOT missing 'firmware.edge_alarms.nominal_fn_hz.value'",
                  file=sys.stderr)
            sys.exit(1)

    # Damage state stiffness ratios from SSOT — optional with documented fallbacks
    _ds = cfg.get("firmware", {}).get("damage_states", {})

    def _ds_get(key, default):
        entry = _ds.get(key, {})
        val = entry.get("value") if isinstance(entry, dict) else entry
        if val is None:
            print(f"[EMU] WARNING: SSOT missing 'firmware.damage_states.{key}' "
                  f"— using default {default}", file=sys.stderr)
            return default
        return float(val)

    _leve_k_ratio        = _ds_get("leve_k_ratio",        _DEFAULT_LEVE_K_RATIO)
    _critico_k_ratio     = _ds_get("critico_k_ratio",     _DEFAULT_CRITICO_K_RATIO)
    _nicla_dano_k_ratio  = _ds_get("nicla_dano_k_ratio",  _DEFAULT_NICLA_DANO_K_RATIO)
    _nicla_critico_k_ratio = _ds_get("nicla_critico_k_ratio", _DEFAULT_NICLA_CRIT_K_RATIO)

    # Presa mode soil parameters from SSOT — optional with documented fallbacks
    _presa = cfg.get("presa", {})

    def _presa_get(key, default):
        entry = _presa.get(key, {})
        val = entry.get("value") if isinstance(entry, dict) else entry
        if val is None:
            print(f"[EMU] WARNING: SSOT missing 'presa.{key}' "
                  f"— using default {default}", file=sys.stderr)
            return default
        return float(val)

    _presa_fg = _presa_get("soil_freq_hz",      _DEFAULT_PRESA_SOIL_FREQ_HZ)
    _presa_dg = _presa_get("soil_damping_ratio", _DEFAULT_PRESA_SOIL_DAMPING)

    _temporal = cfg.get("temporal", {})
    _token_entry = _temporal.get("handshake_token", {})
    token = _token_entry.get("value") if isinstance(_token_entry, dict) else _token_entry
    if token is None:
        print("[EMU] ERROR: SSOT missing 'temporal.handshake_token.value'", file=sys.stderr)
        sys.exit(1)
    _dt_entry = _temporal.get("dt_simulation", {})
    _dt_val = _dt_entry.get("value") if isinstance(_dt_entry, dict) else _dt_entry
    if _dt_val is None:
        print("[EMU] ERROR: SSOT missing 'temporal.dt_simulation.value'", file=sys.stderr)
        sys.exit(1)
    dt_ms = int(float(_dt_val) * 1000)
    
    print(f"🔥 [EMULADOR] Iniciando en puerto virtual: {port_name}")
    print(f"🔥 [EMULADOR] Ejecuta en otra terminal: python src/physics/bridge.py {port_name}")
    
    with open(master, 'wb', buffering=0) as m_out, open(master, 'rb', buffering=0) as m_in:
        # 1. Esperar Handshake
        print(f"🔥 [EMULADOR] Esperando Handshake SSOT...")
        while True:
            line = getattr(m_in, 'readline', lambda: os.read(master, 1024))().decode().strip()
            if line.startswith("HANDSHAKE:"):
                parts = line.split(":")
                if len(parts) >= 3 and parts[1] == token and parts[2] == master_hash[:8]:
                    print(f"🔥 [EMULADOR] Recibido Handshake válido. Enviando ACK.")
                    os.write(master, b"ACK_OK\n")
                    break
                else:
                    print(f"🔥 [EMULADOR] Handshake INVALÍDO. Abortando.")
                    os.write(master, b"ACK_FAIL_HASH\n")
                    return
            time.sleep(0.1)

        # 2. Esperar Time Sync
        line = os.read(master, 1024).decode().strip()
        if "TIME_SYNC" in line:
            os.write(master, f"T:{int(time.time()*1000)},A:0.0,D:0.0\n".encode())
            print(f"🔥 [EMULADOR] Time Sync Enviado. Iniciando inyección de datos.")

        # 3. Bucle de Inyección (Caos)
        start_time = time.time()
        packet_count = 0
        
        try:
            while True:
                current_time = time.time()
                elapsed = current_time - start_time
                current_millis = int(current_time * 1000)
                
                # Jitter simulado (ruido temporal)
                jitter = random.normalvariate(0, _JITTER_STD_MS) # Ruido gausiano de +/- 2ms
                time.sleep(max(0, (dt_ms + jitter) / 1000.0))
                
                # --- Escenarios de Inyección ---
                if chaos_mode == "resonance":
                    # Frecuencia forzada paramétrica (supera RL-2)
                    freq = f_hz
                    amplitude = min(_RESONANCE_AMP_MAX, elapsed * _RESONANCE_GROWTH_RATE)  # Crece hasta 1.5g
                    accel = amplitude * math.sin(2 * math.pi * freq * elapsed)
                    accel += random.normalvariate(0, 0.05)

                elif chaos_mode == "sano":
                    # Estructura SANA: vibración de servicio nominal (baseline)
                    # Frecuencia natural alta, amplitudes pequeñas, sin deriva.
                    fn = f_hz  # fn alta = estructura rígida
                    accel  = 0.05 * math.sin(2 * math.pi * fn * elapsed)
                    accel += 0.02 * math.sin(2 * math.pi * 2 * fn * elapsed)  # armónico
                    accel += random.normalvariate(0, 0.01)  # Ruido sensor mínimo

                elif chaos_mode == "dano_leve":
                    # MICRO-DAÑO LEVE: rigidez degradada ~10% → fn cae ~5%
                    # Simula: micro-fisura en zona de máximo momento flector.
                    fn_nominal = f_hz
                    fn_danada  = fn_nominal * math.sqrt(_leve_k_ratio)  # k drop → fn * sqrt(leve_k_ratio)
                    accel  = 0.10 * math.sin(2 * math.pi * fn_danada * elapsed)
                    # Ruido de impacto leve (aceleración de tapping)
                    if int(elapsed * 10) % 30 == 0:
                        accel += random.normalvariate(0, 0.03)
                    accel += random.normalvariate(0, 0.015)

                elif chaos_mode == "dano_critico":
                    # DAÑO CRÍTICO: rigidez degradada ~40% → fn cae ~37%
                    # Simula: fallo por fatiga progresivo en perno / soldadura.
                    # La amplitud crece porque la amortiguación también cae.
                    fn_nominal = f_hz
                    fn_danada  = fn_nominal * math.sqrt(_critico_k_ratio)  # k drop → fn * sqrt(critico_k_ratio)
                    amplitude  = 0.15 + elapsed * 0.02  # Amplitud creciente
                    accel  = amplitude * math.sin(2 * math.pi * fn_danada * elapsed)
                    # Golpes transitorios (emula impacto recurrente de tráfico pesado)
                    if int(elapsed * 20) % 25 == 0:
                        accel += random.normalvariate(0, 0.08)
                    accel += random.normalvariate(0, 0.025)

                elif chaos_mode == "presa":
                    # SEISMIC PROFILE: perfil sísmico tipo Kanai-Tajimi
                    # Simula la excitación basal que recibe la estructura
                    # durante un sismo de baja frecuencia dominante (2-4 Hz).
                    # Los largos periodos son característicos de suelos blandos.
                    fg    = _presa_fg   # Hz - frecuencia predominante del suelo (SSOT)
                    dg    = _presa_dg   # Amortiguamiento del suelo (SSOT)
                    scale = min(0.8, elapsed * 0.05)  # Acelerogramas crescentes
                    # Componente de fondo (ruido estocástico de baja frec)
                    base  = scale * random.normalvariate(0, 0.2)
                    # Componente harmónica de la estructura (modi Kanai-Tajimi simplif.)
                    accel = (base
                             + scale * 0.4 * math.sin(2 * math.pi * fg * elapsed)
                             + scale * 0.2 * math.sin(2 * math.pi * fg * 1.5 * elapsed)
                             + scale * 0.1 * math.sin(2 * math.pi * fg * 3.0 * elapsed))
                    accel += random.normalvariate(0, 0.02)

                elif chaos_mode == "nicla_sano":
                    # NICLA SENSE ME — nodo edge AI, estructura SANA
                    # No envía accel raw. Envía resultado de FFT on-board cada 2.56s
                    # (ventana de 256 muestras @ 100Hz = 1 paquete cada ~2.5s)
                    # Formato: FN:{fn_hz},PK:{peak_g},ST:{estado},CONF:{conf}
                    fn_out   = f_hz + random.normalvariate(0, 0.05)
                    peak_out = 0.05 + random.normalvariate(0, 0.005)
                    conf     = round(random.uniform(0.92, 0.99), 2)
                    packet   = f"FN:{fn_out:.3f},PK:{peak_out:.4f},ST:INTACT,CONF:{conf}\n"
                    os.write(master, packet.encode())
                    time.sleep(_NICLA_FFT_WINDOW_S)  # Nicla emite 1 paquete cada ventana FFT
                    continue

                elif chaos_mode == "nicla_dano":
                    # NICLA SENSE ME — daño moderado detectado on-board
                    # fn cae ~15% (rigidez -25%), clasificador reporta DAMAGE
                    fn_out   = f_hz * math.sqrt(_nicla_dano_k_ratio) + random.normalvariate(0, 0.08)
                    peak_out = 0.18 + random.normalvariate(0, 0.02)
                    conf     = round(random.uniform(0.78, 0.93), 2)
                    packet   = f"FN:{fn_out:.3f},PK:{peak_out:.4f},ST:DAMAGE,CONF:{conf}\n"
                    os.write(master, packet.encode())
                    time.sleep(_NICLA_FFT_WINDOW_S)
                    continue

                elif chaos_mode == "nicla_critico":
                    # NICLA SENSE ME — daño crítico, fn cae >30%, clasificador: CRITICAL
                    fn_out   = f_hz * math.sqrt(_nicla_critico_k_ratio) + random.normalvariate(0, 0.12)
                    peak_out = 0.45 + elapsed * 0.03 + random.normalvariate(0, 0.04)
                    conf     = round(random.uniform(0.85, 0.97), 2)
                    packet   = f"FN:{fn_out:.3f},PK:{peak_out:.4f},ST:CRITICAL,CONF:{conf}\n"
                    os.write(master, packet.encode())
                    time.sleep(_NICLA_FFT_WINDOW_S)
                    continue

                else:  # modo desconocido → ruido blanco
                    accel = random.normalvariate(0, 0.05)

                # Envío de formato crudo (Nano 33)
                packet = f"T:{current_millis},A:{accel:.4f},D:0.00\n"
                os.write(master, packet.encode())
                packet_count += 1
                
                # Desastre simulado (USB desconectado)
                if chaos_mode == "dropout" and packet_count >= 15:
                    print(f"\n🔥 [EMULADOR] 🔌 [SIMULACRO] Cable desconectado abruptamente. Muriendo...")
                    break
                
                # Escuchar comandos abort (SHUTDOWN)
                r, _, _ = select.select([master], [], [], 0)
                if r:
                    command = os.read(master, 1024).decode().strip()
                    if "SHUTDOWN" in command:
                        print(f"\n🔥 [EMULADOR] 🛑 RECIBIDO COMANDO DE ABORTO (SHUTDOWN)!")
                        print(f"🔥 [EMULADOR] La simulación de Fuego Real logró activar el Cortafuegos de Bridge.py")
                        print(f"🔥 [EMULADOR] Paquetes enviados antes del colapso: {packet_count}")
                        break
                        
        except KeyboardInterrupt:
            print(f"\n🔥 [EMULADOR] Detenido manualmente.")

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "resonance"
    freq = float(sys.argv[2]) if len(sys.argv) > 2 else 5.2
    run_emulator(mode, freq)
