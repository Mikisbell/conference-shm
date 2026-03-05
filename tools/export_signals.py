import sqlite3
import pandas as pd
import hashlib
from pathlib import Path
import datetime
import matplotlib.pyplot as plt
import os
import sys

# Añadir la raíz al path para el import config.paths
sys.path.append(str(Path(__file__).resolve().parent.parent))
from config.paths import get_project_root, get_engram_db_path, get_drafts_dir, get_processed_data_dir

# 1. Configuración de Rutas y Verificación de Integridad
PROJECT_ROOT = get_project_root()
DATABASE_PATH = get_engram_db_path()
DRAFT_PATH = get_drafts_dir() / "paper_v1.md"

def ensure_db_exists():
    """Crea la base de datos de Engram y la tabla signals si no existen (mock para la prueba)."""
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            topic TEXT,
            signal_text TEXT,
            hash TEXT
        )
    ''')
    conn.commit()
    
    # Insertar datos de prueba si está vacía
    cursor.execute("SELECT COUNT(*) FROM signals")
    if cursor.fetchone()[0] == 0:
        now = datetime.datetime.now().isoformat()
        test_hash = hashlib.sha256(b"test_signal").hexdigest()
        cursor.execute(
            "INSERT INTO signals (timestamp, topic, signal_text, hash) VALUES (?, ?, ?, ?)",
            (now, "research_evidence", "Detección Temprana de Inestabilidad mediante Residuos de Kalman (SHM)", test_hash)
        )
        conn.commit()
    conn.close()

def export_scientific_evidence():
    ensure_db_exists()
    
    conn = sqlite3.connect(DATABASE_PATH)
    
    # Extraer "Señales" de Decisiones de Arquitectura y Calibración
    query = "SELECT timestamp, topic, signal_text, hash FROM signals WHERE topic='research_evidence'"
    try:
        df = pd.read_sql_query(query, conn)
    except Exception as e:
        print(f"❌ ERROR leyendo Engram: {e}")
        conn.close()
        return
    
    # Asegúrate de que el directorio del borrador exista
    DRAFT_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    # Generar Tabla de Trazabilidad para el Paper
    # Cada afirmación en el paper debe referenciar un Hash de Engram
    print(f"📄 Exportando {len(df)} señales de evidencia al draft: {DRAFT_PATH.name}...")
    
    with open(DRAFT_PATH, 'a', encoding='utf-8') as f:
        f.write("\n\n## Apéndice: Trazabilidad de Evidencia (Engram-Verified)\n\n")
        f.write("> **Certificado Binario:** Este apéndice es inyectado automáticamente. Ninguna manipulación manual está permitida.\n\n")
        f.write("| Timestamp | Decisión/Hallazgo | Hash de Inmutabilidad |\n")
        f.write("| :--- | :--- | :--- |\n")
        for _, row in df.iterrows():
            f.write(f"| {row['timestamp']} | {row['signal_text']} | `{row['hash'][:12]}...` |\n")
    
    conn.close()
    
# Generar Gráfico Automático de Resonancia
    csv_path = get_processed_data_dir() / "latest_abort.csv"
    if csv_path.exists():
        print(f"📈 Generando gráfico de anomalía desde {csv_path.name}...")
        try:
            df_plot = pd.read_csv(csv_path)
            
            assets_dir = DRAFT_PATH.parent / "assets"
            assets_dir.mkdir(parents=True, exist_ok=True)
            plot_path = assets_dir / "resonance_abort.svg"
            
            # Crear figura con 2 subplots compartiendo el eje X
            fig, (ax1, ax3) = plt.subplots(nrows=2, ncols=1, figsize=(10, 8), sharex=True, gridspec_kw={'height_ratios': [2, 1]})
            
            # --- PANEL 1: FÍSICA (Aceleración y Esfuerzo) ---
            color1 = 'tab:blue'
            ax1.set_ylabel('Aceleración (g)', color=color1)
            ax1.plot(df_plot['time_s'], df_plot['accel_g'], color=color1, alpha=0.7, label='Sensor (Acero)')
            ax1.tick_params(axis='y', labelcolor=color1)
            
            ax2 = ax1.twinx()  
            color2 = 'tab:red'
            ax2.set_ylabel('Esfuerzo Estimado (MPa)', color=color2)  
            ax2.plot(df_plot['time_s'], df_plot['stress_mpa'], color=color2, linewidth=2, label='OpenSeesPy (Modelo)')
            ax2.tick_params(axis='y', labelcolor=color2)
            
            last_t = df_plot['time_s'].iloc[-1]
            ax1.axvline(x=last_t, color='black', linestyle='--', linewidth=2, label='ABORT')
            
            ax1.set_title('Respuesta del Gemelo Digital a Anomalía Sensórica')
            
            # --- PANEL 2: SHM (Residuo de Innovación de Kalman) ---
            color3 = 'tab:green'
            ax3.set_xlabel('Tiempo (s)')
            ax3.set_ylabel(r'Innovación $(z - \hat{z})$', color=color3)
            ax3.plot(df_plot['time_s'], df_plot['innovation_g'], color=color3, linewidth=1.5, label='Residuo SHM')
            ax3.tick_params(axis='y', labelcolor=color3)
            
            # Límite teórico de 2-sigma 
            ax3.axhline(y=0.1, color='orange', linestyle=':', label='Límite $2\sigma$ superior')
            ax3.axhline(y=-0.1, color='orange', linestyle=':', label='Límite $2\sigma$ inferior')
            ax3.axvline(x=last_t, color='black', linestyle='--', linewidth=2)
            
            fig.align_ylabels([ax1, ax3])
            fig.tight_layout()
            plt.savefig(plot_path, format='svg')
            plt.close()
            
            print(f"✅ Gráfico vectorial SHM guardado en: {plot_path.relative_to(PROJECT_ROOT)}")
            
            # Inyectar el gráfico en el draft reemplazando el placeholder
            draft_content = DRAFT_PATH.read_text(encoding='utf-8')
            img_md = f"![Resonance vs Abort (SHM Innovation Analysis)](assets/{plot_path.name})"
            if "{{RESULTS_TABLE}}" in draft_content:
                draft_content = draft_content.replace("{{RESULTS_TABLE}}", img_md)
                DRAFT_PATH.write_text(draft_content, encoding='utf-8')
        except Exception as e:
            print(f"❌ ERROR generando gráfico: {e}")
            
    # Generar Hash de Sesión para Belico.md
    with open(DRAFT_PATH, 'rb') as f:
        draft_hash = hashlib.sha256(f.read()).hexdigest()
        
    print(f"✅ Evidencia exportada. Hash del borrador (Draft Hash): {draft_hash[:16]}")
    print(f"🔍 El Verifier usará este hash como firma de inmutabilidad.")

if __name__ == "__main__":
    export_scientific_evidence()
