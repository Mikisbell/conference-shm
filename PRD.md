# PRD — Belico Stack: Ecosistema de Investigacion Universal (EIU)
# Version: 4.0.0 | Autor: Mikisbell | Fecha: 2026-03-06
# AUDITADO: Cada estado fue verificado leyendo el codigo fuente linea a linea.
# UPDATE 4.0: Orchestrator-delegator, batched IMPLEMENT, ARCHIVE phase, Engram bus, progressive disclosure

---

## 1. Problema

Un investigador en ingenieria estructural necesita publicar papers Q1-Q4 con evidencia sismica real. Hoy, ese proceso es manual, fragmentado y vulnerable:

- Los datos del sensor se procesan en Excel, sin cadena de custodia.
- La simulacion (OpenSeesPy) corre desconectada del sensor.
- El paper se escribe a mano, sin trazabilidad entre dato y afirmacion.
- Un revisor puede cuestionar cualquier resultado porque no hay forma de probar que no fue manipulado.

**Consecuencia:** Papers rechazados, investigacion lenta, evidencia debil.

---

## 2. Vision

Belico Stack es una **Fabrica de Articulos Cientificos Q1-Q4** construida sobre un bunker de ingenieria real. Es un EIU (Ecosistema de Investigacion Universal) que toma el control total desde el sensor en el campo hasta la sumision en revistas como Elsevier o IEEE.

**En una frase:** El investigador supervisa; el sistema trabaja solo.

---

## 3. Usuario

**Mikisbell (Mateo)** — Investigador en ingenieria estructural sismica.
- Trabaja con estructuras de concreto reciclado (C&DW) en La Presa del Norte.
- Necesita publicar en journals Q1-Q4 y conferencias (EWSHM, SHMII, IMAC).
- Opera con hardware de bajo costo (Arduino, ~$30/nodo).
- Supervisa el sistema; no escribe codigo ni papers desde cero.

---

## 4. Dependencias Externas (Ecosistema Gentleman Programming)

El EIU se construye sobre el ecosistema open-source de Gentleman Programming. Estas herramientas proveen memoria, orquestacion y flujo de trabajo.

