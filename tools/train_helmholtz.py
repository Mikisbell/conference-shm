#!/usr/bin/env python3
"""
train_helmholtz.py — Helmholtz-Informed Learning for structural damage identification
======================================================================================
Implements a Physics-Informed Neural Network (PINN) with Helmholtz regularization.

Physics: ∇²u + k²u = 0 (Helmholtz equation — governs AE wave propagation in structure)
Loss: L_total = L_data (cross-entropy) + λ * L_helmholtz (physics residual)
L_helmholtz = ||Δh + k²·h||² where h = hidden layer activations, Δ = discrete Laplacian

Usage:
  python3 tools/train_helmholtz.py
  python3 tools/train_helmholtz.py --epochs 300 --lambda-helm 0.1 --k-wave 2.5
  python3 tools/train_helmholtz.py --dry-run
  python3 tools/train_helmholtz.py --quartile q2 --epochs 500

Outputs:
  data/processed/training_history.csv
  data/processed/damage_predictions.csv
  data/processed/cv_results.json  (enriched with Helmholtz metrics)
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"

DAMAGE_LABELS = ["intact", "damage_5pct", "damage_15pct", "damage_30pct"]


# ── SSOT params ───────────────────────────────────────────────────────────────

def load_params():
    """Read config/params.yaml and extract required physics parameters.

    k_wave default derived from λ ≈ floor height (structure.floor_height_m):
      k = 2π / λ. Returns None for k_wave_default if floor_height_m absent
      (caller must provide --k-wave or exit).
    """
    params_path = ROOT / "config" / "params.yaml"
    try:
        import yaml as _yaml
        cfg = _yaml.safe_load(params_path.read_text(encoding="utf-8")) or {}
    except FileNotFoundError:
        print(f"[ERROR] config/params.yaml not found — run: python3 tools/generate_params.py",
              file=sys.stderr)
        sys.exit(1)
    except _yaml.YAMLError as e:
        print(f"[ERROR] config/params.yaml malformed: {e}", file=sys.stderr)
        sys.exit(1)
    except OSError as e:
        print(f"[ERROR] config/params.yaml read error: {e}", file=sys.stderr)
        sys.exit(1)

    _req = {
        "material.elastic_modulus_E": cfg.get("material", {}).get("elastic_modulus_E", {}).get("value"),
        "damping.ratio_xi":           cfg.get("damping",  {}).get("ratio_xi",          {}).get("value"),
        "structure.mass_m":           cfg.get("structure",{}).get("mass_m",             {}).get("value"),
    }
    for _key, _val in _req.items():
        if _val is None:
            print(f"[ERROR] SSOT missing key '{_key}' in config/params.yaml", file=sys.stderr)
            sys.exit(1)

    floor_height_raw = cfg.get("structure", {}).get("floor_height_m", {}).get("value")
    k_wave_default = (2.0 * np.pi / float(floor_height_raw)) if floor_height_raw is not None else None

    return {
        "E":             float(_req["material.elastic_modulus_E"]),
        "xi":            float(_req["damping.ratio_xi"]),
        "mass":          float(_req["structure.mass_m"]),
        "k_wave_default": k_wave_default,
    }


# ── Data loading / generation ─────────────────────────────────────────────────

def load_or_generate_data(processed_dir, n_synthetic=200):
    """Load simulation CSVs from data/processed/ or generate synthetic fallback.

    Label mapping from filename keywords:
      intact / sano       → 0
      damage_5 / leve     → 1
      damage_15 / moderado→ 2
      damage_30 / critico → 3

    Returns
    -------
    X            : ndarray (n_samples, n_features)
    y            : ndarray (n_samples,)  int class labels
    is_synthetic : bool
    feature_names: list[str]
    """
    csv_files = sorted(processed_dir.glob("*.csv"))
    # Exclude output files this script itself writes
    excluded = {
        "training_history.csv",
        "damage_predictions.csv",
        "latest_abort.csv",
        "ml_training_set.csv",
        "statistics_report.csv",
    }
    csv_files = [f for f in csv_files if f.name not in excluded]

    X_parts, y_parts = [], []
    feature_names = None

    for csv_path in csv_files:
        try:
            data = np.genfromtxt(csv_path, delimiter=",", names=True, deletechars="")
            if data.size == 0:
                continue
            cols = list(data.dtype.names)
            # Select numeric columns only (skip string-type or object columns)
            numeric_cols = []
            for c in cols:
                try:
                    vals = data[c].astype(float)
                    if not np.all(np.isnan(vals)):
                        numeric_cols.append(c)
                except (ValueError, TypeError):
                    pass
            if not numeric_cols:
                continue

            # Infer label from filename
            name = csv_path.stem.lower()
            if any(k in name for k in ("intact", "sano", "undamaged")):
                label = 0
            elif any(k in name for k in ("damage_5", "leve", "5pct", "minor")):
                label = 1
            elif any(k in name for k in ("damage_15", "moderado", "15pct", "moderate")):
                label = 2
            elif any(k in name for k in ("damage_30", "critico", "30pct", "severe", "critical")):
                label = 3
            else:
                # Unknown label — use as class 1 (damage) if 'damage'/'dano' in name
                label = 1 if any(k in name for k in ("damage", "dano", "damaged")) else 0

            rows = np.column_stack([data[c].astype(float) for c in numeric_cols])
            rows = rows[~np.any(np.isnan(rows), axis=1)]
            if rows.ndim == 1:
                rows = rows.reshape(1, -1)
            if rows.shape[0] == 0:
                continue

            if feature_names is None:
                feature_names = numeric_cols
            else:
                # Align columns: use only intersection of known features
                if numeric_cols != feature_names:
                    continue  # skip incompatible file

            X_parts.append(rows)
            y_parts.append(np.full(rows.shape[0], label, dtype=int))

        except (OSError, ValueError, KeyError, TypeError) as e:
            print(f"  [SKIP] {csv_path.name}: {e}", file=sys.stderr)
            continue

    if X_parts:
        X = np.vstack(X_parts)
        y = np.concatenate(y_parts)
        return X, y, False, feature_names

    # ── Synthetic fallback ────────────────────────────────────────────────────
    print(
        "[WARN] SYNTHETIC DATA — replace with real simulation outputs from COMPUTE C2",
        file=sys.stderr,
    )
    rng = np.random.default_rng(42)
    n_per_class = n_synthetic // 4
    n_features = 8
    feature_names = [
        "displacement", "acceleration", "velocity",
        "peak_drift", "residual_drift", "spectral_accel",
        "energy_dissipated", "frequency_shift",
    ]

    X_parts, y_parts = [], []
    # Gaussian clusters with increasing separation per damage level
    centers = [
        np.zeros(n_features),
        np.array([0.5, 0.3, 0.2, 0.4, 0.1, -0.2, 0.3, -0.5]),
        np.array([1.2, 0.8, 0.6, 1.0, 0.4, -0.5, 0.7, -1.2]),
        np.array([2.5, 1.8, 1.5, 2.2, 1.0, -1.0, 1.5, -2.5]),
    ]
    scales = [0.3, 0.4, 0.5, 0.6]

    for cls_idx, (center, scale) in enumerate(zip(centers, scales)):
        samples = rng.normal(loc=center, scale=scale, size=(n_per_class, n_features))
        X_parts.append(samples)
        y_parts.append(np.full(n_per_class, cls_idx, dtype=int))

    X = np.vstack(X_parts)
    y = np.concatenate(y_parts)
    return X, y, True, feature_names


# ── HelmholtzMLP ──────────────────────────────────────────────────────────────

class HelmholtzMLP:
    """Multi-layer perceptron with Helmholtz physics regularization.

    Architecture: Linear → ReLU → Linear → ReLU → Linear → Softmax
    Loss = CrossEntropy(data) + λ * HelmholtzResidual(hidden_activations)

    The Helmholtz term penalises activations that do not satisfy the
    1D discrete approximation of ∇²h + k²h = 0, encouraging the network
    to learn wave-consistent internal representations.
    """

    def __init__(self, n_features, n_classes=4, hidden=None, k_wave=2.5, lambda_helm=0.1):
        if hidden is None:
            hidden = [64, 32]
        self.n_features = n_features
        self.n_classes = n_classes
        self.hidden = hidden
        self.k_wave = k_wave
        self.lambda_helm = lambda_helm

        # He initialisation: W ~ N(0, sqrt(2 / fan_in))
        rng = np.random.default_rng(0)
        layer_sizes = [n_features] + hidden + [n_classes]
        self.weights = []
        self.biases = []
        for fan_in, fan_out in zip(layer_sizes[:-1], layer_sizes[1:]):
            std = np.sqrt(2.0 / fan_in)
            self.weights.append(rng.normal(0.0, std, size=(fan_in, fan_out)))
            self.biases.append(np.zeros(fan_out))

    # ── Activations ──────────────────────────────────────────────────────────

    @staticmethod
    def _relu(x):
        return np.maximum(0.0, x)

    @staticmethod
    def _softmax(x):
        # Numerically stable: subtract row-wise max
        shifted = x - x.max(axis=1, keepdims=True)
        exp_x = np.exp(shifted)
        return exp_x / exp_x.sum(axis=1, keepdims=True)

    # ── Helmholtz physics ─────────────────────────────────────────────────────

    def _discrete_laplacian(self, h):
        """Discrete 1D Laplacian along the feature axis.

        Δh[i] = h[i-1] - 2*h[i] + h[i+1]
        Boundary: symmetric padding (reflect).

        Parameters
        ----------
        h : ndarray (batch, n_hidden)

        Returns
        -------
        lap : ndarray (batch, n_hidden)
        """
        # Symmetric padding: prepend col[1] and append col[-2]
        h_pad = np.concatenate([h[:, 1:2], h, h[:, -2:-1]], axis=1)
        lap = h_pad[:, :-2] - 2.0 * h_pad[:, 1:-1] + h_pad[:, 2:]
        return lap

    def _helmholtz_residual(self, h):
        """Mean squared Helmholtz residual R = ||Δh + k²·h||².

        Averaged over batch and feature dimensions.

        Parameters
        ----------
        h : ndarray (batch, n_hidden)  — first hidden layer activations

        Returns
        -------
        scalar float
        """
        lap = self._discrete_laplacian(h)
        residual = lap + self.k_wave ** 2 * h
        return float(np.mean(residual ** 2))

    # ── Forward pass ──────────────────────────────────────────────────────────

    def forward(self, X):
        """Forward pass through the network.

        Returns
        -------
        probs             : ndarray (batch, n_classes) — softmax probabilities
        hidden_layer1_act : ndarray (batch, hidden[0]) — first hidden activations
        """
        hidden_activations = []
        a = X
        for i, (W, b) in enumerate(zip(self.weights, self.biases)):
            z = a @ W + b
            if i < len(self.weights) - 1:
                a = self._relu(z)
                hidden_activations.append(a)
            else:
                probs = self._softmax(z)
        # Return first hidden layer activations for Helmholtz term
        h1 = hidden_activations[0] if hidden_activations else np.zeros((X.shape[0], 1))
        return probs, h1

    # ── Loss functions ────────────────────────────────────────────────────────

    @staticmethod
    def _cross_entropy(probs, y_onehot):
        """Cross-entropy loss with clipping for numerical stability."""
        clipped = np.clip(probs, 1e-12, 1.0 - 1e-12)
        return -float(np.mean(np.sum(y_onehot * np.log(clipped), axis=1)))

    # ── Backpropagation ───────────────────────────────────────────────────────

    def _backprop(self, X, y_onehot, probs, hidden, lr):
        """Mini-batch SGD step with Helmholtz regularisation gradient.

        The Helmholtz residual R = ||Δh + k²h||² is treated as a penalty on
        the first hidden layer activations.  Its gradient with respect to
        those activations flows back through the hidden → output weights.

        dR/dh = 2*(Δh + k²h) * (Δ1 + k²)
        where Δ1 is the second-difference operator applied to a 1-vector
        (approximated as the identity for the regularisation gradient).
        """
        batch_size = X.shape[0]

        # ── Forward again to collect all pre-activation / activation values ──
        activations = [X]
        pre_activations = []
        a = X
        for i, (W, b) in enumerate(zip(self.weights, self.biases)):
            z = a @ W + b
            pre_activations.append(z)
            if i < len(self.weights) - 1:
                a = self._relu(z)
            else:
                a = self._softmax(z)
            activations.append(a)

        probs_fwd = activations[-1]

        # ── Output layer delta (cross-entropy + softmax combined gradient) ───
        delta = (probs_fwd - y_onehot) / batch_size  # (batch, n_classes)

        grads_W = [None] * len(self.weights)
        grads_b = [None] * len(self.biases)

        for i in reversed(range(len(self.weights))):
            grads_W[i] = activations[i].T @ delta
            grads_b[i] = delta.sum(axis=0)

            if i > 0:
                delta = delta @ self.weights[i].T
                # ReLU gradient
                delta = delta * (pre_activations[i - 1] > 0).astype(float)

                # ── Helmholtz regularisation gradient (first hidden layer) ───
                if i == 1:
                    h1 = activations[1]                     # (batch, hidden[0])
                    lap_h1 = self._discrete_laplacian(h1)
                    helm_grad = (
                        2.0 * (lap_h1 + self.k_wave ** 2 * h1)
                        * (1.0 + self.k_wave ** 2)           # ∂(Δ·+k²·)/∂h ≈ (k²+1) scalar approx
                        / batch_size
                    )
                    delta = delta + self.lambda_helm * helm_grad

        # ── Parameter update ──────────────────────────────────────────────────
        for i in range(len(self.weights)):
            self.weights[i] -= lr * grads_W[i]
            self.biases[i] -= lr * grads_b[i]

    # ── Training loop ─────────────────────────────────────────────────────────

    def fit(self, X_train, y_train, X_val, y_val,
            epochs=200, lr=0.01, batch_size=32):
        """Mini-batch SGD training.

        Returns
        -------
        history : dict with lists:
            epoch, train_loss, val_loss, train_acc, val_acc, helmholtz_residual
        """
        n_classes = self.n_classes
        n_train = X_train.shape[0]
        rng = np.random.default_rng(42)

        history = {
            "epoch": [],
            "train_loss": [],
            "val_loss": [],
            "train_acc": [],
            "val_acc": [],
            "helmholtz_residual": [],
        }

        def to_onehot(y):
            oh = np.zeros((len(y), n_classes))
            oh[np.arange(len(y)), y] = 1.0
            return oh

        y_val_oh = to_onehot(y_val)

        for epoch in range(1, epochs + 1):
            # Shuffle
            idx = rng.permutation(n_train)
            X_shuf, y_shuf = X_train[idx], y_train[idx]

            # Mini-batches
            for start in range(0, n_train, batch_size):
                Xb = X_shuf[start: start + batch_size]
                yb = y_shuf[start: start + batch_size]
                yb_oh = to_onehot(yb)
                probs_b, hidden_b = self.forward(Xb)
                self._backprop(Xb, yb_oh, probs_b, hidden_b, lr)

            # ── Epoch metrics ─────────────────────────────────────────────────
            probs_tr, h_tr = self.forward(X_train)
            y_tr_oh = to_onehot(y_train)
            train_loss = self._cross_entropy(probs_tr, y_tr_oh)
            train_acc = float(np.mean(np.argmax(probs_tr, axis=1) == y_train))
            helm_res = self._helmholtz_residual(h_tr)

            probs_v, _ = self.forward(X_val)
            val_loss = self._cross_entropy(probs_v, y_val_oh)
            val_acc = float(np.mean(np.argmax(probs_v, axis=1) == y_val))

            history["epoch"].append(epoch)
            history["train_loss"].append(train_loss)
            history["val_loss"].append(val_loss)
            history["train_acc"].append(train_acc)
            history["val_acc"].append(val_acc)
            history["helmholtz_residual"].append(helm_res)

            if epoch % max(1, epochs // 10) == 0 or epoch == 1:
                print(
                    f"  Epoch {epoch:4d}/{epochs}  "
                    f"loss={train_loss:.4f}  val_loss={val_loss:.4f}  "
                    f"val_acc={val_acc:.4f}  helm_res={helm_res:.6f}"
                )

        return history

    # ── Inference ─────────────────────────────────────────────────────────────

    def predict(self, X):
        """Run inference.

        Returns
        -------
        predicted_labels : ndarray (n,) int
        confidences      : ndarray (n,) float — max softmax probability
        """
        probs, _ = self.forward(X)
        predicted_labels = np.argmax(probs, axis=1)
        confidences = probs[np.arange(len(probs)), predicted_labels]
        return predicted_labels, confidences


# ── Metrics ───────────────────────────────────────────────────────────────────

def compute_metrics(y_true, y_pred, confidences):
    """Compute classification metrics using sklearn.

    localization_error_m: proxy metric — |true_class - pred_class| * 0.5 m/level

    Returns
    -------
    dict with: precision, recall, f1, accuracy, localization_error_m, mean_confidence
    """
    try:
        from sklearn.metrics import (
            accuracy_score,
            f1_score,
            precision_score,
            recall_score,
        )
    except ImportError:
        print("[ERROR] scikit-learn not installed. Run: pip install scikit-learn", file=sys.stderr)
        sys.exit(1)

    precision = float(precision_score(y_true, y_pred, average="weighted", zero_division=0))
    recall = float(recall_score(y_true, y_pred, average="weighted", zero_division=0))
    f1 = float(f1_score(y_true, y_pred, average="weighted", zero_division=0))
    accuracy = float(accuracy_score(y_true, y_pred))
    loc_error = float(np.mean(np.abs(y_true - y_pred)) * 0.5)
    mean_conf = float(np.mean(confidences))

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "accuracy": accuracy,
        "localization_error_m": loc_error,
        "mean_confidence": mean_conf,
    }


# ── Output writers ────────────────────────────────────────────────────────────

def save_training_history(history, processed_dir):
    """Write training_history.csv with per-epoch metrics."""
    out_path = processed_dir / "training_history.csv"
    header = "epoch,train_loss,val_loss,train_acc,val_acc,helmholtz_residual"
    rows = zip(
        history["epoch"],
        history["train_loss"],
        history["val_loss"],
        history["train_acc"],
        history["val_acc"],
        history["helmholtz_residual"],
    )
    lines = [header]
    for r in rows:
        lines.append(",".join(f"{v:.6f}" if isinstance(v, float) else str(v) for v in r))
    try:
        with open(out_path, "w") as f:
            f.write("\n".join(lines) + "\n")
    except OSError as e:
        print(f"[ERROR] Cannot write {out_path}: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"     Written: {out_path}")


def save_damage_predictions(X_test, y_test, y_pred, confidences, processed_dir):
    """Write damage_predictions.csv with per-sample results."""
    out_path = processed_dir / "damage_predictions.csv"
    header = "sample_id,true_label,predicted_label,confidence,localization_error_m"
    lines = [header]
    for i, (yt, yp, conf) in enumerate(zip(y_test, y_pred, confidences)):
        loc_err = abs(int(yt) - int(yp)) * 0.5
        lines.append(f"{i},{int(yt)},{int(yp)},{conf:.6f},{loc_err:.4f}")
    try:
        with open(out_path, "w") as f:
            f.write("\n".join(lines) + "\n")
    except OSError as e:
        print(f"[ERROR] Cannot write {out_path}: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"     Written: {out_path}")


def save_cv_results(metrics, args, is_synthetic, n_samples, n_features, processed_dir):
    """Enrich (or create) cv_results.json with Helmholtz training metrics.

    Existing keys unrelated to Helmholtz are preserved.
    """
    cv_path = processed_dir / "cv_results.json"

    # Load existing data if present
    existing = {}
    if cv_path.exists():
        try:
            with open(cv_path) as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError):
            existing = {}

    k_wave_val = getattr(args, "k_wave", 2.5)
    lambda_helm_val = getattr(args, "lambda_helm", 0.1)
    epochs_val = getattr(args, "epochs", 200)

    helmholtz_block = {
        "precision": metrics["precision"],
        "recall": metrics["recall"],
        "f1": metrics["f1"],
        "accuracy": metrics["accuracy"],
        "localization_error_m": metrics["localization_error_m"],
        "mean_confidence": metrics["mean_confidence"],
        "n_samples": n_samples,
        "n_features": n_features,
        "lambda_helmholtz": lambda_helm_val,
        "k_wave": k_wave_val,
        "epochs_run": epochs_val,
        "is_synthetic": is_synthetic,
        "is_template_demo": is_synthetic,
        "compute_date": datetime.now(timezone.utc).isoformat(),
    }

    # Merge: Helmholtz fields are injected at top level;
    # existing keys outside this set are untouched.
    merged = {**existing, **helmholtz_block}

    try:
        with open(cv_path, "w") as f:
            json.dump(merged, f, indent=2)
    except OSError as e:
        print(f"[ERROR] Cannot write {cv_path}: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"     Written: {cv_path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Train a Helmholtz-Informed MLP for structural damage identification"
    )
    parser.add_argument("--epochs", type=int, default=200,
                        help="Training epochs (default: 200)")
    parser.add_argument("--lambda-helm", type=float, default=0.1,
                        dest="lambda_helm",
                        help="Helmholtz regularisation weight λ (default: 0.1)")
    parser.add_argument("--k-wave", type=float, default=None,
                        dest="k_wave",
                        help="Wave number k [rad/m] (default: derived from SSOT floor height)")
    parser.add_argument("--quartile", default="conference",
                        choices=["conference", "q4", "q3", "q2", "q1"],
                        help="Paper quartile context (informational, default: conference)")
    parser.add_argument("--lr", type=float, default=0.01,
                        help="Learning rate (default: 0.01)")
    parser.add_argument("--batch-size", type=int, default=32,
                        dest="batch_size",
                        help="Mini-batch size (default: 32)")
    parser.add_argument("--dry-run", action="store_true",
                        dest="dry_run",
                        help="Print plan without training or writing files")
    args = parser.parse_args()

    # ── Load SSOT params ──────────────────────────────────────────────────────
    params = load_params()
    if args.k_wave is not None:
        k_wave = args.k_wave
    elif params["k_wave_default"] is not None:
        k_wave = params["k_wave_default"]
    else:
        print("[ERROR] structure.floor_height_m not in SSOT and --k-wave not provided.",
              file=sys.stderr)
        sys.exit(1)
    args.k_wave = k_wave  # store effective value for save_cv_results

    # ── Load or generate data ─────────────────────────────────────────────────
    X, y, is_synthetic, feature_names = load_or_generate_data(PROCESSED)
    n_samples, n_features = X.shape

    print(f"[INFO] Dataset: {n_samples} samples, {n_features} features, "
          f"{len(np.unique(y))} classes")
    print(f"[INFO] Physics: k={k_wave:.4f} rad/m, λ_helm={args.lambda_helm}")
    print(f"[INFO] Training: {args.epochs} epochs, lr={args.lr}, batch={args.batch_size}")
    if is_synthetic:
        print("[WARN] Using SYNTHETIC data — run COMPUTE C2 to generate real outputs.")

    if args.dry_run:
        print("\n[DRY-RUN] Would train HelmholtzMLP for "
              f"{args.epochs} epochs on {n_samples} samples")
        print("[DRY-RUN] Architecture: "
              f"[{n_features}] → [64] → [32] → [{len(DAMAGE_LABELS)}]")
        print("[DRY-RUN] Outputs: training_history.csv, "
              "damage_predictions.csv, cv_results.json")
        return

    # ── Train / val / test split: 60 / 20 / 20 ───────────────────────────────
    try:
        from sklearn.model_selection import train_test_split
        from sklearn.preprocessing import StandardScaler
    except ImportError:
        print("[ERROR] scikit-learn not installed. Run: pip install scikit-learn",
              file=sys.stderr)
        sys.exit(1)

    X_tv, X_test, y_tv, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y if len(np.unique(y)) > 1 else None
    )
    X_train, X_val, y_train, y_val = train_test_split(
        X_tv, y_tv, test_size=0.25, random_state=42,
        stratify=y_tv if len(np.unique(y_tv)) > 1 else None
    )
    # 0.25 of 0.80 = 0.20 of total → 60 / 20 / 20 split

    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_val = scaler.transform(X_val)
    X_test = scaler.transform(X_test)

    print(f"[INFO] Split: train={len(X_train)}, val={len(X_val)}, test={len(X_test)}")

    # ── Build and train model ─────────────────────────────────────────────────
    model = HelmholtzMLP(
        n_features=n_features,
        n_classes=len(DAMAGE_LABELS),
        hidden=[64, 32],
        k_wave=k_wave,
        lambda_helm=args.lambda_helm,
    )

    print("\n[TRAIN] Starting HelmholtzMLP training ...")
    history = model.fit(
        X_train, y_train,
        X_val, y_val,
        epochs=args.epochs,
        lr=args.lr,
        batch_size=args.batch_size,
    )

    # ── Evaluate on test set ──────────────────────────────────────────────────
    y_pred, confidences = model.predict(X_test)
    metrics = compute_metrics(y_test, y_pred, confidences)

    # ── Write outputs ─────────────────────────────────────────────────────────
    try:
        PROCESSED.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"[ERROR] Cannot create data/processed/: {e}", file=sys.stderr)
        sys.exit(1)
    save_training_history(history, PROCESSED)
    save_damage_predictions(X_test, y_test, y_pred, confidences, PROCESSED)
    save_cv_results(metrics, args, is_synthetic, n_samples, n_features, PROCESSED)

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n[OK] HelmholtzMLP trained — {args.epochs} epochs")
    print(f"     F1: {metrics['f1']:.4f} | Accuracy: {metrics['accuracy']:.4f}")
    print(f"     Precision: {metrics['precision']:.4f} | "
          f"Recall: {metrics['recall']:.4f}")
    print(f"     Localization error: {metrics['localization_error_m']:.4f} m")
    print(f"     Helmholtz λ={args.lambda_helm}, k={k_wave:.3f} rad/m")
    print(f"     Outputs: training_history.csv, damage_predictions.csv, cv_results.json")
    if is_synthetic:
        print("[WARN] Results based on SYNTHETIC data. "
              "Run COMPUTE C2 for real outputs.")


if __name__ == "__main__":
    main()
