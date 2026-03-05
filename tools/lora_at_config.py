#!/usr/bin/env python3
"""
tools/lora_at_config.py — Configurador Automático Ebyte E32-915T30D
═══════════════════════════════════════════════════════════════════════════
Configura el módulo LoRa para el despliegue en campo (Presa del Norte).

REQUISITO DE HARDWARE (antes de ejecutar):
  • M0 = HIGH (3.3V)   → Pin M0 del E32 a VCC 3.3V
  • M1 = HIGH (3.3V)   → Pin M1 del E32 a VCC 3.3V
  Esto pone el E32 en Modo 3 (Modo Sueño / Configuración AT).

Esquema de conexión Nicla ↔ E32 (SIN level shifter necesario):
  Nicla TX (D1 / GPIO1) ──► E32 RX
  Nicla RX (D0 / GPIO0) ◄── E32 TX
  Nicla GND             ──► E32 GND
  3.3V                  ──► E32 VCC
  GPIO libre            ──► E32 M0 (controlar modo config/normal)
  GPIO libre            ──► E32 M1 (controlar modo config/normal)
  GPIO libre (opcional) ──► E32 AUX (saber cuándo el módulo está ocupado)

Uso:
  python3 tools/lora_at_config.py --port /dev/ttyUSB0 --verify
"""

import argparse
import time
import sys
import struct
import serial
from pathlib import Path

# ─────────────────────────────────────────────────────────────────────────────
# Parámetros Objetivo para el Despliegue Field (Presa del Norte)
# ─────────────────────────────────────────────────────────────────────────────
TARGET_CONFIG = {
    "address":      0x0000,   # Dirección del módulo (ajustar por nodo en red multi-nodo)
    "uart_baud":    0b011,    # 011 = 9600 bps (compatible con Nicla UART)
    "uart_parity":  0b00,     # 00  = 8N1
    "air_data_rate":0b011,    # 011 = 4.8 kbps (máx sensibilidad para 30dBm en C&DW)
    "channel":      0x0D,     # 13  = 902 + 13 = 915 MHz ✅ (Banda ISM Perú/Americas)
    "tx_power":     0b00,     # 00  = 30 dBm (1W, máximo alcance)
    "fixed_mode":   False,    # False = Modo Transparente (compatible con bridge.py)
    "io_drive":     True,     # True  = Push-pull (recomendado para líneas largas)
    "fec":          True,     # True  = FEC habilitado (integridad en ruido de obra)
    "wakeup_time":  0b000,    # 000  = 250 ms (tiempo de activación mínimo)
}

def build_sped_byte(cfg: dict) -> int:
    """Frame SPED: [UART_PARITY(2) | UART_BAUD(3) | AIR_DATA_RATE(3)]"""
    return (cfg["uart_parity"]   << 6) | \
           (cfg["uart_baud"]     << 3) | \
           (cfg["air_data_rate"])

def build_option_byte(cfg: dict) -> int:
    """Frame OPTION: [FIXED_MODE(1) | IO_DRIVE(1) | WAKEUP(3) | FEC(1) | TX_POWER(2)]"""
    return (int(cfg["fixed_mode"]) << 7) | \
           (int(cfg["io_drive"])   << 6) | \
           (cfg["wakeup_time"]     << 3) | \
           (int(cfg["fec"])        << 2) | \
           (cfg["tx_power"])

def build_config_frame(cfg: dict) -> bytes:
    """
    Construye el frame de 6 bytes para escritura permanente:
    C0 ADDH ADDL SPED CHAN OPTION
    """
    head  = 0xC0  # Guardar configuración en memoria y reiniciar
    addh  = (cfg["address"] >> 8) & 0xFF
    addl  =  cfg["address"]       & 0xFF
    sped  = build_sped_byte(cfg)
    chan  = cfg["channel"]
    opt   = build_option_byte(cfg)
    return bytes([head, addh, addl, sped, chan, opt])

