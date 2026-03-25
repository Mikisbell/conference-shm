#!/usr/bin/env python3
"""
tools/plot_fig1_icr_architecture.py — ICR Framework Architecture Figure
========================================================================
Generates Fig. 1 for shm_pinn_bolted_conference paper.

Shows the 6-stage Intelligent Circular Resilience (ICR) framework
with the wave-equation constrained PINN at Stage 3 and ifcJSON
middleware at Stage 4 (both highlighted as paper contributions).

Output:
  articles/figures/fig_01_architecture.pdf
  articles/figures/fig_01_architecture.png

Usage:
  python3 tools/plot_fig1_icr_architecture.py
"""

import sys
from pathlib import Path

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
except ImportError:
    print("[FIG1] matplotlib not installed. Run: pip install matplotlib", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "articles" / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Stage definitions
# ---------------------------------------------------------------------------
stages = [
    {
        "number": "Etapa 1",
        "title": "Caracterización",
        "lines": [
            "Detección de aflojamiento",
            "4 escenarios de torque",
            "(0%, 25%, 50%, 100%)",
        ],
        "highlight": False,
    },
    {
        "number": "Etapa 2",
        "title": "Virtualización BIM/DT",
        "lines": [
            "Modelo LOD3 estructural",
            "Modelo analítico de ondas",
            "generación datos sintéticos",
        ],
        "highlight": False,
    },
    {
        "number": "Etapa 3",
        "title": "Despliegue de Sensores y AE",
        "lines": [
            "6 sensores en perímetro",
            "PINN Ec. de Onda",
            "L = L_datos + λ·L_física",
        ],
        "highlight": True,   # contribución del paper
    },
    {
        "number": "Etapa 4",
        "title": "Actualización Estado de Daño",
        "lines": [
            "Middleware ifcJSON",
            "IfcStructuralPointAction",
            "Integración BIM",
        ],
        "highlight": True,   # contribución del paper
    },
    {
        "number": "Etapa 5",
        "title": "Cuantificación del Daño",
        "lines": [
            "Gradiente MAE por escenario",
            "4,94 → 12,83 mm",
            "precisión de localización",
        ],
        "highlight": False,
    },
    {
        "number": "Etapa 6",
        "title": "Soporte a la Decisión",
        "lines": [
            "Actualización autónoma DT",
            "Monitoreo continuo",
            "activación de mantenimiento",
        ],
        "highlight": False,
    },
]

# ---------------------------------------------------------------------------
# Layout: 2 rows × 3 columns
# ---------------------------------------------------------------------------
COLS = 3
ROWS = 2

BOX_W = 3.0          # box width (data units)
BOX_H = 2.0          # box height
COL_GAP = 0.55       # horizontal gap between boxes
ROW_GAP = 0.9        # vertical gap between rows
ARROW_LEN = COL_GAP  # arrow fills the gap

FIG_W = 12.0
FIG_H = 5.2

# Colors
COLOR_NORMAL    = "#EBF4FA"   # light blue-grey — standard stages
COLOR_HIGHLIGHT = "#FFF3CD"   # amber — contribution stages
EDGE_NORMAL     = "#5B8DB8"
EDGE_HIGHLIGHT  = "#E07B00"
TEXT_TITLE      = "#1A3A5C"
TEXT_BODY       = "#2C2C2C"
TEXT_NUMBER     = "#888888"
ARROW_COLOR     = "#5B8DB8"

# ---------------------------------------------------------------------------
# Compute box anchor positions (bottom-left corner in data coords)
# ---------------------------------------------------------------------------
def box_origin(idx):
    """Return (x, y) bottom-left of box at 0-based index."""
    col = idx % COLS
    row = idx // COLS
    # row 0 is top, row 1 is bottom → invert y
    x = col * (BOX_W + COL_GAP)
    y = (ROWS - 1 - row) * (BOX_H + ROW_GAP)
    return x, y

# ---------------------------------------------------------------------------
# Draw
# ---------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(FIG_W, FIG_H))
ax.set_xlim(-0.2, COLS * (BOX_W + COL_GAP) - COL_GAP + 0.2)
ax.set_ylim(-0.3, ROWS * (BOX_H + ROW_GAP) - ROW_GAP + 0.6)
ax.axis("off")

for idx, stage in enumerate(stages):
    x0, y0 = box_origin(idx)

    fc = COLOR_HIGHLIGHT if stage["highlight"] else COLOR_NORMAL
    ec = EDGE_HIGHLIGHT  if stage["highlight"] else EDGE_NORMAL
    lw = 2.2             if stage["highlight"] else 1.2

    # Box
    box = FancyBboxPatch(
        (x0, y0), BOX_W, BOX_H,
        boxstyle="round,pad=0.08",
        facecolor=fc,
        edgecolor=ec,
        linewidth=lw,
        zorder=2,
    )
    ax.add_patch(box)

    # Stage number (small, grey, top-left of box)
    ax.text(
        x0 + 0.12, y0 + BOX_H - 0.18,
        stage["number"],
        fontsize=7.5,
        color=TEXT_NUMBER,
        va="top",
        ha="left",
        fontfamily="DejaVu Sans",
        zorder=3,
    )

    # Stage title (bold, centred)
    ax.text(
        x0 + BOX_W / 2, y0 + BOX_H - 0.42,
        stage["title"],
        fontsize=9.5,
        fontweight="bold",
        color=TEXT_TITLE,
        va="top",
        ha="center",
        fontfamily="DejaVu Sans",
        zorder=3,
    )

    # Bullet lines
    line_y = y0 + BOX_H - 0.82
    for line in stage["lines"]:
        ax.text(
            x0 + BOX_W / 2, line_y,
            line,
            fontsize=8.2,
            color=TEXT_BODY,
            va="top",
            ha="center",
            fontfamily="DejaVu Sans",
            zorder=3,
        )
        line_y -= 0.36

    # --- Arrows ---
    col = idx % COLS
    row = idx // COLS

    # Horizontal arrow: right edge → next box in same row
    if col < COLS - 1:
        ax_start = x0 + BOX_W
        ay      = y0 + BOX_H / 2
        ax.annotate(
            "",
            xy=(ax_start + ARROW_LEN, ay),
            xytext=(ax_start, ay),
            arrowprops=dict(
                arrowstyle="-|>",
                color=ARROW_COLOR,
                lw=1.5,
            ),
            zorder=4,
        )

    # Vertical arrow: bottom of last box in row 0 → top of first box in row 1
    # (connects Stage 3 bottom to Stage 4 top — they are in positions 2 and 3)
    if idx == COLS - 1:   # last box in first row (Stage 3, idx=2)
        x_turn = x0 + BOX_W / 2  # centre of Stage 3

        # Find Stage 4 (idx=3)
        x4, y4 = box_origin(COLS)  # first box of row 1

        # Draw a bent arrow: down from Stage 3 bottom, left to Stage 4 centre, up
        mid_y   = y0 - ROW_GAP / 2
        x4_mid  = x4 + BOX_W / 2

        # Segment 1: straight down from Stage 3 centre
        ax.annotate(
            "",
            xy=(x_turn, mid_y),
            xytext=(x_turn, y0),
            arrowprops=dict(arrowstyle="-", color=ARROW_COLOR, lw=1.5),
            zorder=4,
        )
        # Segment 2: horizontal to Stage 4 centre
        ax.annotate(
            "",
            xy=(x4_mid, mid_y),
            xytext=(x_turn, mid_y),
            arrowprops=dict(arrowstyle="-", color=ARROW_COLOR, lw=1.5),
            zorder=4,
        )
        # Segment 3: up into Stage 4 top
        ax.annotate(
            "",
            xy=(x4_mid, y4 + BOX_H),
            xytext=(x4_mid, mid_y),
            arrowprops=dict(arrowstyle="-|>", color=ARROW_COLOR, lw=1.5),
            zorder=4,
        )

# Legend for highlighted boxes
legend_patches = [
    mpatches.Patch(facecolor=COLOR_HIGHLIGHT, edgecolor=EDGE_HIGHLIGHT,
                   linewidth=1.8, label="Contribución del paper (Etapas 3 y 4)"),
    mpatches.Patch(facecolor=COLOR_NORMAL,    edgecolor=EDGE_NORMAL,
                   linewidth=1.2, label="Contexto del marco ICR"),
]
ax.legend(
    handles=legend_patches,
    loc="lower right",
    fontsize=8,
    framealpha=0.9,
    edgecolor="#CCCCCC",
)

fig.suptitle(
    "Marco ICR: PINN con Ec. de Onda + Pipeline ifcJSON para SHM de Conexiones Empernadas",
    fontsize=10.5,
    fontweight="bold",
    color=TEXT_TITLE,
    y=0.97,
)

plt.tight_layout(rect=[0, 0, 1, 0.95])

# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------
pdf_path = OUT_DIR / "fig_01_architecture.pdf"
png_path = OUT_DIR / "fig_01_architecture.png"

fig.savefig(pdf_path, dpi=150, bbox_inches="tight")
fig.savefig(png_path, dpi=150, bbox_inches="tight")
plt.close(fig)

pdf_kb = pdf_path.stat().st_size // 1024
png_kb = png_path.stat().st_size // 1024

print(f"[FIG1] Saved: {pdf_path}  ({pdf_kb} KB)")
print(f"[FIG1] Saved: {png_path}  ({png_kb} KB)")
print("[FIG1] Done — ICR 6-stage architecture figure generated.")
