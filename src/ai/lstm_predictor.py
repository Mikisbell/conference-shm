import os
import torch
import torch.nn as nn
import pandas as pd
import numpy as np
from torch.utils.data import DataLoader, TensorDataset
from pathlib import Path
from sklearn.preprocessing import MinMaxScaler
import pickle

# Definición del Cerebro Deep Learning
class DegradationLSTM(nn.Module):
    def __init__(self, input_size, hidden_size, num_layers, output_size=1):
        super(DegradationLSTM, self).__init__()
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        
        # Capa LSTM
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers, batch_first=True)
        # Capa de Dropout para Monte Carlo Inference
        self.dropout = nn.Dropout(p=0.20)
        # Capas Densas para Regresión (TTF)
        self.fc1 = nn.Linear(hidden_size, hidden_size // 2)
        self.relu = nn.ReLU()
        self.fc2 = nn.Linear(hidden_size // 2, output_size)
        
    def forward(self, x):
        h0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
        c0 = torch.zeros(self.num_layers, x.size(0), self.hidden_size).to(x.device)
        
        out, _ = self.lstm(x, (h0, c0))
        
        # Tomamos el último output de la secuencia LSTM
        out = out[:, -1, :] 
        out = self.dropout(out)
        
        # Regresión a un único valor (TTF en días)
        out = self.fc1(out)
        out = self.relu(out)
        out = self.dropout(out)
        out = self.fc2(out)
        return out

def prepare_data(csv_path, seq_length=30):
    """
    Convierte el Historial Longitudinal en Ventanas (Secuencias) para el LSTM
    Input Features: fn_hz, k_term, tmp_ext, tmp_int, hum
    Target: ttf_days
    """
    df = pd.read_csv(csv_path)
    features = ['fn_hz', 'k_term', 'tmp_ext', 'tmp_int', 'hum']
    
    # Escalar datos (Vital para Redes Neuronales)
    scaler_X = MinMaxScaler()
    df[features] = scaler_X.fit_transform(df[features])
    
    scaler_y = MinMaxScaler()
    df[['ttf_days']] = scaler_y.fit_transform(df[['ttf_days']])
    
    X, y = [], []
    
    # Agrupamos por Módulo Habitacional para no cruzar ventanas de distintas casas
    for module_id, group_df in df.groupby('module_id'):
        data_x = group_df[features].values
        data_y = group_df['ttf_days'].values
        
        for i in range(len(data_x) - seq_length):
            X.append(data_x[i:i + seq_length])
            y.append(data_y[i + seq_length])
            
    X_tensor = torch.tensor(np.array(X), dtype=torch.float32)
    y_tensor = torch.tensor(np.array(y), dtype=torch.float32).unsqueeze(1)
    
    # Guardar Scalers para Inferencia futura (Ej: LoRa)
    model_dir = Path("models/lstm")
    model_dir.mkdir(parents=True, exist_ok=True)
    with open(model_dir / 'scaler_X.pkl', 'wb') as f:
        pickle.dump(scaler_X, f)
    with open(model_dir / 'scaler_y.pkl', 'wb') as f:
        pickle.dump(scaler_y, f)
        
    return X_tensor, y_tensor

def train_lstm(csv_path="data/synthetic/cdw_degradation_history.csv", epochs=15, batch_size=256):
    print(f"🧠 [AI CORE] Preparando secuencias para entrenamiento LSTM...")
    if not Path(csv_path).exists():
        print(f"❌ Error: El dataset sintético {csv_path} no existe. Ejecuta primero generate_cdw_degradation.py")
        return
        
    X, y = prepare_data(csv_path, seq_length=30) # Miramos 30 días al pasado
    
    # Train/Test Split (80/20)
    split_idx = int(0.8 * len(X))
    train_dataset = TensorDataset(X[:split_idx], y[:split_idx])
    test_dataset = TensorDataset(X[split_idx:], y[split_idx:])
    
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False)
    
    # Configuración de Dispositivo
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model = DegradationLSTM(input_size=5, hidden_size=64, num_layers=2).to(device)
    
    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    
    print(f"🚀 [AI CORE] Iniciando Entrenamiento (Device: {device}) - {epochs} Épocas")
    print("-" * 50)
    
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
        
        # Validación
        model.eval()
        test_loss = 0.0
        with torch.no_grad():
            for batch_X, batch_y in test_loader:
                batch_X, batch_y = batch_X.to(device), batch_y.to(device)
                outputs = model(batch_X)
                loss = criterion(outputs, batch_y)
                test_loss += loss.item() * batch_X.size(0)
        test_loss /= len(test_loader.dataset)
        
        print(f"Época {epoch+1:02d}/{epochs} | Training Loss: {train_loss:.4f} | Validation Loss: {test_loss:.4f}")
        
    # Guardar Pesos (Modelo Físicamente Informado)
        model_path = Path("models/lstm/cdw_lstm_v1.pth")
    torch.save(model.state_dict(), model_path)
    print("\n✅ [AI CORE] Cerebro LSTM Entrenado y Sellado.")
    print(f"   Ruta: {model_path}")


def predict_ttf_with_uncertainty(model_path, x_tensor, scaler_y, n_passes=100) -> dict:
    """
    Inferencia con Monte Carlo Dropout para cuantificar incertidumbre epistémica.
    Realiza `n_passes` activando layers de dropout para generar una distribución predictiva.
    """
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model = DegradationLSTM(input_size=5, hidden_size=64, num_layers=2).to(device)
    model.load_state_dict(torch.load(model_path, map_location=device))
    
    # CRÍTICO: Model.train() mantiene Dropout ACTIVO durante test
    model.train()  
    
    x_tensor = x_tensor.to(device)
    predictions = []
    
    with torch.no_grad():
        for _ in range(n_passes):
            out = model(x_tensor)
            # Deshacer el escalado
            pred_real = scaler_y.inverse_transform(out.cpu().numpy())
            predictions.append(pred_real.flatten()[0])
            
    preds = np.array(predictions)
    mu  = np.mean(preds)
    std = np.std(preds)
    
    return {
        "ttf_mu": float(mu),
        "ttf_sigma": float(std),
        "ci_lower": float(mu - 1.96 * std), # 95% CI
        "ci_upper": float(mu + 1.96 * std),
        "n_passes": n_passes
    }

if __name__ == "__main__":
    train_lstm()
