---
name: "CFD Domain (Water)"
description: "Trigger: domain is 'water', working with FEniCSx, Navier-Stokes, hydraulics, dams, or pipe flow"
metadata:
  author: "belico-stack"
  version: "2.0"
  domain: "water"
---

# Skill: CFD Domain (Water)

## When to Use

- Domain is set to "water" in `config/params.yaml`
- Working with FEniCSx for fluid simulations
- Solving Navier-Stokes, free surface flow, or fluid-structure interaction
- Writing papers in the hydraulics domain

## Critical Patterns

### Solver Backend

The water domain uses FEniCSx for:
- Incompressible Navier-Stokes (pipe flow, open channels)
- Free surface flow (dam breaks, spillways)
- Fluid-structure interaction (submerged structures, piers)
- Hydraulic SHM (pressure monitoring, flow anomalies)

### SSOT Parameters

All water domain params live in `config/params.yaml` under `fluid:`:
```yaml
fluid:
  properties:
    viscosity_mu: null       # Pa.s (typ. 1e-3 for water)
    density_rho: null        # kg/m3 (typ. 1000)
  geometry:
    length: null             # m — simulation domain length
    height: null             # m — domain height
    width: null              # m — domain width (0 for 2D)
  boundary:
    inlet_velocity: null     # m/s — inlet velocity
    outlet_pressure: null    # Pa — outlet pressure (gauge)
  mesh:
    resolution: null         # elem/m — mesh resolution
  analysis:
    time_step: null          # s — transient time step
    total_time: null         # s — total simulation time
```

> **Note:** `reynolds_number` and `turbulence_model` are not in the SSOT.
> Planned — add to `params.yaml` when implementing turbulence selection.

### FEniCSx Mesh Generation

```python
from dolfinx import mesh
domain = mesh.create_rectangle(
    MPI.COMM_WORLD,
    [np.array([0, 0]), np.array([L, H])],
    [nx, ny],
    cell_type=mesh.CellType.triangle
)
```

### Convergence Requirements

- Mesh convergence study: run at 3 refinement levels, check < 2% change
- CFL condition: dt < dx / u_max
- Residual norm < 1e-6 per time step

### Paper Sections (Water Domain)

- **Methodology**: governing equations (NS), discretization (FEM), stabilization
- **Results**: velocity profiles, pressure contours, drag/lift coefficients
- **Validation**: compare against analytical solutions (Poiseuille, Couette) or experimental data

### Key References

Categories: `cfd`, `hydraulics`
- Logg et al. 2012 (FEniCS book)
- Alnaes et al. 2015 (UFL)
- John 2016 (FEM for NS)
- Chanson 2004 (Hydraulics of open channel flow)

### Verifier Checks

1. Mass conservation: integral(div(u))dOmega ≈ 0
2. Energy balance: kinetic + potential + dissipation = input
3. Mesh independence (3-level convergence study)
4. CFL number < 1 for explicit schemes

## Anti-Patterns

- Running CFD without a mesh convergence study
- Using dt that violates CFL condition
- Reporting results without specifying Reynolds number
- Comparing CFD results to codes without stating turbulence model

## Engram Integration
After using this skill, the sub-agent should save:
- `mem_save("result: cfd_analysis — {summary of simulation setup and key results}")`
- If new mesh/solver decisions: `mem_save("decision: cfd — {what} because {why}")`
