#!/usr/bin/env python3
"""
tools/research_director.py — Orquestador de Investigación Universal (EIU)
=============================================================================
Motor principal para automatizar la ejecución de campañas de investigación y
la generación de Papers Científicos (Q1-Q4). 

Flujo:
  1. Configura el tópico y cuartil objetivo.
  2. Ejecuta Cross Validation A/B (Concreto Nominal vs C&DW+Belico).
  3. Lanza el Scientific Narrator para redactar el Paper.
  
Uso:
  python3 tools/research_director.py --quartile Q2 --topic "Resiliencia ante humedad extrema"
"""

import argparse
import sys
import time
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.physics.cross_validation import CrossValidationEngine

def announce_research(quartile: str, topic: str, cycles: int):
    print("\n" + "="*70)
    print(f" 🎓 RESEARCH DIRECTOR: INICIANDO CAMPAÑA DE INVESTIGACIÓN")
    print("="*70)
    print(f"  📌 Status: Buscando publicación {quartile}")
    print(f"  📌 Temática: '{topic}'")
    print(f"  📌 Ciclos Estresantes: {cycles}")
    print(f"  📌 Novelty Central: Auditoría Criptográfica en Edge-AI SHM")
    print("="*70 + "\n")

def run_research(quartile: str, topic: str, cycles: int):
    announce_research(quartile, topic, cycles)
    
    # 1. Ajuste paramétrico (simulado por ahora, usar generate_params en el futuro)
    print("[1/3] ⚙️  Configurando Entorno SSOT (params.yaml)...")
    subprocess.run([sys.executable, "tools/generate_params.py"], cwd=str(ROOT))
    time.sleep(1)
    
    # 2. Validación Cruzada (Caso A vs Caso B)
    print("\n[2/3] 🔬 Ejecutando Motor de Validación Cruzada (A/B Test)...")
    cv_engine = CrossValidationEngine(cycles=cycles)
    results = cv_engine.execute_validation_suite()
    si_results = cv_engine.execute_sensitivity_report()
    results["sensitivity_index"] = si_results
    
    # Guardar temporalmente los resultados de la validación cruzada para el narrador
    import json
    cv_out = ROOT / "data" / "processed" / "cv_results.json"
    cv_out.parent.mkdir(parents=True, exist_ok=True)
    with open(cv_out, "w") as f:
        json.dump(results, f)
    
    # 2b. Cálculo Espectral (Sa vs T) — Norma E.030 / ASCE 7-22
    print("\n[2b/3] 📈 Calculando Espectro de Respuesta Sa(T, ζ=5%)...")
    try:
        from src.physics.peer_adapter import PeerAdapter
        from src.physics.spectral_engine import compute_spectral_response, generate_spectral_report
        import numpy as np
        
        pisco_at2 = ROOT / "data" / "external" / "peer_berkeley" / "PISCO_2007_ICA_EW.AT2"
        if pisco_at2.exists():
            adapter = PeerAdapter(target_frequency_hz=100.0)
            raw_dict = adapter.read_at2_file(pisco_at2)
            accel_raw = adapter.normalize_and_resample(raw_dict)
            dt_target = adapter.target_dt
            
            # Espectro del sismo crudo (antes del Guardian Angel)
            sa_raw = compute_spectral_response(accel_raw, dt_target)
            
            # Espectro del sismo filtrado (Guardian Angel: elimina picos por encima del PGA target)
            accel_filt = adapter.scale_to_pga(accel_raw, target_pga_g=0.45)
            sa_filt = compute_spectral_response(accel_filt, dt_target)
            
            # Encontrar periodo de mayor demanda espectral
            peak_idx = np.argmax(sa_raw["Sa"])
            T_dom = float(sa_raw["T"][peak_idx])
            Sa_max = float(sa_raw["Sa"][peak_idx])
            print(f"   ✅ Periodo Dominante T*={T_dom:.2f}s | Sa max={Sa_max:.3f}g (PGA {sa_raw['pga']:.3f}g)")
            
            results["spectral"] = {
                "T_dominant": T_dom,
                "Sa_max": Sa_max,
                "pga": sa_raw["pga"],
                "sa_raw_report": generate_spectral_report(sa_raw, sa_filt)
            }
            with open(cv_out, "w") as f:
                json.dump(results, f, default=lambda x: x.tolist() if hasattr(x, 'tolist') else x)
        else:
            print(f"   ⚠️ Sismo PEER no encontrado en {pisco_at2}. Ejecuta: python3 tools/fetch_benchmark.py")
    except Exception as spec_err:
        print(f"   ⚠️ Error en cálculo espectral (no crítico): {spec_err}")
        
    # 3. Redacción del Paper (Scientific Narrator)
    print("\n[3/3] 📝 Invocando al Scientific Narrator para redacción IMRaD...")
    
    # Pasamos las variables de entorno para que el Narrator sepa sobre qué escribir
    import os
    env = os.environ.copy()
    env["PAPER_TOPIC"] = topic
    env["PAPER_QUARTILE"] = quartile
    env["EXTERNAL_SOURCES"] = "['peer_berkeley', 'cismid_peru']"
    
    narrator_path = str(ROOT / "articles" / "scientific_narrator.py")
    subprocess.run([sys.executable, narrator_path], cwd=str(ROOT), env=env)
    
    print("\n" + "="*70)
    print(f" 🎉 INVESTIGACIÓN COMPLETADA. Borrador Q-Ranked generado.")
    print("="*70 + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EIU Research Director")
    parser.add_argument("--quartile", choices=["Q1", "Q2", "Q3", "Q4"], default="Q2", help="Cuartil objetivo (ej. Q1)")
    parser.add_argument("--topic", type=str, required=True, help="Temática central de la investigación")
    parser.add_argument("--cycles", type=int, default=500, help="Semanas/Ciclos a simular")
    
    args = parser.parse_args()
    run_research(args.quartile, args.topic, args.cycles)
