---
name: "Engineering Norms and Design Codes"
description: "Trigger: referencing design codes (E.030, Eurocode 8, ASCE 7), seismic norms, load combinations, or code-based verification"
metadata:
  author: "belico-stack"
  version: "2.0"
  domain: "all"
---

# Skill: Engineering Norms and Design Codes

## When to Use

- Referencing seismic design codes (E.030, Eurocode 8, ASCE 7)
- Verifying load combinations or capacity reduction factors
- Computing spectral acceleration or design spectrum
- Writing Methodology sections that reference code provisions

## Critical Patterns

### Active Codes by Domain

**Structural (Seismic):**
| Code | Scope | Key Parameters |
|------|-------|----------------|
| **E.030 (Peru)** | Seismic design | Z, U, S, C, R factors |
| **Eurocode 8** | Seismic design | ag, S, TB, TC, TD, q |
| **ASCE 7-22** | Loads | SDS, SD1, Fa, Fv, R, Cd |
| **ACI 318-19** | Concrete | fc', fy, phi factors |

**Water (Hydraulics):**
| Code | Scope |
|------|-------|
| **ACI 350** | Environmental engineering concrete |
| **FEMA P-93** | Dam safety |

**Air (Wind):**
| Code | Scope |
|------|-------|
| **ASCE 7-22 Ch.26-31** | Wind loads |
| **Eurocode 1 Part 1-4** | Wind actions |

### E.030 Quick Reference (Peru Seismic Code)

Seismic zonation: Z4=0.45, Z3=0.35, Z2=0.25, Z1=0.10

Site amplification:
| Soil | S | TP (s) | TL (s) |
|------|---|--------|--------|
| S0 (hard rock) | 0.80 | 0.30 | 3.0 |
| S1 (rock) | 1.00 | 0.40 | 2.5 |
| S2 (firm soil) | 1.05 | 0.60 | 2.0 |
| S3 (soft soil) | 1.10 | 1.00 | 1.6 |

Spectral acceleration:
```
C = 2.5 * (TP/T)        for T < TL
C = 2.5 * (TP*TL/T^2)   for T >= TL
Sa = Z * U * C * S / R
```

### Eurocode 8 Quick Reference

Damping correction: `eta = sqrt(10 / (5 + xi))` where xi in %

Design spectrum:
```
0 <= T <= TB:    Sd = ag*S*[2/3 + T/TB*(2.5/q - 2/3)]
TB <= T <= TC:   Sd = ag*S*2.5/q
TC <= T <= TD:   Sd = ag*S*2.5/q*(TC/T)
TD <= T:         Sd = ag*S*2.5/q*(TC*TD/T^2)
```

### Load Combinations (ASCE 7)

```
1.4D
1.2D + 1.6L + 0.5(Lr or S or R)
1.2D + 1.6(Lr or S or R) + (L or 0.5W)
1.2D + 1.0W + L + 0.5(Lr or S or R)
1.2D + 1.0E + L + 0.2S
0.9D + 1.0W
0.9D + 1.0E
```

### Verification Checklist

1. Identify which code applies (from domain + location)
2. Verify load factors match the code edition
3. Check capacity reduction factors (phi) are correct
4. Verify drift limits: 0.7-2.5% depending on code
5. Check period bounds: T_code vs T_model (within 20%)
6. Site amplification: soil type matches field conditions

## Normative Framework by Quartile (LAW — enforced by validate_submission.py)

| Quartile | Local code role | Min. international codes | Example framing |
|----------|----------------|------------------------|-----------------|
| **Q1** | Case study only | 2 (e.g., Eurocode 8 + ASCE 7) | "The structure, designed per E.030, was analyzed using the Eurocode 8 damping correction and ASCE 7 site amplification" |
| **Q2** | Regional context | 1 | "E.030 governs the design; methodology follows ASCE 7-22 Ch.11" |
| **Q3** | Primary OK | 0 (1 recommended) | "Designed per E.030, analogous to Eurocode 8 clause 3.2.2.2" |
| **Q4** | Fully valid | 0 | "Designed per E.030 (Peru seismic code)" |
| **Conf** | Fully valid | 0 | "SHM framework validated against E.030 demands" |

**Source of truth**: `.agent/specs/journal_specs.yaml` → `normative_framework` per quartile.

## Anti-Patterns

- Mixing code editions (e.g., ASCE 7-16 factors with ASCE 7-22 provisions)
- Using E.030 outside Peru without noting it as reference-only
- Hardcoding Z, S, or R factors instead of reading from SSOT
- Applying damping correction without stating the xi value used
- **Using ONLY local codes in Q1/Q2 papers** — reviewers will reject as "too local"
- **Not contextualizing local codes** — always state the international equivalent

## Engram Integration
After using this skill, the sub-agent should save:
- `mem_save("result: norms_check — {code applied, pass/fail, key values}")`
- If norm selection: `mem_save("decision: norms — chose {code} because {reason}")`
