#!/usr/bin/env python3
"""
tools/scaffold_investigation.py — Andamiaje Evolutivo
======================================================
Este script automatiza la creación de un nuevo "Búnker de Investigación" (Proyecto)
inyectando los límites físicos (Guardrails) dependientes del dominio seleccionado
para que el Guardian Angel y el Verifier puedan auditar desde el segundo cero.
"""

import os
import yaml
import sys
from pathlib import Path

def get_domain_rules(domain: str) -> dict:
    """Inyección de leyes físicas pre-auditadas por Guardian Angel."""
    rules = {
        'concreto': {
            'check': 'stiffness_matrix', 
            'limit': 'strain_0.003',
            'kf_r': 0.05,
            'integrator': 'Newmark-Beta (gamma=0.5)'
        },
        'agua': {
            'check': 'reynolds_number', 
            'limit': 'convergence_1e-6',
            'kf_r': 0.01,
            'integrator': 'Navier-Stokes-Solver'
        },
        'aire': {
            'check': 'pressure_coeff', 
            'limit': 'lift_stability',
            'kf_r': 0.02,
            'integrator': 'Euler-Solver'
        }
    }
    return rules.get(domain, {
        'check': 'custom_physics',
        'limit': 'custom_limit'
    })

def create_bunker(project_name: str, domain: str):
    print("🎖️ [SCAFFOLD] Generando Búnker Científico...")
    
    # 1. Crear Estructura de Directorios Aislada
    base_dir = Path(project_name)
    folders = [
        'src/physics', 'src/hardware', 'src/bridge',
        'articles/drafts', 'articles/data', 'articles/assets',
        'logs', '.agent/memory', '.agent/skills', '.agent/security'
    ]
    for folder in folders:
        (base_dir / folder).mkdir(parents=True, exist_ok=True)

    # 2. Configurar el Corazón Operativo: belico.yaml
    config = {
        'project': project_name,
        'domain': domain,
        'status': 'active',
        'orchestration': {
            'teams_lite': True,
            'aitmpl_scientific': True,
            'guardian_angel': True
        },
        'physics_guardrails': get_domain_rules(domain)
    }
    
    with open(base_dir / "belico.yaml", 'w') as f:
        yaml.dump(config, f, sort_keys=False)

    print(f"🚀 [SCAFFOLD] Andamiaje para '{project_name}' listo.")
    print(f"🛡️ [SCAFFOLD] Guardrails para dominio '{domain}' inyectados en belico.yaml.")
    print(f"💡 [SCAFFOLD] Evolutivo: Sugerencia de Engram -> Puedes aplicar el integrador {config['physics_guardrails'].get('integrator')} basado en tu último paper.")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Uso: python3 scaffold_investigation.py <nombre_proyecto> <dominio: concreto|agua|aire>")
        sys.exit(1)
        
    p_name = sys.argv[1].replace(" ", "_")
    d_name = sys.argv[2].lower()
    create_bunker(p_name, d_name)
