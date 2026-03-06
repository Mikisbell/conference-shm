# Belico Stack — Scientific Paper Factory

> **From sensor to submission. One monorepo. Zero excuses.**

An AI-powered research system that transforms raw sensor data into publication-ready scientific papers (Q1-Q4 + conference). Built on the [Gentleman Programming](https://github.com/Gentleman-Programming) ecosystem (Engram + SDD + Skills).

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
git clone https://github.com/Mikisbell/belico-stack.git
cd belico-stack
```

### 2. Install dependencies

The stack runs on the Gentleman Programming ecosystem. Install it:

```bash
bash tools/setup_dependencies.sh
```

This installs (via Homebrew or binary download):

| Tool | What it does | Install manually |
|------|-------------|-----------------|
| [Engram](https://github.com/Gentleman-Programming/engram) | Persistent memory across sessions | `brew install gentleman-programming/tap/engram` |
| [Gentle AI](https://github.com/Gentleman-Programming/gentle-ai) | Ecosystem configurator (SDD + Skills + MCP) | `brew install gentleman-programming/tap/gentle-ai` |
| [Agent Teams Lite](https://github.com/Gentleman-Programming/agent-teams-lite) | SDD orchestration with sub-agents | Cloned to `.agents/agent-teams-lite/` |
| [GGA](https://github.com/Gentleman-Programming/gentleman-guardian-angel) | AI code review on commits (optional) | `brew install gentleman-programming/tap/gga` |
| [Gentleman Skills](https://github.com/Gentleman-Programming/Gentleman-Skills) | Skill library reference (optional) | Cloned to `.agents/Gentleman-Skills/` |

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
1. Verify all dependencies are installed
2. Load the project constitution and previous session context
3. Ask you what type of scientific paper you want to develop
4. Start the SDD workflow for your chosen paper type

---

## Architecture

```
belico-stack/
├── CLAUDE.md                  # Agent router (boot sequence, onboarding)
├── Belico.md                  # Project constitution (guardrails, Red Lines)
├── PRD.md                     # Product requirements (what to build)
├── config/
│   └── params.yaml            # SSOT — Single Source of Truth for all parameters
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
│   ├── setup_dependencies.sh  # Ecosystem installer
│   ├── validate_submission.py # Pre-submission validator (9 checks + --diagnose)
│   ├── compile_paper.sh       # Pandoc PDF compiler (IEEE/Elsevier/Conference)
│   ├── bibliography_engine.py # Citation engine (53 refs, 12 categories)
│   └── plot_figures.py        # Figure generator (multi-domain)
├── .agent/
│   ├── prompts/               # Sub-agents (Verifier, Physical Critic, etc.)
│   ├── skills/                # Scientific skills (signal processing, norms, etc.)
│   └── specs/                 # Quality gates per journal quartile
└── .agents/                   # External repos (Engram, Agent Teams Lite, Skills)
```

---

## Paper Production Pipeline (SDD)

Every paper follows a Spec-Driven Development flow as a DAG (not waterfall). If verification fails, the system diagnoses and loops back to the correct step:

```
EXPLORE --> SPEC --> DESIGN --> TASKS --> IMPLEMENT --> VERIFY ---> PUBLISH
  ^                                         |           |
  |                                         |      [diagnose]
  +-------------------------------------+----------+
                                     (loop back)
```

### Sub-agents

| Agent | Role | Activates when |
|-------|------|---------------|
| **Verifier** | Numerical validation of structural models | Changes in `src/physics/models/` |
| **Physical Critic** | Torsion, buckling, modal instability checks | New loads or boundary conditions |
| **Bibliography Agent** | Reference coverage by domain and quartile | Preparing draft references |
| **Figure Agent** | Publication-quality figure generation | Draft needs figures |
| **Reviewer Simulator** | Hostile peer review simulation | Draft reaches `review` status |

### Tools

| Tool | Function |
|------|----------|
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
| [GGA](https://github.com/Gentleman-Programming/gentleman-guardian-angel) | Pre-commit AI code review against engineering rules |
| [Gentleman Skills](https://github.com/Gentleman-Programming/Gentleman-Skills) | Skill format reference (our scientific skills follow this structure) |
| [veil.nvim](https://github.com/Gentleman-Programming/veil.nvim) | Hide secrets in Neovim (optional, for streamers) |
| [Gentleman.Dots](https://github.com/Gentleman-Programming/Gentleman.Dots) | Complete dev environment dotfiles (optional) |

---

## License

MIT License — Free to use for public infrastructure and academic research.

---

*Developed as part of a structural engineering research program for real-time seismic monitoring with digital twins.*
