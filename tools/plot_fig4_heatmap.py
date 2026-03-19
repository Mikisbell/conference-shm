"""
Generate Fig. 4 — Predicted vs ground-truth AE source locations (scatter + arrows).

Fig. 4 — Predicted vs ground-truth AE source locations (N=80 test samples).
Arrows indicate localization error vectors.

Reads:
  data/processed/pinn_localization_results.csv
    columns: source_x, source_y, pred_x, pred_y, error_mm, scenario, torque_loss_pct

Saves:
  articles/figures/fig4_heatmap.pdf
  articles/figures/fig4_heatmap.png
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).parent.parent
CSV_PATH = ROOT / "data" / "processed" / "pinn_localization_results.csv"
OUTPUT_DIR = ROOT / "articles" / "figures"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# --- Load data ---
df = pd.read_csv(CSV_PATH)

# Convert metres → mm
for col in ("source_x", "source_y", "pred_x", "pred_y"):
    df[col] = df[col] * 1000.0

# --- Scenario colours ---
SCENARIOS = ["intact", "loose_25", "loose_50", "full_loose"]
SCENARIO_LABELS = {
    "intact":     "Intact (0% loss)",
    "loose_25":   "25% torque loss",
    "loose_50":   "50% torque loss",
    "full_loose": "Full loose (100%)",
}
PALETTE = ["#2196F3", "#FF9800", "#4CAF50", "#E91E63"]
COLOR_MAP = dict(zip(SCENARIOS, PALETTE))

# --- Geometry (mm) ---
BOLT_X, BOLT_Y = 150.0, 150.0          # bolt at centre of 300×300 mm plate
# 6 sensor vertices: corners + mid-edge points
SENSOR_XY = np.array([
    [0,   0  ],
    [150, 0  ],
    [300, 0  ],
    [300, 300],
    [150, 300],
    [0,   300],
])

# --- Plot ---
fig, ax = plt.subplots(figsize=(6, 6))

# Ground-truth points (light grey)
ax.scatter(
    df["source_x"], df["source_y"],
    c="#bdbdbd", s=28, zorder=2,
    label="Ground truth", alpha=0.7, edgecolors="none",
)

# Predicted points by scenario + error arrows
for scenario, color in COLOR_MAP.items():
    sub = df[df["scenario"] == scenario]
    if sub.empty:
        continue

    ax.scatter(
        sub["pred_x"], sub["pred_y"],
        c=color, s=40, zorder=4,
        label=SCENARIO_LABELS[scenario], alpha=0.85, edgecolors="white", linewidths=0.4,
    )

    # Error arrows: ground truth → predicted
    for _, row in sub.iterrows():
        ax.annotate(
            "",
            xy=(row["pred_x"], row["pred_y"]),
            xytext=(row["source_x"], row["source_y"]),
            arrowprops=dict(
                arrowstyle="-|>",
                color=color,
                lw=0.7,
                mutation_scale=6,
                alpha=0.30,
            ),
            zorder=3,
        )

# Bolt location
ax.scatter(
    [BOLT_X], [BOLT_Y],
    marker="x", s=160, c="black", linewidths=2.5,
    zorder=6, label="Bolt (0.15, 0.15\u202fm)",
)

# Sensor locations
ax.scatter(
    SENSOR_XY[:, 0], SENSOR_XY[:, 1],
    marker="^", s=90, c="black", zorder=6,
    label="Sensors",
)

# Axes and limits
ax.set_xlim(-10, 310)
ax.set_ylim(-10, 310)
ax.set_xlabel("x (mm)", fontsize=10)
ax.set_ylabel("y (mm)", fontsize=10)
ax.set_title(
    "Fig. 4 \u2014 Predicted vs ground-truth AE source locations\n"
    "(N=80 test samples; arrows = localization error vectors)",
    fontsize=9,
)
ax.set_aspect("equal")
ax.grid(True, linestyle="--", alpha=0.35, linewidth=0.6)

# Legend
handles, labels = ax.get_legend_handles_labels()
ax.legend(handles, labels, fontsize=7.5, loc="upper right", framealpha=0.85)

plt.tight_layout()

for ext in ("pdf", "png"):
    out = OUTPUT_DIR / f"fig4_heatmap.{ext}"
    dpi = 150 if ext == "png" else None
    fig.savefig(out, dpi=dpi, bbox_inches="tight")
    print(f"Saved: {out}")

plt.close(fig)
