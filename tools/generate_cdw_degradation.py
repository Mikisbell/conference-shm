import argparse
import numpy as np
import pandas as pd
from pathlib import Path

# Configuración del Gemelo Físico (Propiedades Iniciales SSOT)
INITIAL_FN = 8.0               # Hz (Frecuencia Natural de la Estructura Sano)
INITIAL_K_TERM = 0.51          # W/m·K (Conductividad Térmica C&DW)
CRITICAL_K_TERM = 0.61         # Umbral de falla (Fisuras + Humedad suben conductividad en un 20%)
CRITICAL_FN = 5.6              # Umbral de fatiga (Caída del 30% Fn)

# Parámetros del Entorno (Estocástico)
MONTHS_MAX = 120               # Simulación de 10 años (120 meses)
SAMPLES_PER_MONTH = 30         # "Mediciones" consolidadas por mes

def simulate_cdw_module(module_id, base_damage_rate):
    """
    Simula la vida de un módulo habitacional de C&DW.
    La degradación no es lineal. Usamos Random Walk (Proceso de Wiener) 
    con deriva negativa para 'Fn' y deriva positiva para 'K_term'.
    """
    time_series = []
    
    current_fn = INITIAL_FN
    current_k = INITIAL_K_TERM
    
    # Cada módulo tiene un "defecto de fábrica" invisible (Variabilidad del 75% Reciclado)
    # Algunos módulos nacerán más sanos que otros y resistirán mejor.
    module_resilience = np.random.normal(1.0, 0.15) 
    
    for month in range(1, MONTHS_MAX + 1):
        for day in range(1, SAMPLES_PER_MONTH + 1):
            tiempo_total_dias = (month - 1) * SAMPLES_PER_MONTH + day
            
            temp_ext = 25.0 + 10.0 * np.sin(2 * np.pi * tiempo_total_dias / 365.0) + np.random.normal(0, 2)
            temp_int = 22.0 + 2.0 * np.sin(2 * np.pi * tiempo_total_dias / 365.0) + np.random.normal(0, 0.5)
            humedad  = 60.0 + 20.0 * np.sin(2 * np.pi * tiempo_total_dias / 365.0 + np.pi/2) + np.random.normal(0, 5)
            
            stress_factor = (temp_ext / 30.0) * (humedad / 80.0) 
            
            fn_drop = np.random.exponential(base_damage_rate * stress_factor / module_resilience)
            current_fn -= fn_drop
            
            k_rise = np.random.exponential((base_damage_rate * 0.05) * stress_factor / module_resilience)
            current_k += k_rise
            
            time_series.append({
                "module_id": module_id,
                "month": month,
                "day": day,
                "fn_hz": current_fn,
                "k_term": current_k,
                "tmp_ext": temp_ext,
                "tmp_int": temp_int,
                "hum": humedad,
                "state": "FAILED" if current_fn < CRITICAL_FN or current_k > CRITICAL_K_TERM else "OK"
            })
            
            if current_fn < CRITICAL_FN or current_k > CRITICAL_K_TERM:
                break
                
        if current_fn < CRITICAL_FN or current_k > CRITICAL_K_TERM:
            break
            
    df = pd.DataFrame(time_series)
    
    total_life_days = len(df)
    # TTF real en días: Se calcula inversamente (Vida total - día actual)
    df["ttf_days"] = total_life_days - np.arange(1, total_life_days + 1)
    
    return df

def generate_dataset(num_modules, output_path):
    print(f"🏭 Iniciando Planta Emuladora de Concreto Reciclado C&DW...")
    print(f"   Modulo Objetivo: {num_modules} casas")
    print(f"   Umbral Critico Termico: > {CRITICAL_K_TERM} W/m·K")
    print(f"   Umbral Critico Rigid.:  < {CRITICAL_FN} Hz")
    
    all_data = []
    
    for i in range(1, num_modules + 1):
        # La tasa de daño base influye en si el módulo dura 1 año o 10 años.
        # Asumimos que los diseños están pensados para durar ~5 años (C&DW crudo en clima duro)
        base_rate = np.random.uniform(0.001, 0.005) 
        
        df_module = simulate_cdw_module(f"MOD-{i:04d}", base_rate)
        all_data.append(df_module)
        
        if i % 100 == 0:
            print(f"   Simulados {i}/{num_modules} módulos...")
            
    final_df = pd.concat(all_data, ignore_index=True)
    
    OUTPUT_FILE = Path(output_path)
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    final_df.to_csv(OUTPUT_FILE, index=False)
    
    print(f"\n✅ Dataset Sintético Terminado.")
    print(f"   Total Muestras (Días de Vida Simulados): {len(final_df)}")
    print(f"   Guardado en: {OUTPUT_FILE}")
    print(f"   Módulo con Vida Más Corta: {final_df.groupby('module_id')['ttf_days'].max().min()} días.")
    print(f"   Módulo con Vida Más Larga: {final_df.groupby('module_id')['ttf_days'].max().max()} días.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Emulador de Degradación Reciclada C&DW - LSTM Feeder")
    parser.add_argument("--modules", type=int, default=1000, help="Número de Módulos Habitacionales a simular.")
    parser.add_argument("--out", type=str, default="data/synthetic/cdw_degradation_history.csv")
    args = parser.parse_args()
    
    generate_dataset(args.modules, args.out)
