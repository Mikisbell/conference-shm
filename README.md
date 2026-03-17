# Belico Stack — La Madre Creadora de Fábricas

> **From idea to Q1 paper. One mother stack. Infinite child factories.**

An AI-powered Universal Research Ecosystem (EIU) that creates independent scientific paper factories from a single mother template. Built on the [Gentleman Programming](https://github.com/Gentleman-Programming) ecosystem (Engram + SDD + GGA + Skills).

---

## ⚡ Child First Steps — You Just Cloned This Repo

> You cloned `belico-stack` as a **child factory**. The repo is a template — several fields are intentionally `null` and must be filled with YOUR project data before anything runs.

### Step 1 — Install dependencies

```bash
bash tools/setup_dependencies.sh
```

Requires: Engram, Gentle AI, Agent Teams Lite, GGA. See [Dependencies](#dependencies) section below.

### Step 2 — Configure your project (SSOT)

Open `config/params.yaml` and fill in the `null` fields for your project:

```yaml
project:
  name: "your-project-name"       # e.g. conference-shm
  domain: "structural"            # structural | water | air | other

structure:
  height_m: ???                   # your structure height
  num_stories: ???                # number of stories

design:
  Z: ???                          # seismic zone factor for YOUR code (E.030/ASCE7/EC8)
                                  # E.030: Z=0.10/0.25/0.35/0.45 | ASCE7: SS/S1 from maps
                                  # EC8: ag/g per annex

excitation:
  default_record: ""              # leave empty OR set path after downloading from PEER
                                  # Download: https://ngawest2.berkeley.edu (free account)
```

### Step 3 — Configure your site

Open `config/soil_params.yaml` and fill in site-specific values (soil type, zone factor, period parameters) for your seismic code. Examples for E.030, ASCE 7, and Eurocode 8 are in the file comments.

### Step 4 — (Optional) Download seismic records

If your paper requires real ground motion records:

```bash
# Interactive PEER downloader
python3 tools/peer_downloader.py

# Records go to: db/excitation/records/
# Then set excitation.default_record in config/params.yaml
```

For Conference papers, synthetic data is sufficient — skip this step.

### Step 5 — Open your AI agent and say:

```
Engram conecto
```

The orchestrator will verify your setup, load context, and ask: **"Qué vamos a desarrollar?"**

---

## The Core Identity: Mother → Child Factories

**Belico Stack is the mother. You never write papers here directly.** Instead, the mother spawns child projects — each one an independent scientific paper factory with its own repo, its own data, and its own pipeline.

```
belico-stack (MOTHER — this repo)
    │
    ├── init_child.sh → bridge-shm/          ← Conference SHM 2026
    ├── init_child.sh → material-fatigue/    ← Q3 JCSHM
    ├── init_child.sh → tower-monitoring/    ← Q1 Engineering Structures
    └── init_child.sh → ...as many as needed
```

Each child:
- Is a **complete, independent factory** with its own GitHub repo
- Inherits the full pipeline: tools, sub-agents, skills, config, Engram
- Produces a paper chain: Conference → Q4 → Q3 → Q2 → Q1
- Can pull mother improvements: `git fetch belico && git merge belico/main`

**Improvements, bug fixes, and new tools go here (the mother).** All child factories inherit them.

### Creating a child factory

```bash
# From the mother:
bash tools/init_child.sh --target ~/PROJECTS/bridge-shm

# This bootstraps the child with:
# CLAUDE.md, Belico.md, GEMINI.md, tools/, .agent/, config/, db/ skeleton
# .mcp.json, .gga, requirements.txt, PRD.md skeleton
```

---

## Architecture: The 4 Pillars

These are the vertebral column of the mother stack. Everything else is built on top of them.

```
┌─────────────────────────────────────────────────────────────────────┐
│                    BELICO STACK — MOTHER                            │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  PILLAR 1 — ORCHESTRATOR (CLAUDE.md / GEMINI.md)             │   │
│  │  Plans · Delegates · Coordinates · Validates                 │   │
│  │  NEVER generates content directly                            │   │
│  └─────────────────────────┬────────────────────────────────────┘   │
│                            │ delegates via Agent tool               │
│  ┌─────────────────────────▼────────────────────────────────────┐   │
│  │  PILLAR 2 — SUB-AGENTS (The Muscle)                          │   │
│  │  Verifier · Physical Critic · Bibliography · Figure          │   │
│  │  Reviewer Simulator · Patent · Domain Scaffolder             │   │
│  │  Each reads its own prompt file + works autonomously         │   │
│  └──────────┬──────────────────────────┬───────────────────────┘   │
│             │ reads/writes             │ reads/writes               │
│  ┌──────────▼──────────────────────┐  │                            │
│  │  PILLAR 3 — ENGRAM              │  │                            │
│  │  Brain · Memory · Inter-agent   │  │                            │
│  │  bus · Decisions · Patterns     │  │                            │
│  │  ~/.engram/engram.db (ONE DB)   │  │                            │
│  └─────────────────────────────────┘  │                            │
│                                       │                            │
│  ┌────────────────────────────────────▼───────────────────────┐    │
│  │  PILLAR 4 — GGA (Gentleman Guardian Angel)                 │    │
│  │  Pre-commit AI code review · 11 AGENTS.md rules            │    │
│  │  Blocks: fabricated data · silent failures · hardcoded     │    │
│  │  secrets · SSOT violations · traceability gaps             │    │
│  └────────────────────────────────────────────────────────────┘    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### How the 4 pillars work together

```
User: "Engram conecto"
         │
         ▼
ORCHESTRATOR boots → queries ENGRAM (paper: active, risk:, decisions)
         │
         ▼
ORCHESTRATOR plans → saves task to ENGRAM bus
         │
         ├──→ launches SUB-AGENT (Verifier, Bibliography, Figure, ...)
         │          │
         │          ├── reads task from ENGRAM
         │          ├── reads files autonomously
         │          └── saves result to ENGRAM
         │
         ├──→ ORCHESTRATOR reads result from ENGRAM (not raw output)
         │
         ▼
User commits → GGA intercepts → reviews against 11 rules
         │
         ├── PASS: commit goes through
         └── FAIL: blocked with explanation → fix → re-commit
```

### What the stack produces

```
Sensor (Arduino) → Digital Twin (OpenSeesPy) → Paper (Q1-Q4 / Conference)
     │                      │                           │
  data/raw/           src/physics/                articles/drafts/
  (sacred)            FEM simulation              IMRaD + figures + BibTeX
                                                       │
                                               validate_submission.py
                                               compile_paper.sh
                                               PDF (IEEE / Elsevier)

                    + Motor de Innovación Científica
                          │
    ingest_paper.py → patent_search.py → innovation_gap.py → patent_scaffold.py
         │                  │                  │                    │
  articles/references/  BigQuery Patents   Supabase DB        articles/patents/
```

---

## Supreme Authority Hierarchy

```
Belico.md     ← SUPREMACY — wins over everything on scientific guardrails
CLAUDE.md     ← Orchestrator constitution + full pipeline (Claude Code entry point)
GEMINI.md     ← Entry point for Google Antigravity + Gemini 3.1 Pro
AGENTS.md     ← GGA code review rules (11 rules — do not touch)
```

> If there is a conflict: **Belico.md always wins.**
> If you don't know WHAT to build: read `PRD.md`
> If you don't know HOW to operate: read `Belico.md`

---

## Multi-IDE Compatibility

The stack runs on any AI agent IDE without changes to the codebase:

| IDE | Entry Point | Model | Status |
|-----|-------------|-------|--------|
| **Claude Code** | `CLAUDE.md` | Claude Opus 4.6 / Sonnet 4.6 | ✅ Primary |
| **Google Antigravity** | `GEMINI.md` | Gemini 3.1 Pro + Claude Opus 4.6 | ✅ Documented |
| **Cursor** | `CLAUDE.md` | Claude Sonnet / GPT-4o | ✅ Compatible |
| **Windsurf** | `CLAUDE.md` | Claude / GPT-4o | ✅ Compatible |
| **OpenCode** | `CLAUDE.md` | Any model | ✅ Compatible |

**Engram never changes.** Persistent memory works identically across all IDEs via MCP.

---

## Quick Start

### 1. Start a session

Open your AI coding agent and say:

```
Engram conecto
```

The orchestrator will:
1. Verify all dependencies (Engram, GGA, Agent Teams Lite)
2. Load context from Engram (previous sessions, active papers, open risks)
3. Report system status
4. **Ask what you want to develop** (mandatory every session)

### 2. Choose your paper type

| Type | Words | Refs | Data Required |
|------|-------|------|---------------|
| **Conference** | 2,500 - 5,000 | 10-30 | Synthetic with physics basis |
| **Q4** | 3,000 - 12,000 | 15-40 | Validated synthetic |
| **Q3** | 4,000 - 12,000 | 25-60 | Field or validated synthetic |
| **Q2** | 5,000 - 10,000 | 30-80 | Field + laboratory |
| **Q1** | 6,000 - 10,000 | 40-120 | Field + lab, 2+ structures |

### 3. The mandatory staircase

```
Conference → Q3 → Q2 → Q1
```

Each paper inherits from the previous. Do not skip levels.

---

## Dependencies

```bash
# Install the Gentleman ecosystem:
bash tools/setup_dependencies.sh

# Or check status:
bash tools/setup_dependencies.sh --check
```

| Tool | Role | Install |
|------|------|---------|
| [Engram](https://github.com/Gentleman-Programming/engram) | Persistent memory + inter-agent bus | `brew install gentleman-programming/tap/engram` |
| [Gentle AI](https://github.com/Gentleman-Programming/gentle-ai) | Ecosystem configurator | `brew install gentleman-programming/tap/gentle-ai` |
| [Agent Teams Lite](https://github.com/Gentleman-Programming/agent-teams-lite) | SDD orchestration | Cloned to `.agents/agent-teams-lite/` |
| [GGA](https://github.com/Gentleman-Programming/gentleman-guardian-angel) | Pre-commit AI code review | `gga init && gga install` |

---

## Configuration

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

### Required APIs

| API | Variable | Get it |
|-----|----------|--------|
| **OpenAlex** | `OPENALEX_API_KEY` | [openalex.org](https://openalex.org) — free, no key required for basic |
| **Semantic Scholar** | `SEMANTIC_SCHOLAR_API_KEY` | [semanticscholar.org/product/api](https://www.semanticscholar.org/product/api) — approved key, 1 req/sec |
| **Supabase** | `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` | [supabase.com](https://supabase.com) — articulos_db project |
| **BigQuery** | `BIGQUERY_PROJECT_ID` + `GOOGLE_APPLICATION_CREDENTIALS` | Service account JSON in `secrets/` |
| **PEER NGA-West2** | `PEER_EMAIL` + `PEER_PASSWORD` | [ngawest2.berkeley.edu](https://ngawest2.berkeley.edu) — free account |
| **Elsevier/Scopus** | `ELSEVIER_API_KEY` | [dev.elsevier.com](https://dev.elsevier.com) — optional |

---

## Database Architecture (5 Layers)

```
Layer 1 — Supabase (remote, primary)
  ├── reference_papers      ← ingested PDFs of others' work
  ├── patent_searches       ← BigQuery patent search results
  └── innovation_gaps       ← identified gaps + patentable methodologies

Layer 2 — JSON fallback (local, automatic when Supabase unavailable)
  └── db/patent_search/*.json

Layer 3 — YAML SSOT (config/params.yaml — single source of truth)

Layer 4 — Engram SQLite (~/.engram/engram.db — decisions and memory)

Layer 5 — API Gateway cache (BigQuery 1TB/month, Semantic Scholar rate limit)
```

### Supabase schema

```sql
-- Papers from other researchers (ingested for gap analysis)
CREATE TABLE reference_papers (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title       TEXT NOT NULL,
  authors     TEXT[],
  abstract    TEXT,
  year        INT,
  doi         TEXT UNIQUE,
  source_file TEXT,          -- original PDF path
  ingested_at TIMESTAMPTZ DEFAULT now()
);

-- BigQuery patent searches
CREATE TABLE patent_searches (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  search_id    TEXT NOT NULL UNIQUE,
  query        TEXT NOT NULL,
  results      JSONB,
  result_count INT DEFAULT 0,
  searched_at  TIMESTAMPTZ DEFAULT now()
);

-- Innovation gaps (paper → patent pathway)
CREATE TABLE innovation_gaps (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  paper_id     UUID NOT NULL REFERENCES reference_papers(id) ON DELETE CASCADE,
  gap_summary  TEXT,
  assumptions  TEXT[],
  methodology  TEXT,          -- patentable methodology draft
  gap_score    FLOAT,
  created_at   TIMESTAMPTZ DEFAULT now()
);
```

---

## Motor de Innovación Científica

Transforms papers you read into patentable methodologies:

```
articles/references/   →   ingest_paper.py   →   reference_papers (Supabase)
                                                         │
                                               innovation_gap.py
                                                         │
                                              gaps + methodology draft
                                                         │
                                              patent_scaffold.py
                                                         │
                                        articles/patents/draft_*.md
```

### Usage

```bash
# 1. Ingest a reference paper PDF
python3 tools/ingest_paper.py --file articles/references/paper.pdf

# 2. Search relevant patents
python3 tools/patent_search.py --query "structural health monitoring edge AI" --limit 20

# 3. Find innovation gaps
python3 tools/innovation_gap.py --paper-id <uuid-from-supabase>

# 4. Generate patent scaffold
python3 tools/patent_scaffold.py --gap-id <uuid-from-supabase>
```

> **Patent API status**: BigQuery `patents-public-data` (100M+ patents, US/EP/WO) is operational. Lens.org API token pending for extended coverage.

---

## Supported Research Domains

| Domain | Solver | SSOT Keys | Status |
|--------|--------|-----------|--------|
| `structural` | OpenSeesPy | `nonlinear.*`, `structure.*`, `damping.*` | **OPERATIONAL** |
| `water` | FEniCSx | `fluid.*` | Planned |
| `air` | FEniCSx / SU2 | `air.*` | Planned |
| `{any}` | Domain scaffolder | Auto-generated | On demand |

### Adding a new domain

When you describe your research and the domain doesn't exist, the orchestrator scaffolds it automatically:

```bash
# Automatic (via orchestrator — describe your research topic in free text)
# Manual:
python3 tools/scaffold_investigation.py --domain biomedical
# Creates: config/domains/biomedical.yaml + domains/biomedical.py + .agent/skills/domains/biomedical.md
```

---

## Paper Production Pipeline (SDD)

```
                    ┌─→ SPEC ──┐
EXPLORE ──→ PROPOSE ─┤          ├─→ TASKS ──→ COMPUTE ──→ IMPLEMENT ──→ VERIFY ──→ FINALIZE ──→ ARCHIVE
                     └─→ DESIGN ┘                │             │
                                            [no data?]    [diagnose]
                                           (loop back)   (loop back)
```

**Core rule:** A paper is a REPORT of computational/experimental results. Without real data in `data/processed/`, there is no paper.

### Mandatory gates

| Gate | Tool | Blocks |
|------|------|--------|
| Novelty | `check_novelty.py` | PROPOSE (DUPLICATE → 3 pivots → re-check) |
| Data | `fetch_domain_data.py --verify` | COMPUTE → IMPLEMENT |
| Statistics (Q1/Q2) | `compute_statistics.py` | IMPLEMENT B2 → B3 |
| Submission | `validate_submission.py` | FINALIZE → ARCHIVE |
| Reviewer | `reviewer_simulator.md` | FINALIZE → ARCHIVE |

### COMPUTE phases (mandatory, sequential)

```
C0 — Infrastructure check (OpenSeesPy, domain backend, SSOT valid)
C1 — Data acquisition (PEER NGA-West2 / domain sources)
C2 — Solver execution (FEM → data/processed/)
C3 — Hardware emulator (arduino_emu.py — skipped if no hardware)
C4 — Synthetic complement (generate_degradation.py — skipped if not needed)
C5 — Data gate (COMPUTE_MANIFEST.json — all_design_sources_exist: true)
```

### IMPLEMENT batches

```
Pre-Batch: Style Calibration (style_calibration.py — downloads 3-5 real venue papers)
Batch 1: Methodology + Fig_methodology     → partial verify
Batch 2: Results + Fig_results             → partial verify
Batch 3: Discussion + Conclusions          → partial verify
Batch 4: Abstract + Intro + Refs           → full validate_submission.py
```

---

## Architecture

```
belico-stack/
├── Belico.md                 # SUPREME AUTHORITY — scientific guardrails
├── CLAUDE.md                 # Claude Code orchestrator constitution
├── GEMINI.md                 # Google Antigravity entry point (Gemini 3.1 Pro)
├── AGENTS.md                 # GGA code review rules (11 rules)
├── .gga                      # GGA config (provider=claude|gemini)
├── .mcp.json                 # MCP servers (Engram + Semantic Scholar)
├── secrets/
│   └── gcp_bigquery.json     # Google Cloud service account (gitignored)
├── config/
│   ├── params.yaml           # SSOT — Single Source of Truth
│   ├── domains/              # Domain descriptors (structural.yaml, ...)
│   ├── research_lines.yaml   # Active paper profile (quartile arbiter)
│   ├── soil_params.yaml      # Site-specific geotechnical data
│   └── paths.py              # Centralized path constants
├── domains/
│   ├── base.py               # DomainBackend ABC + DomainRegistry
│   ├── structural.py         # OpenSeesPy backend
│   └── {domain}.py           # Auto-generated by domain_scaffolder
├── src/
│   ├── firmware/             # Arduino (Nano 33 BLE Sense Rev2 + Nicla Sense ME)
│   ├── physics/              # Digital twin (OpenSeesPy, Kalman, spectral engine)
│   └── ai/                   # ML models (LSTM, PgNN surrogate — under demand)
├── data/
│   ├── raw/                  # Sacred sensor data (NEVER written by agent)
│   ├── processed/            # Simulation outputs for papers
│   └── synthetic/            # Generated synthetic datasets
├── db/
│   ├── excitation/           # PEER NGA-West2 seismic records (.AT2)
│   ├── benchmarks/           # Published reference datasets (LANL, Z24, IASC-ASCE)
│   ├── calibration/          # Site-specific calibration data
│   ├── validation/           # Independent field/lab measurements
│   ├── patent_search/        # Patent search JSON fallback
│   └── manifest.yaml         # Traceability: paper claims → data → sources
├── articles/
│   ├── drafts/               # Papers in progress (YAML frontmatter + IMRaD)
│   ├── figures/              # Publication-quality figures (PDF + PNG)
│   ├── references/           # Ingested PDFs of others' work
│   ├── patents/              # Patent scaffold drafts
│   └── scientific_narrator.py # IMRaD draft generator (multi-domain)
├── tools/
│   ├── init_child.sh         # Bootstrap child factory from mother
│   ├── init_project.py       # Interactive setup wizard
│   ├── check_novelty.py      # Novelty checker (OpenAlex 250M+ + Semantic Scholar)
│   ├── patent_search.py      # Patent search via BigQuery patents-public-data
│   ├── ingest_paper.py       # PDF ingest → Supabase reference_papers
│   ├── innovation_gap.py     # Gap analysis → patentable methodology
│   ├── patent_scaffold.py    # Patent draft scaffold generator
│   ├── style_calibration.py  # Anti-AI style calibration (real venue papers)
│   ├── validate_submission.py # Pre-submission validator (9 gates)
│   ├── compile_paper.sh      # Pandoc PDF (IEEE/Elsevier/Conference)
│   ├── compute_statistics.py # Statistical gates Q1/Q2 (Mann-Whitney, Cohen's d)
│   ├── plot_figures.py       # Numbered figures by domain + quartile
│   ├── research_director.py  # Full campaign orchestrator
│   ├── fetch_benchmark.py    # PEER record verifier
│   ├── peer_downloader.py    # PEER NGA-West2 downloader
│   ├── generate_degradation.py # Synthetic degradation data (Wiener process)
│   ├── generate_compute_manifest.py # COMPUTE C5 gate
│   ├── generate_params.py    # SSOT propagator: params.yaml → params.h + params.py
│   ├── arduino_emu.py        # Arduino emulator via PTY (9 modes)
│   ├── setup_dependencies.sh # Gentleman ecosystem installer
│   └── activate_paper_profile.py # Research line activator
├── .agent/
│   ├── prompts/              # Sub-agents (verifier, physical_critic, reviewer_simulator, ...)
│   ├── skills/               # Scientific skills (signal_processing, literature_review, ...)
│   └── specs/
│       └── journal_specs.yaml # Quality gates per journal quartile
└── .agents/                  # External repos (Engram, Agent Teams Lite, Skills)
```

---

## Data Governance

Every number in a paper must trace back to a real source:

```bash
# 1. Select ground motions (ASCE 7)
python3 tools/select_ground_motions.py

# 2. Download .AT2 files (PEER NGA-West2)
python3 tools/peer_downloader.py --auto

# 3. Verify records
python3 tools/fetch_benchmark.py --verify

# 4. Pre-submission traceability check
python3 tools/validate_submission.py articles/drafts/your_paper.md
```

| Folder | Role | Required for |
|--------|------|-------------|
| `db/excitation/` | Ground motions (PEER NGA-West2) | ALL quartiles |
| `db/benchmarks/` | Published datasets (LANL, Z24, IASC-ASCE) | Q3+ |
| `db/calibration/` | Site-specific data | Q2+ |
| `db/validation/` | Independent measurements | Q2+ |

---

## The Orchestrator — Regla de Oro (NON-NEGOTIABLE)

**The orchestrator NEVER generates content directly.** It only:

1. **Plans** — defines WHAT to do and in what order
2. **Delegates** — launches sub-agents for each atomic task
3. **Coordinates** — reads results from Engram and decides next step
4. **Validates** — confirms output meets quality gates

**Explicit prohibitions:**
- ❌ Read files > 50 lines (delegate to sub-agent)
- ❌ Use Edit/Write ever (sub-agent always edits)
- ❌ Generate paper text, code, figures, or BibTeX
- ❌ Copy file contents into sub-agent prompts (sub-agent reads itself)
- ❌ Process long sub-agent outputs (read from Engram instead)

The orchestrator keeps its context at **10-15% of total**. If it saturates, it's doing work it should delegate.

### Allowed orchestrator tools

| Tool | Use |
|------|-----|
| `Grep` | Single-fact lookup |
| `Glob` | List files (no content) |
| `Agent` | Delegate tasks |
| `mem_save / mem_search` | Engram bus |
| `TodoWrite` | Planning |
| `Bash` | One-liners only: `git status`, check scripts |

---

## Engram — The Brain

Engram is the **persistent memory AND inter-agent bus**. Every agent in the stack communicates through it. It stores WHY decisions were made — not raw data, not file contents, not code.

### Inter-agent bus protocol (5 steps, no exceptions)

```
STEP 1 (orchestrator): mem_save("task: {agent} — what to do")
STEP 2 (orchestrator): Launch sub-agent with SHORT prompt (< 30 lines)
STEP 3 (sub-agent):    mem_search("task: {agent}") to get context
                       + reads its own files + works
STEP 4 (sub-agent):    mem_save("result: {agent} — summary < 500 chars")
STEP 5 (orchestrator): mem_search("result: {agent}") to read result
```

**Anti-pattern (FORBIDDEN):**
```python
# BAD: orchestrator reads file and passes it in the prompt
content = Read("articles/references.bib")   # 200 lines in orchestrator context
Agent(prompt=f"Here is the current BibTeX:\n{content}\nAdd 30 refs...")
```

### Progressive disclosure (3 layers)

| Layer | Command | Returns | When to use |
|-------|---------|---------|-------------|
| **1. Compact** | `mem_search("keyword")` | Titles + snippets (< 500 chars) | Always first |
| **2. Context** | `mem_context` | Temporal sequence of decisions | When you need history |
| **3. Full** | `mem_get_observation({id})` | Complete observation | Only when snippet is not enough |

Start ALWAYS at layer 1. Only go deeper if the information is insufficient.

### What to save (mandatory)

| Type | Format | Example |
|------|--------|---------|
| Decision | `decision: {what} because {why}` | `"decision: Mann-Whitney because normality fails for damage data"` |
| Error+Fix | `error: {problem} → fix: {solution}` | `"error: narrator crashed water → fix: added DOMAIN_SECTIONS fallback"` |
| Pattern | `pattern: {when} → {then}` | `"pattern: mesh > 50k elements → use iterative solver"` |
| Paper event | `paper: {status} {title}` | `"paper: VERIFY passed icr-shm-ae for EWSHM"` |
| Task (bus) | `task: {agent} — {description}` | `"task: bibliography_agent — 30 refs for icr-shm-ae, structural, conference"` |
| Result (bus) | `result: {agent} — {summary}` | `"result: bibliography_agent — 25 refs OK, missing category 'cfd'"` |
| Risk | `risk: {paper_id} — {description}` | `"risk: icr-shm-ae — synthetic data without experimental validation"` |

### What NOT to save

- ❌ Complete file contents (that's in git)
- ❌ Raw numerical results (that's in `data/processed/`)
- ❌ Complete generated code (that's in source files)

### Critical configuration

**ONE DB ONLY:** `~/.engram/engram.db`. NEVER use `ENGRAM_DATA_DIR` in settings.json.
If settings.json has `env.ENGRAM_DATA_DIR`, the MCP writes to a dead copy and everything desyncs.

### Session lifecycle

```bash
# Boot (automatic via SessionStart hook):
mem_context                           # general context from recent sessions
mem_search("paper: active")           # papers in progress, last known state
mem_search("risk:")                   # open unmitigated risks
mem_search("decision: last session")  # recent pending decisions

# Before saying "done" (MANDATORY):
mem_session_summary  # Goal, Discoveries, Accomplished, Next Steps, Relevant Files
```

---

## Sub-agents

The orchestrator's muscle. Each one reads its own prompt file — the orchestrator never copies prompt content.

| Agent | Prompt | Activates when |
|-------|--------|---------------|
| **Verifier** | `.agent/prompts/verifier.md` | Changes in `src/physics/models/` |
| **Physical Critic** | `.agent/prompts/physical_critic.md` | New loads, boundary conditions, geometry |
| **Bibliography Agent** | `.agent/prompts/bibliography_agent.md` | Preparing draft references |
| **Figure Agent** | `.agent/prompts/figure_agent.md` | Draft needs figures |
| **Reviewer Simulator** | `.agent/prompts/reviewer_simulator.md` | Draft reaches `review` status (Gates 0-2) |
| **Patent Agent** | `.agent/prompts/patent_agent.md` | EXPLORE with reference PDFs, gap analysis, patent claims |
| **Domain Scaffolder** | `.agent/prompts/domain_scaffolder.md` | New domain detected → auto-generate config + backend + skill |
| **Data Config Agent** | `.agent/prompts/data_config_agent.md` | COMPUTE C1 — domain params have TODO values |

### Launching sub-agents (correct pattern)

```python
# STEP 1: Save task to Engram bus
mem_save("task: bibliography_agent — generate 30 refs for icr-shm-ae, structural, conference quartile")

# STEP 2: Launch with SHORT prompt (< 30 lines, no file contents)
Agent(prompt="""
You are the Bibliography Agent. Read .agent/prompts/bibliography_agent.md for your instructions.
Search Engram: mem_search("task: bibliography_agent") for your task.
Read: articles/references.bib, .agent/specs/journal_specs.yaml (conference section)
When done: mem_save("result: bibliography_agent — {N} refs generated, categories: {list}")
""")

# STEP 5: Read result from Engram (NOT the raw agent output)
mem_search("result: bibliography_agent")
```

---

## GGA — Gentleman Guardian Angel

GGA is the pre-commit AI code reviewer. It enforces 11 rules from `AGENTS.md` on every commit touching `.py`, `.ino`, `.h`, or `.sh` files.

```bash
# Install (once):
gga init && gga install

# Change AI provider:
# Edit .gga:
PROVIDER="claude"   # or "gemini" or "openai"
```

### The 11 AGENTS.md rules (enforced on every commit)

| # | Rule | What it blocks |
|---|------|---------------|
| 1 | No hardcoded physical parameters | Values that belong in `config/params.yaml` |
| 2 | No fabricated data | Fallback values that invent scientific results |
| 3 | No silent data loss | Writing partial results without warning |
| 4 | Sacred raw data | Agent code writing to `data/raw/` |
| 5 | No silent failures | Bare `except: pass` that hides errors |
| 6 | No duplicate SSOT | Parameters defined in more than one place |
| 7 | No auto-generated file edits | Editing `params.h` or `params.py` manually |
| 8 | Commit coherence | Firmware + simulation + paper out of sync |
| 9 | Verifier mandatory | Structural model changes without validation |
| 10 | No hardcoded secrets | API keys, passwords in source code |
| 11 | Traceability required | Paper numbers without `db/manifest.yaml` entry |

GGA runs automatically on `git commit`. If it finds a violation, the commit is blocked with an explanation.

---

## Gentleman Programming Ecosystem

| Repo | Role |
|------|------|
| [Engram](https://github.com/Gentleman-Programming/engram) | Persistent memory — decisions, patterns, errors across sessions |
| [Agent Teams Lite](https://github.com/Gentleman-Programming/agent-teams-lite) | SDD orchestration — 9 phases, delegate-only coordinator |
| [Gentle AI](https://github.com/Gentleman-Programming/gentle-ai) | One-command ecosystem setup for any AI agent |
| [GGA](https://github.com/Gentleman-Programming/gentleman-guardian-angel) | Pre-commit AI code review — 11 rules (Python/Arduino/Shell) |
| [Gentleman Skills](https://github.com/Gentleman-Programming/Gentleman-Skills) | Skill format reference |

---

## AutoResearch (Optional)

After each 3 papers, the stack can self-improve:

```bash
python3 tools/autoresearch.py --experiments 5 --room validator
# Rooms: validator, prompts, skills, simulation, quartile_gates, tool_chain
```

---

## License

MIT License — Free to use for public infrastructure and academic research.

---

*Built for structural engineering research. Extensible to any scientific domain via the Domain Registry pattern.*
