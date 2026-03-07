import os
from pathlib import Path

def get_project_root() -> Path:
    """
    Escala automáticamente desde la ubicación de este script
    hasta encontrar el archivo 'belico.yaml' o la estructura base.
    """
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "belico.yaml").exists() or (current / ".agent").exists():
            return current
        current = current.parent
    
    # Fallback to current working directory if belico.yaml is missing
    return Path(os.getcwd())

PROJECT_ROOT = get_project_root()

def get_data_dir() -> Path:
    return PROJECT_ROOT / "data"

def get_processed_data_dir() -> Path:
    p = get_data_dir() / "processed"
    p.mkdir(parents=True, exist_ok=True)
    return p

def get_articles_dir() -> Path:
    return PROJECT_ROOT / "articles"

def get_drafts_dir() -> Path:
    p = get_articles_dir() / "drafts"
    p.mkdir(parents=True, exist_ok=True)
    return p

def get_config_dir() -> Path:
    return PROJECT_ROOT / "config"

def get_engram_db_path() -> Path:
    """
    Devuelve la ruta absoluta al Engram (SQLite DB).
    Puede ser sobrescrita por .env pero por defecto busca en la raíz del proyecto.
    """
    env_path = os.getenv("ENGRAM_DB_PATH")
    if env_path:
        p = Path(env_path)
        if not p.is_absolute():
            # Resolviendo rutas relativas ingresadas en el .env respecto al ROOT
            return PROJECT_ROOT / p
        return p
    return Path.home() / ".engram" / "engram.db"

def get_params_file() -> Path:
    return get_config_dir() / "params.yaml"

def get_schema_engram_file() -> Path:
    return PROJECT_ROOT / ".agent" / "memory" / "schema_engram.yaml"
