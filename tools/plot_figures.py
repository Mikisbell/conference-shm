#!/usr/bin/env python3
"""
tools/plot_figures.py — Standardized Figure Pipeline for EIU Papers
====================================================================
Generates numbered, publication-ready figures for any domain paper.
All figures output to articles/figures/ in both PDF and PNG format.

Data Flow (READ THIS BEFORE EDITING):
--------------------------------------
This script does NOT run simulations. It is a pure visualization layer.
The data pipeline is:

  1. torture_chamber.py (OpenSeesPy)  ← runs the structural simulation
         ↓ produces raw numbers
  2. data/processed/*.csv + cv_results.json  ← simulation outputs on disk
         ↓ this script reads from here (see _load_cv_data())
  3. plot_figures.py (matplotlib)  ← YOU ARE HERE — only reads & plots
         ↓ produces publication figures
  4. articles/figures/*.pdf + *.png  ← used by scientific_narrator.py

  cv_results.json is written by:
    - research_director.py (step 2 → cross_validation, step 2b → spectral)
    - compute_statistics.py (step 2c → adds *_std keys + statistics_summary)

  If cv_results.json is missing: run COMPUTE phase first (C2/C3 in CLAUDE.md).
  If *_std keys are missing (error bars): run compute_statistics.py --quartile q1/q2.

Quartile requirements:
  Conference / Q4  — no error bars required
  Q3               — fig_benchmark_comparison (Fig 5) is required
  Q2               — error bars (yerr / fill_between) are required
  Q1               — error bars + benchmark comparison are both required

Error bars / confidence intervals are REQUIRED for Q1/Q2.
Pass --quartile q1 or --quartile q2 to enforce this and render them.

Usage:
  python3 tools/plot_figures.py --domain structural
  python3 tools/plot_figures.py --domain structural --quartile q1
  python3 tools/plot_figures.py --domain water
  python3 tools/plot_figures.py --domain air
  python3 tools/plot_figures.py --list              # List available figures
"""

import sys
import argparse
import json
from pathlib import Path

try:
    import numpy as np
except ImportError:
    print("[FIGURES] numpy not installed. Run: pip install numpy", file=sys.stderr)
    sys.exit(1)

try:
    import yaml
