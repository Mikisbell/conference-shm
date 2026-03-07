# Belico Stack — Scientific Paper Factory

> **From sensor to submission. One monorepo. Zero excuses.**

An AI-powered research system that transforms raw sensor data into publication-ready scientific papers (Q1-Q4 + conference). Built on the [Gentleman Programming](https://github.com/Gentleman-Programming) ecosystem (Engram + SDD + Skills).

---

## How It Works: Template → Projects

**Belico Stack is a template, not a project.** You never write papers directly here. Instead, you clone it once per research topic and each clone becomes an independent project with its own repo.

```
belico-stack (template — this repo)
    │
    ├── clone → bridge-shm/          → Conference EWSHM 2026
    ├── clone → cdw-fatigue/          → Q3 JCSHM
    ├── clone → tower-monitoring/     → Q1 Engineering Structures
    └── clone → ...as many as needed
```

Each clone:
- Gets a **unique name** from its folder (detected by `init_project.py`)
- Has its own `PRD.md`, `params.yaml`, and GitHub repo
- Produces one paper (or a paper chain: Conference → Q4 → Q1)
- Can pull template updates: `git fetch belico && git merge belico/main`

**Improvements go here (the template).** New tools, sub-agents, skills, and bug fixes are developed in belico-stack and propagated to project clones via git merge. See [Updating an existing project](#updating-an-existing-project).

---

## What It Does

```
Sensor (Arduino)  -->  Digital Twin (OpenSeesPy)  -->  Paper (Q1-Q4 / Conference)
    |                        |                              |
  data/raw/            src/physics/                   articles/drafts/
    |                        |                              |
  Kalman filter        FEM simulation               IMRaD + figures + BibTeX
    |                        |                              |
  Engram (memory)      Verifier (validation)         PDF (IEEE / Elsevier)
```

You choose the paper type. The system handles the rest:

| Type | Complexity | Words | Refs | Data Required |
|------|-----------|-------|------|---------------|
| **Conference** | Low | 2,500 - 5,000 | 10-30 | Synthetic with physics basis |
| **Q4** | Low-Medium | 3,000 - 6,000 | 15-40 | Validated synthetic |
| **Q3** | Medium | 4,000 - 7,000 | 25-60 | Field or validated synthetic |
| **Q2** | High | 5,000 - 8,000 | 35-80 | Field or laboratory |
| **Q1** | Very High | 6,000 - 10,000 | 50-120 | Field + lab, 2+ structures |

---

## Quick Start

### 1. Clone

```bash
git clone https://github.com/Mikisbell/belico-stack.git my-project-name
cd my-project-name
```

> **Tip:** The folder name becomes your default project name. Clone into a descriptive folder (e.g., `bridge-monitor`, `tower-shm`) so each project is unique.

### 2. Bootstrap your project

```bash
python3 tools/init_project.py
```

This is the **single entry point** for new projects. It handles everything:

1. **Detects your folder name** as default project name (no two projects look the same)
2. **Asks only 3 things**: project name, domain (structural/water/air), and author
3. **Creates the directory structure** (14 required directories)
4. **Checks and installs dependencies** (Engram, Gentle AI, GGA, Agent Teams Lite)
5. **Generates config files** with `null` values ready for research:
   - `config/params.yaml` — SSOT skeleton (parameters to fill during your AI session)
   - `PRD.md` — research roadmap (to fill with Claude)
   - `src/firmware/params.h` — C header with placeholders
   - `src/physics/params.py` — Python constants with `None`

You don't need to know material properties upfront — that's what the research is for. The AI agent will guide you to find and fill the right values during your session.

```bash
# Options:
python3 tools/init_project.py              # Full setup (interactive)
python3 tools/init_project.py --skip-deps  # Skip dependency installation
python3 tools/init_project.py --reset      # Backup existing config and start fresh
```

### Dependencies

The bootstrapper checks and installs these automatically. If you prefer manual installation:

| Tool | What it does | Install manually |
|------|-------------|-----------------|
| [Engram](https://github.com/Gentleman-Programming/engram) | Persistent memory across sessions | `brew install gentleman-programming/tap/engram` |
| [Gentle AI](https://github.com/Gentleman-Programming/gentle-ai) | Ecosystem configurator (SDD + Skills + MCP) | `brew install gentleman-programming/tap/gentle-ai` |
| [Agent Teams Lite](https://github.com/Gentleman-Programming/agent-teams-lite) | SDD orchestration with sub-agents | Cloned to `.agents/agent-teams-lite/` |
| [GGA](https://github.com/Gentleman-Programming/gentleman-guardian-angel) | Pre-commit AI code review (Python/Arduino/Shell) | `gga init && gga install` |
| [Gentleman Skills](https://github.com/Gentleman-Programming/Gentleman-Skills) | Skill library reference (optional) | Cloned to `.agents/Gentleman-Skills/` |

#### Keeping dependencies updated

```bash
bash tools/setup_dependencies.sh --update   # update all to latest
bash tools/setup_dependencies.sh --lock     # save current versions
bash tools/setup_dependencies.sh --check    # check status without changing anything
```

Current versions are tracked in `config/dependencies.lock`.

### Updating an existing project

If you created your project by copying belico-stack (not cloning), add the upstream remote to pull future updates:

```bash
cd ~/PROYECTOS/your-project
git remote add belico https://github.com/Mikisbell/belico-stack.git
git fetch belico
git merge belico/main --allow-unrelated-histories
```

For subsequent updates:

```bash
git fetch belico && git merge belico/main
```

This brings new tools, sub-agents, skills, and bug fixes without overwriting your project-specific files (`PRD.md`, `config/params.yaml`). Resolve any merge conflicts if your local files differ.

### 3. Configure your AI agent

```bash
# If using Claude Code:
engram setup claude-code

# Or use Gentle AI for full ecosystem setup:
gentle-ai
```

### 4. Start

Open your AI coding agent (Claude Code, OpenCode, Gemini CLI, etc.) and say:

```
Engram conecto
```

The system will:
1. Verify all dependencies are installed (Engram, GGA, Agent Teams Lite)
2. Load the project constitution (`Belico.md`) and previous session context from Engram
3. Report system status (SSOT, sub-agents, MCP servers, pending papers)
4. **Ask you what quartile to develop** — this is mandatory every session:

```
=== QUE VAMOS A DESARROLLAR? ===

Que tipo de articulo quieres producir?

  1. Conference  — Framework/arquitectura, datos sinteticos OK (2,500-5,000 words, 10-30 refs)
  2. Q4          — Validated synthetic data (3,000-6,000 words, 15-40 refs)
  3. Q3          — Field or strong synthetic data (4,000-7,000 words, 25-60 refs)
  4. Q2          — Field + laboratory data (5,000-8,000 words, 35-80 refs)
  5. Q1          — Field + lab + 2 structures + theoretical contribution (6,000-10,000 words, 50-120 refs)
```

5. Validate feasibility based on available data (blocks impossible quartiles)
6. Guide you through the research: fill `params.yaml`, find literature, run simulations
7. Start the SDD paper production workflow

---

## Architecture

```
belico-stack/
├── CLAUDE.md                  # Agent router (boot sequence, onboarding)
├── Belico.md                  # Project constitution (guardrails, Red Lines)
├── PRD.md                     # Product requirements (what to build)
├── AGENTS.md                  # GGA code review rules (11 rules, Python/Arduino/Shell)
├── .gga                       # GGA config (provider=claude, file patterns)
├── .mcp.json                  # MCP servers (Engram)
├── config/
│   ├── params.yaml            # SSOT — Single Source of Truth for all parameters
│   └── research_lines.yaml   # Research lines + active paper profile (quartile arbiter)
├── src/
│   ├── firmware/              # Arduino code (Nano 33 BLE + Nicla Sense ME)
│   ├── physics/               # Digital twin (OpenSeesPy, Kalman, spectral engine)
│   └── ai/                    # ML models (LSTM, PgNN surrogate)
├── data/
│   ├── raw/                   # Sacred sensor data (NEVER written by agent)
│   ├── processed/             # Processed data for papers
│   └── external/              # PEER NGA-West2 seismic records
├── articles/
│   ├── drafts/                # Papers in progress (YAML frontmatter + IMRaD)
│   ├── figures/               # Publication-quality figures (PDF + PNG)
│   └── scientific_narrator.py # IMRaD draft generator (multi-domain)
├── tools/
│   ├── init_project.py        # Interactive setup wizard (params.yaml generator)
│   ├── check_novelty.py       # Deep novelty checker (OpenAlex 250M+ papers + arXiv, standalone)
│   ├── setup_dependencies.sh  # Ecosystem installer (--check, --update, --lock)
│   ├── boot_engram.sh         # SessionStart hook (active memory retrieval)
│   ├── validate_submission.py # Pre-submission validator (9 checks + --diagnose)
│   ├── compile_paper.sh       # Pandoc PDF compiler (IEEE/Elsevier/Conference)
│   ├── bibliography_engine.py # Citation engine (53 refs, 12 categories)
│   └── plot_figures.py        # Figure generator (multi-domain)
├── .agent/
│   ├── prompts/               # Sub-agents (Verifier, Physical Critic, etc.)
│   ├── skills/                # Scientific skills (signal processing, literature review, norms, etc.)
│   └── specs/                 # Quality gates per journal quartile
└── .agents/                   # External repos (Engram, Agent Teams Lite, Skills)
```

---

## Paper Production Pipeline (SDD)

Every paper follows a Spec-Driven Development flow as a DAG (not waterfall). SPEC and DESIGN run in parallel. IMPLEMENT executes in batches with incremental verification. ARCHIVE closes each cycle.

```
                         +-> SPEC --+
EXPLORE --> NOVELTY --> PROPOSE -|          |-> TASKS --> IMPLEMENT --> VERIFY --> ARCHIVE --> PUBLISH
  ^          CHECK       ^      +-> DESIGN +       |         |                       |
  |           |          |                         |    [diagnose]              [merge specs]
  |      [DUPLICATE?]    |                         |         |                       |
  |       3 pivots --> pick                        |         |                       |
  +------------------------------------------------+---------+-----------------------+
                                   (loop back)
```

The orchestrator (CLAUDE.md) never generates content directly — it delegates to sub-agents.

### Novelty Check (automatic gate)

Before any paper advances to PROPOSE, the system **automatically** verifies originality:

1. `check_novelty.py` searches **OpenAlex** (250M+ academic works) and **arXiv** automatically — no API key, no MCP, no manual queries
2. Generates `articles/drafts/novelty_report.md` with threat assessment per paper found
3. Use `--deep` for citation network analysis. Verdict determines next step:

| Verdict | Action |
|---------|--------|
| **ORIGINAL** | Proceed to PROPOSE |
| **INCREMENTAL** | Proceed, but PROPOSE must state explicit differentiation |
| **DUPLICATE** | Agent proposes 3 concrete pivots (change focus, method, or domain). User picks one, PRD updates, novelty re-runs. Max 3 iterations, then fallback to INCREMENTAL. |

The agent does this without the user asking — it's a mandatory gate like quartile selection.

### Batched Implementation

IMPLEMENT runs in 4 sequential batches (Methodology → Results → Discussion → Abstract+Intro), each verified before advancing.

### Sub-agents

| Agent | Role | Activates when |
|-------|------|---------------|
| **Verifier** | Numerical validation of structural models | Changes in `src/physics/models/` |
| **Physical Critic** | Torsion, buckling, modal instability checks | New loads or boundary conditions |
| **Bibliography Agent** | Reference coverage by domain and quartile | Preparing draft references |
| **Figure Agent** | Publication-quality figure generation | Draft needs figures |
| **Reviewer Simulator** | Hostile peer review simulation | Draft reaches `review` status |

### MCP Servers

| Server | Function | Config |
|--------|----------|--------|
| **Engram** | Persistent memory across sessions | `.mcp.json` |

### Tools

| Tool | Function |
|------|----------|
| `init_project.py` | Interactive setup wizard — creates `params.yaml` via guided Q&A |
| `check_novelty.py` | Deep novelty checker — searches OpenAlex (250M+ papers) + arXiv, `--deep` for citation network, exit codes 0/1/2 |
| `validate_submission.py` | 9 checks + journal specs + `--diagnose` mode |
| `compile_paper.sh` | Pandoc + XeLaTeX + citeproc (IEEE/Elsevier/Conference) |
| `scientific_narrator.py` | IMRaD draft generator (structural/water/air) |
| `bibliography_engine.py` | 53 refs in 12 categories + BibTeX generator |
| `plot_figures.py` | Numbered figures PDF+PNG by domain |

---

## Domains

| Domain | Solver | Status |
|--------|--------|--------|
| `structural` | OpenSeesPy | **Active** — full pipeline |
| `water` | FEniCSx | Skill ready, no code yet |
| `air` | FEniCSx/SU2 | Skill ready, no code yet |

---

## Gentleman Programming Ecosystem

This stack is built on top of the Gentleman Programming open-source ecosystem:

| Repo | Role in Belico Stack |
|------|---------------------|
| [Engram](https://github.com/Gentleman-Programming/engram) | Persistent memory — stores decisions, patterns, errors across sessions |
| [Agent Teams Lite](https://github.com/Gentleman-Programming/agent-teams-lite) | SDD orchestration — 9 phases with delegate-only coordinator |
| [Gentle AI](https://github.com/Gentleman-Programming/gentle-ai) | One-command ecosystem setup for any AI agent |
| [GGA](https://github.com/Gentleman-Programming/gentleman-guardian-angel) | Pre-commit AI code review — 11 rules for Python/Arduino/Shell (AGENTS.md) |
| [Gentleman Skills](https://github.com/Gentleman-Programming/Gentleman-Skills) | Skill format reference (our scientific skills follow this structure) |
| [veil.nvim](https://github.com/Gentleman-Programming/veil.nvim) | Hide secrets in Neovim (optional, for streamers) |
| [Gentleman.Dots](https://github.com/Gentleman-Programming/Gentleman.Dots) | Complete dev environment dotfiles (optional) |

---

## License

MIT License — Free to use for public infrastructure and academic research.

---

*Developed as part of a structural engineering research program for real-time seismic monitoring with digital twins.*
