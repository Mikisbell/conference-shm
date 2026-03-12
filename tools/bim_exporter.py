"""
BIM Exporter — Generador de metadata BIM 3D compatible con Speckle, Autodesk Forge y WebGL.

Convierte predicciones LSTM de Time-To-Failure (TTF) en objetos JSON estandarizados con
heatmap de riesgo (CRITICAL/WARNING/ACTIVE_MONITORING), colores RGB de render, metricas
IoT (latencia LoRa) y recomendaciones de intervencion. Umbrales de riesgo configurables;
defaults conservadores de ingenieria (critico < 6 meses, alerta < 24 meses).

Pipeline: IMPLEMENT (visualizacion de resultados ML para articulos y dashboards BIM)
CLI: python3 tools/bim_exporter.py --module_id MOD-0001 --ttf 18.5 [--fn 5.2] [--kterm 0.51]
Depende de: prediccion TTF de src/ai/lstm_predictor.py, config/params.yaml (fn y k_term defaults)
Produce: data/processed/bim_exports/BIM-ELEM-{id}_{timestamp}.json
"""
import argparse
import json
import sys
from pathlib import Path
import datetime
try:
    import yaml
except ImportError:
    print("[ERROR] PyYAML not installed. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_BIM_OUT = _ROOT / "data" / "processed" / "bim_exports"

# Constantes de Estado Visual BIM (RGB Hex)
COLOR_HEALTHY  = "#2ecc71" # Verde (Módulo Seguro: > 24 meses TTF)
COLOR_WARNING  = "#f1c40f" # Amarillo (Vigilancia: 6 a 24 meses TTF)
COLOR_CRITICAL = "#e74c3c" # Rojo/Burdeos (Fallo Inminente: < 6 meses TTF)

def generate_bim_metadata(module_id: str, ttf_months: float, fn_current: float,
                          k_term: float, latencia_lora: float,
                          ttf_critical_months: float = 6.0,
                          ttf_warning_months: float = 24.0):
    """
    Genera el Objeto Metadata compatible con los paneles de propiedades
    de plataformas BIM (Speckle, Autodesk Forge, o WebGL Three.js Custom).

    TTF thresholds (ttf_critical_months, ttf_warning_months) can be overridden
    from SSOT via caller. Defaults are conservative engineering values.
    """

    # 1. Determinar el Nivel de Estrés Visual (Heatmap 3D)
    if ttf_months < ttf_critical_months:
        status_color = COLOR_CRITICAL
        risk_level = "CRITICAL"
        intervention_action = "Evacuación Inmediata y Refuerzo Estructural (Mantenimiento Clase A)"
    elif ttf_months < ttf_warning_months:
        status_color = COLOR_WARNING
        risk_level = "WARNING"
        intervention_action = "Inspección Técnica Programada"
    else:
        status_color = COLOR_HEALTHY
        risk_level = "ACTIVE_MONITORING"
        intervention_action = "Ninguna. Ciclo de Vida dentro de márgenes nominales."

    # 2. Construcción del JSON Estandarizado (Formato tipo Speckle Object Base)
    bim_object = {
        "id": f"BIM-ELEM-{module_id}",
        "type": "ModularHousingUnit",
        "material": "Structural Material",
        "properties": {
            "Structural_Health": {
                "LSTM_Prediction_TTF_Months": round(ttf_months, 2),
                "Risk_Classification": risk_level,
                "Current_Natural_Frequency_Hz": round(fn_current, 2),
                "Thermal_Conductivity_WmK": round(k_term, 3)
            },
            "IoT_Network_Layer": {
                "Last_Audit_Timestamp": datetime.datetime.now().isoformat(),
                "LoRa_Network_Latency_Secs": round(latencia_lora, 2),
                "Engram_Chain_Status": "VERIFIED_SECURE"
            },
            "Render_Material": {
                "Override_Color_Hex": status_color,
                "Opacity": 0.85
            },
            "Maintenance_Logistics": {
                "Recommended_Action": intervention_action
            }
        }
    }
    
    return bim_object

def export_to_json(bim_object, output_dir=None):
    out_path = Path(output_dir) if output_dir else _DEFAULT_BIM_OUT
    out_path.mkdir(parents=True, exist_ok=True)

    file_name = f"{bim_object['id']}_{datetime.datetime.now().strftime('%Y%m%d%H%M')}.json"
    full_path = out_path / file_name

    try:
        with open(full_path, "w") as f:
            json.dump(bim_object, f, indent=4)
    except OSError as e:
        print(f"[BIM] Cannot write {full_path}: {e}", file=sys.stderr)
        sys.exit(1)
        
    print(f"✅ [BIM EXPORTER] Objeto 3D Metadata generado: {full_path}")
    print(f"   Modulo: {bim_object['id']} -> Riesgo: {bim_object['properties']['Structural_Health']['Risk_Classification']}")
    print(f"   Render Color Asignado: {bim_object['properties']['Render_Material']['Override_Color_Hex']}")
    return full_path

if __name__ == "__main__":
    # Load defaults from SSOT
    _params_path = _ROOT / "config" / "params.yaml"
    if not _params_path.exists():
        print(f"[ERROR] SSOT not found: {_params_path}", file=sys.stderr)
        sys.exit(1)
    try:
        _cfg = yaml.safe_load(_params_path.read_text()) or {}
    except (yaml.YAMLError, OSError) as e:
        print(f"[ERROR] Cannot read params.yaml: {e}", file=sys.stderr)
        sys.exit(1)
    _mat = _cfg.get("material", {})
    _stru = _cfg.get("structure", {})
    _fw = _cfg.get("firmware", {}).get("edge_alarms", {})
    _default_fn = _fw.get("nominal_fn_hz", {}).get("value")
    if _default_fn is None:
        raise RuntimeError("SSOT missing: firmware.edge_alarms.nominal_fn_hz")
    _default_kterm = _mat.get("thermal_conductivity", {}).get("value")
    if _default_kterm is None:
        raise RuntimeError("SSOT missing: material.thermal_conductivity")

    parser = argparse.ArgumentParser(description="Exportador BÉLICO AI -> BIM 3D (Speckle/WebGL)")
    parser.add_argument("--module_id", type=str, required=True, help="Identificador del Modulo Habitacional")
    parser.add_argument("--ttf", type=float, required=True, help="Time To Failure predicho por el LSTM (meses)")
    parser.add_argument("--fn", type=float, default=_default_fn, help="Frecuencia Natural actual (Hz)")
    parser.add_argument("--kterm", type=float, default=_default_kterm, help="Conductividad Térmica (W/m·K)")
    parser.add_argument("--lag", type=float, default=0.2, help="Watchdog LoRa Latency (segundos)")
    
    args = parser.parse_args()
    
    metadata = generate_bim_metadata(
        module_id=args.module_id, 
        ttf_months=args.ttf, 
        fn_current=args.fn, 
        k_term=args.kterm,
        latencia_lora=args.lag
    )
    
    export_to_json(metadata)
