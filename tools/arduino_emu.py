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

def run_emulator(chaos_mode="resonance", f_hz=5.2):
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
                    # Frecuencia forzada paramétrica (supera RL-2)
                    freq = f_hz
                    amplitude = min(1.5, elapsed * 0.1)  # Crece hasta 1.5g
                    accel = amplitude * math.sin(2 * math.pi * freq * elapsed)
                    accel += random.normalvariate(0, 0.05)

                elif chaos_mode == "sano":
                    # Estructura SANA: vibración de servicio nominal (baseline)
                    # Frecuencia natural alta, amplitudes pequeñas, sin deriva.
                    fn = f_hz if f_hz != 5.2 else 8.0  # fn alta = estructura rígida
                    accel  = 0.05 * math.sin(2 * math.pi * fn * elapsed)
                    accel += 0.02 * math.sin(2 * math.pi * 2 * fn * elapsed)  # armónico
                    accel += random.normalvariate(0, 0.01)  # Ruido sensor mínimo

                elif chaos_mode == "dano_leve":
                    # MICRO-DAÑO LEVE: rigidez degradada ~10% → fn cae ~5%
                    # Simula: micro-fisura en zona de máximo momento flector.
                    fn_nominal = f_hz if f_hz != 5.2 else 8.0
                    fn_danada  = fn_nominal * math.sqrt(0.90)  # k-10% → fn * sqrt(0.9)
                    accel  = 0.10 * math.sin(2 * math.pi * fn_danada * elapsed)
                    # Ruido de impacto leve (aceleración de tapping)
                    if int(elapsed * 10) % 30 == 0:
                        accel += random.normalvariate(0, 0.03)
                    accel += random.normalvariate(0, 0.015)

                elif chaos_mode == "dano_critico":
                    # DAÑO CRÍTICO: rigidez degradada ~40% → fn cae ~37%
                    # Simula: fallo por fatiga progresivo en perno / soldadura.
                    # La amplitud crece porque la amortiguación también cae.
                    fn_nominal = f_hz if f_hz != 5.2 else 8.0
                    fn_danada  = fn_nominal * math.sqrt(0.60)  # k-40%
                    amplitude  = 0.15 + elapsed * 0.02  # Amplitud creciente
                    accel  = amplitude * math.sin(2 * math.pi * fn_danada * elapsed)
                    # Golpes transitorios (emula impacto recurrente de tráfico pesado)
                    if int(elapsed * 20) % 25 == 0:
                        accel += random.normalvariate(0, 0.08)
                    accel += random.normalvariate(0, 0.025)

                elif chaos_mode == "presa":
                    # PRESA DEL NORTE: perfil sísmico tipo Kanai-Tajimi
                    # Simula la excitación basal que recibe la corona de una presa
                    # durante un sismo de baja frecuencia dominante (2-4 Hz).
                    # Los largos periodos son característicos de suelos blandos.
                    fg    = 2.5     # Hz - frecuencia predominante del suelo
                    dg    = 0.60    # Amortiguamiento del suelo
                    scale = min(0.8, elapsed * 0.05)  # Acelerogramas crescentes
                    # Componente de fondo (ruido estocástico de baja frec)
                    base  = scale * random.normalvariate(0, 0.2)
                    # Componente harmónica de la presa (modi Kanai-Tajimi simplif.)
                    accel = (base
                             + scale * 0.4 * math.sin(2 * math.pi * fg * elapsed)
                             + scale * 0.2 * math.sin(2 * math.pi * fg * 1.5 * elapsed)
                             + scale * 0.1 * math.sin(2 * math.pi * fg * 3.0 * elapsed))
                    accel += random.normalvariate(0, 0.02)

                else:  # modo desconocido → ruido blanco
                    accel = random.normalvariate(0, 0.05)
                
                # Envío de formato crudo
                packet = f"T:{current_millis},A:{accel:.4f},D:0.00\n"
                os.write(master, packet.encode())
                packet_count += 1
                
                # Desastre simulado (USB desconectado)
                if chaos_mode == "dropout" and packet_count >= 15:
                    print(f"\n🔥 [EMULADOR] 🔌 [SIMULACRO] Cable desconectado abruptamente. Muriendo...")
                    break
                
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
    freq = float(sys.argv[2]) if len(sys.argv) > 2 else 5.2
    run_emulator(mode, freq)
