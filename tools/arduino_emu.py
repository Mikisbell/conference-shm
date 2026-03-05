import time
import math
import hashlib
import random
import yaml
import sys
import pty
import os

from pathlib import Path

# ─────────────────────────────────────────────────────────
# EMULADOR ARDUINO BÉLICO (Ingeniería del Caos)
# ─────────────────────────────────────────────────────────
# Este script crea un puerto serial virtual (pty) y emula el
# comportamiento del firmware de Arduino, inyectando un
# escenario de resonancia para forzar un fallo controlado (RL-2).

PARAMS_PATH = Path(__file__).parent.parent / "config" / "params.yaml"

def load_config() -> dict:
    with open(PARAMS_PATH, "r") as f:
        return yaml.safe_load(f)

def run_emulator(chaos_mode="resonance"):
    """
    Crea un PTY (Pseudo-Terminal) y actúa como el Arduino.
    Imprime el nombre del puerto que el bridge.py debe escuchar.
    """
    master, slave = pty.openpty()
    port_name = os.ttyname(slave)
    
    cfg = load_config()
    with open(PARAMS_PATH, 'rb') as f:
        master_hash = hashlib.sha256(f.read()).hexdigest()
        
    token = cfg["temporal"]["handshake_token"]["value"]
    dt_ms = int(cfg["temporal"]["dt_simulation"]["value"] * 1000)
    
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
                jitter = random.normalvariate(0, 2) # Ruido gausiano de +/- 2ms
                time.sleep(max(0, (dt_ms + jitter) / 1000.0))
                
                # --- Escenarios de Inyección ---
                if chaos_mode == "resonance":
                    # Frecuencia forzada (simulando resonancia que supera umbral RL-2)
                    # Aumentamos la amplitud gradualmente.
                    freq = 2.0  # Hz (Frecuencia natural supuesta)
                    amplitude = min(1.5, elapsed * 0.1) # Crece hasta 1.5g
                    accel = amplitude * math.sin(2 * math.pi * freq * elapsed)
                    
                    # Añadir ruido electromagnético
                    noise = random.normalvariate(0, 0.05)
                    accel += noise
                else:
                    accel = random.normalvariate(0, 0.05)
                
                # Envío de formato crudo
                packet = f"T:{current_millis},A:{accel:.4f},D:0.00\n"
                os.write(master, packet.encode())
                packet_count += 1
                
                # Escuchar comandos abort (SHUTDOWN)
                import select
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
    run_emulator(mode)
