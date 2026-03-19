#!/usr/bin/env python3
"""
train_pinn_localization.py — PINN-based AE source localization (Conference paper)
==================================================================================
Physics-Informed Neural Network for acoustic-emission source localization on a
300x300 mm aluminum plate with 6 piezoelectric sensors.

Architecture: MLP 6→[hidden×layers]→2  (fully-connected, Tanh activations)
Input  : [t1..t6] — arrival times in microseconds (normalized)
Output : [x, y]   — source coordinates in meters (normalized to [0,1])

Hybrid loss:
  L_total = L_data + lambda_helm * L_physics
  L_data    = MSE(pred_xy, true_xy)              over training samples
  L_physics = MSE(t̂_i, t_i)                     wave-equation residual
              where t̂_i = dist(pred_source, sensor_i) / wave_speed
              and   t_i  are the measured arrival times from the batch

True wave-equation constraint: given the predicted source (x̂,ŷ), compute
theoretical arrival times for all 6 sensors using the wave propagation model
t_i = dist(source, S_i) / c, and penalize against the measured arrival times.
This enforces genuine physics consistency — not a geometric prior.

Usage:
  python3 tools/train_pinn_localization.py
  python3 tools/train_pinn_localization.py --epochs 500 --lambda-helm 0.1
  python3 tools/train_pinn_localization.py --epochs 200 --lr 5e-4 --hidden 128 --layers 6

Outputs:
  data/processed/pinn_localization_results.csv  — per-sample predictions + error
  data/processed/training_history.csv           — per-epoch loss breakdown
  models/pinn_localization.pt                   — saved PyTorch model state dict
"""

import argparse
import csv
import math
import sys
from pathlib import Path

import numpy as np

ROOT      = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
MODELS    = ROOT / "models"

# Physical constants
PLATE_SIZE_M  = 0.30   # plate is 300 mm × 300 mm
WAVE_SPEED    = 5000.0  # m/s  — longitudinal wave speed in aluminum plate
US_SCALE      = 1e6    # seconds → microseconds conversion factor

# Sensor positions in meters (fixed layout on plate)
SENSOR_POS_M = [
    [0.00, 0.00], [0.15, 0.00], [0.30, 0.00],
    [0.00, 0.30], [0.15, 0.30], [0.30, 0.30],
]
CHECKPOINT_INTERVAL = 100  # save checkpoint every N epochs if val_loss improves


# ── PyTorch import guard ───────────────────────────────────────────────────────

def _require_torch():
    try:
        import torch
        import torch.nn as nn
        return torch, nn
    except ImportError:
        print(
            "[ERROR] PyTorch not installed.\n"
            "  Install: pip install torch\n"
            "  Or:      pip install torch --index-url https://download.pytorch.org/whl/cpu",
            file=sys.stderr,
        )
        sys.exit(1)


# ── Data loading ───────────────────────────────────────────────────────────────