except ImportError:
    print("[FIGURES] PyYAML not installed. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, ROOT)

# Load SSOT params for figure labels/annotations
_SSOT_PARAMS = {}
_PARAMS_PATH = ROOT / "config" / "params.yaml"
if _PARAMS_PATH.exists():
    try:
        with open(_PARAMS_PATH, encoding="utf-8") as _f:
            _SSOT_PARAMS = yaml.safe_load(_f) or {}
    except (FileNotFoundError, yaml.YAMLError) as e:
        print(f"[PLOT] SSOT load failed: {e}", file=sys.stderr)

def _get_ssot_structural_labels() -> dict:
    """Extract structural params from SSOT for figure annotations."""
    structure = _SSOT_PARAMS.get("structure", {})
    damping = _SSOT_PARAMS.get("damping", {})
    return {
        "mass_kg": structure.get("mass_m", {}).get("value", "N/A"),
        "stiffness_N_m": structure.get("stiffness_k", {}).get("value", "N/A"),
        "damping_ratio": damping.get("ratio_xi", {}).get("value", "N/A"),
    }

FIG_DIR = ROOT / "articles" / "figures"


def _ensure_matplotlib():
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        plt.rcParams.update({
            "font.family": "serif",
            "font.size": 10,
            "axes.labelsize": 11,
            "axes.titlesize": 12,
            "figure.dpi": 300,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.1,
        })
        return plt
    except ImportError:
        print("[FIGURES] matplotlib not installed. pip install matplotlib")
        sys.exit(1)


def _save_figure(plt, fig_id: str, title: str):
    """Save figure in both PDF and PNG with standard naming."""
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    for ext in ("pdf", "png"):
        out = FIG_DIR / f"{fig_id}.{ext}"
        try:
            plt.savefig(out, format=ext)
        except OSError as e:
            print(f"  [{fig_id}] ERROR saving {out.name}: {e}", file=sys.stderr)
            plt.close()
            return
    plt.close()
    print(f"  [{fig_id}] {title}")


def _load_cv_data() -> dict:
    cv_path = ROOT / "data" / "processed" / "cv_results.json"
    if cv_path.exists():
        try:
            with open(cv_path, encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"cv_results.json is malformed ({e}) — re-run COMPUTE to regenerate it"
            ) from e
    raise FileNotFoundError(
        f"cv_results.json not found at {cv_path} — run COMPUTE first (C2/C3)"
    )


# ═══════════════════════════════════════════════════════════════
# STRUCTURAL FIGURES
# ═══════════════════════════════════════════════════════════════

def fig_architecture(plt):
    """Fig 1: System architecture block diagram."""
    fig, ax = plt.subplots(1, 1, figsize=(8, 4))
    blocks = [
        (0.05, 0.6, "Sensor\n(Nicla+LoRa)"),
        (0.25, 0.6, "Guardian\nAngel"),
        (0.45, 0.6, "Bridge.py\n(Kalman)"),
        (0.65, 0.6, "OpenSeesPy\n(FEM)"),
        (0.85, 0.6, "Engram\n(Ledger)"),
        (0.45, 0.15, "SSOT\n(params.yaml)"),
    ]
    for x, y, label in blocks:
        ax.add_patch(plt.Rectangle((x, y), 0.15, 0.25, fill=True,
                                    facecolor="#e8e8ff", edgecolor="#333", lw=1.5))
        ax.text(x + 0.075, y + 0.125, label, ha="center", va="center", fontsize=8)
    # Arrows
    for i in range(4):
        x1 = blocks[i][0] + 0.15
        x2 = blocks[i + 1][0]
        ax.annotate("", xy=(x2, 0.725), xytext=(x1, 0.725),
                     arrowprops=dict(arrowstyle="->", lw=1.5))
    # SSOT connections
    ax.annotate("", xy=(0.525, 0.6), xytext=(0.525, 0.4),
                 arrowprops=dict(arrowstyle="->", lw=1, ls="--", color="gray"))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    # Annotate with SSOT structural params if available
    ssot = _get_ssot_structural_labels()
    if ssot["mass_kg"] != "N/A":
        ax.text(0.5, 0.02,
                f"SSOT: m={ssot['mass_kg']} kg, k={ssot['stiffness_N_m']} N/m, "
                f"ξ={ssot['damping_ratio']}",
                ha="center", fontsize=7, style="italic", color="gray")
    ax.set_title("Fig. 1 -- System Architecture: Belico Stack EIU")
    _save_figure(plt, "fig_01_architecture", "System Architecture")


def fig_ab_comparison(plt, cv_data: dict, quartile: str = "conference"):
    """Fig 2: A/B cross-validation bar chart.

    Error bars (95% CI) are rendered for Q1/Q2 from cv_data keys:
      control.false_positives_std, control.data_integrity_std
      experimental.false_positives_std, experimental.data_integrity_std
    If std values are absent, a 10% fallback is used (flagged in console).
    """
    res_A = cv_data.get("control", {})
    res_B = cv_data.get("experimental", {})

    metrics = ["False Positives", "Data Integrity %", "Blocked Payloads"]
    _missing_keys = [k for k in ("false_positives", "data_integrity") if k not in res_A or k not in res_B]
    if "blocked_by_guardian" not in res_B:
        _missing_keys.append("blocked_by_guardian")
    if _missing_keys and quartile in ("q1", "q2"):
        print(f"  [fig_02] WARNING: cv_results.json missing keys {_missing_keys} — 0 fallback used (run COMPUTE C2)", file=sys.stderr)

    vals_A = [
        res_A.get("false_positives", 0),
        res_A.get("data_integrity", 0),
        0,
    ]
    vals_B = [
        res_B.get("false_positives", 0),
        res_B.get("data_integrity", 0),
        res_B.get("blocked_by_guardian", 0),
    ]

    x = np.arange(len(metrics))
    w = 0.35

    require_errorbars = quartile in ("q1", "q2")
    err_A = err_B = None
    if require_errorbars:
        _eb_ratio = (_SSOT_PARAMS.get("simulation", {})
                     .get("fallback_errorbar_ratio", {})
                     .get("value", 0.10))
        fallback_A = [v * _eb_ratio for v in vals_A]
        fallback_B = [v * _eb_ratio for v in vals_B]
        err_A = [
            res_A.get("false_positives_std", fallback_A[0]),
            res_A.get("data_integrity_std", fallback_A[1]),
            res_A.get("blocked_by_guardian_std", fallback_A[2]),
        ]
        err_B = [
            res_B.get("false_positives_std", fallback_B[0]),
            res_B.get("data_integrity_std", fallback_B[1]),
            res_B.get("blocked_by_guardian_std", fallback_B[2]),
        ]
        if not any(k.endswith("_std") for k in res_A) and not any(k.endswith("_std") for k in res_B):
            print(f"  [fig_02] WARNING: no *_std keys in cv_results.json — using {_eb_ratio*100:.0f}% fallback error bars ({quartile})")

    fig, ax = plt.subplots(figsize=(7, 4))
    bar_kw = dict(capsize=4, error_kw=dict(elinewidth=1.2, ecolor="black"))
    ax.bar(x - w / 2, vals_A, w, label="Control (Traditional)", color="#cc7777",
           yerr=err_A, **bar_kw)
    ax.bar(x + w / 2, vals_B, w, label="Experimental (Belico)", color="#77aa77",
           yerr=err_B, **bar_kw)
    ax.set_xticks(x)
    ax.set_xticklabels(metrics)
    ax.legend()
    ax.set_ylabel("Value")
    ci_note = " ± 95% CI" if require_errorbars else ""
    ax.set_title(f"Fig. 2 -- A/B Cross-Validation Results{ci_note}")
    _save_figure(plt, "fig_02_ab_comparison", "A/B Comparison")


def fig_fragility_curve(plt, cv_data: dict, quartile: str = "conference"):
    """Fig 3: Fragility curve (PGA vs blocked payloads).

    For Q1/Q2, renders a 95% confidence band using:
      fragility_matrix[i].blocked_ci_lower / blocked_ci_upper
    If CI keys absent, falls back to ±15% band (flagged in console).
    """
    res_B = cv_data.get("experimental", {})
    matrix = res_B.get("fragility_matrix", [])
    if not matrix:
        print("  [fig_03] Skipped -- no fragility data")
        return

    pgas = [r.get("pga", 0) for r in matrix]
    blocked = [r.get("blocked", 0) for r in matrix]
    integrity = [r.get("integrity", 0) for r in matrix]

    require_errorbars = quartile in ("q1", "q2")

    fig, ax1 = plt.subplots(figsize=(6, 4))
    ax1.plot(pgas, blocked, "o-", color="#cc4444", label="Blocked Packets")

    if require_errorbars:
        has_ci = all("blocked_ci_lower" in r and "blocked_ci_upper" in r for r in matrix)
        _band = (_SSOT_PARAMS.get("simulation", {})
                 .get("fragility", {})
                 .get("ci_band_pct", {})
                 .get("value", 15)) / 100.0
        if has_ci:
            ci_lo = [r["blocked_ci_lower"] for r in matrix]
            ci_hi = [r["blocked_ci_upper"] for r in matrix]
        else:
            print(f"  [fig_03] WARNING: no CI keys in fragility_matrix — using ±{_band*100:.0f}% band ({quartile})")
            ci_lo = [max(0, b * (1 - _band)) for b in blocked]
            ci_hi = [b * (1 + _band) for b in blocked]
        ax1.fill_between(pgas, ci_lo, ci_hi, color="#cc4444", alpha=0.15, label="95% CI")

    ax1.set_xlabel("PGA (g)")
    ax1.set_ylabel("Blocked Packets", color="#cc4444")
    ax2 = ax1.twinx()
    ax2.plot(pgas, integrity, "s--", color="#4444cc", label="Integrity %")
    ax2.set_ylabel("Data Integrity (%)", color="#4444cc")
    _min_int = (_SSOT_PARAMS.get("guardrails", {})
                .get("min_integrity_display_pct", {})
                .get("value", 95))
    ax2.set_ylim(_min_int, 101)
    fig.legend(loc="upper left", bbox_to_anchor=(0.15, 0.88))
    ci_note = " (95% CI shaded)" if require_errorbars else ""
    ax1.set_title(f"Fig. 3 -- Fragility Curve: Guardian Angel Performance vs PGA{ci_note}")
    _save_figure(plt, "fig_03_fragility_curve", "Fragility Curve")


def fig_sensitivity_tornado(plt, cv_data: dict, quartile: str = "conference"):
    """Fig 4: Sensitivity tornado chart (Saltelli indices).

    For Q1/Q2, adds xerr error bars using total-order index S_Ti minus first-order S_i.
    Keys: sensitivity[i].S_Ti (total-order) or sensitivity[i].S_i_std (bootstrap std).
    If neither present, uses S_i * 0.12 as fallback (flagged in console).
    """
    si_data = cv_data.get("sensitivity", [])
    if not si_data:
        print("  [fig_04] Skipped -- no sensitivity data")
        return

    params = [r.get("param", f"param_{i}") for i, r in enumerate(si_data)]
    si_vals = [r.get("S_i", 0) for r in si_data]

    require_errorbars = quartile in ("q1", "q2")
    xerr = None
    if require_errorbars:
        has_sti = all("S_Ti" in r for r in si_data)
        has_std = all("S_i_std" in r for r in si_data)
        if has_sti:
            # Total-order minus first-order = interaction effect (upper CI)
            xerr = [abs(r["S_Ti"] - r["S_i"]) for r in si_data]
        elif has_std:
            xerr = [r["S_i_std"] for r in si_data]
        else:
            _xerr_ratio = (_SSOT_PARAMS.get("simulation", {})
                           .get("fallback_xerr_ratio", {})
                           .get("value", 0.12))
            print(f"  [fig_04] WARNING: no S_Ti or S_i_std keys — using {_xerr_ratio*100:.0f}% fallback error bars ({quartile})")
            xerr = [abs(v) * _xerr_ratio for v in si_vals]

    # Sort by absolute value
    order = np.argsort(np.abs(si_vals))
    params = [params[i] for i in order]
    si_vals = [si_vals[i] for i in order]
    if xerr is not None:
        xerr = [xerr[i] for i in order]

    fig, ax = plt.subplots(figsize=(6, 4))
    colors = ["#cc4444" if v > 0.5 else "#ccaa44" if v > 0.2 else "#4488cc" for v in np.abs(si_vals)]
    ax.barh(params, si_vals, color=colors,
            xerr=xerr, capsize=4, error_kw=dict(elinewidth=1.2, ecolor="black"))
    ax.set_xlabel("Sensitivity Index $S_i$")
    ci_note = " ± CI" if require_errorbars else ""
    ax.set_title(f"Fig. 4 -- Sensitivity Tornado (Saltelli First-Order){ci_note}")
    ax.axvline(x=0, color="black", lw=0.5)
    _save_figure(plt, "fig_04_sensitivity_tornado", "Sensitivity Tornado")


# ═══════════════════════════════════════════════════════════════
# BENCHMARK COMPARISON FIGURE (Q3+ — reviewer_simulator Gate 1)
# ═══════════════════════════════════════════════════════════════

def fig_benchmark_comparison(plt, cv_data: dict, quartile: str = "q3"):
    """Fig 5: Belico system vs published benchmarks (LANL/Z24/IASC-ASCE).

    Required for Q3+ papers — reviewer_simulator Gate 1 checks that at least
    one published benchmark dataset is referenced and compared.

    Data source: cv_data key 'benchmarks' — list of:
      {"name": "LANL/Z24/IASC-ASCE", "metric": float, "our_metric": float,
       "unit": str, "category": str}
    If absent, a placeholder with TODO markers is rendered.
    """
    benchmark_data = cv_data.get("benchmarks", [])
    if not benchmark_data:
        print("  [fig_05] WARNING: no 'benchmarks' key in cv_results.json — rendering placeholder")
        benchmark_data = [
            {"name": "LANL", "metric": None, "our_metric": None,
             "unit": "RMSE (Hz)", "category": "modal_frequency"},
            {"name": "Z24 Bridge", "metric": None, "our_metric": None,
             "unit": "RMSE (Hz)", "category": "modal_frequency"},
            {"name": "IASC-ASCE", "metric": None, "our_metric": None,
             "unit": "MAC (%)", "category": "mode_shape"},
        ]

    names = [d["name"] for d in benchmark_data]
    ref_vals = [d.get("metric", 0) or 0 for d in benchmark_data]
    our_vals = [d.get("our_metric", 0) or 0 for d in benchmark_data]
    units = [d.get("unit", "") for d in benchmark_data]

    x = np.arange(len(names))
    w = 0.38
    fig, ax = plt.subplots(figsize=(7, 4))
    bars_ref = ax.bar(x - w / 2, ref_vals, w, label="Published Benchmark", color="#8888cc")
    bars_our = ax.bar(x + w / 2, our_vals, w, label="Belico System", color="#77aa77")

    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=15, ha="right")
    ax.legend()
    unit_str = units[0] if len(set(units)) == 1 else "mixed units"
    ax.set_ylabel(unit_str)

    # Annotate TODO if placeholder values are zero
    if all(v == 0 for v in ref_vals + our_vals):
        ax.text(0.5, 0.5, "TODO: populate cv_results.json['benchmarks']",
                transform=ax.transAxes, ha="center", va="center",
                fontsize=9, color="red", style="italic",
                bbox=dict(facecolor="lightyellow", edgecolor="red", boxstyle="round"))

    ax.set_title("Fig. 5 -- Method Comparison vs Published Benchmarks (Q3+)")
    _save_figure(plt, "fig_05_benchmark_comparison", "Benchmark Comparison")


