"""
Transparency Dashboard — Dashboard publico de auditoria ciudadana del sistema Belico.

Aplicacion Dash/Plotly que expone en tiempo real (polling cada 2s) el estado del gemelo
digital: semaforo Engram (hash del ultimo bloque inmutable), curva de esfuerzo P-Delta vs
umbral de fluencia (f_y del SSOT), diagnostico del Guardian Angel (abortos/nominal), y
enlace al shadow paper del informe de resiliencia. Opera en modo solo lectura sobre
engram.db y data/processed/latest_abort.csv; no escribe ningun archivo.

Pipeline: post-COMPUTE C3 / FINALIZE (visualizacion de resultados para transparencia publica)
CLI: python3 articles/transparency_dashboard.py  →  http://localhost:8080/
Depende de: ~/.engram/engram.db, data/processed/latest_abort.csv, config/params.yaml (fy, stress_ratio)
Produce: dashboard web en puerto 8080 (solo lectura, sin outputs en disco)
"""
import os
import sqlite3
import json
from pathlib import Path
import sys

try:
    import dash
    from dash import dcc, html
    from dash.dependencies import Input, Output
    import plotly.graph_objects as go
except ImportError:
    print("[ERROR] dash and plotly required. Run: pip install dash plotly", file=sys.stderr)
    sys.exit(1)

try:
    import yaml
