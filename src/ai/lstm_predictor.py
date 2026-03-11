"""
LSTM Predictor — Entrenamiento e inferencia de red LSTM para prediccion de degradacion estructural.

Implementa DegradationLSTM (PyTorch), entrenamiento sobre ventanas deslizantes de series
temporales (fn_hz, k_term, tmp_ext, tmp_int, hum) y prediccion de Time-To-Failure con
incertidumbre epistemica via MC Dropout. Lee hiperparametros desde config/params.yaml (SSOT).

Pipeline: COMPUTE C4 (generacion de datos sinteticos) → entrenamiento → IMPLEMENT (resultados ML)
CLI: python3 src/ai/lstm_predictor.py
Depende de: data/synthetic/degradation_history.csv, config/params.yaml
Produce: models/lstm/lstm_v1.pth, models/lstm/scaler_X.pkl, models/lstm/scaler_y.pkl
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pickle
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.preprocessing import MinMaxScaler

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from config.paths import get_params_file

import yaml

# Standardized output paths (relative to project root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MODEL_DIR = PROJECT_ROOT / "models" / "lstm"
SYNTHETIC_DATA = PROJECT_ROOT / "data" / "synthetic" / "degradation_history.csv"

# Training hyperparameters (factory defaults)
SEQ_LENGTH = 30
HIDDEN_SIZE = 64
NUM_LAYERS = 2
DROPOUT = 0.20
FEATURES = ["fn_hz", "k_term", "tmp_ext", "tmp_int", "hum"]
TARGET = "ttf_days"


def _load_ssot() -> dict:
    with open(get_params_file(), "r") as f:
        return yaml.safe_load(f)


class DegradationLSTM(nn.Module):
    def __init__(self, input_size=len(FEATURES), hidden_size=HIDDEN_SIZE,
                 num_layers=NUM_LAYERS, output_size=1):
        super(DegradationLSTM, self).__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers

        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True)
        self.dropout = nn.Dropout(p=DROPOUT)
        self.fc1 = nn.Linear(hidden_size, hidden_size // 2)
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(hidden_size // 2, output_size)

    def forward(self, x):
        h0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
        c0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)

        out, _ = self.lstm(x, (h0, c0))
        out = out[:, -1, :]
        out = self.dropout(out)
        out = self.fc1(out)
        out = self.relu(out)
        out = self.dropout(out)
        out = self.fc2(out)
        return out


def prepare_data(csv_path, seq_length=SEQ_LENGTH):
    """
    Convert longitudinal history into sliding windows for LSTM.
    Input features: fn_hz, k_term, tmp_ext, tmp_int, hum
    Target: ttf_days
    """
    df = pd.read_csv(csv_path)

    scaler_X = MinMaxScaler()
    df[FEATURES] = scaler_X.fit_transform(df[FEATURES])

    scaler_y = MinMaxScaler()
    df[[TARGET]] = scaler_y.fit_transform(df[[TARGET]])

    X, y = [], []

    for module_id, group_df in df.groupby("module_id"):
        data_x = group_df[FEATURES].values
        data_y = group_df[TARGET].values

        for i in range(len(data_x) - seq_length):
            X.append(data_x[i : i + seq_length])
            y.append(data_y[i + seq_length])

    X_tensor = torch.tensor(np.array(X), dtype=torch.float32)
    y_tensor = torch.tensor(np.array(y), dtype=torch.float32).unsqueeze(1)

    # Save scalers for inference
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    with open(MODEL_DIR / "scaler_X.pkl", "wb") as f:
        pickle.dump(scaler_X, f)
    with open(MODEL_DIR / "scaler_y.pkl", "wb") as f:
        pickle.dump(scaler_y, f)

    return X_tensor, y_tensor


def train_lstm(csv_path=None, epochs=15, batch_size=256):
    if csv_path is None:
        csv_path = SYNTHETIC_DATA

    csv_path = Path(csv_path)
    if not csv_path.exists():
        print(f"[LSTM] ERROR: Dataset {csv_path} not found. "
              "Run: python tools/generate_degradation.py")
        return None

    cfg = _load_ssot()
    print(f"[LSTM] SSOT: m={cfg['structure']['mass_m']['value']}kg "
          f"k={cfg['structure']['stiffness_k']['value']}N/m "
          f"k_term={cfg['material']['thermal_conductivity']['value']}")

    print(f"[LSTM] Preparing sequences from {csv_path}...")
    X, y = prepare_data(csv_path, seq_length=SEQ_LENGTH)

    split_idx = int(0.8 * len(X))
    train_dataset = TensorDataset(X[:split_idx], y[:split_idx])
    test_dataset = TensorDataset(X[split_idx:], y[split_idx:])

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = DegradationLSTM().to(device)

    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)

    print(f"[LSTM] Training on {device} | {len(train_dataset)} train, "
          f"{len(test_dataset)} test | {epochs} epochs")

    for epoch in range(epochs):
        model.train()
        train_loss = 0.0
        for batch_X, batch_y in train_loader:
            batch_X, batch_y = batch_X.to(device), batch_y.to(device)
            optimizer.zero_grad()
            outputs = model(batch_X)
            loss = criterion(outputs, batch_y)
            loss.backward()
            optimizer.step()
            train_loss += loss.item() * batch_X.size(0)
        train_loss /= len(train_loader.dataset)

        model.eval()
        test_loss = 0.0
        with torch.no_grad():
            for batch_X, batch_y in test_loader:
                batch_X, batch_y = batch_X.to(device), batch_y.to(device)
                outputs = model(batch_X)
                loss = criterion(outputs, batch_y)
                test_loss += loss.item() * batch_X.size(0)
        test_loss /= len(test_loader.dataset)

        print(f"  Epoch {epoch + 1:02d}/{epochs} | "
              f"Train: {train_loss:.6f} | Val: {test_loss:.6f}")

    # Save model weights
    model_path = MODEL_DIR / "lstm_v1.pth"
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), model_path)
    print(f"[LSTM] Model saved: {model_path}")

    return model_path


def predict_ttf_with_uncertainty(model_path=None, x_tensor=None,
                                  scaler_y=None, n_passes=100) -> dict:
    """
    MC Dropout inference for epistemic uncertainty quantification.
    Runs n_passes with dropout active to generate predictive distribution.
    """
    if model_path is None:
        model_path = MODEL_DIR / "lstm_v1.pth"
    if scaler_y is None:
        with open(MODEL_DIR / "scaler_y.pkl", "rb") as f:
            scaler_y = pickle.load(f)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = DegradationLSTM().to(device)
    model.load_state_dict(torch.load(model_path, map_location=device))

    # CRITICAL: model.train() keeps Dropout ACTIVE during inference
    model.train()

    x_tensor = x_tensor.to(device)
    predictions = []

    with torch.no_grad():
        for _ in range(n_passes):
            out = model(x_tensor)
            pred_real = scaler_y.inverse_transform(out.cpu().numpy())
            predictions.append(pred_real.flatten()[0])

    preds = np.array(predictions)
    mu = float(np.mean(preds))
    std = float(np.std(preds))

    return {
        "ttf_mu": mu,
        "ttf_sigma": std,
        "ci_lower": mu - 1.96 * std,
        "ci_upper": mu + 1.96 * std,
        "n_passes": n_passes,
    }


if __name__ == "__main__":
    train_lstm()
