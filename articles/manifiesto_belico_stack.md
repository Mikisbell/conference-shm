# Manifiesto de Ingeniería: Sistema Belico Stack
# Framework de Gemelo Digital para Infraestructura Pública Sostenible

**Mateo Mikisbell · Campaña 2026 · Versión Técnica de Divulgación**

---

## Introducción

Este documento resume la arquitectura y las 32 fases de desarrollo del **Belico Stack**: un sistema de monitoreo y predicción inteligente de infraestructuras habitacionales construidas con Concreto Reciclado (C&DW, 75% de reemplazo de agregados). El sistema fue diseñado como una propuesta de gestión pública rigurosa, auditable e imposible de manipular.

> **Principio rector**: *La transparencia técnica es la única forma de rendición de cuentas que no puede ser editada por un spin doctor.*

---

## Arquitectura del Sistema (Pipeline de Verdad Auditada)

```
Sensor Edge (Nicla SE) → LoRa Radio → Watchdog Telemétrico
    → Guardian Angel (Física) → Engram (Blockchain Local)
    → LSTM Predictor (PyTorch) → BIM Exporter (JSON 3D)
    → Scientific Narrator → Paper Maestro (Evidencia Ciudadana)
```

Cada capa tiene su propia "Aduana de Integridad". Ningún dato puede avanzar si viola las leyes que rigen la capa anterior.

---

## Las 32 Fases: De la Idea al Sistema Inatacable

### Bloque I: Cimientos del Gemelo Digital (Fases 1–10)
- **Fases 1–5**: SSOT (`params.yaml`), Prototipo de Cámara de Tortura (OpenSeesPy P-Delta), handshake criptográfico Arduino↔Python.
- **Fases 6–10**: Filtro de Kalman 1D (reducción de ruido eléctrico), Protocolo de Aborto con 3 Red Lines estructurales (RL-1 Jitter, RL-2 Esfuerzo, RL-3 Divergencia).

### Bloque II: La Aduana Temporal (Fases 11–20)
- **Fases 11–15**: Engram (base de datos inmutable con SHA-256), Scientific Narrator, AITMPL (Marco de Proposiciones Científicas).
- **Fases 16–20**: Shadow Play (detección de daño por Innovación de Kalman), Modo Predicción (worst-case en hilo paralelo).

### Bloque III: El Salto al Borde (Fases 21–28)
- **Fases 21–24**: Firmware C++ en Nicla Sense ME (FFT, Kalman on-board), payload LoRa < 50 bytes.
- **Fases 25–28**: Bridge asíncrono para LoRa, **Watchdog Telemétrico** (descarte de paquetes con Lag > 15s para prevenir replay attacks).

### Bloque IV: La Inteligencia Predictiva (Fases 29–32)
- **Fase 29**: Blueprint de Investigación (`gemelo_digital_reciclado.md`). Integración física-narrativa.
- **Fase 30**: Generador sintético de degradación C&DW (634,000 días simulados) + Red LSTM en PyTorch. MSE de validación: 0.18%.
- **Fase 31**: BIM Exporter API. Traducción de Time-To-Failure (meses) a colores de gestión (🟢🟡🔴) consumibles por cualquier visor 3D (Speckle/Forge/WebGL).
- **Fase 32**: **Guardian Angel** — Validador de Leyes Físicas Inmutables.

---

## El Guardian Angel: La Distinción que todo auditor exige

El sistema distingue entre **dato imposible** (sabotaje/fallo de hardware) y **evento extremo real** (impacto o fenómeno climático):

| Escenario | Clasificación | Acción del Sistema |
|-----------|--------------|-------------------|
| `fn` sube > 3 Hz | `IMPOSSIBLE` | 🚫 Bloqueo total. Sellado en Engram como fraude. |
| `fn` sube 1–3 Hz | `EXTREME_EVENT` | ⚠️ Alerta escalada humana. Pipeline continúa monitoreando. |
| T° = 500°C | `IMPOSSIBLE` | 🚫 Sensor alucinando o saboteado. BIM no se actualiza. |
| T° = 95°C (incendio perif.) | `EXTREME_EVENT` | ⚠️ Alerta de peligro externo. Pasa al LSTM con bandera. |
| ΔT = 38°C/paquete | `IMPOSSIBLE` | 🚫 Violación termodinámica. Descartado. |
| ΔT = 25°C/paquete | `EXTREME_EVENT` | ⚠️ Posible El Niño. Contexto climático requiere revisión. |