except ImportError:
    print("[ERROR] PyYAML required. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

# Añadir la raíz al path para el import config.paths
sys.path.append(str(Path(__file__).resolve().parent.parent))
from config.paths import get_engram_db_path, get_drafts_dir, get_processed_data_dir, get_params_file

# Load SSOT params once at startup — cached to avoid disk I/O on every callback tick
try:
    with open(get_params_file(), "r") as _pf:
        _PARAMS_CFG = yaml.safe_load(_pf) or {}
except (yaml.YAMLError, OSError) as _e:
    print(f"[DASHBOARD] WARNING: cannot read params.yaml: {_e}", file=sys.stderr)
    _PARAMS_CFG = {}

# Configuración del servidor cívico (Solo Lectura)
app = dash.Dash(__name__, title="Auditoría Ciudadana - Búnker Bélico")

ENGRAM_DB_PATH = get_engram_db_path()
REPORT_PATH = get_drafts_dir() / "transparency_report.md"

def fetch_engram_data():
    """Lee el histórico del payload para el Front-End."""
    if not ENGRAM_DB_PATH.exists():
        return None
    try:
        # Modo solo lectura para proteger sqlite3
        uri = f"file:{ENGRAM_DB_PATH}?mode=ro"
        with sqlite3.connect(uri, uri=True) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, timestamp, hash_code, payload, tags 
                FROM records 
                ORDER BY timestamp DESC LIMIT 1
            ''')
            return cursor.fetchone()
    except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
        print(f"[DASHBOARD] Error reading Engram: {e}", file=sys.stderr)
        return None

def fetch_latest_abort_csv():
    """Para la 'Curva de Agonía', extraemos el histórico temporal de pandas."""
    csv_path = get_processed_data_dir() / "latest_abort.csv"
    if not csv_path.exists():
        return None
    try:
        import pandas as pd
    except ImportError:
        print("[DASHBOARD] pandas required for CSV plot. Run: pip install pandas", file=sys.stderr)
        return None
    try:
        return pd.read_csv(csv_path)
    except OSError as e:
        print(f"[DASHBOARD] Cannot read latest_abort.csv: {e}", file=sys.stderr)
        return None

# Layout de la Ventanilla de Transparencia
app.layout = html.Div(style={'fontFamily': 'system-ui, sans-serif', 'maxWidth': '1200px', 'margin': '0 auto', 'padding': '20px', 'backgroundColor': '#f8f9fa'}, children=[
    
    # ── SEMÁFORO DE ENGRAM (Hash Banner) ──
    html.Div(style={'backgroundColor': '#2c3e50', 'color': 'white', 'padding': '20px', 'borderRadius': '10px', 'marginBottom': '20px', 'display': 'flex', 'justifyContent': 'space-between', 'alignItems': 'center'}, children=[
        html.Div([
            html.H1("🛡️ FARO DE TRANSPARENCIA", style={'margin': '0 0 10px 0', 'fontSize': '24px'}),
            html.Div(id='engram-status', style={'fontSize': '16px'})
        ]),
        html.Div(id='guardian-indicator', style={'fontSize': '40px'})
    ]),

    # ── LA CIRUGÍA (Gráficos) ──
    html.Div(style={'display': 'grid', 'gridTemplateColumns': '2fr 1fr', 'gap': '20px'}, children=[
        
        # Panel Izquierdo: Curva de Agonía
        html.Div(style={'backgroundColor': 'white', 'padding': '20px', 'borderRadius': '10px', 'boxShadow': '0 4px 6px rgba(0,0,0,0.1)'}, children=[
            html.H2("📉 La Curva de Agonía (Esfuerzo P-Delta vs Yield)", style={'marginTop': '0', 'fontSize': '20px', 'color': '#c0392b'}),
            html.P("El modelo teórico (f_y) vs. el avance en tiempo real al colapso, documentado inmutablemente.", style={'color': '#7f8c8d'}),
            dcc.Graph(id='live-stress-graph')
        ]),

        # Panel Derecho: Analíticas y Paper
        html.Div(style={'display': 'flex', 'flexDirection': 'column', 'gap': '20px'}, children=[
            html.Div(style={'backgroundColor': 'white', 'padding': '20px', 'borderRadius': '10px', 'boxShadow': '0 4px 6px rgba(0,0,0,0.1)'}, children=[
                html.H3("⚖️ Diagnóstico Guardian Angel", style={'margin': '0 0 10px 0'}),
                html.Div(id='diagnostico-card')
            ]),
            
            html.Div(style={'backgroundColor': 'white', 'padding': '20px', 'borderRadius': '10px', 'boxShadow': '0 4px 6px rgba(0,0,0,0.1)'}, children=[
                html.H3("📄 Shadow Paper", style={'margin': '0 0 10px 0'}),
                html.P("Enlace directo a la evidencia traducida para la ciudadanía y pares académicos:"),
                html.A("Leer Informe de Resiliencia", href="/report", target="_blank", style={'display': 'inline-block', 'padding': '10px 20px', 'backgroundColor': '#3498db', 'color': 'white', 'textDecoration': 'none', 'borderRadius': '5px', 'fontWeight': 'bold'})
            ])
        ])
    ]),
    
    dcc.Interval(id='interval-update', interval=2000, n_intervals=0) # Update cada 2 seg
])

@app.callback(
    [Output('engram-status', 'children'),
     Output('guardian-indicator', 'children'),
     Output('live-stress-graph', 'figure'),
     Output('diagnostico-card', 'children')],
    [Input('interval-update', 'n_intervals')]
)
def update_dashboard(n):
    # 1. Chequear BD Engram
    engram_event = fetch_engram_data()
    status_text = "Buscando Bloque Génesis..."
    indicator = "⚪"
    diag_content = html.P("No hay eventos registrados.")
    
    if engram_event:
        hash_code = engram_event['hash_code']
        try:
            tags = json.loads(engram_event.get('tags', '[]') or '[]')
        except json.JSONDecodeError:
            tags = []
        try:
            payload = json.loads(engram_event.get('payload', '{}') or '{}')
        except json.JSONDecodeError:
            payload = {}
        
        status_text = html.Div([
            html.Span("✅ INMUTABLE", style={'color': '#2ecc71', 'fontWeight': 'bold'}),
            html.Span(f" | Hash: {hash_code[:16]}... | Tags: {', '.join(tags)}")
        ])
        
        # Si es un aborto, mostramos el escudo rojo, si no es una prueba exitosa (verde)
        if "abort" in tags:
            indicator = "🛑"
            diag_content = html.Div([
                html.P(html.Strong("COLAPSO PREVENIDO"), style={'color': '#c0392b'}),
                html.P(f"Motivo: {payload.get('reason', 'Desconocido')}"),
                html.P(f"La simulación se abortó tras {payload.get('packets_processed', 0)} iteraciones micro-temporales.")
            ])
        else:
            indicator = "🛡️"
            diag_content = html.P("Sistema bajo parámetros nominales.")

    # 2. Renderizar Curva de Agonía
    df = fetch_latest_abort_csv()
    fig = go.Figure()
    
    if df is not None and not df.empty and 'time_s' in df.columns and 'stress_mpa' in df.columns:
        # Real stress
        fig.add_trace(go.Scatter(
            x=df['time_s'], y=df['stress_mpa'],
            mode='lines',
            name='Esfuerzo Físico Censor',
            line=dict(color='#e74c3c', width=3)
        ))
        # Yield limit from SSOT (cached at startup)
        _fy_raw = _PARAMS_CFG.get("material", {}).get("yield_strength_fy", {})
        _fy_val = _fy_raw.get("value") if isinstance(_fy_raw, dict) else _fy_raw
        _sr_raw = _PARAMS_CFG.get("guardrails", {}).get("max_stress_ratio", {})
        _sr_val = _sr_raw.get("value") if isinstance(_sr_raw, dict) else _sr_raw
        if _fy_val is None or _sr_val is None:
            limit_mpa = None
        else:
            fy_mpa = float(_fy_val) / 1e6
            stress_ratio = float(_sr_val)
            limit_mpa = stress_ratio * fy_mpa
        if limit_mpa is not None:
            fig.add_trace(go.Scatter(
                x=[df['time_s'].min(), df['time_s'].max()],
                y=[limit_mpa, limit_mpa],
                mode='lines',
                name='Umbral Crítico Teórico (f_y)',
                line=dict(color='#2c3e50', width=2, dash='dash')
            ))
        
        # Shade the gap (Incertidumbre eliminada)
        fig.update_layout(
            margin=dict(l=20, r=20, t=20, b=20),
            yaxis_title="Esfuerzo (MPa)",
            xaxis_title="Tiempo (s)",
            plot_bgcolor='white',
            hovermode='x unified'
        )
    else:
        fig.update_layout(title="Esperando inicialización del Lazo Cerrado...", plot_bgcolor='#ecf0f1')

    return status_text, indicator, fig, diag_content

if __name__ == '__main__':
    print("🚦 INICIANDO EL FARO DE TRANSPARENCIA (DASHBOARD PUBLICO)")
    print("🔗 Visite: http://localhost:8080/")
    app.run(host='0.0.0.0', port=8080, debug=False)
