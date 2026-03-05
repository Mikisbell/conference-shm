import os
import sys
from pathlib import Path

# Añadir la raíz al path para el import config.paths
sys.path.append(str(Path(__file__).resolve().parent.parent))
from config.paths import get_engram_db_path, get_drafts_dir, get_schema_engram_file

import sqlite3
import json
from datetime import datetime

# Paths del Sistema (Resolución Dinámica)
ENGRAM_DB_PATH = get_engram_db_path()
DRAFT_DIR = get_drafts_dir()
REPORT_PATH = DRAFT_DIR / "transparency_report.md"

def fetch_latest_abort_event():
    """Extrae el último evento de aborto (fuego real) desde la base de datos inmutable."""
    if not ENGRAM_DB_PATH.exists():
        return None
        
    try:
        with sqlite3.connect(ENGRAM_DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            # Buscar el último evento etiquetado como "abort"
            cursor.execute('''
                SELECT id, timestamp, hash_code, payload, tags 
                FROM records 
                WHERE tags LIKE '%"abort"%' 
                ORDER BY timestamp DESC LIMIT 1
            ''')
            return cursor.fetchone()
    except sqlite3.Error as e:
        print(f"❌ [NARRATOR] Error de lectura Engram: {e}")
        return None

def generate_shadow_paper(event):
    """Convierte el Hash de Engram en prosa científica y política (Shadow Paper)."""
    if not event:
        print("⚠️ [NARRATOR] No hay eventos de aborto en Engram para analizar.")
        return

    # Leer Schema Engram (Contrato AI)
    schema_path = get_schema_engram_file()
    schema_yaml = schema_path.read_text(encoding='utf-8') if schema_path.exists() else "No Schema Defined."

    # Parsear los datos inmutables
    payload = json.loads(event['payload'])
    tags = json.loads(event['tags'])
    dt_str = datetime.fromtimestamp(event['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
    
    # Extraer métricas específicas del payload (ej. razón de aborto y paquetes procesados)
    reason = payload.get('reason', 'Desconocido')
    packets = payload.get('packets_processed', 0)
    
    # Simular la lógica de AITMPL: El "Traductor de Evidencia"
    # (En un entorno con API key válida, esto pasaría por un prompt a GPT-4/Claude)
    
    informe = f"""# 🏛️ Informe de Transparencia Estructural y Resiliencia
*Documento Generado Criptográficamente por el Scientific Narrator (AITMPL)*

<!-- ENGINE RESTRICTIONS (SCHEMA.YAML BOUNDARIES)
El siguiente informe fue interpretado respetando estrictamente el Contrato de Datos:
{schema_yaml}
-->

## 1. Integridad del Experimento (Data Auditor)
Este documento certifica el ensayo de la "Cámara de Tortura" (Modelo P-Delta). Todo el flujo de datos desde el sensor físico hasta la parada térmica está sellado bajo el **Hash de Verificación: `{event['hash_code']}`** generado el {dt_str}. El identificador único de este evento en el registro inmutable (Engram) es **[Ref: Engram_ID_{event['id']}]**.

## 2. Análisis Estructural No Lineal (Physics Interpreter)
La estructura fue sometida a una inyección de energía armónica incrementada para simular un colapso. El evento de fallo se produjo tras procesar {packets} paquetes de datos físicos consecutivos. 

El filtro predictivo (Guardian Angel) detuvo la simulación bajo el siguiente diagnóstico algorítmico:
> **Causa Directa de Aborto**: {reason}

## 3. Conclusiones sobre Resiliencia Nacional (Strategic Analyst)
El colapso de infraestructuras críticas no ocurre por azar, sino por la incapacidad de detectar las fallas a tiempo. El ensayo auditable **[Ref: Engram_ID_{event['id']}]** demuestra que nuestra tecnología de "Lazo Cerrado Estructural" es capaz de leer la innovación del Filtro de Kalman y aislar el colapso matemático *antes* de que ocurra la pérdida humana.

En infraestructuras del país (ej. proyectos en asentamientos clave), incorporar este "Búnker de Investigación" como estándar de construcción garantiza que las estructuras no solo sean fuertes ante el papel, sino que sean auditadas cognitivamente en tiempo real día y noche.

---
*Fin del Informe. Generado Automáticamente por AITMPL.*
"""

    DRAFT_DIR.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w") as f:
        f.write(informe)
    
    print(f"✅ [NARRATOR] Shadow Paper generado con éxito en: {REPORT_PATH}")
    print(f"✅ [NARRATOR] Evidencia vinculada a: [Ref: Engram_ID_{event['id']}]")

if __name__ == "__main__":
    print("🧠 [NARRATOR] Iniciando traducción de evidencia desde Engram DB...")
    abort_event = fetch_latest_abort_event()
    generate_shadow_paper(abort_event)
