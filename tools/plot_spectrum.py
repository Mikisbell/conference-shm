#!/usr/bin/env python3
"""
tools/plot_spectrum.py — Generador de Gráficas SVG para el EIU
================================================================
Genera la figura comparativa del Espectro de Pseudo-Aceleración Sa(T, ζ=5%)
para el paper científico:
  - Línea Azul: Registro crudo PEER/CISMID (sismo real sin filtrar)
  - Línea Verde: Registro filtrado por el Guardian Angel (escalado a 0.45g)
  - Banda Roja: Periodos de peligro para study material

El SVG se incrusta directamente en el Draft Markdown del paper.
"""

import sys
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.physics.peer_adapter import PeerAdapter
from src.physics.spectral_engine import compute_spectral_response


def generate_svg_spectrum(sa_raw: dict, sa_filt: dict, out_path: Path) -> str:
    """
    Genera un SVG académico comparando el espectro crudo vs. filtrado.
    Retorna el SVG como string (también lo guarda en out_path).
    """
    T      = sa_raw["T"]
    Sa_r   = sa_raw["Sa"]
    Sa_f   = sa_filt["Sa"]
    pga_r  = sa_raw["pga"]
    pga_f  = sa_filt["pga"]

    # ── Normalización a coordenadas SVG (viewport 700 x 420 px) ──
    W, H   = 700, 420
    MARGIN = {"top": 40, "right": 40, "bottom": 70, "left": 70}

    pw = W - MARGIN["left"] - MARGIN["right"]   # Plot width
    ph = H - MARGIN["top"] - MARGIN["bottom"]   # Plot height

    T_min, T_max = 0.0, 3.0
    Sa_max       = max(np.max(Sa_r), np.max(Sa_f)) * 1.15  # Con margen

    def tx(t_val):  return MARGIN["left"] + (t_val - T_min) / (T_max - T_min) * pw
    def ty(sa_val): return MARGIN["top"]  + (1 - sa_val / Sa_max) * ph

    # Polilíneas
    def polypoints(T_arr, Sa_arr):
        return " ".join(f"{tx(t):.1f},{ty(s):.1f}" for t, s in zip(T_arr, Sa_arr))

    poly_raw  = polypoints(T, Sa_r)
    poly_filt = polypoints(T, Sa_f)

    # Periodo dominante
    peak_idx = int(np.argmax(Sa_r))
    T_star   = T[peak_idx]
    Sa_star  = Sa_r[peak_idx]

    # Etiquetas del eje X (cada 0.5s)
    x_ticks = np.arange(0, 3.5, 0.5)
    x_tick_svg = "".join([
        f'<line x1="{tx(t):.1f}" y1="{MARGIN["top"]+ph}" x2="{tx(t):.1f}" y2="{MARGIN["top"]+ph+5}" stroke="#aaa" stroke-width="1"/>'
        f'<text x="{tx(t):.1f}" y="{MARGIN["top"]+ph+18}" text-anchor="middle" font-size="11" fill="#555">{t:.1f}</text>'
        for t in x_ticks
    ])

    # Etiquetas del eje Y (cada 0.25g)
    y_ticks = np.round(np.arange(0, Sa_max + 0.01, Sa_max / 6), 2)
    y_tick_svg = "".join([
        f'<line x1="{MARGIN["left"]-5}" y1="{ty(s):.1f}" x2="{MARGIN["left"]}" y2="{ty(s):.1f}" stroke="#aaa" stroke-width="1"/>'
        f'<text x="{MARGIN["left"]-8}" y="{ty(s)+4:.1f}" text-anchor="end" font-size="11" fill="#555">{s:.2f}</text>'
        for s in y_ticks if s <= Sa_max
    ])

    # Grid horizontal
    grid_svg = "".join([
        f'<line x1="{MARGIN["left"]}" y1="{ty(s):.1f}" x2="{MARGIN["left"]+pw}" y2="{ty(s):.1f}" stroke="#eee" stroke-width="1"/>'
        for s in y_ticks if s <= Sa_max
    ])

    # Línea T* (periodo dominante)
    t_star_line = f"""
    <line x1="{tx(T_star):.1f}" y1="{MARGIN["top"]}" x2="{tx(T_star):.1f}" y2="{MARGIN["top"]+ph}"
          stroke="#e74c3c" stroke-width="1.5" stroke-dasharray="6,3"/>
    <text x="{tx(T_star)+5:.1f}" y="{MARGIN["top"]+15}" font-size="10" fill="#e74c3c">
      T*={T_star:.2f}s
    </text>"""

    # Marcador del pico
    peak_mark = f"""
    <circle cx="{tx(T_star):.1f}" cy="{ty(Sa_star):.1f}" r="5" fill="#e74c3c" opacity="0.9"/>
    <text x="{tx(T_star)+8:.1f}" y="{ty(Sa_star)-5:.1f}" font-size="10" fill="#e74c3c">
      Sa={Sa_star:.3f}g
    </text>"""

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">
  <rect width="{W}" height="{H}" fill="white" rx="8"/>

  <!-- Título -->
  <text x="{W//2}" y="22" text-anchor="middle" font-size="13" font-weight="bold" fill="#2c3e50">
    Pseudo-Acceleration Spectrum Sa(T, ζ=5%) — PISCO 2007 vs Guardian Angel Filter
  </text>

  <!-- Área del gráfico -->
  <rect x="{MARGIN["left"]}" y="{MARGIN["top"]}" width="{pw}" height="{ph}"
        fill="#fafafa" stroke="#ccc" stroke-width="1"/>

  <!-- Grid -->
  {grid_svg}

  <!-- Ejes -->
  <line x1="{MARGIN["left"]}" y1="{MARGIN["top"]+ph}" x2="{MARGIN["left"]+pw}" y2="{MARGIN["top"]+ph}"
        stroke="#555" stroke-width="1.5"/>
  <line x1="{MARGIN["left"]}" y1="{MARGIN["top"]}" x2="{MARGIN["left"]}" y2="{MARGIN["top"]+ph}"
        stroke="#555" stroke-width="1.5"/>

  <!-- Ticks -->
  {x_tick_svg}
  {y_tick_svg}

  <!-- Etiquetas de ejes -->
  <text x="{MARGIN["left"]+pw//2}" y="{H-10}" text-anchor="middle" font-size="12" fill="#333">
    Period T (s)
  </text>
  <text transform="rotate(-90 18 {MARGIN["top"]+ph//2})"
        x="18" y="{MARGIN["top"]+ph//2}" text-anchor="middle" font-size="12" fill="#333">
    Sa (g)
  </text>

  <!-- Línea T* peligro -->
  {t_star_line}

  <!-- Espectro Crudo (azul) -->
  <polyline points="{poly_raw}"
            fill="none" stroke="#2980b9" stroke-width="2" opacity="0.85"/>

  <!-- Espectro Filtrado por Guardian Angel (verde) -->
  <polyline points="{poly_filt}"
            fill="none" stroke="#27ae60" stroke-width="2" stroke-dasharray="8,3" opacity="0.85"/>

  <!-- Marcador pico -->
  {peak_mark}

  <!-- Leyenda -->
  <rect x="{MARGIN["left"]+10}" y="{MARGIN["top"]+10}" width="220" height="52" fill="white"
        stroke="#ddd" stroke-width="1" rx="4"/>
  <line x1="{MARGIN["left"]+20}" y1="{MARGIN["top"]+22}" x2="{MARGIN["left"]+45}" y2="{MARGIN["top"]+22}"
        stroke="#2980b9" stroke-width="2"/>
  <text x="{MARGIN["left"]+50}" y="{MARGIN["top"]+26}" font-size="10" fill="#333">
    PEER Raw (PGA={pga_r:.3f}g)
  </text>
  <line x1="{MARGIN["left"]+20}" y1="{MARGIN["top"]+40}" x2="{MARGIN["left"]+45}" y2="{MARGIN["top"]+40}"
        stroke="#27ae60" stroke-width="2" stroke-dasharray="6,2"/>
  <text x="{MARGIN["left"]+50}" y="{MARGIN["top"]+44}" font-size="10" fill="#333">
    Guardian Angel Filtered (PGA={pga_f:.3f}g)
  </text>
  <line x1="{MARGIN["left"]+20}" y1="{MARGIN["top"]+58}" x2="{MARGIN["left"]+45}" y2="{MARGIN["top"]+58}"
        stroke="#e74c3c" stroke-width="1.5" stroke-dasharray="4,2"/>
  <text x="{MARGIN["left"]+50}" y="{MARGIN["top"]+62}" font-size="10" fill="#e74c3c">
    Dominant Period T*
  </text>
