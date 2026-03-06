---
name: "Literature Review Agent"
description: "Trigger: building Related Work section, searching references, expanding bibliography, citation analysis"
metadata:
  author: "belico-stack"
  version: "1.0"
  domain: "all"
  requires: "semantic-scholar MCP server"
---

# Skill: Literature Review Agent

## When to Use

- Building the "Related Work" or "Literature Review" section of a paper
- Expanding `tools/bibliography_engine.py` with new references
- Validating that cited papers actually exist (anti-hallucination)
- Analyzing citation networks (who cites whom, h-index, impact)
- Finding state-of-the-art papers for a specific research gap

## Prerequisites

- Semantic Scholar MCP server configured in `.mcp.json`
- Tools available: `search_semantic_scholar`, `get_semantic_scholar_paper_details`, `get_semantic_scholar_citations_and_references`, `get_semantic_scholar_author_details`

## Workflow

### Phase 1: Keyword Extraction

From the paper's abstract or research question, extract 3-5 search queries:

```
Query 1: core topic (e.g., "structural health monitoring digital twin")
Query 2: methodology (e.g., "Kalman filter accelerometer vibration")
Query 3: application domain (e.g., "recycled concrete seismic response")
Query 4: competing approach (e.g., "LSTM prediction structural damage")
Query 5: normative context (e.g., "Eurocode 8 seismic design concrete")
```

### Phase 2: Search and Retrieve

For each query, use the MCP tools:

1. `search_semantic_scholar(query)` — get top 10 results per query
2. Filter by:
   - Year >= 2019 (prefer last 5 years, allow seminal older works)
   - Citation count > 10 (quality signal)
   - Open access preferred (reproducibility)
3. For top candidates: `get_semantic_scholar_paper_details(paper_id)` — get abstract, authors, venue, citation count

### Phase 3: Citation Network Analysis

For the 5-10 strongest papers:

1. `get_semantic_scholar_citations_and_references(paper_id)` — find shared references
2. Identify "hub papers" cited by multiple results (these are foundational)
3. Check for very recent papers (< 1 year) citing the same hubs (emerging work)

### Phase 4: Categorize References

Map each reference to the bibliography_engine.py categories:

| Category | Min refs (Q1) | Min refs (Conference) |
|----------|--------------|----------------------|
| SHM & Vibration | 8 | 3 |
| Digital Twin | 6 | 2 |
| FEM / OpenSees | 5 | 2 |
| Machine Learning | 5 | 2 |
| Seismic Codes | 4 | 1 |
| Recycled Materials | 4 | 1 |
| Signal Processing | 3 | 1 |
| Edge Computing / IoT | 3 | 1 |
| Bayesian / Uncertainty | 3 | 0 |
| Fragility Curves | 3 | 0 |
| BIM Integration | 2 | 0 |
| Validation / Benchmarks | 2 | 0 |

### Phase 5: Generate Related Work

Structure the section by research themes (NOT chronologically):

```markdown
## Related Work

### Theme 1: [Major research area]
[3-5 sentences synthesizing 4-6 papers, showing evolution and gaps]

### Theme 2: [Second research area]
[3-5 sentences synthesizing 3-5 papers]

### Theme 3: [Methodological area]
[3-5 sentences synthesizing 3-5 papers]

[Final paragraph: identify the GAP that this paper fills]
```

### Phase 6: Validate and Export

1. Verify every cited paper exists via `get_semantic_scholar_paper_details`
2. Extract BibTeX-ready metadata (title, authors, year, venue, DOI)
3. Flag any reference that cannot be verified (potential hallucination)
4. Update `tools/bibliography_engine.py` with new verified references
5. Mark generated text with `<!-- AI_Assist -->`

## Output Format

For each verified reference, produce:

```python
{
    "key": "AuthorYear",           # e.g., "Farrar2013"
    "title": "...",
    "authors": ["..."],
    "year": 2013,
    "venue": "...",
    "doi": "10.xxxx/...",
    "category": "shm_vibration",   # matches bibliography_engine categories
    "citation_count": 1500,
    "semantic_scholar_id": "...",
    "verified": True
}
```

## Anti-Patterns

- Citing papers without verifying they exist via Semantic Scholar
- Using only keyword search without citation network analysis
- Listing references chronologically instead of thematically
- Including >30% self-citations or single-group citations
- Missing seminal/foundational papers (high citation count, pre-2019)
- Generating fake DOIs or fabricating paper titles
- Writing Related Work before defining the paper's own contribution (the gap must be clear first)

## Integration with Paper Production

This skill feeds into Phase 6 (IMPLEMENT Batch 4: Abstract + Intro + Refs) of the `paper_production.md` skill. The Bibliography Agent sub-agent should invoke this skill when preparing references for any paper draft.
