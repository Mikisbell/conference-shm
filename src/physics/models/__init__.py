"""
Models Package — Sub-paquete de definiciones de modelo y acceso a parametros del SSOT.

Exporta dos fuentes de parametros con propositos distintos: `params.py` (runtime YAML,
lectura fresca en cada import, para simulacion) y el modulo auto-generado
`src/physics/params.py` (constantes estaticas para firmware y herramientas de test).
Tambien expone `init_model()` para inicializar el oscilador de 1-GDL en OpenSeesPy.

Pipeline: COMPUTE C0 (CHECK 4) — verificacion de lectura del SSOT antes de simular
Depende de: config/params.yaml (SSOT), openseespy
Produce: objeto P con parametros de simulacion, funcion init_model()
"""
