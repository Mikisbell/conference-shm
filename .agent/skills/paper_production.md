---
name: "Paper Production Pipeline"
description: "Trigger: generating a draft, compiling PDF, running validate_submission, managing paper status flow"
metadata:
  author: "belico-stack"
  version: "4.0"
  domain: "all"
---

# Skill: Paper Production Pipeline

## When to Use

- Starting a new paper draft
- Running `validate_submission.py` or `compile_paper.sh`
- Managing paper status transitions (draft → review → submitted → accepted)
- Debugging validation failures with `--diagnose`

## Critical Patterns

### SDD Flow for Papers (DAG with parallel phases)

The orchestrator NEVER generates content. It delegates to sub-agents.
SPEC and DESIGN run in parallel (both depend only on EXPLORE/PROPOSE).

```
                    +-> SPEC --+
EXPLORE --> PROPOSE -|          |-> TASKS --> COMPUTE --> IMPLEMENT --> VERIFY --> FINALIZE --> ARCHIVE
  ^                  +-> DESIGN +       |        |           |                                    |
  |                                     |   [no data?]  [diagnose]                         [ask user]
  +-------------------------------------+--------+-----------+
```

**FUNDAMENTAL RULE: A paper is a REPORT of computational/experimental results. Without real data in `data/processed/`, there is no paper. COMPUTE generates the data. IMPLEMENT writes about it.**

### 1. EXPLORE (Orchestrator)
- Grep `project.domain` in `config/params.yaml` to confirm active domain
- Glob `data/processed/` to list available datasets (names only, do not read contents)
- Search Engram (layer 1 compact): `mem_search("paper")`
- Identify risks: `mem_save("risk: {paper_id} — {description}")`

### 2. PROPOSE (Orchestrator)
- One-paragraph proposal: topic, contribution, target journal
- Quick feasibility check: do we have the data for this quartile?
- `mem_save("paper_spec: {title} targeting {journal}")`

### 3. SPEC (Sub-agent, parallel with DESIGN)
- Define: quartile, target journal, quality gates from journal_specs.yaml
- Set word count, ref count, figure count targets
- List required figures (numbered: fig_01, fig_02...)

### 4. DESIGN (Sub-agent, parallel with SPEC)
- Outline IMRaD sections with estimated word counts per section
- Map figures to sections
- Map references to sections (use bibliography_engine categories)
- Identify which sub-agents needed (Verifier, Figure Agent, etc.)

### 5. TASKS (Orchestrator)
- Decompose into batches (NOT individual sections):
  - Batch 1: Methodology + Fig_methodology
  - Batch 2: Results + Fig_results
  - Batch 3: Discussion + Conclusions
  - Batch 4: Abstract + Intro + Refs
- Each batch has: input data, output sections, validation criteria
- **TASKS must also define COMPUTE requirements:** what records to download, what simulations to run, what damage states to sweep, what emulation modes to use.

### 5.5 COMPUTE (Sub-agents + User — MANDATORY)

**COMPUTE runs AFTER TASKS and BEFORE IMPLEMENT. It is NOT optional. It is NOT skippable. Without it, IMPLEMENT is BLOCKED.**

A paper without COMPUTE is an essay. The agent produced text about what "would happen" instead of reporting what DID happen. This is the root cause of papers with invented numbers.

#### Sub-phases (sequential, each has an exit gate):

**C0 — Infrastructure Check:**
- Verify solver installed (OpenSeesPy/FEniCSx/SU2 depending on domain)
- Verify SSOT readable: `from src.physics.models.params import P`
- Regenerate params: `python3 tools/generate_params.py`
- Gate: all checks pass → continue. Any failure → BLOCK.

**C1 — Excitation Data Acquisition:**
- Check what records exist: `python3 tools/fetch_benchmark.py --scan`
- If none exist → **ASK USER** which records to download (PEER NGA-West2, field data, etc.)
- Validate downloaded records: `python3 tools/fetch_benchmark.py --verify`
- Parse with `src/physics/peer_adapter.py` → numpy arrays
- Gate: ≥1 validated excitation record on disk → continue. Zero → BLOCK.

**C2 — Simulation Execution:**
- Build model: `torture_chamber.py` → `init_model()`
- For EACH record × EACH damage state: run transient analysis
- Extract outputs: displacement, acceleration, forces, rotations
- Save to `data/processed/{record}_{damage}.csv`
- Post-process: spectral analysis, damage metrics
- Verify convergence and physical plausibility
- Gate: all runs converged + files in `data/processed/` → continue. Divergence → BLOCK.

