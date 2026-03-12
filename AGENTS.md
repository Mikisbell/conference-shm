# Belico Stack — Code Review Rules (GGA)

These rules are enforced by Gentleman Guardian Angel on every commit.

## Python Rules

1. **No hardcoded physical parameters.** All constants (stiffness, mass, damping, fy, E) must come from `config/params.yaml` via `src/physics/models/params.py`. Never define physics values inline.

2. **No data fabrication.** Functions must not generate fake sensor data or return placeholder values. If data is unavailable, raise an exception or return None.

3. **SSOT consistency.** Any file importing physical parameters must use `from src.physics.models.params import P` or read from `config/params.yaml`. No duplicate parameter definitions.
   - **Exception:** `src/physics/torture_chamber.py` uses `_load_ssot()` (full YAML tree for non-linear fiber model: Concrete02, Steel02, column geometry). This is intentional two-layer design: `_load_ssot()` serves the non-linear solver; `models/params.P` serves the 1-DOF oscillator. They are NOT duplicates.

4. **Path hygiene.** Use `Path` objects (not string concatenation) for file paths. Never use `simulation/` or `firmware/` — the correct paths are `src/physics/` and `src/firmware/`.

5. **No silent failures.** Catch specific exceptions, not bare `except:`. Log errors with enough context to diagnose (parameter name, expected vs actual value).

## Arduino/C++ Rules

6. **Include params.h.** All `.ino` files must `#include "params.h"`. Never define constants that exist in `params.h`.

7. **Heartbeat safety.** Any firmware controlling actuators must implement a watchdog/heartbeat. If no Python heartbeat in `2*dt`, cut the load.

## Shell Script Rules

8. **set -euo pipefail.** All bash scripts must start with strict mode.

9. **No absolute user paths.** Use `$ROOT`, `$HOME`, or relative paths. Never hardcode `/home/mateo/` in committed scripts.

## General Rules

10. **No secrets in code.** No API keys, tokens, or credentials in any committed file.

11. **AI attribution.** Generated content in `articles/drafts/` must include `<!-- AI_Assist -->` markers.

12. **Mathematical model constants vs configuration parameters.** Not all numeric literals are Rule 1 violations. Two categories are explicitly distinguished:

    | Category | Where it lives | Pattern |
    |----------|---------------|---------|
    | **Config params** — change between runs, sites, or experiments (mass, PGA target, damping ratio) | `config/params.yaml` → SSOT | Read via `.get()` + `sys.exit(1)` on None |
    | **Mathematical model constants** — form part of the equation itself; changing them changes the model, not the instance (Saltelli weights, Sobol factors, Newmark β/γ, Runge-Kutta coefficients) | Source code, module-level `UPPER_CASE` | Named constant + inline citation |

    **Mandatory pattern for mathematical constants:**
    ```python
    _SALTELLI_PGA_WEIGHT = 5       # Saltelli & Tarantola 2002, Eq. 21
    _SALTELLI_K_SCALE    = 1.2     # Saltelli & Tarantola 2002, Eq. 22 — normalized thermal factor
    _NEWMARK_BETA        = 0.25    # Newmark 1959 — average acceleration method (unconditionally stable)
    ```
    Rule: if moving the number to YAML requires adding a math note explaining which published equation it implements, it is a model constant, not a configuration parameter.

    **Known analytical-constant zones (GGA false-positive list):**
    - `src/physics/cross_validation.py` — `_SALTELLI_*` constants in `compute_sensitivity_index._y()`
    - `src/physics/torture_chamber.py` — Newmark integration β/γ if set as named constants
    - Any file implementing a published numerical method with coefficients cited in docstring