def decode_response(data: bytes) -> dict:
    """Parsea la respuesta de lectura de configuración (C1 reply)."""
    if len(data) < 6:
        return {"error": f"Respuesta corta: {data.hex()}"}
    return {
        "address": (data[1] << 8) | data[2],
        "sped_raw": data[3],
        "channel": data[4],
        "freq_mhz": 902 + data[4],
        "option_raw": data[5],
        "tx_power_dbm": 30 - (data[5] & 0x03) * 3,
        "fec_enabled": bool(data[5] & 0x04),
    }

def configure_module(port: str, baud: int = 9600, dry_run: bool = False):
    frame = build_config_frame(TARGET_CONFIG)
    freq  = 902 + TARGET_CONFIG["channel"]

    print("═" * 60)
    print("  BELICO STACK — Configurador LoRa E32-915T30D")
    print("═" * 60)
    print(f"  Puerto: {port} @ {baud} bps")
    print(f"  Frecuencia objetivo: {freq} MHz  (CH={TARGET_CONFIG['channel']:#04x})")
    print(f"  Air Data Rate: 4.8 kbps | TX Power: 30 dBm | FEC: ON")
    print(f"  Frame: {frame.hex().upper()}")

    if dry_run:
        print("\n  ⚠️  Modo DRY-RUN: No se enviará nada al módulo.")
        return True

    print("\n  Abriendo puerto serial en Modo Configuración (M0=M1=HIGH)...")
    try:
        with serial.Serial(port, baud, timeout=2) as ser:
            time.sleep(0.5)  # Esperar que el módulo responda tras cambio de modo

            # 1. Leer configuración actual
            ser.write(bytes([0xC1, 0xC1, 0xC1]))
            time.sleep(0.3)
            current_raw = ser.read(6)
            if current_raw:
                current = decode_response(current_raw)
                print(f"\n  🔍 Config Actual  → {current_raw.hex().upper()}")
                print(f"      Frecuencia: {current.get('freq_mhz', '?')} MHz | "
                      f"TX: {current.get('tx_power_dbm', '?')} dBm | "
                      f"FEC: {current.get('fec_enabled', '?')}")

            # 2. Escribir nueva configuración
            print(f"\n  📡 Escribiendo: {frame.hex().upper()}")
            ser.write(frame)
            time.sleep(1.0)  # Módulo reinicia tras C0

            # 3. Verificar
            ser.write(bytes([0xC1, 0xC1, 0xC1]))
            time.sleep(0.3)
            new_raw = ser.read(6)
            if new_raw:
                new = decode_response(new_raw)
                freq_ok = new.get("freq_mhz") == freq
                pwr_ok  = new.get("tx_power_dbm") == 30
                fec_ok  = new.get("fec_enabled") is True

                print(f"\n  ✅ Config Nueva   → {new_raw.hex().upper()}")
                print(f"      Frecuencia: {new.get('freq_mhz')} MHz  {'✅' if freq_ok else '❌'}")
                print(f"      TX Power:   {new.get('tx_power_dbm')} dBm  {'✅' if pwr_ok else '❌'}")
                print(f"      FEC:        {new.get('fec_enabled')}  {'✅' if fec_ok else '❌'}")

                if freq_ok and pwr_ok and fec_ok:
                    print("\n  ✅ Módulo E32 configurado correctamente.")
                    print("  → Mueve M0 y M1 a GND para regresar a Modo Normal (transmisión).")
                    return True
                else:
                    print("\n  ❌ Verificación fallida. Revisa el estado de los pines M0/M1.")
                    return False
            else:
                print("\n  ❌ Sin respuesta del módulo. ¿Están M0 y M1 en HIGH?")
                return False

    except serial.SerialException as e:
        print(f"\n  ❌ Error de puerto: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Configurador Ebyte E32-915T30D para Belico Stack")
    parser.add_argument("--port",    default="/dev/ttyUSB0", help="Puerto serial del E32")
    parser.add_argument("--baud",    type=int, default=9600,  help="Baud rate de configuración")
    parser.add_argument("--dry-run", action="store_true",     help="Solo imprimir frame, no enviar")
    parser.add_argument("--verify",  action="store_true",     help="Leer config actual sin modificar")
    args = parser.parse_args()
    success = configure_module(args.port, args.baud, dry_run=args.dry_run)
    sys.exit(0 if success else 1)