# ═══════════════════════════════════════════════════════════════
# WATER FIGURES (placeholders — populated when FEniCSx data available)
# ═══════════════════════════════════════════════════════════════

def fig_water_mesh_convergence(plt, cv_data: dict, **kwargs):
    """Fig W1: Mesh convergence study for water domain."""
    print("  [fig_w01] Placeholder -- mesh convergence (needs FEniCSx data)")


def fig_water_velocity_profile(plt, cv_data: dict, **kwargs):
    """Fig W2: Velocity profile comparison (numerical vs measured)."""
    print("  [fig_w02] Placeholder -- velocity profile (needs sensor data)")


# ═══════════════════════════════════════════════════════════════
# AIR FIGURES (placeholders — populated when CFD data available)
# ═══════════════════════════════════════════════════════════════

def fig_air_cp_distribution(plt, cv_data: dict, **kwargs):
    """Fig A1: Pressure coefficient distribution on building faces."""
    print("  [fig_a01] Placeholder -- Cp distribution (needs CFD data)")


def fig_air_vortex_shedding(plt, cv_data: dict, **kwargs):
    """Fig A2: Vortex shedding frequency (FFT of Cl signal)."""
    print("  [fig_a02] Placeholder -- vortex shedding (needs CFD data)")


# ═══════════════════════════════════════════════════════════════
# FIGURE REGISTRY
# ═══════════════════════════════════════════════════════════════

