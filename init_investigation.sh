#!/bin/bash
# init_investigation.sh - Despliegue del Stack Bélico (Arquitectura Pura)

echo "🚀 [STACK BÉLICO] Inicializando Arquitectura Pura..."

# 1. Crear Estructura Base
mkdir -p .agent/{memory,teams,skills,security}
mkdir -p src
mkdir -p articles
mkdir -p tools

# 2. Archivos Maestros
touch belico.yaml
cp .env.example .env

echo "📦 [STACK BÉLICO] Estructura de carpetas creada."

# 3. Clonar los 7 Repositorios Core
echo "📥 [STACK BÉLICO] Clonando Ecosistema Cognitivo..."

# Memoria y Equipos
git clone https://github.com/Gentleman-Programming/engram.git .agent/memory/engram || true
git clone https://github.com/Gentleman-Programming/agent-teams-lite.git .agent/teams/agent-teams-lite || true

# Habilidades y Seguridad
git clone https://github.com/Gentleman-Programming/Gentleman-Skills.git .agent/skills/gentleman || true
git clone https://github.com/Gentleman-Programming/gentleman-guardian-angel.git .agent/security/guardian-angel || true

# Inteligencia (AITMPL) - Mock/CLI
echo "📥 [STACK BÉLICO] Instalando AITMPL Skills..."
npx aitmpl@latest install --skill=scientific-research --path=.agent/skills/aitmpl || true

# Configuración y Entorno
git clone https://github.com/Gentleman-Programming/veil.nvim.git .agent/security/veil.nvim || true
git clone https://github.com/Gentleman-Programming/Gentleman.Dots.git .agent/config/dots || true


echo "✅ [STACK BÉLICO] Los 7 repositorios han sido inyectados. Despertando al Búnker..."

# 4. Certificación del Entorno (Smoke Test)
echo "🔍 [STACK BÉLICO] Ejecutando Smoke Test del Guardian Angel..."
python3 src/init_bunker.py
