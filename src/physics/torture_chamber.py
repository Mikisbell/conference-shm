"""
simulation/torture_chamber.py — La Víctima (Modelo No-Lineal)
==============================================================
Este script configura un modelo de columna en OpenSeesPy diseñado
específicamente para fallar ante inestabilidad (P-Delta) bajo la
influencia de vibraciones externas.

Carga Axial (P) cercana a la Carga Crítica de Euler (Pcr).
"""

import sys
import openseespy.opensees as ops

def init_model():
    """Inicializa la Cámara de Tortura."""
    print("🏗️ [OPENSEES] Inicializando Cámara de Tortura (Columna No-Lineal P-Delta)...")
    
    ops.wipe()
    # 2D, 3 grados de libertad por nodo (X, Y, Rotación Z)
    ops.model('basic', '-ndm', 2, '-ndf', 3)

    # Nodos (L = 3.0 m)
    L = 3.0
    ops.node(1, 0.0, 0.0)
    ops.node(2, 0.0, L)

    # Condiciones de Borde: Empotrado en la base
    ops.fix(1, 1, 1, 1)

    # Transformación Geométrica P-Delta (AQUÍ ESTÁ LA NO-LINEALIDAD)
    transf_tag = 1
    ops.geomTransf('PDelta', transf_tag)

    # Material Elástico
    mat_tag = 1
    E = 200e9      # Pa (Acero)
    A = 0.01       # m^2
    I = 8.33e-6    # m^4
    ops.uniaxialMaterial('Elastic', mat_tag, E)

    # Elemento: Columna elástica no-lineal (con P-Delta)
    ele_tag = 1
    # Usamos elasticBeamColumn que soporta P-Delta a través del transf
    ops.element('elasticBeamColumn', ele_tag, 1, 2, A, E, I, transf_tag)

    # Masa en el tope para la dinámica
    m = 5000.0 # kg
    ops.mass(2, m, m, 0.0)

    # Carga Axial Gravitatoria Inicial (P cercana a Pcr)
    # Pcr = pi^2 * E * I / (4 * L^2)  (voladizo, K=2)
    # Pcr = 3.1416^2 * 200e9 * 8.33e-6 / (4 * 9) = 456,778 N
    # Aplicaremos el 90% de Pcr para dejarla al borde del abismo
    P_applied = -410000.0 # N (hacia abajo)
    
    ops.timeSeries('Constant', 1)
    ops.pattern('Plain', 1, 1)
    ops.load(2, 0.0, P_applied, 0.0)
    
    # Análisis Estático Inicial
    ops.system('BandGeneral')
    ops.numberer('RCM')
    ops.constraints('Plain')
    ops.test('NormDispIncr', 1.0e-8, 10)
    ops.algorithm('Newton')
    ops.integrator('LoadControl', 1.0)
    ops.analysis('Static')
    ops.analyze(1)
    
    # Reset temporal para iniciar dinámica a t=0
    ops.loadConst('-time', 0.0)

    # Configuramos el Análisis Dinámico para el Bridge
    ops.timeSeries('Linear', 2)
    ops.pattern('Plain', 2, 2)
    # La fuerza lateral se aplicará en X (DOF 1) usando ops.load(2, F, 0, 0) en bridge.py
    
    # Amortiguamiento de Rayleigh (Críticamente bajo para hacerla frágil)
    # xi = 0.5% (muy bajo)
    zeta = 0.005
    wn = 3.14 # Rad/s aprox
    a0 = zeta * 2 * wn
    ops.rayleigh(a0, 0.0, 0.0, 0.0)

    ops.system('BandGeneral')
    ops.numberer('RCM')
    ops.constraints('Plain')
    ops.test('NormDispIncr', 1.0e-6, 20)
    ops.algorithm('Newton')
    ops.integrator('Newmark', 0.5, 0.25)
    ops.analysis('Transient')

    print("🏗️ [OPENSEES] Cámara de Tortura construida. Esperando el temblor.")
    return True