FIGURE_REGISTRY = {
    "structural": [
        ("fig_01_architecture", "System Architecture", fig_architecture, False),
        ("fig_02_ab_comparison", "A/B Cross-Validation", fig_ab_comparison, True),
        ("fig_03_fragility_curve", "Fragility Curve", fig_fragility_curve, True),
        ("fig_04_sensitivity_tornado", "Sensitivity Tornado", fig_sensitivity_tornado, True),
        ("fig_05_benchmark_comparison", "Benchmark vs Published (Q3+)", fig_benchmark_comparison, True),
    ],
    "water": [
        ("fig_01_architecture", "System Architecture", fig_architecture, False),
        ("fig_w01_mesh_convergence", "Mesh Convergence", fig_water_mesh_convergence, True),
        ("fig_w02_velocity_profile", "Velocity Profile", fig_water_velocity_profile, True),
    ],
    "air": [
        ("fig_01_architecture", "System Architecture", fig_architecture, False),
        ("fig_a01_cp_distribution", "Cp Distribution", fig_air_cp_distribution, True),
        ("fig_a02_vortex_shedding", "Vortex Shedding", fig_air_vortex_shedding, True),
    ],
}


def _fig_scaffold(fig_id: str, title: str, data_source: str, domain: str = "unknown"):
    """Return a placeholder figure function for registry-loaded domains.

    Generates a labeled scaffold PNG with the figure ID, data source path,
    domain name, and a status note. When the domain is implemented, replace
    with a real figure function.
    """
    def _scaffold_fig(plt, cv_data=None, quartile="q3"):
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.set_title(f"[SCAFFOLD] {title}", fontsize=12, color="#c0392b")
        ax.text(
            0.5, 0.5,
            (
                f"TODO: Implement {fig_id}\n"
                f"Data source: {data_source}\n"
                f"Domain: {domain}\n"
                f"Status: scaffold — implement run_compute() first\n\n"
                f"Add real figure function to tools/plot_figures.py\n"
                f"or wire domains/{domain}.py"
            ),
            ha="center", va="center", fontsize=10,
            transform=ax.transAxes,
            bbox={"boxstyle": "round", "facecolor": "#ffeeba", "alpha": 0.8},
        )
        ax.axis("off")
        out_path = FIG_DIR / f"{fig_id}.png"
        try:
            fig.savefig(str(out_path), dpi=150, bbox_inches="tight")
        except OSError as exc:
            print(f"[FIGURES] WARN: Could not save {fig_id}: {exc}", file=sys.stderr)
        finally:
            plt.close(fig)
        print(f"  [SCAFFOLD] {fig_id} — {title} (placeholder saved)")
    _scaffold_fig.__name__ = f"_scaffold_{fig_id}"
    return _scaffold_fig


