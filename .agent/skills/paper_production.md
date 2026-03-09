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

### Style Calibration (pre-IMPLEMENT — mandatory)

Before writing ANY section, the narrator must have a **style reference** from real published papers in the target venue. This is NOT optional.

**Procedure (runs once per paper, before Batch 1):**

1. **Search target venue**: Use `search_semantic_scholar` to find 3-5 recent papers (last 3 years) from the exact target journal/conference (e.g., "EWSHM 2024", "Engineering Structures 2023"), then `get_semantic_scholar_paper_details` to fetch abstracts
2. **Extract style patterns** from abstracts and introductions:
   - How do authors open their Introduction? (with a problem statement? a statistic? a question?)
   - How do they transition between paragraphs? (explicit connectors? implicit flow?)
   - What is their citation density per paragraph? (1-2? 3-5?)
   - Do they use first person ("We") or passive voice ("was measured")?
   - Average sentence length?
   - How do they introduce their contribution? (explicitly? embedded in context?)
3. **Create a Style Card** saved to Engram:
   ```
   mem_save("style: {paper_id} — venue={venue}, voice={active/passive/mixed},
   citation_density={N per paragraph}, avg_sentence_length={N words},
   opener_pattern={description}, contribution_intro={description}")
   ```
4. **Every batch narrator** reads the Style Card from Engram before writing
5. **Reviewer Simulator** compares draft style against the Style Card during VERIFY

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

### 6. IMPLEMENT (Sub-agents, batched)
- Before generating content for any batch, verify data sources in `db/manifest.yaml`. If manifest has `status: pending` for a required data role, BLOCK and report.
- Execute one batch at a time via delegated sub-agents
- Each batch must pass partial VERIFY before advancing
- Sub-agent generates sections via `scientific_narrator.py` or manual writing
- Sub-agent generates figures via `plot_figures.py`
- Sub-agent generates BibTeX via `generate_bibtex.py`
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