| Componente | Repo | Requerido | Funcion | Instalacion |
|------------|------|-----------|---------|-------------|
| **Engram** | [Gentleman-Programming/engram](https://github.com/Gentleman-Programming/engram) | SI | Memoria persistente (SQLite + FTS5, 14 MCP tools) | `brew install gentleman-programming/tap/engram` |
| **Gentle AI** | [Gentleman-Programming/gentle-ai](https://github.com/Gentleman-Programming/gentle-ai) | SI | Configurador ecosistema (SDD + Skills + MCP) | `brew install gentleman-programming/tap/gentle-ai` |
| **Agent Teams Lite** | [Gentleman-Programming/agent-teams-lite](https://github.com/Gentleman-Programming/agent-teams-lite) | SI | Orquestacion SDD (9 fases, sub-agentes delegados) | Clonado en `.agents/agent-teams-lite/` |
| **GGA** | [Gentleman-Programming/gentleman-guardian-angel](https://github.com/Gentleman-Programming/gentleman-guardian-angel) | NO | Pre-commit code review con IA | `brew install gentleman-programming/tap/gga` |
| **Gentleman Skills** | [Gentleman-Programming/Gentleman-Skills](https://github.com/Gentleman-Programming/Gentleman-Skills) | NO | Referencia de formato SKILL.md | Clonado en `.agents/Gentleman-Skills/` |
| **veil.nvim** | [Gentleman-Programming/veil.nvim](https://github.com/Gentleman-Programming/veil.nvim) | NO | Ocultar secretos en Neovim | Plugin Neovim |
| **Gentleman.Dots** | [Gentleman-Programming/Gentleman.Dots](https://github.com/Gentleman-Programming/Gentleman.Dots) | NO | Dotfiles de entorno de desarrollo | `brew install gentleman-programming/tap/gentleman-dots` |

**Instalacion rapida:** `bash tools/setup_dependencies.sh` (interactivo) o `bash tools/setup_dependencies.sh --all` (todo).

### Flujo de Onboarding

```
1. git clone belico-stack && cd belico-stack
2. bash tools/setup_dependencies.sh          # instala Engram, Gentle AI, Agent Teams Lite
3. engram setup claude-code                   # configura MCP para Claude Code
4. Abre Claude Code y di: "Engram conecto"
5. El sistema verifica dependencias, carga contexto, y pregunta:
   "Que tipo de articulo cientifico quieres desarrollar?"
   → Conference | Q4 | Q3 | Q2 | Q1
6. Segun la eleccion, se cargan quality gates y arranca el flujo SDD
```

---

## 5. Arquitectura: Tres Capas del EIU

### 5.1 El Musculo (Capa Fisica — Evidencia Inatacable)

**Proposito:** Adquirir datos del mundo real y sellarlos criptograficamente.

| Componente | Archivo | Estado | Notas |
|------------|---------|--------|-------|
| Firmware Nicla (campo) | `src/firmware/nicla_edge_field.ino` | FUNCIONAL | Kalman on-board + LoRa + deep sleep. Consume params.h. |
| Firmware Nicla (SHM) | `src/firmware/nicla_edge_shm.ino` | FUNCIONAL | FFT on-board + alarmas fn/max_g. Consume params.h. |
| Firmware Nano33 (backup) | `src/firmware/nano33_belico.ino` | FUNCIONAL | USB directo 100Hz. Consume params.h. |
| SSOT | `config/params.yaml` | FUNCIONAL | Fuente unica de verdad (166 lineas). |
| Generador SSOT | `tools/generate_params.py` | FUNCIONAL | params.yaml -> params.h + params.py. Verificado. |
| Bridge (lazo cerrado) | `src/physics/bridge.py` | FUNCIONAL | Handshake + Watchdog + Guardian Angel + Kalman + Abort. `inject_and_analyze()` recibe model_props de torture_chamber. |
| Guardian Angel | En `bridge.py` clase `GuardianAngel` | FUNCIONAL | 4 gates fisicos (S1-S4): rigidez, temp, gradiente, bateria. Logica correcta. |
| Protocolo de Aborto | En `bridge.py` clase `AbortController` | FUNCIONAL | 3 Red Lines: jitter, esfuerzo, divergencia. Logica correcta. |
| Engram (notario) | `src/physics/engram_client.py` + `.agent/memory/engram/engram.db` | COMPILADO / VACIO | SQLite funcional, inserta SHA-256. Pero la DB tiene 0 registros reales. MCP tools no cargan. |
| Kalman 1D | `src/physics/kalman.py` | FUNCIONAL | Prediccion + innovacion + varianza. 51 lineas, correcto. |
| Paths centralizados | `config/paths.py` | FUNCIONAL | Resolucion dinamica de rutas del proyecto. |

### 5.2 El Cerebro (IA + Fisica Profunda)

**Proposito:** Simular, predecir y validar comportamiento estructural.

| Componente | Archivo | Estado | Notas |
|------------|---------|--------|-------|
| Camara de Tortura | `src/physics/torture_chamber.py` | FUNCIONAL | Lee E, fy, rho, m, k, xi de SSOT. P-Delta 2D con Pcr de Euler. Retorna dict de propiedades para bridge.py. |
| Modelo SDOF (params) | `src/physics/models/params.py` | FUNCIONAL | 1-GDL OpenSeesPy que SI lee la SSOT (m, k, fy, xi). Pero NO es usado por bridge.py. |
| Motor Espectral | `src/physics/spectral_engine.py` | FUNCIONAL | Sa(T,z) via Duhamel real (420 lineas), Newmark-Beta, E.030 site amplification, Eurocode 8 damping correction. Componente mas solido del stack. |
| Cross Validation | `src/physics/cross_validation.py` | FUNCIONAL (analitico) | FP rate via erfc(), PGA sweep parametrico, Saltelli con k_term de SSOT. Documentado como estimacion analitica, no simulacion. |
| Adaptador PEER | `src/physics/peer_adapter.py` | FUNCIONAL | Parser .AT2, resampling con scipy, scale_to_pga. 133 lineas, verificado. |
| Boveda Sismica | `data/external/peer_berkeley/` | 3 REGISTROS | Pisco 2007, Loma Prieta, Sintetico extremo. |
| LSTM Predictor | `src/ai/lstm_predictor.py` | CODIGO OK / INOPERABLE | Arquitectura correcta (2-layer LSTM + MC Dropout). Pero: datos de entrenamiento borrados, modelo no existe, scalers no existen. |
| Generador Sintetico | `tools/generate_cdw_degradation.py` | FUNCIONAL | Wiener process + estacionalidad. Lee fn y k_term de SSOT. Dataset regenerado: 47,417 muestras. |
| PgNN Surrogate | `src/ai/pgnn_surrogate.py` | FUNCIONAL | Bridge a Hybrid-Twin, namespace isolation, 10-story Seq2Seq, ~2ms. Verificado end-to-end. |

### 5.3 La Voz (Q-Factory — Publicacion Automatizada)

**Proposito:** Generar papers listos para submission bajo supervision humana.
**Flujo SDD:** EXPLORE → PROPOSE → [SPEC ‖ DESIGN] → TASKS → IMPLEMENT (batched) → VERIFY → ARCHIVE → PUBLISH.
**Patron:** Orchestrator-delegator puro. El orquestador NUNCA genera contenido, solo delega a sub-agentes.
**Comunicacion:** Engram como bus inter-agente (sub-agentes leen/escriben en Engram, no reciben prompts largos).

| Componente | Archivo | Estado | Notas |
|------------|---------|--------|-------|
| Research Director | `tools/research_director.py` | FUNCIONAL (con datos falsos) | Orquesta: generate_params -> CrossValidation -> Spectral -> Narrator. Pipeline ejecuta, datos de cross_validation son simulacro. |
| Scientific Narrator | `articles/scientific_narrator.py` | FUNCIONAL (multi-dominio) | Genera IMRaD por dominio (structural/water/air). Fallback "Zero-Trust Cold Start". |
| Motor de Citas | `tools/bibliography_engine.py` | FUNCIONAL | 53 refs en 12 categorias (incluye cfd, hydraulics, wind). |
| Generador BibTeX | `tools/generate_bibtex.py` | FUNCIONAL | Vault → .bib para Pandoc --citeproc. 65 entradas. |
| Compilador PDF | `tools/compile_paper.sh` | FUNCIONAL | Pandoc + XeLaTeX + citeproc: IEEE, Elsevier, Conference, Plain. |
| Generador de Figuras | `tools/plot_figures.py` | FUNCIONAL (multi-dominio) | Figuras numeradas PDF+PNG. Structural: 4 figs. Water/Air: placeholders. |
| Validador Pre-Submission | `tools/validate_submission.py` | FUNCIONAL (verificado E2E) | 9 checks + journal specs + modo --diagnose (DAG loop-back). |
| Cover Letter Generator | `tools/generate_cover_letter.py` | FUNCIONAL | Cover letter parametrica + respuesta a reviewers point-by-point. |
| Journal Specs (TDD) | `.agent/specs/journal_specs.yaml` | FUNCIONAL | Quality gates: Q1(50+refs,8+figs,6k+words), conference(10+refs,3+figs,2.5k+words). |

### 5.4 Sub-Agentes y Skills (Refuerzos Gentleman v3.0)

| Componente | Path | Tipo | Notas |
|------------|------|------|-------|
| Verifier | `.agent/prompts/verifier.md` | Sub-agente | 7 pasos verificacion numerica. |
| Physical Critic | `.agent/prompts/physical_critic.md` | Sub-agente | Torsion, pandeo, inestabilidad modal. |
| Bibliography Agent | `.agent/prompts/bibliography_agent.md` | Sub-agente | Cobertura categorias por dominio + recency. |
| Figure Agent | `.agent/prompts/figure_agent.md` | Sub-agente | Generacion + validacion calidad + cross-ref. |
| Reviewer Simulator | `.agent/prompts/reviewer_simulator.md` | Sub-agente | Pre-submission review hostil (Major/Minor/Optional). |
| Signal Processing | `.agent/skills/signal_processing.md` | Skill | Kalman, drift, phase lag. |
| Paper Production | `.agent/skills/paper_production.md` | Skill | SDD flow completo para papers. |
| CFD Domain | `.agent/skills/cfd_domain.md` | Skill | FEniCSx, Navier-Stokes, mesh convergence. |
| Wind Domain | `.agent/skills/wind_domain.md` | Skill | SU2, ABL profiles, Cp distribution. |
| Norms & Codes | `.agent/skills/norms_codes.md` | Skill | E.030, Eurocode 8, ASCE 7, load combos. |

### 5.5 Herramientas de Soporte

| Componente | Archivo | Estado | Notas |
|------------|---------|--------|-------|
| Setup Dependencies | `tools/setup_dependencies.sh` | FUNCIONAL | Instala Engram, Gentle AI, Agent Teams Lite, GGA, Skills. Modos: --check, --all, interactive. |
| Emulador Arduino USB | `tools/arduino_emu.py` | FUNCIONAL | PTY + 6 modos de caos (sano, resonancia, dano leve/critico, presa, dropout). |
| Emulador LoRa | `tools/lora_emu.py` | FUNCIONAL | PTY + 6 modos (sano, lag_attack, dano leve/critico, paradoja_fisica, peer_benchmark). |
| Calibrador Baseline | `tools/baseline_calibration.py` | FUNCIONAL | Estadisticas 3-sigma sobre paquetes LoRa. Genera field_baseline.yaml. |
| BIM Exporter | `tools/bim_exporter.py` | FUNCIONAL | JSON Speckle-compatible con heatmap de riesgo. Depende del LSTM para TTF. |
| Audit Bunker | `src/init_bunker.py` | FUNCIONAL | Smoke test de dependencias. |
| Field Acquire | `tools/field_acquire.sh` | FUNCIONAL | Launcher automatizado de campanas de campo. |

### 5.6 Requisitos de Workflow (v4.0)

Estas son las reglas operativas del EIU. No son sugerencias — son requisitos activos.

| # | Requisito | Verificacion |
|---|-----------|-------------|
| W1 | El orquestador (CLAUDE.md) NUNCA genera contenido directamente | Revisar que toda generacion de texto/figuras/BibTeX pasa por sub-agente |
| W2 | SPEC y DESIGN corren en paralelo (ambas dependen solo de PROPOSE) | Verificar que no hay dependencia secuencial entre ellas |
| W3 | IMPLEMENT se ejecuta por batches con verificacion incremental | Cada batch pasa VERIFY parcial antes de avanzar |
| W4 | Sub-agentes usan Engram como bus (no prompts largos) | Sub-agente lee `mem_search`, escribe `mem_save` |
| W5 | Progressive disclosure: siempre empezar por capa 1 (compact) | `mem_search` antes de `mem_timeline` antes de `mem_get_observation` |
| W6 | Riesgos identificados en EXPLORE se guardan en Engram | `mem_save("risk: {paper_id} — {desc}")` |
| W7 | VERIFY usa riesgos de Engram para atacar el paper | `mem_search("risk: {paper_id}")` |
| W8 | ARCHIVE cierra cada ciclo SDD (merge specs + lecciones) | `mem_save("paper: archived ...")` + patterns |
| W9 | Seleccion de modelo: Opus para planificacion, Sonnet para generacion | Ver tabla en CLAUDE.md |
| W10 | Contexto del orquestador <= 15% del total | Si se satura, esta haciendo trabajo que deberia delegar |

---

## 6. Flujo End-to-End

```
Sensor (Arduino)
  |
  v
bridge.py --- Handshake SSOT --- Guardian Angel --- Kalman --- Watchdog
  |                                  |
  |  [SHUTDOWN si viola fisica] <----+
  v
OpenSeesPy (torture_chamber.py) --- Red Lines (Abort si diverge)
  |
  v
cross_validation.py --- spectral_engine.py --- peer_adapter.py
  |
  v
lstm_predictor.py / pgnn_surrogate.py
  |
  v
research_director.py --- scientific_narrator.py --- bibliography_engine.py
  |
  v
validate_submission.py --diagnose (9 checks + journal specs + DAG loop-back)
  |
  v [PASS]                        [FAIL] --> loop back al paso indicado
compile_paper.sh --> PDF (IEEE / Elsevier / Conference)
  |
  v
generate_cover_letter.py --> Cover letter + reviewer response template
  |
  v
Paper Q1-Q4 listo para submission
```

**ESTADO REAL DEL FLUJO (post-fix B1-B6):**
- torture_chamber lee SSOT correctamente (C&DW 20GPa, m=1000kg)
- bridge.py usa model_props de torture_chamber (masa, inercia, seccion)
- cross_validation usa parametros SSOT (erfc para FP, k_term para Saltelli)
- Datos sinteticos LSTM regenerados (47,417 muestras)
- PENDIENTE: LSTM aun no entrenado, Engram sin registros reales, datos de campo no adquiridos

---

## 7. Bugs Criticos (Bloquean Integridad Cientifica)

| # | Bug | Estado | Resolucion |
|---|-----|--------|------------|
| B1 | `torture_chamber.py` ignoraba SSOT | CORREGIDO | Reescrito: lee E, fy, rho, m, k, xi de params.yaml. Retorna dict de propiedades. |
| B2 | `bridge.py` hardcodeaba mass=5000kg | CORREGIDO | `inject_and_analyze()` ahora recibe `model_props` dict de torture_chamber. |
| B3 | `cross_validation.py` retornaba valores inventados | CORREGIDO | Reescrito: FP rate via `math.erfc()`, PGA sweep parametrico, Saltelli con k_term de SSOT. |
| B4 | Dos modelos OpenSeesPy en conflicto | CORREGIDO | `models/params.py` ya no auto-ejecuta `init_model()`. Bridge usa torture_chamber como modelo principal. |
| B5 | LSTM sin datos sinteticos | CORREGIDO | `generate_cdw_degradation.py` reescrito para leer SSOT. Regenerado: 47,417 muestras en `data/synthetic/`. |
| B6 | Engram vacio | VERIFICADO | Schema completo (15 tablas, FTS). Se llenara con uso real del sistema. No es bug de codigo. |
| B7 | `transparency_dashboard.py` fy_mpa=250 (acero) | CORREGIDO | Lee fy de SSOT (20 MPa concreto) y stress_ratio de guardrails. |
| B8 | `bridge.py` referencia `worst_case.py` inexistente | CORREGIDO | Funcion limpiada como placeholder con TODO documentado. |
| B9 | `models/params.py` fallback k=100000, fy=250e6 | CORREGIDO | Fallbacks alineados con SSOT: k=5000, fy=20e6. |
| B10 | `scientific_narrator.py` rutas relativas `models/lstm/` | CORREGIDO | Rutas absolutas via `Path(__file__).resolve().parent.parent`. |
| B11 | 3 scripts test hardcodean FS=100 | CORREGIDO | Importan `SAMPLE_RATE_HZ` de `src.physics.params`. |
| B12 | `belico.yaml` rutas `.agent/teams/` vs `.agents/` | CORREGIDO | Paths actualizados a estructura real. |
| B13 | `Presa_del_Norte/belico.yaml` dominio agua + Navier-Stokes | CORREGIDO | Reescrito como proyecto structural C&DW. |
| B14 | `init_investigation.sh` referencia `.env.example` inexistente | CORREGIDO | Eliminada referencia, paths corregidos. |

---

## 8. Gap Analysis (Lo que falta)

### Critico (bloquea publicacion):
| Gap | Impacto | Accion |
|-----|---------|--------|
| Datos de campo reales (S1, 30 min) | Sin datos no hay Q3/Q4 | Ejecutar campana de campo |
| ~~Corregir torture_chamber para usar SSOT~~ | ~~RESUELTO~~ | B1 corregido |
| ~~Corregir bridge.py hardcodes~~ | ~~RESUELTO~~ | B2 corregido |
| ~~Reemplazar cross_validation simulacro~~ | ~~RESUELTO~~ | B3 corregido (analitico con SSOT) |

### Importante (mejora calidad):
| Gap | Impacto | Accion |
|-----|---------|--------|
| LSTM: pipeline validable pero sin proyecto | Se entrena cuando haya un proyecto real | Pipeline listo (datos sinteticos + arquitectura). Entrenar es paso de PRODUCCION, no de fabrica. |
| Engram MCP tools no cargan | Sin memoria persistente entre sesiones | Diagnosticar MCP server |
| Boveda sismica con solo 3 registros | Limitado para analisis estadistico | Expandir con PEER NGA-West2 |
| ~~Bibliografia en 42 refs~~ | ~~RESUELTO~~ | Expandida a 53 refs en 12 categorias + BibTeX generator (65 entradas) |

### Menor (puede esperar):
| Gap | Impacto | Accion |
|-----|---------|--------|
| worst_case.py no existe | Modo prediccion no funciona | Implementar o remover referencia |
| ~~Belico.md tiene secciones duplicadas~~ | ~~RESUELTO~~ | Limpiado en v3.0 |

### Resuelto en v3.0 (Refuerzos Gentleman):
| Gap | Resolucion |
|-----|------------|
| Sin flujo SDD para papers | Implementado: EXPLORE→SPEC→DESIGN→TASKS→IMPLEMENT→VERIFY (DAG) |
| Sin quality gates por journal | `journal_specs.yaml`: gates Q1-Q4+conference (refs, figs, words, novelty) |
| Sin sub-agentes para La Voz | 3 nuevos: Bibliography Agent, Figure Agent, Reviewer Simulator |
| Sin skills multi-dominio | 4 nuevos: paper_production, cfd_domain, wind_domain, norms_codes |
| Sin estrategia de compactacion | Zona Roja/Amarilla/Verde en CLAUDE.md |
| Engram guardaba eventos, no decisiones | Protocolo reformado: decisions/patterns/errors (formato tabla) |
| Validador sin diagnose ni specs | validate_submission.py: 9 checks + --diagnose + journal_specs.yaml |

---

## 9. Producto: Que Entrega el EIU

| Nivel | Target | Requisitos de Datos | Refs | Estado |
|-------|--------|-------------------|------|--------|
| Conference | EWSHM, SHMII, IMAC | Datos sinteticos + framework | 10-30 | FABRICA LISTA (pipeline E2E verificado, falta producir draft real) |
| Q3/Q4 | Journals regionales | Datos de campo (30min) + 2 metodos | 25-60 | PENDIENTE campo |
| Q2 | Journals intermedios | Campo + laboratorio + fragilidad | 35-80 | PENDIENTE lab |
| Q1 | Engineering Structures, SHM (SAGE) | 2+ estructuras + contribucion teorica | 50-120 | PENDIENTE datos |

---

## 10. Criterios de Exito

### MVP (Fabrica operativa):
- [x] Bugs B1-B14 corregidos (SSOT respetada en todos los archivos)
- [x] Pipeline La Voz completo: narrator → figures → bibtex → validate → compile → cover letter
- [x] Sub-agentes La Voz operativos: Bibliography, Figure, Reviewer Simulator
- [x] Skills multi-dominio: paper_production, cfd, wind, norms
- [x] TDD specs por journal: quality gates Q1-Q4+conference
- [x] Flujo SDD para papers: DAG iterativo con --diagnose
- [x] Estrategia de compactacion de contexto definida
- [x] Protocolo Engram reformado (decisiones, no datos)
- [ ] `research_director.py` ejecuta end-to-end con datos reales de OpenSeesPy
- [ ] Un paper conference se genera desde `cv_results.json` hasta PDF en < 5 minutos
- [ ] Todos los datos en el paper son trazables a `data/processed/` o Engram

### V1 (Primera publicacion):
- [ ] Paper conference enviado a SHMII-14 (deadline: Sep 30, 2026)
- [ ] Datos de campo S1 adquiridos y procesados
- [ ] Verifier firma el `export_manifest.json`

### V2 (Q3/Q4 Journal):
- [ ] 30+ minutos de datos reales de campo
- [ ] Comparacion A/B con datos reales (no sinteticos ni hardcodeados)
- [ ] Paper enviado a journal Q3/Q4

### V3 (Q1 Journal):
- [ ] 2+ estructuras monitoreadas
- [ ] Contribucion teorica original
- [ ] 50+ referencias
- [ ] Paper enviado a Engineering Structures o SHM (SAGE)

---

## 11. Fuera de Alcance

- Belico Stack **NO** es un producto comercial ni un SaaS
- Belico Stack **NO** reemplaza al investigador — es su herramienta
- El PgNN Surrogate (Hybrid-Digital-Twin) es un proyecto separado que se integra como modulo opcional
- La estructura de C&DW en La Presa es un **caso de uso**, no la identidad del stack
- El stack es transferible a cualquier estructura y cualquier material

---

## 12. Documentos Relacionados

| Documento | Funcion | Path |
|-----------|---------|------|
| Belico.md | Constitucion operativa (guardrails, Red Lines, sub-agentes) | `Belico.md` |
| CLAUDE.md | Router del agente (protocolo arranque, skills, SDD, compactacion) | `CLAUDE.md` |
| PRD.md | **Este documento** — Que construimos y para que | `PRD.md` |
| MEMORY.md | Memoria persistente del agente entre sesiones | `.claude/.../memory/MEMORY.md` |
| params.yaml | SSOT — Fuente unica de verdad de parametros fisicos | `config/params.yaml` |
| journal_specs.yaml | Quality gates TDD por quartil (Q1-Q4+conference) | `.agent/specs/journal_specs.yaml` |