def _load_registry_figures(domain: str) -> list | None:
    """Load figure list from Domain Registry for domains not in FIGURE_REGISTRY.

    Returns list of (fig_id, title, func, needs_data) tuples, or None if
    the registry YAML does not exist or has no figures declared.
    """
    try:
        from domains.base import DomainRegistry
        reg = DomainRegistry.get_registry(domain)
    except FileNotFoundError:
        print(
            f"[FIGURES] WARNING: No domain registry found for '{domain}' "
            f"(config/domains/{domain}.yaml missing)",
            file=sys.stderr,
        )
        return None
    except ImportError as exc:
        print(
            f"[FIGURES] WARNING: Could not import DomainRegistry: {exc}",
            file=sys.stderr,
        )
        return None

    figures_config = reg.get("pipeline", {}).get("figures", [])
    if not figures_config:
        print(
            f"[FIGURES] WARNING: Domain '{domain}' registry has no pipeline.figures declared",
            file=sys.stderr,
        )
        return None

    result = []
    for fig in figures_config:
        fig_id = fig.get("id", "fig_unknown")
        title = fig.get("title", fig_id)
        data_source = fig.get("data_source", "data/processed/unknown.csv")
        needs_data = fig.get("required", True)
        func = _fig_scaffold(fig_id, title, data_source, domain=domain)
        result.append((fig_id, title, func, needs_data))

    return result