---

## Propuesta Política: Vivienda Inteligente de Economía Circular

### El Problema
Las obras de Concreto Reciclado en vivienda social han sido históricamente rechazadas por falta de monitoreo post-construcción. El ciudadano no tiene forma de saber si su vivienda está en buen estado.

### La Solución Belico Stack
1. **Instalación**: Cada módulo habitacional recibe un sensor embebido (Arduino Nicla Sense ME, ~$35 USD) que transmite su estado de salud estructural.
2. **Transparencia**: El ciudadano (o su alcalde) puede consultar el estado de su vivienda en un visor BIM desde cualquier tablet. Un edificio verde significa "sano por 24+ meses". Un edificio rojo significa "requiere atención en menos de 6 meses".
3. **Forense**: Todo evento (alarma, predicción, anomalía) queda sellado con SHA-256 en el Engram. Ninguna empresa constructora puede borrar el historial de fallos del material.
4. **Predicción**: El modelo LSTM, entrenado con 634,000 días de simulación de concreto reciclado, emite advertencias de mantenimiento con **meses de anticipación**, no horas.

### Costo de No Actuar
> Cada centímetro de fisura no detectada en una vivienda de material reciclado cuesta 10 veces más en reparación de emergencia que en mantenimiento preventivo. El Belico Stack convierte ese diferencial en ahorro presupuestal auditable.

---

## Integridad del Sistema: Respuestas a Auditores

**"¿Esto es propaganda técnica?"**
> No. El sistema es incapaz de generar un paper favorable si los datos son incorrectos. El Guardian Angel rechaza activamente datos que confirmarían premisas falsas.

**"¿El LSTM fue entrenado con datos reales?"**
> El modelo v1 fue entrenado con datos sintéticos calibrados con propiedades reales del C&DW (E=20GPa, ρ=1800 kg/m³, k=0.51 W/m·K, fc=20MPa). El siguiente paso es la validación con datos de laboratorio de muestras reales.

**"¿Qué pasa si el Guardian Angel bloquea un evento real?"**
> El sistema tiene dos niveles: `IMPOSSIBLE` (bloqueo total) y `EXTREME_EVENT` (alerta escalada). Un evento de impacto directo o fenómeno El Niño es clasificado como `EXTREME_EVENT`, pasa al pipeline con bandera de revisión humana, y no es bloqueado.

---

## Estado Actual del Repositorio

```
belico-stack/
├── config/params.yaml          # SSOT: Concreto C&DW (1800kg/m³, 0.51W/m·K)
├── src/
│   ├── physics/bridge.py       # Sincronizador + Guardian Angel v2
│   ├── physics/kalman.py       # Filtro de Kalman 1D
│   ├── ai/lstm_predictor.py    # Red LSTM PyTorch (MSE=0.18%)
│   └── firmware/
│       └── nicla_edge_shm.ino  # Firmware C++ FFT+Kalman Edge AI
├── tools/
│   ├── lora_emu.py             # Emulador LoRa (6 modos incl. paradoja_fisica)
│   ├── bim_exporter.py         # API de exportación JSON-BIM 3D
│   └── run_guardian_test.sh    # Stress Test: 6/6 PASS
├── articles/
│   ├── scientific_narrator.py  # Orquestador LSTM→Paper→BIM
│   └── blueprints/             # Intenciones científicas del Paper
└── data/
    └── synthetic/              # 634,000 días de degradación C&DW simulada
```

**Commits**: Fases 28–32 selladas en `main`. Cada commit vincula el código con el evento físico que lo motivó.

---

*"No proponemos obras. Proponemos obras que no pueden mentir."*
