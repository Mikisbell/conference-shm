---
name: "Paper Production Pipeline"
description: "Trigger: generating a draft, compiling PDF, running validate_submission, managing paper status flow"
metadata:
  author: "belico-stack"
  version: "3.0"
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
EXPLORE --> PROPOSE -|          |-> TASKS --> IMPLEMENT --> VERIFY --> ARCHIVE --> PUBLISH
  ^                  +-> DESIGN +       |         |                       |
  |                                     |    [diagnose]              [merge specs]
  +-------------------------------------+---------+
```

### 1. EXPLORE (Orchestrator)
- Read `config/params.yaml` to confirm active domain
- Check `data/processed/` for available datasets
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

### 6. IMPLEMENT (Sub-agents, batched)
- Execute one batch at a time via delegated sub-agents
- Each batch must pass partial VERIFY before advancing
- Generate sections via `scientific_narrator.py` or manual writing
- Generate figures via `plot_figures.py`
- Generate BibTeX via `generate_bibtex.py`
- Mark AI-generated content with `<!-- AI_Assist -->`
- Sub-agents read context from Engram, write results to Engram

### 7. VERIFY (Verifier + Reviewer Simulator)
- Run `validate_submission.py` — must pass all 9 checks
- Run `validate_submission.py --diagnose` on failure
- Reviewer Simulator reads risks from Engram: `mem_search("risk: {paper_id}")`
- Run Verifier sub-agent if paper includes numerical results

### 8. ARCHIVE (Orchestrator, post-VERIFY)
- Merge delta specs (if SPEC changed during implementation)
- `mem_save("paper: verified {title} — all gates passed")`
- `mem_save("pattern: {lessons learned}")`
- Update draft status
- Document mitigated and pending risks

### 9. PUBLISH (Sub-agent)
- Compile PDF via `compile_paper.sh`
- Generate cover letter via `generate_cover_letter.py`
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
| IMPLEMENT (batches) | Sonnet | Content generation, high throughput |
| VERIFY | Opus | Critical evaluation, error detection |
| ARCHIVE, PUBLISH | Sonnet | Mechanical documentation |

### Tools Reference

| Step | Tool | Command |
|------|------|---------|
| Generate draft | `articles/scientific_narrator.py` | `--domain X --quartile QN --topic "..."` |
| Generate figures | `tools/plot_figures.py` | `--domain X` |
| Generate BibTeX | `tools/generate_bibtex.py` | `--output articles/references.bib` |
| Validate | `tools/validate_submission.py` | `articles/drafts/paper_*.md [--diagnose]` |
| Compile PDF | `tools/compile_paper.sh` | `draft.md --template ieee\|conference\|elsevier` |
| Cover letter | `tools/generate_cover_letter.py` | `cover --draft draft.md` |

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