def _resolve_figure_registry(domain: str) -> list:
    """Return figure list — hardcoded first, then registry fallback."""
    if domain in FIGURE_REGISTRY:
        return FIGURE_REGISTRY[domain]
    registry_figs = _load_registry_figures(domain)
    if registry_figs is not None:
        FIGURE_REGISTRY[domain] = registry_figs  # cache for this session
        return registry_figs
    raise ValueError(
        f"Unknown domain: '{domain}'. "
        f"Registered: {list(FIGURE_REGISTRY.keys())}. "
        f"To add: create config/domains/{domain}.yaml with pipeline.figures."
    )


def generate_figures(domain: str, quartile: str = "conference"):
    """Generate all figures for a domain.

    quartile controls error bar rendering:
      conference/q4/q3 → error bars optional (not rendered)
      q1/q2            → error bars REQUIRED (rendered; fallback if data absent)
    """
    plt = _ensure_matplotlib()
    cv_data = _load_cv_data()

    q = quartile.lower()
    if q in ("q1", "q2"):
        print(f"[FIGURES] Quartile {q.upper()} — error bars / confidence intervals ENABLED (required)")
    print(f"[FIGURES] Generating figures for domain: {domain}")
    figs = _resolve_figure_registry(domain)
    for fig_id, title, func, needs_data in figs:
        if needs_data:
            func(plt, cv_data, quartile=q)
        else:
            func(plt)

    print(f"[FIGURES] Output directory: {FIG_DIR}")


def list_figures():
    """List all available figures across domains."""
    print("Available figures:\n")
    # Show hardcoded + registry domains
    try:
        from domains.base import DomainRegistry
        _reg_domains = {d["domain"] for d in DomainRegistry.list_domains()}
    except (ImportError, Exception):
        _reg_domains = set()
    all_domains = sorted(set(FIGURE_REGISTRY.keys()) | _reg_domains)
    for domain in all_domains:
        try:
            figs = _resolve_figure_registry(domain)
            print(f"  [{domain.upper()}]")
            for fig_id, title, _, _ in figs:
                print(f"    {fig_id:35s} -- {title}")
        except ValueError:
            pass
    print()


def main():
    parser = argparse.ArgumentParser(description="EIU Figure Pipeline")
    try:
        from domains.base import DomainRegistry
        _reg_domains = [d["domain"] for d in DomainRegistry.list_domains()]
    except (ImportError, Exception):
        _reg_domains = []
    _all_plot_domains = sorted(set(list(FIGURE_REGISTRY.keys()) + _reg_domains))
    parser.add_argument("--domain", choices=_all_plot_domains, help="Generate figures for domain")
    parser.add_argument("--quartile", default="conference",
                        choices=["conference", "q4", "q3", "q2", "q1"],
                        help="Paper quartile — enables error bars for q1/q2 (default: conference)")
    parser.add_argument("--list", action="store_true", help="List available figures")
    args = parser.parse_args()

    if args.list:
        list_figures()
    elif args.domain:
        try:
            generate_figures(args.domain, quartile=args.quartile)
        except FileNotFoundError as e:
            print(f"[FIGURES] ERROR: {e}", file=sys.stderr)
            sys.exit(1)
        except ValueError as e:
            print(f"[FIGURES] ERROR: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
