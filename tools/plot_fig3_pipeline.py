"""
Generate Fig. 3 — Synthetic pipeline flowchart for shm-pinn-bolted.

Saves:
  articles/figures/fig3_pipeline.pdf
  articles/figures/fig3_pipeline.png
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent / "articles" / "figures"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# --- Layout constants ---
FIG_W, FIG_H = 10, 3
N_BOXES = 5
BOX_W, BOX_H = 1.35, 0.70
Y_CENTER = 0.62          # vertical center of boxes (axes fraction 0-1 mapped to data)
ARROW_GAP = 0.08         # gap between box edge and arrow tip (in data units)

# Box labels (main text)
LABELS = [
    "Modelo Analítico\nde Ondas",
    "Tiempos de\nArribo AE (\u00d7400)",
    "PINN\nEc. de Onda",
    "Localización\nde Fuente (x,y)",
    "Exportación\nifcJSON",
]

# Sub-labels (small text below each box)
SUBLABELS = [
    "4 escenarios de torque",
    "ae_synthetic_arrivals.csv",
    "\u03bb=0.1, 500 épocas",
    "MAE=8.3\u202fmm",
    "ifc_export_sample.json",
]

# Blue-grey progressive palette (light → dark)
COLORS = [
    "#c9d9e8",  # lightest
    "#a3bdd4",
    "#7fa2bf",
    "#5a87ab",
    "#3a6d97",  # darkest
]
TEXT_COLORS = ["#1a2a3a"] * 3 + ["#ffffff"] * 2

# --- Figure ---
fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
ax.set_xlim(0, FIG_W)
ax.set_ylim(0, FIG_H)
ax.axis("off")

# Spacing: distribute boxes evenly with equal gaps
total_box_width = N_BOXES * BOX_W
total_gap = FIG_W - total_box_width
gap = total_gap / (N_BOXES + 1)

box_centers_x = [gap + i * (BOX_W + gap) + BOX_W / 2 for i in range(N_BOXES)]
box_y0 = FIG_H * Y_CENTER - BOX_H / 2      # bottom of boxes in data coords

for i, (cx, label, sublabel, color, tc) in enumerate(
    zip(box_centers_x, LABELS, SUBLABELS, COLORS, TEXT_COLORS)
):
    x0 = cx - BOX_W / 2
    # Main box
    rect = mpatches.FancyBboxPatch(
        (x0, box_y0), BOX_W, BOX_H,
        boxstyle="round,pad=0.05",
        linewidth=1.2,
        edgecolor="#2c5f8a",
        facecolor=color,
        zorder=3,
    )
    ax.add_patch(rect)

    # Main label
    ax.text(
        cx, box_y0 + BOX_H / 2,
        label,
        ha="center", va="center",
        fontsize=8.5, fontweight="bold",
        color=tc, zorder=4,
        linespacing=1.4,
    )

    # Sub-label below box
    ax.text(
        cx, box_y0 - 0.18,
        sublabel,
        ha="center", va="top",
        fontsize=6.8, color="#555555",
        style="italic", zorder=4,
    )

# Arrows between boxes
arrow_y = box_y0 + BOX_H / 2
for i in range(N_BOXES - 1):
    x_start = box_centers_x[i] + BOX_W / 2 + ARROW_GAP
    x_end   = box_centers_x[i + 1] - BOX_W / 2 - ARROW_GAP
    ax.annotate(
        "",
        xy=(x_end, arrow_y),
        xytext=(x_start, arrow_y),
        arrowprops=dict(
            arrowstyle="-|>",
            color="black",
            lw=1.4,
            mutation_scale=14,
        ),
        zorder=5,
    )

# Title
ax.text(
    FIG_W / 2, FIG_H - 0.12,
    "Fig. 2 \u2014 Pipeline de datos sintéticos desde simulación analítica hasta gemelo digital BIM",
    ha="center", va="top",
    fontsize=8, color="#333333",
)

plt.tight_layout(pad=0.1)

for ext in ("pdf", "png"):
    out = OUTPUT_DIR / f"fig3_pipeline.{ext}"
    dpi = 150 if ext == "png" else None
    fig.savefig(out, dpi=dpi, bbox_inches="tight")
    print(f"Saved: {out}")

plt.close(fig)
