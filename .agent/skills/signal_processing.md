---
name: "Signal Processing (Shadow Play)"
description: "Trigger: Kalman filter, sensor data processing, bridge.py, phase lag analysis"
metadata:
  author: "belico-stack"
  version: "2.0"
  domain: "structural"
---

# Skill: Signal Processing (Shadow Play)

## When to Use

- Working with `src/physics/bridge.py` or `src/physics/kalman.py`
- Processing raw sensor data from `data/raw/`
- Debugging phase lag, drift, or noise in accelerometer readings
- Auditing a Kalman filter experiment with the Verifier

## Critical Patterns

### Kalman vs Buffer: Always prefer Kalman

A moving-average buffer introduces **phase lag** — OpenSeesPy receives a delayed signal.
The Kalman filter mitigates lag while penalizing measurement variance (noise).

```python
from src.physics.kalman import RealTimeKalmanFilter1D

# Parameters from config/params.yaml
q = cfg["signal_processing"]["kalman"]["process_noise_q"]["value"]
r = cfg["signal_processing"]["kalman"]["measurement_noise_r"]["value"]

kf = RealTimeKalmanFilter1D(q=q, r=r)

# In the loop: replace buffer with filter
accel_raw = pkt["accel_g"]
accel_filtered = kf.step(accel_raw)
# Inject accel_filtered into OpenSeesPy
```

### Signal classification

A spike in acceleration can mean two things:
1. **Sensory anomaly** (electromagnetic noise): high-frequency, no structural energy. Do NOT abort.
2. **Structural failure** (impact/rupture): real energy transfer. Abort protocol MUST activate.

The Kalman filter's innovation sequence (raw - filtered) distinguishes them:
- Normal innovation distribution (mean ≈ 0): sensor noise, safe
- Persistent bias in innovation: filter diverging OR accelerometer zero-G offset shifted

### SSOT for Kalman parameters

Q and R MUST come from `config/params.yaml` → `signal_processing.kalman`. Never hardcode.
- Q (process noise): how much the true state changes between samples
- R (measurement noise): how noisy the sensor is

### Verifier integration (STEP 7)

When auditing a Kalman experiment, the Verifier must add:
**STEP 7 — Estimator Variance:** `(accel_raw - accel_filtered)` must be a normal distribution with mean ≈ 0. Persistent offset means filter divergence or sensor calibration loss.

## Anti-Patterns

- Using a moving-average buffer instead of Kalman (introduces uncontrolled phase lag)
- Hardcoding Q or R values instead of reading from SSOT
- Aborting on a single spike without checking the innovation sequence
- Skipping mesh between Kalman output and OpenSeesPy input (must verify units: g vs m/s^2)

## Engram Integration
After using this skill, the sub-agent should save:
- `mem_save("result: signal_processing — {filter applied, freq range, key findings}")`
- If calibration changes: `mem_save("calibration: {param} {old}→{new} because {reason}")`
