#!/usr/bin/env python3
"""
tools/research_director.py — Orquestador de Investigación Universal (EIU)
=============================================================================
Motor principal para automatizar la ejecución de campañas de investigación y
la generación de Papers Científicos (Conference-Q1).

Flujo COMPUTE completo:
  1. Propaga SSOT: generate_params.py → params.h + params.py
  2. Validación Cruzada A/B: CrossValidationEngine → cv_results.json
  2b. Espectro de Respuesta Sa(T): spectral_engine + peer_adapter → cv_results.json
  2c. Estadísticos (obligatorio Q1/Q2, recomendado Q3):
      compute_statistics.py → cv_results.json enriquecido (*_std + statistics_summary)
  2d. COMPUTE Manifest (Gate C5): generate_compute_manifest.py → COMPUTE_MANIFEST.json
  3. Redacción IMRaD: scientific_narrator.py → articles/drafts/

Uso:
  python3 tools/research_director.py --quartile Q2 --topic "Digital Twin framework for SHM"
  python3 tools/research_director.py --quartile Conference --topic "SHM with IoT sensors"
"""

import argparse
import json
import logging
import re
import sys
import time
from pathlib import Path
import subprocess
import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.physics.cross_validation import CrossValidationEngine


def _engram_save(content: str) -> None:
    """Write to Engram native schema via CLI — searchable by mem_search/mem_context.

    Uses `engram save "..."` CLI (writes to ~/.engram/engram.db observations table
    with FTS5). Distinct from engram_client.py which writes to the `records` table
    (telemetry-only, not searchable by the orchestrator MCP).
    Fails silently if engram CLI is not installed.
    """
    try:
        subprocess.run(
            ["engram", "save", content],
            check=False, capture_output=True, timeout=5
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass  # engram CLI not installed or timeout — non-blocking

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

    # Derivar paper_id del topic para trazabilidad en Engram
    _paper_id = re.sub(r"[^a-z0-9]+", "-", topic.lower())[:40].strip("-")

    # Bus: registrar inicio de campaña en Engram (searchable por orquestador)
    _engram_save(f"task: research_director — paper:{_paper_id} — {quartile} '{topic}' ({cycles} cycles)")

    # 1. Ajuste paramétrico (simulado por ahora, usar generate_params en el futuro)
    print("[1/3] ⚙️  Configurando Entorno SSOT (params.yaml)...")
    result_gp = subprocess.run(
        [sys.executable, "tools/generate_params.py"], cwd=str(ROOT), capture_output=True
    )
    if result_gp.returncode != 0:
        logging.warning("generate_params.py exited with code %d — SSOT propagation may be incomplete", result_gp.returncode)
    time.sleep(1)

    # 2. Validación Cruzada (Caso A vs Caso B)
    print("\n[2/3] 🔬 Ejecutando Motor de Validación Cruzada (A/B Test)...")
    cv_engine = CrossValidationEngine(cycles=cycles)
    results = cv_engine.execute_validation_suite()

    # Bus: resultado de cross-validation
    fp_rate = results.get("false_positive_rate", "?")
    sens    = results.get("sensitivity", "?")
    _engram_save(
        f"result: cross_validation — fp_rate={fp_rate}, sensitivity={sens}, "
        f"cycles={cycles}, output=data/processed/cv_results.json"
    )

    # Guardar temporalmente los resultados de la validación cruzada para el narrador
    cv_out = ROOT / "data" / "processed" / "cv_results.json"
    cv_out.parent.mkdir(parents=True, exist_ok=True)
    with open(cv_out, "w") as f:
        json.dump(results, f)
    
    # Load SSOT params early (needed for spectral config and narrator)
    cfg_path = ROOT / "config" / "params.yaml"
    params = {}
    domain = "structural"
    if cfg_path.exists():
        with open(cfg_path) as _f:
            params = yaml.safe_load(_f) or {}
            domain = params.get("project", {}).get("domain", "structural")

    # 2b. Cálculo Espectral (Sa vs T) — Norma E.030 / ASCE 7-22
    print("\n[2b/3] 📈 Calculando Espectro de Respuesta Sa(T, ζ=5%)...")
    # Ground motion file: read from SSOT (config/params.yaml → excitation.default_record)
    seismic_file = params.get("excitation", {}).get("default_record", "PISCO_2007_ICA_EW.AT2")
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
            logging.warning("design.Z not found in params.yaml (SSOT) — falling back to soil_params.yaml")
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
    except (MemoryError, KeyboardInterrupt, SystemExit):
        raise
    except Exception as spec_err:
        print(f"   ⚠️ Error en cálculo espectral (no crítico): {spec_err}")

    # 2c. Estadísticos — obligatorio Q1/Q2 (Gate 2 reviewer_simulator), recomendado Q3
    # compute_statistics.py enriquece cv_results.json con *_std keys (error bars)
    # y statistics_summary (p-value, Cohen's d, CI) que validate_submission Gate 0.8 requiere.
    _stats_ran = False
    if quartile in ("Q1", "Q2", "Q3"):
        _label = "obligatorio" if quartile in ("Q1", "Q2") else "recomendado"
        print(f"\n[2c/3] 📊 Computando Estadísticos ({_label} para {quartile})...")
        result_stats = subprocess.run(
            [sys.executable, "tools/compute_statistics.py",
             "--quartile", quartile.lower()],
            cwd=str(ROOT), capture_output=True, text=True
        )
        if result_stats.returncode == 0:
            print("   ✅ Estadísticos OK — cv_results.json enriquecido con *_std + statistics_summary")
            _stats_ran = True
        else:
            if quartile in ("Q1", "Q2"):
                # Gate 2 bloqueará en VERIFY sin estos estadísticos — fallar aquí es correcto.
                raise RuntimeError(
                    f"compute_statistics.py falló (exit {result_stats.returncode}) — "
                    f"requerido para {quartile}. Verifica data/processed/*.csv\n"
                    + (result_stats.stderr or "")[-500:]
                )
            else:
                logging.warning(
                    "compute_statistics.py exited %d (no crítico para %s)",
                    result_stats.returncode, quartile
                )

    # 2d. COMPUTE Manifest (Gate C5 — habilita IMPLEMENT)
    # Sin COMPUTE_MANIFEST.json, validate_submission bloquea IMPLEMENT.
    print("\n[2d/3] 🔒 Generando COMPUTE_MANIFEST.json (Gate C5)...")
    result_cm = subprocess.run(
        [sys.executable, "tools/generate_compute_manifest.py"],
        cwd=str(ROOT), capture_output=True, text=True
    )
    _manifest_path = ROOT / "data" / "processed" / "COMPUTE_MANIFEST.json"
    if result_cm.returncode == 0:
        print("   ✅ COMPUTE_MANIFEST.json generado — IMPLEMENT habilitado")
    else:
        logging.warning(
            "generate_compute_manifest.py exited %d — "
            "IMPLEMENT puede no estar habilitado. Corre manualmente si falla.",
            result_cm.returncode
        )

    # Bus: COMPUTE completado — trazabilidad para el orquestador
    _simulations_run = results.get("n_simulations", results.get("cycles_completed", cycles))
    _engram_save(
        f"paper: COMPUTE done — topic='{topic}', quartile={quartile}, "
        f"record={seismic_file}, simulations_run={_simulations_run}, "
        f"files=data/processed/cv_results.json, "
        f"statistics={'ran (cv_results.json enriched)' if _stats_ran else 'skipped'}, "
        f"compute_manifest={'present' if _manifest_path.exists() else 'missing'}, "
        f"emulation=skipped, guardian=skipped"
    )

    # 3. Redacción del Paper (Scientific Narrator — multi-dominio)
    print("\n[3/3] Invocando al Scientific Narrator para redaccion IMRaD...")

    narrator_path = str(ROOT / "articles" / "scientific_narrator.py")
    subprocess.run([
        sys.executable, narrator_path,
        "--domain", domain,
        "--quartile", quartile,
        "--topic", topic,
    ], cwd=str(ROOT))

    # Bus: resultado final del director
    _engram_save(
        f"result: research_director — paper:{_paper_id} draft generated, "
        f"quartile={quartile}, topic='{topic}', domain={domain}"
    )

    print("\n" + "="*70)
    print(f" 🎉 INVESTIGACIÓN COMPLETADA. Borrador Q-Ranked generado.")
    print("="*70 + "\n")

def main():
    parser = argparse.ArgumentParser(description="EIU Research Director")
    parser.add_argument("--quartile", choices=["Conference", "Q1", "Q2", "Q3", "Q4"], default="Q2", help="Cuartil objetivo (ej. Q1, Conference)")
    parser.add_argument("--topic", type=str, required=True, help="Temática central de la investigación")
    parser.add_argument("--cycles", type=int, default=500, help="Semanas/Ciclos a simular")

    args = parser.parse_args()
    run_research(args.quartile, args.topic, args.cycles)

if __name__ == "__main__":
    main()
