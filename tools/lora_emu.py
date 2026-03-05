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
import os
import pty
import sys
import time
import random

# --- Configuración del Enlace LoRa Simulado ---
TX_INTERVAL_SEC = 5.0   # Cada cuánto "habla" el sensor (Duty cycle)
FN_NOMINAL      = 8.0   # Hz (Estructura Sana)

def run_lora_emulator(mode: str = "sano"):
    master, slave = pty.openpty()
    tty_name = os.ttyname(slave)
    
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
                fn    = FN_NOMINAL + random.normalvariate(0, 0.05)
                max_g = 0.05 + random.normalvariate(0, 0.01)
                stat  = "OK"
                t_unix = int(current_time)
            elif mode == "lag_attack":
                fn    = FN_NOMINAL * 0.60
                max_g = 0.40
                stat  = "ALARM_RL2"
                # Simulamos que el sensor envió esto hace 45 segundos, pero la red LoRa lo retuvo
                t_unix = int(current_time) - 45
            elif mode == "dano_leve":
                fn    = FN_NOMINAL * 0.95 + random.normalvariate(0, 0.05)
                max_g = 0.12 + random.normalvariate(0, 0.02)
                stat  = "WARN"
                t_unix = int(current_time)
            elif mode == "dano_critico":
                # Al simular daño crítico, la Fn cae >30% y la amplitud sube
                fn    = FN_NOMINAL * 0.60 + random.normalvariate(0, 0.1)
                max_g = 0.40 + (elapsed_sys * 0.01) # Crece con el tiempo
                stat  = "ALARM_RL2"
                t_unix = int(current_time)
            else:
                fn    = 0.0; max_g = 0.0; stat = "ERR"; t_unix = int(current_time)
            
            tmp = 22.0 + random.normalvariate(0, 0.5)
            hum = 55.0 + random.normalvariate(0, 1.0)
            
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
    _mode = "sano"
    if len(sys.argv) > 1:
         _mode = sys.argv[1].lower()
    run_lora_emulator(_mode)
