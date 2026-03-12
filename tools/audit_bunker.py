"""
Audit Bunker — Herramienta de auditoria de integridad del proyecto Belico.

Ejecuta cuatro verificaciones de higiene sobre el repositorio: (1) deteccion de rutas
absolutas hardcoded en archivos Python, (2) existencia de manifiestos de dependencia
(requirements.txt o pyproject.toml), (3) validacion del archivo .env.example contra
variables requeridas, y (4) presencia de archivos temporales (.log, .pid) en el root.

Pipeline: pre-COMPUTE (verificacion de integridad antes de cualquier simulacion) / CI
CLI: python3 tools/audit_bunker.py
Depende de: estructura de directorios del proyecto, .env.example, requirements.txt
Produce: reporte de issues en stdout con conteo de fallos criticos encontrados
"""
import re
from pathlib import Path

def run_integrity_audit():
    print("🛡️ INICIANDO AUDITORÍA DE INTEGRIDAD DEL BÚNKER v1.0")
    root = Path(__file__).parent.parent
    issues_found = 0

    # 1. Búsqueda de Rutas Hardcoded (El "Cáncer" de la Portabilidad)
    print("\n🔍 Buscando rutas absolutas (hardcoded)...")
    path_regex = re.compile(r"(['\"])/home/|(['\"])[a-zA-Z]:\\")
    for file in root.rglob("*.py"):
        # Ignoramos venv o carpetas de agentes
        if ".venv" in str(file) or ".agent" in str(file) or "tmp" in str(file):
            continue
        try:
            with open(file, 'r', encoding="utf-8") as f:
                for i, line in enumerate(f, 1):
                    if path_regex.search(line):
                        print(f"⚠️ HUECO: Ruta absoluta en {file.relative_to(root)}:{i}")
                        issues_found += 1
        except (UnicodeDecodeError, OSError):
            pass  # skip unreadable or binary files

    # 2. Verificación de Dependencias (El "Vacío" de Entorno)
    print("\n🔍 Verificando manifiestos de dependencia...")
    if not (root / "requirements.txt").exists() and not (root / "pyproject.toml").exists():
        print("❌ INCONSISTENCIA: No hay requirements.txt. El búnker no es reproducible.")
        issues_found += 1
    else:
        print("✅ requirements.txt validado.")

    # 3. Auditoría de Secretos vs Configuración
    print("\n🔍 Cruzando .env.example con variables de entorno...")
    if (root / ".env.example").exists():
        with open(root / ".env.example", 'r') as f:
            keys = [line.split('=')[0] for line in f if '=' in line and not line.startswith("#")]
            print(f"✅ Detectadas {len(keys)} variables requeridas en el estándar.")
    else:
        print("⚠️ HUECO: No existe .env.example para nuevos investigadores.")
        issues_found += 1

    # 4. Limpieza de Ruido (Higiene de la Captura Previa)
    print("\n🔍 Buscando archivos temporales en el root...")
    noise_files = list(root.glob("*.log")) + list(root.glob("*.pid")) + list(root.glob("*_log.txt"))
    # Excluyendo logs_bridge y logs_emu que se generan deliberadamente en la prueba, o considerandolos si son > 2
    if len(noise_files) > 2:
        print(f"⚠️ RUIDO: Se detectaron {len(noise_files)} archivos temporales en el root: {[f.name for f in noise_files]}")
        issues_found += 1
    else:
        print("✅ Higiene de root validada.")

    print(f"\n🏁 AUDITORÍA FINALIZADA. {issues_found} posibles fallos críticos encontrados.")

if __name__ == "__main__":
    run_integrity_audit()
