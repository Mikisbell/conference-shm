#!/bin/bash
# tools/run_battle.sh — Orquestador del Combate Total
# Lanza el Agresor y el Bridge simultáneamente.

echo "🎖️ [BATTLE] Iniciando la Operación Resonancia en Cámara de Tortura..."

source .venv/bin/activate
export PYTHONPATH=$PWD:$PYTHONPATH

# Matar procesos huérfanos previos
pkill -f arduino_emu.py
pkill -f bridge.py

# 1. Iniciar el Emulador en segundo plano
PYTHONUNBUFFERED=1 python3 tools/arduino_emu.py resonance > logs_emu.txt 2>&1 &
EMU_PID=$!
sleep 2

# Extraer el puerto PTY
EMU_PTY=$(head -n 1 logs_emu.txt | grep -oE '/dev/pts/[0-9]+')

if [ -z "$EMU_PTY" ]; then
    echo "❌ ERROR: No se pudo iniciar el emulador o extraer el puerto PTY."
    cat logs_emu.txt
    kill -9 $EMU_PID
    exit 1
fi

echo "🔫 [BATTLE] Emulador armado en $EMU_PTY -> Atacando."

# 2. Iniciar el Bridge leyendo del emulador
PYTHONUNBUFFERED=1 python3 src/physics/bridge.py "$EMU_PTY" > logs_bridge.txt 2>&1 &
BRIDGE_PID=$!

echo "🛡️ [BATTLE] Bridge desplegado. Protegiendo la Cámara de Tortura."
echo "👀 [BATTLE] Observando el combate (Ctrl+C para salir prematuramente)..."

# Monitorear logs en vivo
tail -f logs_bridge.txt logs_emu.txt &
TAIL_PID=$!

# Esperar a que el Emulador y el Bridge terminen la limpieza
wait $EMU_PID
echo "🛑 [BATTLE] El Agresor ha sido desconectado."

wait $BRIDGE_PID
echo "🛡️ [BATTLE] El Bridge ha asegurado los datos y se ha cerrado."

kill -9 $TAIL_PID 2>/dev/null

echo "📊 [BATTLE] Generando reporte de bajas..."
python3 tools/export_signals.py

echo "✅ [BATTLE] Operación finalizada con rigor."
