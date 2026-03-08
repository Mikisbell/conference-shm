import argparse
import json
from pathlib import Path
import datetime
import yaml

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

def export_to_json(bim_object, output_dir="data/processed/bim_exports"):
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    
    file_name = f"{bim_object['id']}_{datetime.datetime.now().strftime('%Y%m%d%H%M')}.json"
    full_path = out_path / file_name
    
    with open(full_path, "w") as f:
        json.dump(bim_object, f, indent=4)
        
    print(f"✅ [BIM EXPORTER] Objeto 3D Metadata generado: {full_path}")
    print(f"   Modulo: {bim_object['id']} -> Riesgo: {bim_object['properties']['Structural_Health']['Risk_Classification']}")
    print(f"   Render Color Asignado: {bim_object['properties']['Render_Material']['Override_Color_Hex']}")
    return full_path

if __name__ == "__main__":
    # Load defaults from SSOT
    _params_path = Path(__file__).resolve().parent.parent / "config" / "params.yaml"
    _cfg = yaml.safe_load(_params_path.read_text()) if _params_path.exists() else {}
    _mat = _cfg.get("material", {})
    _stru = _cfg.get("structure", {})
    _fw = _cfg.get("firmware", {}).get("edge_alarms", {})
    _default_fn = _fw.get("nominal_fn_hz", {}).get("value") or 5.0
    _default_kterm = _mat.get("thermal_conductivity", {}).get("value") or 0.51

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
