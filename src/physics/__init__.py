"""
Physics Package — Paquete raiz del dominio de simulacion numerica del proyecto Belico.

Agrupa los modulos del backend de simulacion estructural (OpenSeesPy), el cliente de
memoria persistente (Engram), y los parametros derivados del SSOT. El sub-paquete
`models` contiene las definiciones de modelo y params runtime; `bridge.py` conecta
el hardware/emulador con el gemelo digital en tiempo real.

Pipeline: COMPUTE C0-C2 (verificacion de infraestructura y ejecucion de simulacion)
Depende de: config/params.yaml (SSOT)
Produce: expone torture_chamber, engram_client, models a los consumidores del paquete
"""
