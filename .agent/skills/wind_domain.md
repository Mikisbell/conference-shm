---
name: "Wind Engineering Domain (Air)"
description: "Trigger: domain is 'air', working with SU2/FEniCSx for wind, aerodynamics, or ventilation"
metadata:
  author: "belico-stack"
  version: "2.0"
  domain: "air"
---

# Skill: Wind Engineering Domain (Air)

## When to Use

- Domain is set to "air" in `config/params.yaml`
- Working with SU2 or FEniCSx for aerodynamic simulations
- Computing wind loads, Cp distributions, or vortex-induced vibration
- Writing papers in the wind engineering domain

## Critical Patterns

### Solver Backend

The air domain uses FEniCSx or SU2 for:
- Wind load analysis on structures (ASCE 7, Eurocode 1)
- Aerodynamic coefficients (Cp, Cd, Cl)
- Vortex-induced vibration (VIV)
- Natural ventilation and thermal comfort
- Wind tunnel validation (CFD vs experimental)

### SSOT Parameters

All air domain params live in `config/params.yaml` under `air:`:
```yaml
air:
  properties:
    viscosity_mu: null           # Pa.s (typ. 1.8e-5 at 20°C)
    density_rho: null            # kg/m3 (typ. 1.225 at sea level)
  geometry:
    length: null                 # m — wind tunnel / domain length
    height: null                 # m — domain height
    width: null                  # m — domain width (0 for 2D)
    obstacle_width: null         # m — building/obstacle width
    obstacle_height: null        # m — building/obstacle height
  boundary:
    inlet_velocity: null         # m/s — wind speed at inlet
    turbulence_intensity: null   # dimensionless (typ. 0.1-0.2)
  mesh:
    resolution: null             # elem/m — mesh resolution
  analysis:
    time_step: null              # s — time step
    total_time: null             # s — total simulation time
```

> **Note:** `roughness_length`, `reference_height`, `exposure_category`, and `kinematic_viscosity`
> are not yet in the SSOT. Planned — add to `params.yaml` when implementing ABL profile generation.

### Wind Profile (ABL)

```python
# Power law
U(z) = U_ref * (z / z_ref) ** alpha

# Log law
U(z) = (u_star / kappa) * ln(z / z_0)
```

Alpha values by terrain:
| Terrain | alpha | z_0 (m) |
|---------|-------|---------|
| Open water | 0.10 | 0.003 |
| Open terrain | 0.14 | 0.03 |
| Suburban | 0.22 | 0.3 |
| Urban center | 0.33 | 1.0 |

### SU2 Integration

```bash
SU2_CFD config.cfg
SU2_SOL config.cfg
```

Key config: `SOLVER= RANS`, `TURB_MODEL= SA` or `SST`, `MESH_FILENAME= mesh.su2`

### Paper Sections (Air Domain)

- **Methodology**: ABL profile, turbulence model selection, mesh strategy
- **Results**: Cp distribution, drag coefficients, flow visualization
- **Discussion**: compare CFD vs wind code provisions (ASCE 7 / Eurocode 1)

### Key References

Categories: `cfd`, `wind`
- Simiu & Yeo 2019 (Wind Effects on Structures)
- Kareem et al. 2020 (Aeroelasticity)
- Blocken 2015 (CFD for urban physics)

### Verifier Checks

1. Pressure coefficient validation: Cp vs wind tunnel data
2. Grid convergence index (GCI): 3-mesh Richardson extrapolation
3. y+ check: first cell height appropriate for wall treatment
4. Strouhal number (if VIV): compare vs empirical St ≈ 0.2

## Anti-Patterns

- Using power law profile without specifying terrain category
- Running RANS without checking y+ values
- Reporting wind loads without comparing to code provisions
- Omitting turbulence model justification in Methodology

## Engram Integration
After using this skill, the sub-agent should save:
- `mem_save("result: wind_analysis — {summary of wind load calculations}")`
- If norm selection decisions: `mem_save("decision: wind — chose {norm} because {reason}")`
