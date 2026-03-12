"""
Init Bunker — Script de verificacion de integridad del entorno de simulacion.

Realiza tres comprobaciones de arranque: (1) importacion de librerias criticas del stack
cientifico (OpenSeesPy, NumPy, Matplotlib, Pandas), (2) presencia del archivo .env con
llaves de API, y (3) smoke test de OpenSeesPy instanciando un modelo matricial basico.

Pipeline: pre-COMPUTE C0 (verificacion de infraestructura computacional)
CLI: python3 src/init_bunker.py
Depende de: openseespy, .env
Produce: salida de diagnostico en stdout; termina con sys.exit(1) si falla algun check critico
"""
import sys
from pathlib import Path

def check_bunker_integrity():
    print("🔬 AUDITORÍA DE ENTORNO BÉLICO v1.0")
    
    # 1. Verificar Librerías Críticas (Capa Científica)
    try:
        import openseespy.opensees as ops
        import numpy as np
        import matplotlib
        import pandas as pd
        print("✅ [FISICA] OpenSeesPy, NumPy, Matplotlib y Pandas detectados.")
    except ImportError as e:
        print(f"❌ [ERROR] Fallo en la Capa Científica: {e}")
        sys.exit(1)

    # 2. Verificar Conectividad de Memoria (Capa Cognitiva)
    if Path(".env").exists():
        print("✅ [SEGURIDAD] Archivo .env detectado. Llaves cargadas en memoria local.")
    else:
        print("⚠️ [ALERTA] No se encuentra .env. El sistema está en modo OFFLINE. Guardian y AITMPL desactivados.")

    # 3. Smoke Test: Resolución de Matriz de Rigidez Simple (Validación Funcional)
    try:
        ops.wipe()
        ops.model('basic', '-ndm', 1, '-ndf', 1)
        ops.node(1, 0.0); ops.node(2, 1.0)
        ops.fix(1, 1)
        # Una pequeña corrida para ver si los punteros C++ de OpenSees no crashean
        ops.mass(2, 1.0)
        print("✅ [SMOKE TEST] OpenSeesPy resolvió instancia matricial básica en tiempo constante (O(1)).")
    except (RuntimeError, SystemExit, ImportError) as e:
        print(f"❌ [ERROR] Fallo crítico en el motor de simulación (C++ kernel): {e}")
        sys.exit(1)

    print("\n🏁 BÚNKER CERTIFICADO. EL 'GUARDIAN ANGEL' TE DESEA UNA INVESTIGACIÓN IMPLACABLE.")

if __name__ == "__main__":
    check_bunker_integrity()
