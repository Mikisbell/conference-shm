#!/usr/bin/env python3
"""
tools/lora_emu.py — Emulador de Enlace Telemétrico LoRa
═══════════════════════════════════════════════════════════════════════════
Inyecta ráfagas periódicas simulando el comportamiento de un Arduino Nicla
Sense ME conectado a un módulo LoRa UART.
A diferencia de `arduino_emu.py` que inyecta a 100 Hz continuos, este solo
envía un "Resumen Ejecutivo" cada X segundos, imitando las restricciones
físicas (Duty Cycle) y la baja latencia de la arquitectura Edge IoT.

Formato: LORA:TMP:28.1,FN:5.20,MAX_G:1.15,STAT:OK\n
"""
import math
import os
import pty
import sys
import time
import random
from pathlib import Path

try:
    import yaml
except ImportError:
    print("[LORA_EMU] PyYAML not installed. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

try:
    import numpy as np
    _NP_AVAILABLE = True
except ImportError:
    np = None  # type: ignore
    _NP_AVAILABLE = False  # only needed for peer_benchmark mode

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.paths import get_params_file

try:
    from src.physics.peer_adapter import PeerAdapter as _PeerAdapter
    _PEER_AVAILABLE = True
except ImportError:
    _PeerAdapter = None  # type: ignore
    _PEER_AVAILABLE = False

# ---------------------------------------------------------------------------
# Emulator timing constants
# ---------------------------------------------------------------------------
TX_INTERVAL_SEC = 5.0   # s — LoRa duty cycle interval (hardware physical constraint)

# ---------------------------------------------------------------------------
# LoRa damage simulation constants — AGENTS.md Rule 12
# Frequency drop ratios based on FEMA P-58-1 §3.6 stiffness loss—fragility model:
#   Δfn/fn ≈ ½·(Δk/k) for linear SDOF (Taylor expansion of sqrt(k/m)/(2π))
# ---------------------------------------------------------------------------
_LORA_LEVE_FN_RATIO       = 0.95  # fn fraction: minor damage (≈10% stiffness loss, FEMA P-58-1)
_LORA_CRITICO_FN_RATIO    = 0.60  # fn fraction: critical damage (≈64% stiffness loss, FEMA P-58-1)
_LORA_LAG_FN_RATIO        = 0.60  # fn fraction: lag-attack scenario (same stiffness level as critical)
_LORA_PARADOJA_INC_HZ_PKT = 0.80  # Hz/packet: impossible increasing fn (paradox detection test)
_LORA_CRITICO_GROW_HZ_PS  = 0.01  # Hz/s: max_g growth rate in sustained critical scenario
_LORA_MAX_G_LEVE          = 0.12  # g — typical peak acceleration, minor damage mode
_LORA_MAX_G_CRITICO       = 0.40  # g — typical peak acceleration, critical damage mode
_PEER_BENCHMARK_PGA_G     = 0.45  # g — Perú Zone 4 design PGA (E.030-2018 §10, Zona 4)
_PEER_SAMPLE_RATE_HZ      = 100.0 # Hz — PEER record resampling rate (= Arduino Nano 33 acquisition)
_TMP_NOMINAL_C            = 22.0  # °C — ambient nominal temperature for healthy-state telemetry
_TMP_STD_C                =  0.5  # °C — temperature measurement noise std dev
_HUM_NOMINAL_PCT          = 55.0  # % — nominal relative humidity for healthy-state telemetry
_HUM_STD_PCT              =  1.0  # % — humidity measurement noise std dev


def _load_fn_nominal() -> float:
    """Derive fn_nominal from SSOT: fn = sqrt(k/m) / (2π). sys.exit(1) if keys absent."""
    params_path = get_params_file()
    try:
        with open(params_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    except (FileNotFoundError, yaml.YAMLError, OSError) as e:
        print(f"[LORA_EMU] ERROR: cannot read params.yaml: {e}", file=sys.stderr)
        sys.exit(1)
    _k_raw = cfg.get("structure", {}).get("stiffness_k", {}).get("value")
    _m_raw = cfg.get("structure", {}).get("mass_m", {}).get("value")
    for _name, _val in (("structure.stiffness_k.value", _k_raw), ("structure.mass_m.value", _m_raw)):
        if _val is None:
            print(f"[LORA_EMU] ERROR: SSOT missing '{_name}' in config/params.yaml", file=sys.stderr)
            sys.exit(1)
    return math.sqrt(float(_k_raw) / float(_m_raw)) / (2.0 * math.pi)

def run_lora_emulator(mode: str = "sano", peer_file: str = ""):
    fn_nominal = _load_fn_nominal()  # Hz — from SSOT (sqrt(k/m)/(2π))

    master, slave = pty.openpty()
    tty_name = os.ttyname(slave)

    peer_data = None
    if mode == "peer_benchmark" and peer_file:
        if not _PEER_AVAILABLE:
            print("[LORA_EMU] ERROR: src.physics.peer_adapter not available (check openseespy install)",
                  file=sys.stderr)
            sys.exit(1)
        if not _NP_AVAILABLE:
            print("[LORA_EMU] ERROR: numpy required for peer_benchmark mode. Run: pip install numpy",
                  file=sys.stderr)
            sys.exit(1)
        adapter = _PeerAdapter(target_frequency_hz=_PEER_SAMPLE_RATE_HZ)
        raw_dict = adapter.read_at2_file(Path(peer_file))
        resampled = adapter.normalize_and_resample(raw_dict)
        # Escalando a Peligro Sísmico Z4 (E.030-2018 §10)
        peer_data = adapter.scale_to_pga(resampled, target_pga_g=_PEER_BENCHMARK_PGA_G)
        print(f"🌍 Cofre de Conocimiento Enlazado: {len(peer_data)} muestras PEER listas "
              f"(PGA {_PEER_BENCHMARK_PGA_G}g).")
    
    print("═" * 50)
    print("📡 [LORA MOCK] Enlace Telemétrico Activo")
    print(f"   Modo: {mode} | Tx Rate: 1 pkt / {TX_INTERVAL_SEC}s")
    print(f"   Puerto Virtual: {tty_name}")
    print("═" * 50)
    print(f"🔥 Ejecuta en otra terminal: python3 src/physics/bridge.py {tty_name}\n")
    
    start_time = time.time()
    packet_count = 0
    
    try:
        # Falso Handshake para engañar al bridge.py (simulando que el LoRa Rx está listo)
        # El bridge envía "HANDSHAKE:..." al arrancar
        handshake_done = False
        print("Esperando intento de Handshake del Bridge...")
        while not handshake_done:
            # En IoT real, el Handshake se hace a nivel local USB (Laptop <-> Módulo LoRa Tx)
            # no end-to-end hasta el Arduino a través del aire.
            # Aquí inyectamos el ACK directamente para despertar al bridge.
            time.sleep(1)
            ping_pkt = "ACK_OK\n"
            os.write(master, ping_pkt.encode())
            
            # Limpiamos el buffer de Rx (lo que manda el bridge)
            # En un mock simplificado asumiremos que si escribimos ACK_OK 3 veces, 
            # el bridge avanza rápido.
            packet_count += 1
            if packet_count > 3:
                handshake_done = True
                print("Handshake forzado: ACK_OK inyectado.")
                packet_count = 0

        # Esperar "TIME_SYNC" del bridge y responder asincronamente
        # Para LoRa NO ENVIAMOS "T:..." porque eso indicaría un paquete raw clásico
        # y activaría el Jitter Watchdog. En su lugar, el bridge tolerará 
        # que solo lleguen paquetes LORA:.
        time.sleep(1)
        print("Sincronización inicial omitida para modo telemetría LoRa. Iniciando Edge AI...")
        
        while True:
            current_time = time.time()
            elapsed_sys  = current_time - start_time
            
            # --- Simulación del Motor Edge AI (C++) en el Nicla ---
            if mode == "sano":
                fn    = fn_nominal + random.normalvariate(0, 0.05)
                max_g = 0.05 + random.normalvariate(0, 0.01)
                stat  = "OK"
                t_unix = int(current_time)
            elif mode == "lag_attack":
                fn    = fn_nominal * _LORA_LAG_FN_RATIO
                max_g = _LORA_MAX_G_CRITICO
                stat  = "ALARM_RL2"
                # Simulamos que el sensor envió esto hace 45 segundos, pero la red LoRa lo retuvo
                t_unix = int(current_time) - 45
            elif mode == "dano_leve":
                fn    = fn_nominal * _LORA_LEVE_FN_RATIO + random.normalvariate(0, 0.05)
                max_g = _LORA_MAX_G_LEVE + random.normalvariate(0, 0.02)
                stat  = "WARN"
                t_unix = int(current_time)
            elif mode == "dano_critico":
                # Al simular daño crítico, la Fn cae >30% y la amplitud sube
                fn    = fn_nominal * _LORA_CRITICO_FN_RATIO + random.normalvariate(0, 0.1)
                max_g = _LORA_MAX_G_CRITICO + (elapsed_sys * _LORA_CRITICO_GROW_HZ_PS)
                stat  = "ALARM_RL2"
                t_unix = int(current_time)
            elif mode == "paradoja_fisica":
                fn    = fn_nominal + (packet_count * _LORA_PARADOJA_INC_HZ_PKT)
                max_g = 0.05
                stat  = "OK"  # Mentira: el sensor dice "sano"
                t_unix = int(current_time)
                tmp   = 500.0 if packet_count > 0 else _TMP_NOMINAL_C  # Primer pkt normal, luego 500°C
            elif mode == "peer_benchmark" and peer_data is not None:
                SAMPLES_PER_TX = int(TX_INTERVAL_SEC * _PEER_SAMPLE_RATE_HZ)
                start_idx = packet_count * SAMPLES_PER_TX
                end_idx = start_idx + SAMPLES_PER_TX
                if start_idx >= len(peer_data):
                    print("🏁 [LORA] Fin del benchmark sísmico PEER.")
                    break
                
                chunk = peer_data[start_idx:min(end_idx, len(peer_data))]
                max_g = float(np.max(np.abs(chunk)))
                
                # Zero-crossing rápido para estimar Frecuencia Predominante del sismo
                zero_crossings = np.where(np.diff(np.sign(chunk)))[0]
                if len(zero_crossings) > 0:
                    fn = (len(zero_crossings) / 2.0) / (len(chunk)/100.0)
                else:
                    fn = fn_nominal
                
                stat = "ALARM_EQ" if max_g > 0.05 else "OK"
                t_unix = int(current_time)
            else:
                fn    = 0.0; max_g = 0.0; stat = "ERR"; t_unix = int(current_time)
            
            # Temperatura ambiente estable, Humedad estable
            if mode != "paradoja_fisica":
                tmp = _TMP_NOMINAL_C + random.normalvariate(0, _TMP_STD_C)
            hum = _HUM_NOMINAL_PCT + random.normalvariate(0, _HUM_STD_PCT)
            
            # Formato Payload Edge AI con Timestamp (RTC/Epoch)
            payload = f"LORA:T:{t_unix},TMP:{tmp:.1f},HUM:{hum:.1f},FN:{fn:.2f},MAX_G:{max_g:.3f},STAT:{stat}\n"
            
            os.write(master, payload.encode())
            packet_count += 1
            print(f"[Tx #{packet_count}] {payload.strip()}")
            
            time.sleep(TX_INTERVAL_SEC)
            
    except OSError as e:
        print(f"\n🛑 [LORA MOCK] Conexión cerrada (Bridge desconectado): {e}")
    except KeyboardInterrupt:
        print("\n🛑 [LORA MOCK] Apagado manual.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Emulador de Enlace LoRa")
    parser.add_argument("tty_dummy", nargs="?", default="", help="Ignorado, para pseudo-compatibilidad")
    parser.add_argument("--mode", default="sano", help="Modo de inyección")
    parser.add_argument("--cycles", type=int, default=500, help="Ignorado (corre indefinidamente hasta CTL+C o fin de PEER)")
    parser.add_argument("--peer-file", default="", help="Ruta al sismo de validación cruzada (.AT2)")
    args = parser.parse_args()
    
    run_lora_emulator(args.mode, args.peer_file)