def load_arrivals(data_dir: Path):
    """Load ae_synthetic_arrivals.csv.

    Returns
    -------
    t_raw    : ndarray (N, 6)  — arrival times in seconds
    xy_true  : ndarray (N, 2)  — source coordinates in meters
    scenarios: list[str]       — scenario label per row
    torques  : list[float]     — torque_loss_pct per row
    """
    csv_path = data_dir / "ae_synthetic_arrivals.csv"
    if not csv_path.exists():
        print(f"[ERROR] Data file not found: {csv_path}", file=sys.stderr)
        print("  Generate it first: python3 tools/generate_ae_synthetic.py", file=sys.stderr)
        sys.exit(1)

    t_rows, xy_rows, scenarios, torques = [], [], [], []
    try:
        with open(csv_path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                t_rows.append([
                    float(row["t1"]), float(row["t2"]), float(row["t3"]),
                    float(row["t4"]), float(row["t5"]), float(row["t6"]),
                ])
                xy_rows.append([float(row["source_x"]), float(row["source_y"])])
                scenarios.append(row["scenario"])
                torques.append(float(row["torque_loss_pct"]))
    except (KeyError, ValueError) as e:
        print(f"[ERROR] Malformed CSV {csv_path}: {e}", file=sys.stderr)
        sys.exit(1)

    t_raw   = np.array(t_rows,  dtype=np.float32)
    xy_true = np.array(xy_rows, dtype=np.float32)
    print(f"[INFO] Loaded {len(t_rows)} samples from {csv_path.name}")
    return t_raw, xy_true, scenarios, torques


# ── Normalisation ──────────────────────────────────────────────────────────────

def build_normalizers(t_raw: np.ndarray, xy_true: np.ndarray):
    """Compute normalization statistics on training data only.

    t  : seconds → microseconds  (×1e6), then standardize (μ, σ)
    xy : [0, PLATE_SIZE_M] → [0, 1]  via divide by PLATE_SIZE_M

    Returns callables (normalize_t, normalize_xy, denormalize_xy) and stats dict.
    """
    t_us = t_raw * US_SCALE  # seconds → microseconds
    t_mean = t_us.mean(axis=0)
    t_std  = t_us.std(axis=0) + 1e-8  # avoid division by zero

    def normalize_t(t_s: np.ndarray) -> np.ndarray:
        return (t_s * US_SCALE - t_mean) / t_std

    def normalize_xy(xy_m: np.ndarray) -> np.ndarray:
        return xy_m / PLATE_SIZE_M  # → [0, 1]

    def denormalize_xy(xy_norm: np.ndarray) -> np.ndarray:
        return xy_norm * PLATE_SIZE_M  # → meters

    stats = {"t_mean": t_mean, "t_std": t_std}
    return normalize_t, normalize_xy, denormalize_xy, stats


# ── Model definition ───────────────────────────────────────────────────────────

def build_model(hidden: int, layers: int):
    """Build MLP: 6 → [hidden × layers] → 2, Tanh activations, Sigmoid output.

    Output sigmoid constrains predictions to [0, 1] (normalised plate coordinates).
    """
    torch, nn = _require_torch()

    layer_list = [nn.Linear(6, hidden), nn.Tanh()]
    for _ in range(layers - 1):
        layer_list += [nn.Linear(hidden, hidden), nn.Tanh()]
    layer_list += [nn.Linear(hidden, 2), nn.Sigmoid()]

    model = nn.Sequential(*layer_list)

    # Xavier uniform initialization for Tanh networks
    for m in model.modules():
        if isinstance(m, nn.Linear):
            nn.init.xavier_uniform_(m.weight)
            nn.init.zeros_(m.bias)

    return model


# ── Training ───────────────────────────────────────────────────────────────────

def train(args):
    torch, nn = _require_torch()

    # Reproducibility
    torch.manual_seed(args.seed)
    rng = np.random.default_rng(args.seed)

    # ── Load data ─────────────────────────────────────────────────────────────
    data_dir = Path(args.data_dir)
    t_raw, xy_true, scenarios, torques = load_arrivals(data_dir)
    n_total = len(t_raw)

    # ── Stratified 80/20 split by scenario ────────────────────────────────────
    unique_scenarios = sorted(set(scenarios))
    train_idx, test_idx = [], []
    for sc in unique_scenarios:
        idx = [i for i, s in enumerate(scenarios) if s == sc]
        rng.shuffle(idx)
        split = max(1, int(math.ceil(len(idx) * 0.8)))
        train_idx.extend(idx[:split])
        test_idx.extend(idx[split:])
    train_idx = np.array(train_idx)
    test_idx  = np.array(test_idx)

    print(f"[INFO] Split: train={len(train_idx)}, test={len(test_idx)} "
          f"(stratified by scenario)")

    # ── Normalizers (fit on train only) ───────────────────────────────────────
    normalize_t, normalize_xy, denormalize_xy, stats = build_normalizers(
        t_raw[train_idx], xy_true[train_idx]
    )

    X_all  = normalize_t(t_raw).astype(np.float32)
    Y_all  = normalize_xy(xy_true).astype(np.float32)

    X_train = torch.tensor(X_all[train_idx])
    Y_train = torch.tensor(Y_all[train_idx])
    X_test  = torch.tensor(X_all[test_idx])
    Y_test  = torch.tensor(Y_all[test_idx])

    # ── Model, optimizer, loss ────────────────────────────────────────────────
    model  = build_model(args.hidden, args.layers)
    optim  = torch.optim.Adam(model.parameters(), lr=args.lr)
    mse    = nn.MSELoss()

    import torch.nn.functional as F  # noqa: E402 — used for wave-eq residual

    n_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"[INFO] Model: MLP 6→[{args.hidden}×{args.layers}]→2 | "
          f"params={n_params} | Tanh+Sigmoid")
    print(f"[INFO] Training: epochs={args.epochs}, lr={args.lr}, "
          f"batch={args.batch_size}, λ_phys={args.lambda_helm}")
    print(f"[INFO] Physics constraint: wave-equation residual "
          f"t̂_i = dist(pred_source, S_i) / {WAVE_SPEED:.0f} m/s")

    # Pre-build sensor position tensor (reused every batch)
    sensor_pos_tensor = torch.tensor(SENSOR_POS_M, dtype=torch.float32)  # (6, 2)

    # t_mean and t_std for de-normalizing arrival times back to seconds
    t_mean_tensor = torch.tensor(stats["t_mean"], dtype=torch.float32)   # (6,)
    t_std_tensor  = torch.tensor(stats["t_std"],  dtype=torch.float32)   # (6,)

    # ── Output dirs ───────────────────────────────────────────────────────────
    data_dir.mkdir(parents=True, exist_ok=True)
    MODELS.mkdir(parents=True, exist_ok=True)

    # ── Initial-loss calibration (Wu et al. 2023) ─────────────────────────────
    # Compute L_data_0 and L_phys_0 on the first batch so that relative weights
    # are scale-invariant: loss = (L_data / L_data_0) + λ * (L_phys / L_phys_0)
    # This ensures λ=0.1 means "physics contributes 10% relative to data",
    # regardless of the absolute magnitude of each term.
    n_train    = len(X_train)
    batch_size = args.batch_size

    model.eval()
    with torch.no_grad():
        Xb0 = X_train[:batch_size]
        Yb0 = Y_train[:batch_size]
        pred_b0   = model(Xb0)
        L_data_0  = F.mse_loss(pred_b0, Yb0).item() + 1e-8

        pred_xy_m0 = pred_b0 * PLATE_SIZE_M
        diffs0 = pred_xy_m0.unsqueeze(1) - sensor_pos_tensor.unsqueeze(0)
        dists0 = torch.sqrt((diffs0 ** 2).sum(dim=2).clamp(min=1e-8))
        t_hat_us0   = (dists0 / WAVE_SPEED) * US_SCALE
        t_hat_norm0 = (t_hat_us0 - t_mean_tensor) / t_std_tensor
        L_phys_0 = F.mse_loss(t_hat_norm0, Xb0).item() + 1e-8
    model.train()

    print(f"[INFO] Initial loss calibration: L_data_0={L_data_0:.6f}  "
          f"L_phys_0={L_phys_0:.6f}  ratio={L_phys_0/L_data_0:.1f}:1")
    print(f"[INFO] Normalized loss: (L_data/L_data_0) + λ*(L_phys/L_phys_0)  "
          f"→ physics contributes {args.lambda_helm*100:.0f}% relative weight")

    # ── Training loop ─────────────────────────────────────────────────────────
    history_rows = []   # (epoch, loss_total, loss_data, loss_physics, val_mae_mm)
    best_val_mae = float("inf")
    best_state   = None

    for epoch in range(1, args.epochs + 1):
        model.train()
        # Shuffle training data
        perm = torch.randperm(n_train)
        epoch_loss_total   = 0.0
        epoch_loss_data    = 0.0
        epoch_loss_physics = 0.0
        n_batches = 0

        for start in range(0, n_train, batch_size):
            idx_b = perm[start: start + batch_size]
            Xb, Yb = X_train[idx_b], Y_train[idx_b]

            # ── Data loss ────────────────────────────────────────────────────
            pred_b     = model(Xb)
            loss_data  = mse(pred_b, Yb)

            # ── Physics loss: true wave-equation residual ─────────────────────
            # pred_b is normalized [0,1]; denormalize to meters
            pred_xy_m = pred_b * PLATE_SIZE_M  # (batch, 2) in meters

            # Compute theoretical arrival times for each sensor
            # t̂_i = ||pred_source - S_i||_2 / wave_speed
            # sensor_pos_tensor: (6, 2) → broadcast over batch
            # pred_xy_m: (batch, 2) → unsqueeze to (batch, 1, 2)
            diffs  = pred_xy_m.unsqueeze(1) - sensor_pos_tensor.unsqueeze(0)  # (batch, 6, 2)
            dists  = torch.sqrt((diffs ** 2).sum(dim=2).clamp(min=1e-8))     # (batch, 6) in m

            # Convert to microseconds then standardize using the same normalization
            # used for the network inputs, so physics residual has comparable scale
            # to L_data (both O(1e-3) or lower in normalized space).
            t_hat_us     = (dists / WAVE_SPEED) * US_SCALE                    # (batch, 6) in μs
            t_hat_norm   = (t_hat_us - t_mean_tensor) / t_std_tensor          # normalized

            # t_inputs are already normalized arrival times (the network's input Xb)
            loss_phys  = F.mse_loss(t_hat_norm, Xb)

            # Normalized loss (Wu et al. 2023): scale-invariant relative weighting
            loss_total = (loss_data / L_data_0) + args.lambda_helm * (loss_phys / L_phys_0)

            optim.zero_grad()
            loss_total.backward()
            optim.step()

            epoch_loss_total   += loss_total.item()
            epoch_loss_data    += loss_data.item()
            epoch_loss_physics += loss_phys.item()
            n_batches += 1

        avg_total  = epoch_loss_total   / n_batches
        avg_data   = epoch_loss_data    / n_batches
        avg_phys   = epoch_loss_physics / n_batches

        # ── Validation MAE (in mm) ────────────────────────────────────────────
        model.eval()
        with torch.no_grad():
            pred_val    = model(X_test).numpy()
            pred_val_m  = denormalize_xy(pred_val)
            true_val_m  = xy_true[test_idx]
            errs_mm     = np.sqrt(((pred_val_m - true_val_m) ** 2).sum(axis=1)) * 1000.0
            val_mae_mm  = float(errs_mm.mean())

        history_rows.append((epoch, avg_total, avg_data, avg_phys, val_mae_mm))

        # ── Checkpoint ───────────────────────────────────────────────────────
        if epoch % CHECKPOINT_INTERVAL == 0:
            if val_mae_mm < best_val_mae:
                best_val_mae = val_mae_mm
                best_state   = {k: v.clone() for k, v in model.state_dict().items()}
                ckpt_path    = MODELS / "pinn_localization.pt"
                torch.save(best_state, ckpt_path)
                print(f"  [CKPT] Epoch {epoch:4d} — val_mae={val_mae_mm:.2f} mm → saved")

        # ── Progress print every 10% ──────────────────────────────────────────
        if epoch % max(1, args.epochs // 10) == 0 or epoch == 1:
            print(
                f"  Epoch {epoch:4d}/{args.epochs}  "
                f"loss={avg_total:.6f}  data={avg_data:.6f}  "
                f"phys={avg_phys:.6f}  val_mae={val_mae_mm:.2f} mm"
            )

    # ── Save final model (best checkpoint or last) ────────────────────────────
    model_path = MODELS / "pinn_localization.pt"
    if best_state is not None:
        torch.save(best_state, model_path)
        model.load_state_dict(best_state)
        print(f"\n[INFO] Best checkpoint restored (val_mae={best_val_mae:.2f} mm)")
    else:
        torch.save(model.state_dict(), model_path)
    print(f"     Saved model: {model_path}")

    return model, history_rows, X_test, Y_test, test_idx, xy_true, scenarios, torques, \
           normalize_t, denormalize_xy


# ── Output writers ─────────────────────────────────────────────────────────────

def save_training_history(history_rows, data_dir: Path):
    """Write training_history.csv (per-epoch loss breakdown)."""
    out_path = data_dir / "training_history.csv"
    header   = "epoch,loss_total,loss_data,loss_physics,val_mae_mm"
    lines    = [header]
    for epoch, lt, ld, lp, vm in history_rows:
        lines.append(f"{epoch},{lt:.8f},{ld:.8f},{lp:.8f},{vm:.4f}")
    try:
        with open(out_path, "w") as f:
            f.write("\n".join(lines) + "\n")
    except OSError as e:
        print(f"[ERROR] Cannot write {out_path}: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"     Written: {out_path}")
    return out_path


def save_localization_results(model, X_test_t, test_idx, xy_true,
                               scenarios, torques, denormalize_xy, data_dir: Path):
    """Write pinn_localization_results.csv with per-sample predictions."""
    torch, _ = _require_torch()

    model.eval()
    with torch.no_grad():
        pred_norm = model(X_test_t).numpy()
    pred_m    = denormalize_xy(pred_norm)
    true_m    = xy_true[test_idx]

    errs_mm = np.sqrt(((pred_m - true_m) ** 2).sum(axis=1)) * 1000.0

    out_path = data_dir / "pinn_localization_results.csv"
    header   = "source_x,source_y,pred_x,pred_y,error_mm,scenario,torque_loss_pct"
    lines    = [header]
    for i, gi in enumerate(test_idx):
        lines.append(
            f"{true_m[i,0]:.6f},{true_m[i,1]:.6f},"
            f"{pred_m[i,0]:.6f},{pred_m[i,1]:.6f},"
            f"{errs_mm[i]:.4f},"
            f"{scenarios[gi]},"
            f"{torques[gi]:.1f}"
        )
    try:
        with open(out_path, "w") as f:
            f.write("\n".join(lines) + "\n")
    except OSError as e:
        print(f"[ERROR] Cannot write {out_path}: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"     Written: {out_path}")
    return out_path, errs_mm, test_idx, scenarios


def compute_mae_by_scenario(errs_mm, test_idx, scenarios):
    """Compute mean absolute error (mm) per scenario from test set results."""
    sc_errors = {}
    for i, gi in enumerate(test_idx):
        sc = scenarios[gi]
        sc_errors.setdefault(sc, []).append(errs_mm[i])
    return {sc: float(np.mean(v)) for sc, v in sorted(sc_errors.items())}


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Train PINN for AE source localization (conference paper)"
    )
    parser.add_argument("--epochs",      type=int,   default=500,
                        help="Training epochs (default: 500)")
    parser.add_argument("--lambda-helm", "--lambda", type=float, default=0.1,
                        dest="lambda_helm",
                        help="Physics loss weight λ (default: 0.1)")
    parser.add_argument("--lr",          type=float, default=1e-3,
                        help="Adam learning rate (default: 1e-3)")
    parser.add_argument("--hidden",      type=int,   default=64,
                        help="Hidden layer width (default: 64)")
    parser.add_argument("--layers",      type=int,   default=4,
                        help="Number of hidden layers (default: 4)")
    parser.add_argument("--seed",        type=int,   default=42,
                        help="Random seed (default: 42)")
    parser.add_argument("--data-dir",    type=str,   default=str(PROCESSED),
                        dest="data_dir",
                        help=f"Data directory (default: {PROCESSED})")
    parser.add_argument("--batch-size",  type=int,   default=32,
                        dest="batch_size",
                        help="Mini-batch size (default: 32)")
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(" PINN Localization — AE Source on 300×300 mm Plate")
    print(f"{'='*60}\n")

    (model, history_rows, X_test_t, Y_test_t,
     test_idx, xy_true, scenarios, torques,
     normalize_t, denormalize_xy) = train(args)

    # ── Write outputs ─────────────────────────────────────────────────────────
    print("\n[OUTPUTS]")
    save_training_history(history_rows, Path(args.data_dir))
    out_path, errs_mm, test_idx_out, scenarios_out = save_localization_results(
        model, X_test_t, test_idx, xy_true, scenarios, torques,
        denormalize_xy, Path(args.data_dir)
    )

    # ── MAE by scenario ───────────────────────────────────────────────────────
    mae_by_sc = compute_mae_by_scenario(errs_mm, test_idx_out, scenarios_out)
    val_mae_global = float(errs_mm.mean())

    # Final epoch val_mae from history (last row)
    last_val_mae = history_rows[-1][4] if history_rows else 0.0

    print(f"\n[RESULTS] MAE by scenario:")
    for sc, mae in mae_by_sc.items():
        print(f"  {sc:<12}: {mae:.2f} mm")
    print(f"  {'global':<12}: {val_mae_global:.2f} mm  (test set)")
    print(f"  val_mae_last_epoch: {last_val_mae:.2f} mm")
    print(f"\n[OK] Training complete — {args.epochs} epochs, λ={args.lambda_helm}")
    print(f"     model saved: models/pinn_localization.pt")

    return mae_by_sc, val_mae_global


if __name__ == "__main__":
    main()
