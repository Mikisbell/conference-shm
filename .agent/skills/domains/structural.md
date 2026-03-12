# Skill: Structural Domain — SHM / Seismic Papers
# Loaded lazily by subagents when project.domain = "structural"

## Domain Identity
- **Solver**: OpenSeesPy (nonlinear FEM, transient analysis)
- **Hardware layer**: Arduino Nano 33 BLE Sense Rev2 (acquisition) + Nicla Sense ME (edge AI)
- **Emulator**: `tools/arduino_emu.py` — PTY serial, bridge.py cannot distinguish emulator from real board
- **Data format**: PEER NGA-West2 AT2 acelerogramas → `src/physics/peer_adapter.py` → numpy arrays
- **Status**: OPERATIONAL

## SSOT Namespaces (config/params.yaml)
```
structure.*    → mass_kg, height_m, n_stories, base_area_m2
nonlinear.*    → fy_mpa, E_gpa, fc_mpa, cover_m
damping.*      → xi (damping ratio, dimensionless)
material.*     → rho_kg_m3, Poisson
acquisition.*  → sample_rate_hz, window_size_s, overlap
firmware.*     → guardian_angel.* (Red Lines, Gates)
```

## Compute Pipeline
```
C0: python3 src/init_bunker.py                           # env check
C1: python3 tools/fetch_benchmark.py --verify            # AT2 records
C2: src/physics/torture_chamber.py                       # OpenSeesPy FEM
C3: tools/arduino_emu.py {mode} {freq_hz}               # hardware-in-loop
C4: tools/generate_degradation.py --modules N           # synthetic if needed
C5: python3 tools/generate_compute_manifest.py          # gate
Stats: python3 tools/compute_statistics.py --quartile q1  # Q1/Q2 only
```

## Emulator Modes
| Board | Mode | What it emulates |
|-------|------|-----------------|
| Nano 33 BLE Sense Rev2 | `sano` | Healthy structure @ fs |
| | `resonance` | Structure at resonance frequency |
| | `dano_leve` | ~5% stiffness degradation |
| | `dano_critico` | ~30% stiffness + drift alarm |
| | `presa` | Dam / water-retaining scenario |
| | `dropout` | LoRa communication loss |
| Nicla Sense ME | `nicla_sano` | Edge AI: healthy classification |
| | `nicla_dano` | Edge AI: damage classification |
| | `nicla_critico` | Edge AI: critical alert |

## Guardian Angel (bridge.py Red Lines)
- **RL-1**: Jitter — packet inter-arrival time out of bounds → abort
- **RL-2**: Stress — computed stress > 0.4 fy → Physical Critic alert
- **RL-3**: Convergence — OpenSeesPy divergence → abort
- **Gates S-1..S-4**: Progressive escalation (warn → throttle → pause → abort)

## Key Source Files
```
src/physics/torture_chamber.py   — OpenSeesPy nonlinear backend
src/physics/bridge.py            — Serial ↔ OpenSeesPy + Guardian Angel
src/physics/peer_adapter.py      — AT2 parser → numpy (time, accel_g)
src/physics/spectral_engine.py   — Sa(T) response spectra
src/physics/cross_validation.py  — scenario A vs B (without/with Guardian)
tools/arduino_emu.py             — PTY emulator (9 modes)
tools/fetch_benchmark.py         — AT2 record validator + PEER scanner
```

## Normative Codes
- E.030 (Peru seismic design)
- ASCE 7-22 (US seismic loads)
- Eurocode 8 (European seismic)
- ACI 318-19 (concrete design)

## Paper Quartile Requirements
| Quartile | Data requirement |
|----------|-----------------|
| Conference | Synthetic/emulated data OK |
| Q4 | Synthetic + validated against benchmark |
| Q3 | Field data OR strong synthetic |
| Q2 | Field data + laboratory |
| Q1 | Field + lab + ≥2 structures + theoretical contribution |

## Figures Produced by plot_figures.py
```bash
python3 tools/plot_figures.py --domain structural --quartile q2
```
- Fig 1: Time-history (displacement vs time, all damage levels)
- Fig 2: Frequency spectrum (FFT — intact vs damaged)
- Fig 3: Force-displacement hysteresis loop
- Fig 4: Sa(T) response spectrum (PEER record vs E.030/ASCE)
- Fig 5: Benchmark comparison (Q3+, required for Q3/Q2/Q1)
- Error bars: mandatory for Q1/Q2 (yerr/fill_between)

## Subagent Instructions
When activated for a structural paper:
1. Read `config/params.yaml` → `structure.*`, `nonlinear.*`, `damping.*`
2. Verify `db/excitation/records/` has AT2 files (`tools/fetch_benchmark.py --scan`)
3. Confirm `data/processed/COMPUTE_MANIFEST.json` exists before IMPLEMENT
4. Use narrator flag: `python3 articles/scientific_narrator.py --domain structural`
5. Cite normative codes (E.030, ASCE, Eurocode 8) in Methods section
6. For Q1/Q2: include statistical tests from `compute_statistics.py` in Results