**C3 — Hardware Emulation (if paper involves sensors/firmware):**
- Run `arduino_emu.py` in appropriate mode
- Run `bridge.py` against emulator via `run_battle.sh`
- Validate Guardian Angel Red Lines and Gates
- Save telemetry to `data/processed/`
- Gate: if paper needs hardware → telemetry saved. If not → SKIP (document why).

**C4 — Supplementary Data (if needed):**
- Degradation datasets: `generate_degradation.py`
- ML training sets: combine simulation + degradation outputs
- Comparative spectra: `plot_spectrum.py`
- Gate: all DESIGN data sources exist on disk → continue. Missing → BLOCK.

**C5 — Data Gate Final (BLOCKING):**
- `ls data/processed/` must have ≥1 file
- Every figure planned in DESIGN must have its data source file on disk
- Every table must have its numbers traceable to a real file
- Create `data/processed/COMPUTE_MANIFEST.json` documenting everything
- Gate: COMPUTE_MANIFEST exists + all sources satisfied → IMPLEMENT unblocked.

**Engram (mandatory):**
```
mem_save("paper:{id} COMPUTE done — Records: [N], Simulations: [N], Files: [N in data/processed/]")
```

### IMPLEMENT Rules (post-COMPUTE)

Now that COMPUTE generated real data, IMPLEMENT changes fundamentally:

| Batch | What it writes | Where data comes from | Entry gate |
|-------|---------------|----------------------|------------|
| B1: Methodology | Describes the model THAT RAN (not "would run"). Real paths, real SSOT params, real OpenSeesPy version. | `config/params.yaml`, source code, `COMPUTE_MANIFEST.json` | C2 completed |
| B2: Results | Reports REAL simulation outputs. Figures plotted from `data/processed/`. Tables with numbers from CSVs. | `data/processed/*.csv`, `plot_figures.py` | Data files exist |
| B3: Discussion | Compares real results vs benchmarks and literature. Discusses REAL model limitations. | `data/processed/`, bibliography refs | B2 verified |
| B4: Abstract+Intro | Summarizes what WAS DONE and WAS FOUND, not what "is proposed". | All of the above | B1-B3 verified |

**Golden rule:** If a paper sentence says "the model produced X" and X is not in a file in `data/processed/`, that sentence is a LIE. The Verifier rejects it.

### Style Calibration (pre-IMPLEMENT — mandatory)

Before writing ANY section, the narrator must have a **style reference** from real published papers in the target venue. This is NOT optional.

**Procedure (runs once per paper, before Batch 1):**

**Run the script — este es el método canónico:**
```bash
python3 tools/style_calibration.py \
  --venue "{venue name}" \
  --year {year} \
  --n 5 \
  --paper-id {paper_id} \
  --save-md
```
Ejemplo: `python3 tools/style_calibration.py --venue "EWSHM" --year 2024 --n 5 --paper-id icr_shm_ae_conference --save-md`

El script hace todo automáticamente:
1. Busca en Semantic Scholar primero (`SEMANTIC_SCHOLAR_API_KEY` en `.env` para mayor cuota)
2. Cae a OpenAlex si hay rate limit (`OPENALEX_API_KEY` ya está en `.env`)
3. Extrae: voice, tense, avg sentence length, citation density, intro openers reales
4. Guarda Style Card en Engram (`mem_search("style: {paper_id}")` para recuperar)
5. Guarda Style Card en `articles/drafts/style_card_{paper_id}.md`

**Cada batch narrator** lee el Style Card antes de escribir:
- `mem_search("style: {paper_id}")` — desde Engram
- O lee `articles/drafts/style_card_{paper_id}.md` directamente

**Reviewer Simulator** compara el estilo del draft contra el Style Card durante VERIFY.

**Style Card example:**
```
Venue: EWSHM 2024
Voice: Mixed (active for methods, passive for results)
Citation density: 2-3 per paragraph in Intro, 1-2 in Methods, 0-1 in Results
Avg sentence length: 18 words
Opener pattern: Start with specific problem + statistic ("Fatigue cracking accounts for 23% of...")
Contribution intro: Explicit statement at end of Introduction ("This paper proposes...")
Transition style: No "Furthermore/Moreover". Use topical flow (last sentence of P1 introduces topic of P2)
```

**Anti-pattern:**
- Writing without a Style Card = writing blind = AI-detectable prose
- Using ChatGPT-style connectors instead of venue-appropriate transitions