</svg>"""

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        f.write(svg)

    print(f"📊 [SVG] Espectro exportado: {out_path}")
    return svg


if __name__ == "__main__":
    import yaml
    import argparse

    _params_path = ROOT / "config" / "params.yaml"
    if not _params_path.exists():
        raise FileNotFoundError(f"SSOT not found: {_params_path}")
    _cfg = yaml.safe_load(_params_path.read_text())
    dt_target = _cfg["temporal"]["dt_simulation"]["value"]

    # Read PGA from params.yaml (SSOT) first, soil_params.yaml as fallback
    design_pga = None
    _design_section = _cfg.get("design", {})
    if isinstance(_design_section, dict):
        _z_entry = _design_section.get("Z")
        if isinstance(_z_entry, dict):
            design_pga = _z_entry.get("value")
        elif _z_entry is not None:
            design_pga = _z_entry
    if design_pga is None:
        _soil_path = ROOT / "config" / "soil_params.yaml"
        if _soil_path.exists():
            import logging as _logging
            _logging.warning("design.Z not found in params.yaml (SSOT) — falling back to soil_params.yaml")
            _soil = yaml.safe_load(_soil_path.read_text()) or {}
            design_pga = _soil.get("design", {}).get("Z")
    if design_pga is None:
        raise ValueError(
            "design.Z (PGA) not found in config/params.yaml or config/soil_params.yaml — "
            "set the seismic zone factor before plotting"
        )

    ap = argparse.ArgumentParser(description="Plot response spectrum SVG")
    ap.add_argument("--record", type=str, default=str(ROOT / "db" / "excitation" / "records" / "PISCO_2007_ICA_EW.AT2"),
                    help="Path to .AT2 ground motion record")
    args = ap.parse_args()

    adapter = PeerAdapter(target_frequency_hz=100.0)
    record_path = Path(args.record)

    raw_dict   = adapter.read_at2_file(record_path)
    accel_raw  = adapter.normalize_and_resample(raw_dict)
    accel_filt = adapter.scale_to_pga(accel_raw, target_pga_g=design_pga)

    print("⚡ Calculando Sa crudo...")
    sa_raw  = compute_spectral_response(accel_raw,  dt_target)
    print("⚡ Calculando Sa filtrado (Guardian Angel)...")
    sa_filt = compute_spectral_response(accel_filt, dt_target)

    out = ROOT / "articles" / "figures" / "spectrum_pisco2007.svg"
    generate_svg_spectrum(sa_raw, sa_filt, out)
    print(f"✅ Listo. Abre: {out}")
