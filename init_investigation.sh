#!/bin/bash
# init_investigation.sh - Bootstrap for new Belico Stack deployment
# NOTE: This is a one-time init script. The current project is already deployed.

set -euo pipefail

echo "[STACK BELICO] Initializing directory structure..."

# 1. Core directories
mkdir -p .agent/{memory,prompts,skills}
mkdir -p .agents
mkdir -p src/{physics,ai,firmware}
mkdir -p config
mkdir -p articles/drafts
mkdir -p tools
mkdir -p data/{raw,processed,synthetic,external}
mkdir -p db/{excitation/{flatfiles,records,selections},benchmarks,calibration,validation}
mkdir -p models/lstm
mkdir -p projects

# 2. Master files
touch belico.yaml

echo "[STACK BELICO] Directory structure created."

# 3. Clone external repos
echo "[STACK BELICO] Cloning external dependencies..."

git clone https://github.com/Gentleman-Programming/engram.git .agents/engram || true
git clone https://github.com/Gentleman-Programming/agent-teams-lite.git .agents/agent-teams-lite || true
git clone https://github.com/Gentleman-Programming/Gentleman-Skills.git .agents/Gentleman-Skills || true

echo "[STACK BELICO] External repos cloned into .agents/"

# 4. Smoke test
echo "[STACK BELICO] Running smoke test..."
python3 src/init_bunker.py
