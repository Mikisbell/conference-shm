#!/usr/bin/env bash
# Boot Engram — Active memory retrieval at session start
# Called by Claude Code SessionStart hook
# Outputs structured context for the agent to consume

set -euo pipefail

# Engram uses ~/.engram/engram.db by default. Do NOT override ENGRAM_DATA_DIR.
# See CLAUDE.md "Configuracion critica" section for details.

echo "=== ENGRAM BOOT (active memory retrieval) ==="
echo ""

# 1. Context — recent sessions
echo "--- SESIONES RECIENTES ---"
engram context 2>/dev/null || echo "[DESCONECTADO] Engram no responde"
echo ""

# 2. Active papers
echo "--- PAPERS ACTIVOS ---"
engram search "paper: active" --limit 5 2>/dev/null || echo "[sin resultados]"
echo ""

# 3. Open risks
echo "--- RIESGOS ABIERTOS ---"
engram search "risk:" --limit 10 2>/dev/null || echo "[sin riesgos]"
echo ""

# 4. Recent decisions
echo "--- DECISIONES RECIENTES ---"
engram search "decision:" --limit 5 2>/dev/null || echo "[sin decisiones]"
echo ""

echo "=== BOOT COMPLETO ==="
