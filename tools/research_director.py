#!/usr/bin/env python3
"""
tools/research_director.py — Orquestador de Investigación Universal (EIU)
=============================================================================
Motor principal para automatizar la ejecución de campañas de investigación y
la generación de Papers Científicos (Q1-Q4). 

Flujo:
  1. Configura el tópico y cuartil objetivo.
  2. Ejecuta Cross Validation A/B y campana espectral parametrica.
  3. Lanza el Scientific Narrator para redactar el Paper.
  
Uso:
  python3 tools/research_director.py --quartile Q2 --topic "Digital Twin framework for SHM"
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
    
    # Guardar temporalmente los resultados de la validación cruzada para el narrador
    import json
    cv_out = ROOT / "data" / "processed" / "cv_results.json"
    cv_out.parent.mkdir(parents=True, exist_ok=True)
    with open(cv_out, "w") as f:
        json.dump(results, f)
    
    # Load SSOT params early (needed for spectral config and narrator)
    import yaml
    cfg_path = ROOT / "config" / "params.yaml"
    params = {}
    domain = "structural"
    if cfg_path.exists():
        with open(cfg_path) as _f:
            params = yaml.safe_load(_f) or {}
            domain = params.get("project", {}).get("domain", "structural")

    # 2b. Cálculo Espectral (Sa vs T) — Norma E.030 / ASCE 7-22
    print("\n[2b/3] 📈 Calculando Espectro de Respuesta Sa(T, ζ=5%)...")
    # Ground motion file: default fallback (no SSOT section for this)
    seismic_file = "PISCO_2007_ICA_EW.AT2"
    # Target PGA: read from params.yaml (SSOT) first, soil_params.yaml as fallback
    target_pga = None
    _design_section = params.get("design", {})
    if isinstance(_design_section, dict):
        _z_entry = _design_section.get("Z")
        if isinstance(_z_entry, dict):
            target_pga = _z_entry.get("value")
        elif _z_entry is not None:
            target_pga = _z_entry
    if target_pga is None:
        soil_cfg_path = ROOT / "config" / "soil_params.yaml"
        if soil_cfg_path.exists():
            import logging as _logging
            _logging.warning("design.Z not found in params.yaml (SSOT) — falling back to soil_params.yaml")
            _soil = yaml.safe_load(soil_cfg_path.read_text()) or {}
            target_pga = _soil.get("design", {}).get("Z")
    if target_pga is None:
        raise ValueError(
            "design.Z (PGA) not found in config/params.yaml or config/soil_params.yaml. "
            "Set the seismic zone factor before running the research director."
        )
    try:
        from src.physics.peer_adapter import PeerAdapter
        from src.physics.spectral_engine import compute_spectral_response, generate_spectral_report
        import numpy as np
        
        pisco_at2 = ROOT / "db" / "excitation" / "records" / seismic_file
        if pisco_at2.exists():
            adapter = PeerAdapter(target_frequency_hz=100.0)
            raw_dict = adapter.read_at2_file(pisco_at2)
            accel_raw = adapter.normalize_and_resample(raw_dict)
            dt_target = adapter.target_dt
            
            # Espectro del sismo crudo (antes del Guardian Angel)
            sa_raw = compute_spectral_response(accel_raw, dt_target)
            
            # Espectro del sismo filtrado (Guardian Angel: elimina picos por encima del PGA target)
            accel_filt = adapter.scale_to_pga(accel_raw, target_pga_g=target_pga)
            sa_filt = compute_spectral_response(accel_filt, dt_target)
            
            # Fase 40: Amplificación de Suelo E.030 (site-specific)
            from src.physics.spectral_engine import apply_site_amplification, generate_site_amplification_report, load_soil_params
            soil_p   = load_soil_params()
            sa_site  = apply_site_amplification(sa_raw, soil_p)
            sa_report_site = generate_site_amplification_report(sa_site)
            
            # Encontrar periodo de mayor demanda espectral
            peak_idx = np.argmax(sa_raw["Sa"])
            T_dom = float(sa_raw["T"][peak_idx])
            Sa_max = float(sa_raw["Sa"][peak_idx])
            print(f"   ✅ Periodo Dominante T*={T_dom:.2f}s | Sa max={Sa_max:.3f}g (PGA {sa_raw['pga']:.3f}g)")
            
            results["spectral"] = {
                "T_dominant": T_dom,
                "Sa_max": Sa_max,
                "pga": sa_raw["pga"],
                "sa_raw_report": generate_spectral_report(sa_raw, sa_filt),
                "site_report":  sa_report_site,
                "Sa_site_max":  float(sa_site["Sa_star_site"]),
                "T_star_site":  float(sa_site["T_star_site"]),
                "soil_type":    soil_p["soil_type"]
            }
            with open(cv_out, "w") as f:
                json.dump(results, f, default=lambda x: x.tolist() if hasattr(x, 'tolist') else x)
            
            # Generar figura SVG para el paper
            try:
                from tools.plot_spectrum import generate_svg_spectrum
                svg_name = f"spectrum_{Path(seismic_file).stem}.svg"
                svg_out = ROOT / "articles" / "figures" / svg_name
                generate_svg_spectrum(sa_raw, sa_filt, svg_out)
                results["spectral"]["svg_path"] = str(svg_out)
                with open(cv_out, "w") as f:
                    json.dump(results, f, default=lambda x: x.tolist() if hasattr(x, 'tolist') else x)
            except Exception as svg_err:
                print(f"   ⚠️ SVG no generado (no crítico): {svg_err}")
            
        else:
            print(f"   ⚠️ Sismo PEER no encontrado en {pisco_at2}. Ejecuta: python3 tools/fetch_benchmark.py --verify")
    except Exception as spec_err:
        print(f"   ⚠️ Error en cálculo espectral (no crítico): {spec_err}")
        
    # 3. Redacción del Paper (Scientific Narrator — multi-dominio)
    print("\n[3/3] Invocando al Scientific Narrator para redaccion IMRaD...")

    narrator_path = str(ROOT / "articles" / "scientific_narrator.py")
    subprocess.run([
        sys.executable, narrator_path,
        "--domain", domain,
        "--quartile", quartile,
        "--topic", topic,
    ], cwd=str(ROOT))
    
    print("\n" + "="*70)
    print(f" 🎉 INVESTIGACIÓN COMPLETADA. Borrador Q-Ranked generado.")
    print("="*70 + "\n")

def main():
    parser = argparse.ArgumentParser(description="EIU Research Director")
    parser.add_argument("--quartile", choices=["Q1", "Q2", "Q3", "Q4"], default="Q2", help="Cuartil objetivo (ej. Q1)")
    parser.add_argument("--topic", type=str, required=True, help="Temática central de la investigación")
    parser.add_argument("--cycles", type=int, default=500, help="Semanas/Ciclos a simular")

    args = parser.parse_args()
    run_research(args.quartile, args.topic, args.cycles)

if __name__ == "__main__":
    main()
