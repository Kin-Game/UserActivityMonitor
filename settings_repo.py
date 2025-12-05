import json
import sqlite3
from pathlib import Path


class SettingsRepository:


    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._ensure_table()

    def _ensure_table(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        self.conn.commit()

    def get(self, key: str, default=None):
        cur = self.conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cur.fetchone()
        if not row:
            return default
        try:
            return json.loads(row["value"])
        except:
            return row["value"]

    def set(self, key: str, value):
        as_json = json.dumps(value)
        self.conn.execute("""
            INSERT OR REPLACE INTO settings (key, value)
            VALUES (?, ?)
        """, (key, as_json))
        self.conn.commit()

    def all(self) -> dict:
        cur = self.conn.execute("SELECT key, value FROM settings")
        out = {}
        for row in cur.fetchall():
            try:
                out[row["key"]] = json.loads(row["value"])
            except:
                out[row["key"]] = row["value"]
        return out
