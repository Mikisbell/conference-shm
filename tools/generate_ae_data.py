"""
tools/generate_ae_data.py — Acoustic Emission Synthetic Data Generator
=======================================================================
Generates synthetic Acoustic Emission (AE) arrival-time datasets for a
bolted steel plate under four torque-loss scenarios.

Physics model
-------------
- Steel plate: 300 mm × 300 mm (0.0–0.3 m in x and y)
- Single bolt at center: (0.15, 0.15) m
- Six perimeter sensors:
    S1=(0.00, 0.00)  S2=(0.15, 0.00)  S3=(0.30, 0.00)
    S4=(0.30, 0.30)  S5=(0.15, 0.30)  S6=(0.00, 0.30)
- Wave speed: Lamb S0 mode in a steel plate, 10–100 kHz band.
  Reference: Rose, J.L. (2014) "Ultrasonic Guided Waves in Solid Media",
  Cambridge University Press. Typical S0 phase speed ≈ 5000 m/s for steel.
- Arrival time at sensor i: t_i = dist(source, S_i) / wave_speed + N(0, σ_noise)
  σ_noise = 1 µs (realistic for 1 MHz ADC; see Grosse & Ohtsu, 2008)

Four torque-loss scenarios
--------------------------
intact    (0% loss)  : uniform sources across plate — few near bolt
loose_25 (25% loss)  : 70% within r<0.08 m of bolt, noise ×1.5
loose_50 (50% loss)  : 85% within r<0.05 m of bolt, noise ×2.0
full_loose(100% loss): 95% within r<0.03 m of bolt, noise ×3.0

SSOT note
---------
Steel wave speed and noise floor are domain-specific AE parameters not
present in config/params.yaml (which stores structural/seismic params).
They are defined as module-level constants below, annotated with their
physical sources, in compliance with AGENTS.md Rule 3 (no silent magic).

Output
------
data/processed/ae_synthetic_arrivals.csv
Columns: source_x, source_y, t1, t2, t3, t4, t5, t6, scenario, torque_loss_pct
Rows:    400 total (100 per scenario, configurable via --n-per-scenario)
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Physical constants — annotated with sources (AGENTS.md Rule 3)
# ---------------------------------------------------------------------------

# Lamb S0 wave speed in a 6 mm steel plate at 50 kHz centre frequency.
# Source: Rose (2014) §5.3; Giurgiutiu (2014) Table 2-1.
# Typical range: 4500–5400 m/s depending on thickness and frequency.
_WAVE_SPEED_DEFAULT_MS = 5000.0  # m/s

# Measurement noise standard deviation — 1 µs.
# Rationale: 1 MHz ADC → 1 µs resolution; Johnson noise < 0.1 µs for typical
# preamplifiers (PAC 2/4/6 series, 40 dB gain).
# Source: Grosse & Ohtsu (2008) "Acoustic Emission Testing", §3.4.
_NOISE_SIGMA_DEFAULT_S = 1.0e-6  # s

# Plate geometry (m) — fixed for this study
_PLATE_MIN = 0.0   # m
_PLATE_MAX = 0.3   # m

# Bolt centre position (m)
_BOLT_X = 0.15  # m
_BOLT_Y = 0.15  # m

# Sensor positions: [S1..S6] as (x, y) tuples (m)
_SENSORS = [
    (0.00, 0.00),   # S1 — corner BL
    (0.15, 0.00),   # S2 — edge B-mid
    (0.30, 0.00),   # S3 — corner BR
    (0.30, 0.30),   # S4 — corner TR
    (0.15, 0.30),   # S5 — edge T-mid
    (0.00, 0.30),   # S6 — corner TL
]

# Scenario definitions
# Each entry: (scenario_name, torque_loss_pct, bolt_fraction, bolt_radius_m, noise_multiplier)
_SCENARIOS = [
    ("intact",     0,   0.05, 0.08, 1.0),   # almost uniform; 5% clustered near bolt
    ("loose_25",  25,   0.70, 0.08, 1.5),
    ("loose_50",  50,   0.85, 0.05, 2.0),
    ("full_loose", 100, 0.95, 0.03, 3.0),
]


# ---------------------------------------------------------------------------
# Core geometry helpers
# ---------------------------------------------------------------------------

def _euclidean(x1: float, y1: float, x2: float, y2: float) -> float:
    """Return Euclidean distance between two 2-D points (m)."""
    return float(np.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2))


def _sample_sources_uniform(rng: np.random.Generator, n: int,
                             margin: float = 0.02) -> np.ndarray:
    """Return (n, 2) array of source positions uniformly distributed on the plate
    with a 20 mm margin from the boundary (avoids edge singularities)."""
    lo = _PLATE_MIN + margin
    hi = _PLATE_MAX - margin
    return rng.uniform(lo, hi, size=(n, 2))


def _sample_sources_near_bolt(rng: np.random.Generator, n: int,
                               radius: float) -> np.ndarray:
    """Return (n, 2) array of source positions within `radius` of the bolt centre.

    Uses polar sampling (uniform in r², uniform in θ) to avoid centre bias.
    Sources are clipped to [0.02, 0.28] to stay inside the plate margin.
    """
    angles = rng.uniform(0, 2 * np.pi, size=n)
    # Uniform area sampling: r = sqrt(U) * radius
    r = np.sqrt(rng.uniform(0, 1, size=n)) * radius
    x = np.clip(_BOLT_X + r * np.cos(angles), 0.02, 0.28)
    y = np.clip(_BOLT_Y + r * np.sin(angles), 0.02, 0.28)
    return np.column_stack([x, y])


def _generate_scenario(rng: np.random.Generator,
                        n: int,
                        bolt_fraction: float,
                        bolt_radius: float,
                        noise_multiplier: float,
                        wave_speed: float,
                        base_noise_sigma: float,
                        scenario_name: str,
                        torque_loss_pct: int) -> pd.DataFrame:
    """Generate `n` AE events for a single torque-loss scenario.

    Parameters
    ----------
    rng               : NumPy random generator (seeded externally for reproducibility)
    n                 : Number of AE events to generate
    bolt_fraction     : Fraction of events placed near the bolt (0–1)
    bolt_radius       : Radius (m) within which bolt-cluster events are placed
    noise_multiplier  : Scale factor applied to base_noise_sigma
    wave_speed        : Lamb S0 wave speed (m/s)
    base_noise_sigma  : Base timing noise standard deviation (s)
    scenario_name     : Label string written to 'scenario' column
    torque_loss_pct   : Integer written to 'torque_loss_pct' column

    Returns
    -------
    pd.DataFrame with columns: source_x, source_y, t1..t6, scenario, torque_loss_pct
    """
    n_bolt = int(round(n * bolt_fraction))
    n_uniform = n - n_bolt

    parts = []
    if n_bolt > 0:
        parts.append(_sample_sources_near_bolt(rng, n_bolt, bolt_radius))
    if n_uniform > 0:
        parts.append(_sample_sources_uniform(rng, n_uniform))

    sources = np.vstack(parts)  # (n, 2)

    # Shuffle so bolt-cluster and uniform events are interleaved
    idx = rng.permutation(n)
    sources = sources[idx]

    sigma = base_noise_sigma * noise_multiplier

    # Compute arrival times: t_i = dist / wave_speed + noise
    arrivals = np.zeros((n, len(_SENSORS)))
    for j, (sx, sy) in enumerate(_SENSORS):
        dist = np.sqrt((sources[:, 0] - sx) ** 2 + (sources[:, 1] - sy) ** 2)
        noise = rng.normal(0.0, sigma, size=n)
        arrivals[:, j] = dist / wave_speed + noise

    df = pd.DataFrame({
        "source_x": sources[:, 0],
        "source_y": sources[:, 1],
        "t1": arrivals[:, 0],
        "t2": arrivals[:, 1],
        "t3": arrivals[:, 2],
        "t4": arrivals[:, 3],
        "t5": arrivals[:, 4],
        "t6": arrivals[:, 5],
        "scenario": scenario_name,
        "torque_loss_pct": torque_loss_pct,
    })
    return df


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate synthetic AE arrival-time data for bolted-joint SHM."
    )
    parser.add_argument(
        "--n-per-scenario",
        type=int,
        default=100,
        metavar="INT",
        help="Number of AE events per torque-loss scenario (default: 100)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        metavar="INT",
        help="NumPy random seed for reproducibility (default: 42)",
    )
    parser.add_argument(
        "--wave-speed",
        type=float,
        default=_WAVE_SPEED_DEFAULT_MS,
        metavar="FLOAT",
        help=f"Lamb S0 wave speed in m/s (default: {_WAVE_SPEED_DEFAULT_MS})",
    )
    parser.add_argument(
        "--noise-sigma",
        type=float,
        default=_NOISE_SIGMA_DEFAULT_S,
        metavar="FLOAT",
        help=f"Base timing noise std dev in seconds (default: {_NOISE_SIGMA_DEFAULT_S})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/processed"),
        metavar="PATH",
        help="Output directory (default: data/processed)",
    )
    return parser


def main() -> int:
    """Entry point. Returns 0 on success, 1 on error."""
    parser = _build_arg_parser()
    args = parser.parse_args()

    # ------------------------------------------------------------------
    # Resolve output path relative to project root (not CWD)
    # ------------------------------------------------------------------
    project_root = Path(__file__).resolve().parent.parent
    output_dir = (
        args.output_dir
        if args.output_dir.is_absolute()
        else project_root / args.output_dir
    )

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"[generate_ae_data] ERROR — cannot create output dir: {exc}", file=sys.stderr)
        return 1

    output_path = output_dir / "ae_synthetic_arrivals.csv"

    # ------------------------------------------------------------------
    # Generate data
    # ------------------------------------------------------------------
    rng = np.random.default_rng(args.seed)
    frames = []

    for scenario_name, torque_loss_pct, bolt_fraction, bolt_radius, noise_mult in _SCENARIOS:
        df = _generate_scenario(
            rng=rng,
            n=args.n_per_scenario,
            bolt_fraction=bolt_fraction,
            bolt_radius=bolt_radius,
            noise_multiplier=noise_mult,
            wave_speed=args.wave_speed,
            base_noise_sigma=args.noise_sigma,
            scenario_name=scenario_name,
            torque_loss_pct=torque_loss_pct,
        )
        frames.append(df)

    result = pd.concat(frames, ignore_index=True)
    total = len(result)

    # ------------------------------------------------------------------
    # Write CSV
    # ------------------------------------------------------------------
    try:
        result.to_csv(output_path, index=False, float_format="%.9e")
    except OSError as exc:
        print(f"[generate_ae_data] ERROR — cannot write CSV: {exc}", file=sys.stderr)
        return 1

    print(f"Generated {total} samples → {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
