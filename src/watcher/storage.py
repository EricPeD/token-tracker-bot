# src/watcher/storage.py
import sqlite3
import os
from typing import Optional, List, Dict

DB_FILE = "tx_storage.db"

class TxStorage:
    def __init__(self, user_id: int = 0):
        self.user_id = user_id
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._create_table()

    def _create_table(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS last_tx (
                user_id INTEGER PRIMARY KEY,
                last_timestamp TEXT
            )
        """)
        self.conn.commit()

    def load_last(self) -> Optional[str]:
        self.cursor.execute("SELECT last_timestamp FROM last_tx WHERE user_id = ?", (self.user_id,))
        row = self.cursor.fetchone()
        return row[0] if row else None

    def save_last(self, timestamp: str):
        self.cursor.execute("""
            INSERT OR REPLACE INTO last_tx (user_id, last_timestamp) VALUES (?, ?)
        """, (self.user_id, timestamp))
        self.conn.commit()

    def filter_new(self, deposits: List[Dict]) -> List[Dict]:
        last = self.load_last()
        if not last:
            return deposits
        return [d for d in deposits if d["block_timestamp"] > last]

    def reset(self):
        """Reset para desarrollo: borra tu registro y el archivo físico"""
        self.cursor.execute("DELETE FROM last_tx WHERE user_id = ?", (self.user_id,))
        self.conn.commit()
        
        try:
            self.conn.close()
            if os.path.exists(DB_FILE):
                os.remove(DB_FILE)
                print("DB BORRADA FÍSICAMENTE - reset completo")
        except Exception as e:
            print(f"Error: {e}")
        
        print(f"RESET COMPLETADO → user_id {self.user_id}")