> **Cross-reference:** For the complete style extraction workflow, see `.agent/skills/literature_review.md` Phase 0.

### 7. IMPLEMENT (Sub-agents, batched)
- **BLOCKED if COMPUTE_MANIFEST.json does not exist or has `design_sources_satisfied: false`.**
- Before generating content for any batch, verify data sources in `db/manifest.yaml`. If manifest has `status: pending` for a required data role, BLOCK and report.
- Execute one batch at a time via delegated sub-agents
- Each batch must pass partial VERIFY before advancing
- Sub-agent generates sections via `scientific_narrator.py` or manual writing
- Sub-agent generates figures via `plot_figures.py`
- Sub-agent generates BibTeX via `generate_bibtex.py`
- Mark AI-generated content with `<!-- AI_Assist -->`
- Sub-agents read context from Engram, write results to Engram

### 8. VERIFY (Verifier + Reviewer Simulator)
- Run `validate_submission.py` — must pass all 9 checks
- Run `validate_submission.py --diagnose` on failure
- Reviewer Simulator reads risks from Engram: `mem_search("risk: {paper_id}")`
- Run Verifier sub-agent if paper includes numerical results

### 9. FINALIZE (Sub-agents, post-VERIFY — prepare submission)

**This phase is MANDATORY. A paper is NOT done just because VERIFY passes.**

1. Generate final figures (real PDF/PNG, not placeholders) — Figure Agent
2. Compile PDF — `compile_paper.sh draft.md --template {template}`
3. Run Reviewer Simulator — must pass Gate 0 (AI prose), Gate 1 (data), Gate 2 (technical)
4. Generate cover letter if applicable — `generate_cover_letter.py`
5. Ask user for human review before ARCHIVE
6. `mem_save("paper: finalized {title} — figures: N, PDF: ok, reviewer: pass")`

### 10. ARCHIVE (Orchestrator, post-FINALIZE — close cycle)
- Merge delta specs (if SPEC changed during implementation)
- `mem_save("paper: archived {title} — ready for submission")`
- `mem_save("pattern: {lessons learned}")`
- Update draft status: `review` → `submitted`
- Document mitigated and pending risks
- **Ask user what's next** (submit? next paper? other?) — MANDATORY before any new EXPLORE

### 11. SUBMIT (Optional, user-initiated)
- Send to journal/conference (manual by user)
- `mem_save("paper: submitted {title} for {journal}")`

### Status Flow

```
draft --> review --> submitted --> accepted
```

### Engram Protocol for Papers (Bus Pattern)

```
# Orchestrator writes task
mem_save("task: {agent} — {description}")

# Sub-agent reads context, writes result
mem_search("task: {agent}")
mem_save("result: {agent} — {summary}")

# Orchestrator reads result (compact)
mem_search("result: {agent}")

# Standard paper events
mem_save("paper: [event] {title} for {journal}")
mem_save("decision: chose {journal} because {reason}")
mem_save("risk: {paper_id} — {risk description}")
mem_save("error: {check} failed → fix: {action}")
```

### Model Selection

| Phase | Recommended Model | Reason |
|-------|------------------|--------|
| EXPLORE, PROPOSE | Opus | Deep reasoning, gap analysis |
| SPEC, DESIGN | Opus | Critical architectural decisions |
| COMPUTE | Opus | Simulation setup requires engineering judgment |
| IMPLEMENT (batches) | Sonnet | Content generation, high throughput |
| VERIFY | Opus | Critical evaluation, error detection |
| FINALIZE | Sonnet | Mechanical: figures, PDF, cover letter |
| ARCHIVE, PUBLISH | Sonnet | Mechanical documentation |

### Tools Reference

| Step | Tool | Command |
|------|------|---------|
| Check records | `tools/fetch_benchmark.py` | `--scan`, `--verify` |
| Parse .AT2 | `src/physics/peer_adapter.py` | imported by simulation scripts |
| Run simulation | `src/physics/torture_chamber.py` | `init_model()`, transient analysis |
| Emulate Arduino | `tools/arduino_emu.py` | `[mode] [freq_hz]` (6 modes) |
| Run bridge | `tools/run_battle.sh` | launches emulator + bridge together |
| Spectral analysis | `src/physics/spectral_engine.py` | `compute_spectral_response(accel, dt)` |
| Cross-validation | `src/physics/cross_validation.py` | A vs B scenario comparison |
| Generate degradation | `tools/generate_degradation.py` | `--modules N --out path.csv` |
| Generate draft | `articles/scientific_narrator.py` | `--domain X --quartile QN --topic "..."` |
| Generate figures | `tools/plot_figures.py` | `--domain X` |
| Generate BibTeX | `tools/generate_bibtex.py` | `--output articles/references.bib` |
| Validate | `tools/validate_submission.py` | `articles/drafts/paper_*.md [--diagnose]` |
| Compile PDF | `tools/compile_paper.sh` | `draft.md --template ieee\|conference\|elsevier` |
| Cover letter | `tools/generate_cover_letter.py` | `cover --draft draft.md` |

