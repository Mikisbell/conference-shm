import os
import sqlite3
import json
import time

class _EngramClient:
    def __init__(self):
        # Resolver ruta basada en .env si existe, sino path por defecto
        self.db_path = os.getenv("ENGRAM_DB_PATH", ".agent/memory/engram/engram.db")
        
    def _init_db(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
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
        except Exception as e:
            print(f"⚠️ [ENGRAM] Fallo al escribir en memoria: {e}")

EngramClient = _EngramClient()
