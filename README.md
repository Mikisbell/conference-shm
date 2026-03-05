# 🛡️ Stack Bélico — Ecosistema de Investigación Estructural

> **"La transparencia que no puede ser auditada no es transparencia. Es un espejismo."**

Un Monorepo Cognitivo de Ingeniería Estructural diseñado para transformar datos brutos de sensores físicos en evidencia científica inmutable. Este sistema es simultáneamente una plataforma de investigación universitaria y un estándar de transparencia para obra pública.

---

## 🏗️ Arquitectura del Sistema

```
Sensor Físico (Arduino)
    │
    ▼
🔬 Shadow Play (Filtro de Kalman)         ← Separa ruido de señal estructural real
    │
    ▼
⚙️ Cámara de Tortura (OpenSeesPy P-Delta) ← Motor de Elementos Finitos No-Lineal
    │
    ▼
🛑 Guardian Angel (Protocolo de Aborto)   ← 3 Red Lines: Jitter / Esfuerzo / Divergencia
    │
    ▼
🧠 Engram (SQLite Inmutable)              ← Registro criptográfico de cada evento de aborto
    │
    ▼
📜 Scientific Narrator (AITMPL)           ← Traductor de Evidencia (Técnico → Cívico)
    │
    ▼
🚦 Dashboard de Transparencia (Dash)     ← Ventanilla Pública de Auditoría Ciudadana
```

---

## ⚡ Inicio Rápido

```bash
# 1. Clonar el Ecosistema
git clone https://github.com/tu-usuario/belico-stack.git
cd belico-stack

# 2. Desplegar la Arquitectura
bash init_investigation.sh

# 3. Configurar llaves de motor cognitivo (OpenAI / Anthropic / Gemini)
cp .env.example .env && nano .env

# 4. Certificar el Búnker
source .venv/bin/activate
python3 src/init_bunker.py

# 5. Lanzar la Prueba de Fuego Real (Hardware Simulado → Colapso → Evidencia)
./tools/run_battle.sh

# 6. Encender el Faro de Transparencia
python3 articles/transparency_dashboard.py
# → Visitar: http://localhost:8080
```

---

## 🔬 Capas del Ecosistema

| Capa | Componente | Función |
|------|------------|---------|
| **Física** | `OpenSeesPy` + `Kalman` | Simulación no-lineal P-Delta y filtrado de señal |
| **Memoria** | `Engram` (SQLite) | Registro inmutable y sellado criptográfico de eventos |
| **Auditoría** | `Guardian Angel` | Bloqueo automático por criterios de esfuerzo crítico |
| **Narrativa** | `Scientific Narrator` | Traducción de métricas tensoriales a prosa cívica |
| **Visibilidad** | `Dashboard` (Dash/Plotly) | Ventanilla pública de auditoría en tiempo real |

---

## 📐 Protocolo de Aborto — Las 3 Red Lines

El sistema es **autónomo y no-negociable** ante estos tres escenarios:

- **RL-1 — Jitter Serial:** 3 paquetes consecutivos con latencia > 10ms (corrupción de canal)
- **RL-2 — Esfuerzo Crítico:** σ > 0.85 · f_y (la estructura se aproxima al colapso plástico)
- **RL-3 — Divergencia Numérica:** OpenSeesPy no converge (inestabilidad del modelo P-Delta)

Cada evento de aborto queda firmado con SHA-256 del código en ejecución y estampado inmutablemente en `Engram` antes de que el operador pueda intervenir.

---

## 🏛️ Uso en Obra Pública e Investigación Académica

Este stack está diseñado como un **estándar de obra pública** bajo el paradigma del **"Contrato de Resiliencia"**:

> En lugar de fiscalizar infraestructuras *después* del colapso, este sistema observa la agonía de la materia en vivo y emite la alerta autónoma *antes* de la tragedia.

### Para investigadores:
- El flujo `sensor → Kalman → OpenSeesPy → Engram` es reproducible al 100% gracias al hash del SSOT (`config/params.yaml`).
- El `Scientific Narrator` genera automáticamente la Sección de *Integridad del Experimento* del paper.

### Para auditores públicos:
- El Dashboard (`http://localhost:8080`) expone la evidencia en **Solo Lectura**. Ningún visitante puede alterar los datos del núcleo de simulación.
- El Hash de Verificación mostrado en el "Semáforo de Engram" puede ser confrontado contra el registro de Git para descartar manipulación.

---

## 📂 Estructura del Repositorio

```
belico-stack/
├── .agent/                    # Memoria cognitiva (Engram, Teams, Skills)
│   ├── memory/engram.db       # Base de datos inmutable de eventos
│   ├── prompts/               # Directivas del Verifier y Physical Critic
│   └── skills/                # Habilidades modulares (SHM, señales, etc.)
├── config/params.yaml         # SSOT: Única fuente de verdad de parámetros físicos
├── src/physics/               # Motor de Combate (OpenSeesPy, Kalman, Bridge)
├── tools/                     # Emulador Arduino, Exportador de señales, run_battle.sh
├── articles/                  # Motor Narrativo AITMPL y drafts del paper
│   ├── scientific_narrator.py # Traductor de evidencia Engram → Markdown
│   ├── transparency_dashboard.py # Servidor de la Ventanilla Pública
│   └── drafts/                # Paper académico y reporte de transparencia
├── firmware/                  # Código del microcontrolador (PlatformIO)
├── .env.example               # Plantilla de configuración (no subir .env)
└── init_investigation.sh      # Despliegue del Ecosistema completo
```

---

## 🔐 Seguridad y Reproducibilidad

- **Núcleo Aislado:** El Dashboard usa conexión `read-only` a SQLite. No hay superficie de ataque hacia el motor de simulación.
- **Hashing SSOT:** Cada ensayo verifica que el firmware del Arduino y el `params.yaml` tienen el mismo SHA-256 (Handshake de integridad).
- **Variables de Entorno:** Las API Keys de los motores cognitivos se gestionan vía `.env` (nunca versionadas).

---

## 📄 Licencia

MIT License — Este estándar es libre para su uso en proyectos de infraestructura pública.

---

*Desarrollado como parte de un programa de investigación en ingeniería estructural y gemelos digitales para monitoreo sísmico en tiempo real.*