## Writing Style — Anti-AI Enforcement

**Every sub-agent generating paper text MUST follow these rules. Violations cause VERIFY to fail.**

### Blacklisted Phrases (from Belico.md Red Line)

These phrases are BANNED in any draft. `validate_submission.py` scans for them automatically:

- "It is worth noting", "It is important to note", "It should be noted"
- "Furthermore", "Moreover", "Additionally" as sentence starters
- "In this study, we", "This paper presents", "This work proposes"
- "delve into", "delve deeper", "shed light on"
- "leveraging", "utilizing", "harnessing" (use "using")
- "novel framework", "novel approach", "novel methodology" (without evidence)
- "comprehensive", "robust", "seamless", "cutting-edge", "state-of-the-art" (without citation)
- "plays a crucial role", "has gained significant attention"
- "In recent years", "In the last decade"
- "paradigm shift", "game-changer", "groundbreaking", "revolutionary"
- "a myriad of", "a plethora of", "a multitude of"
- "In conclusion, this study has demonstrated"
- "paving the way for future research"

### BAD vs GOOD Examples

```
BAD:  "Furthermore, the novel framework leverages state-of-the-art PINNs to comprehensively address the problem."
GOOD: "The framework uses PINNs to locate damage sources without a predefined mesh."

BAD:  "It is worth noting that the results clearly demonstrate a significant improvement."
GOOD: "Localization error dropped from 12.3% to 3.1% after adding the Helmholtz constraint (Table 2)."

BAD:  "In recent years, structural health monitoring has gained significant attention."
GOOD: "Bolt fatigue causes 23% of steel connection failures in seismic zones (Swanson, 2020)."
```

### The Specificity Rule

Every sentence must contain at least ONE of:
- (a) a number or measurement
- (b) a citation
- (c) a method name
- (d) a specific technical detail

Generic prose = AI prose. If a sentence could appear in any paper from any field, it is too generic. Rewrite it with domain-specific content.

### Structural Rules

- Never start 2 consecutive paragraphs with the same word
- Never start 3 consecutive sentences with "The"
- Maximum 1 semicolon per paragraph
- No sentences longer than 40 words
- Active voice: "We model..." not "The model was developed..."
- Specific verbs: "measured", "computed", "observed", "recorded" — not "obtained", "performed", "conducted"
- Vary sentence length: mix short (8-12 words) with medium (15-25 words)

### Tone

- Write like an engineer explaining to a colleague
- Be direct: what you did, what you found, what it means
- Uncertainty is honest: "The results suggest..." > "The results clearly demonstrate..."
- Acknowledge limitations explicitly

## Anti-Patterns

- Orchestrator generating paper content directly (MUST delegate)
- Running all IMPLEMENT at once instead of batched with incremental verify
- Passing large prompts to sub-agents instead of using Engram bus
- Writing a paper without first checking journal_specs.yaml gates
- Skipping EXPLORE (leads to duplicate work or wrong quartile)
- Skipping ARCHIVE (loses lessons learned, delta specs not merged)
- Running compile_paper.sh before validate_submission.py passes
- Forgetting `<!-- AI_Assist -->` markers on AI-generated paragraphs
- Leaving `[TODO]` markers in a draft marked as `review`
- **Skipping COMPUTE and going straight to IMPLEMENT** (produces essays with invented numbers, not papers with real data)
- **Writing Results without files in `data/processed/`** (if the directory is empty, COMPUTE didn't run)
- **Describing what a model "would do" instead of what it DID** (run the simulation first, write about it after)
- **Generating figures from placeholder data instead of simulation outputs** (figures must have `data_source` pointing to real files)
- **Not asking the user for excitation records** (PEER downloads require user action — the agent must ask)
- **Adding future paper tasks to current TODO** (scope creep — ideas go to Engram, not TodoWrite)
- **Starting a new EXPLORE before current paper reaches ARCHIVE** (one paper at a time)
- **Planning Q3/Q2/Q1 while Conference paper is still in IMPLEMENT** (finish first, plan later)
