# Belico Stack — La Madre Creadora de Fábricas

> **From idea to Q1 paper. One mother stack. Infinite child factories.**

An AI-powered Universal Research Ecosystem (EIU) that creates independent scientific paper factories from a single mother template. Built on the [Gentleman Programming](https://github.com/Gentleman-Programming) ecosystem (Engram + SDD + GGA + Skills).

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

## What the Stack Does

```
Sensor (Arduino) → Digital Twin (OpenSeesPy) → Paper (Q1-Q4 / Conference)
     │                      │                           │
  data/raw/           src/physics/                articles/drafts/
     │                      │                           │
  Kalman filter       FEM simulation             IMRaD + figures + BibTeX
     │                      │                           │
  Engram (memory)     Verifier (validation)       PDF (IEEE / Elsevier)

                    + Motor de Innovación
                          │
    ingest_paper.py → patent_search.py → innovation_gap.py → patent_scaffold.py
         │                  │                  │                    │
  articles/references/  BigQuery Patents   Supabase DB        patentable methodology
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

## Sub-agents

| Agent | Prompt | Activates when |
|-------|--------|---------------|
| **Verifier** | `.agent/prompts/verifier.md` | Changes in `src/physics/models/` |
| **Physical Critic** | `.agent/prompts/physical_critic.md` | New loads, boundary conditions, geometry |
| **Bibliography Agent** | `.agent/prompts/bibliography_agent.md` | Preparing draft references |
| **Figure Agent** | `.agent/prompts/figure_agent.md` | Draft needs figures |
| **Reviewer Simulator** | `.agent/prompts/reviewer_simulator.md` | Draft reaches `review` status |

---

## Engram — The Brain

Engram is the persistent memory and inter-agent bus. **It is not a log. It stores WHY decisions were made.**

```bash
# Session start (automatic via .claude/settings.json hooks)
engram session start

# Manual save
engram save "decision: chose Mann-Whitney because normality assumption fails for damage data"

# Search
engram search "paper: active"
```

**One rule:** `~/.engram/engram.db` is the ONLY database. Never set `ENGRAM_DATA_DIR` in settings.json — it creates a dead copy that desynchronizes all agents.

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
