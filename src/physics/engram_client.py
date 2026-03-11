"""
Engram Client — Cliente directo SQLite para escritura en la base de datos de memoria persistente Engram.

Alternativa ligera al MCP de Engram: escribe registros (hash, payload, tags) directamente
en ~/.engram/engram.db sin depender del servidor MCP. Usado por bridge.py y otros modulos
del pipeline de simulacion para registrar eventos de aborto y telemetria en tiempo real.

Pipeline: COMPUTE C2-C3 (registro de eventos del Guardian Angel durante simulacion/emulacion)
Depende de: config/paths.py (get_engram_db_path), ~/.engram/engram.db
Produce: registros en tabla `records` de engram.db; activa debug log si TEAMS_DEBUG=true
"""
import os
import sqlite3
import json
import time
import sys
from pathlib import Path

# Resolver ruta basada en utilitario unificado
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))
from config.paths import get_engram_db_path

class _EngramClient:
    def __init__(self):
        self.db_path = get_engram_db_path()
        
    def _init_db(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL,
                    hash_code TEXT,
                    payload TEXT,
                    tags TEXT
                )
            ''')
            conn.commit()

    def record(self, hash_code: str, payload: dict, tags: list):
        try:
            self._init_db()
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'INSERT INTO records (timestamp, hash_code, payload, tags) VALUES (?, ?, ?, ?)',
                    (time.time(), hash_code, json.dumps(payload), json.dumps(tags))
                )
                conn.commit()
                # Debug output solo si TEAMS_DEBUG está activo
                if os.getenv("TEAMS_DEBUG", "false").lower() == "true":
                    print(f"[ENGRAM] 🧠 HASH:{hash_code[:8]} | TAGS:{tags} registrado.")
        except sqlite3.Error as e:
            print(f"⚠️ [ENGRAM] Fallo al escribir en memoria: {e}")

EngramClient = _EngramClient()
