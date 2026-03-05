#!/bin/bash
# tools/run_battle_freq.sh — Wrapper paramétrico para el barrido de frecuencias
# Uso: bash tools/run_battle_freq.sh <frecuencia_hz>
# Ejemplo: bash tools/run_battle_freq.sh 8.0

FREQ=${1:-5.2}

source .venv/bin/activate 2>/dev/null
export PYTHONPATH=$PWD:$PYTHONPATH

# Matar procesos huérfanos previos
pkill -f arduino_emu.py 2>/dev/null
pkill -f bridge.py 2>/dev/null
sleep 0.5

# Iniciar emulador con la frecuencia paramétrica
PYTHONUNBUFFERED=1 python3 tools/arduino_emu.py resonance "$FREQ" > logs_emu.txt 2>&1 &
EMU_PID=$!
sleep 2

# Extraer el puerto PTY
EMU_PTY=$(head -n 1 logs_emu.txt | grep -oE '/dev/pts/[0-9]+')

if [ -z "$EMU_PTY" ]; then
    kill -9 $EMU_PID 2>/dev/null
    exit 1
fi

# Iniciar el bridge
PYTHONUNBUFFERED=1 python3 src/physics/bridge.py "$EMU_PTY" > logs_bridge.txt 2>&1 &
BRIDGE_PID=$!

# Esperar a que terminen
wait $EMU_PID 2>/dev/null
wait $BRIDGE_PID 2>/dev/null
