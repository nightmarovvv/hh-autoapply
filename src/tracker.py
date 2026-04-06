"""SQLite трекер откликов.

Хранит vacancy_id, статус, дату. Дедупликация: повторно не откликаемся
ТОЛЬКО на успешные (sent, cover_letter_sent). Ошибки можно ретраить.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path


SUCCESS_STATUSES = ("sent", "cover_letter_sent")


class Tracker:
    def __init__(self, db_path: str):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self._init_db()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _init_db(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                vacancy_id TEXT PRIMARY KEY,
                title TEXT,
                company TEXT,
                status TEXT,
                applied_at TEXT
            )
        """)
        self.conn.commit()

    def is_applied(self, vacancy_id: str) -> bool:
        """Возвращает True только если отклик УСПЕШНО отправлен."""
        row = self.conn.execute(
            "SELECT 1 FROM applications WHERE vacancy_id = ? AND status IN (?, ?)",
            (vacancy_id, *SUCCESS_STATUSES),
        ).fetchone()
        return row is not None

    def record(self, vacancy_id: str, title: str, company: str, status: str):
        self.conn.execute(
            """INSERT OR REPLACE INTO applications
               (vacancy_id, title, company, status, applied_at)
               VALUES (?, ?, ?, ?, ?)""",
            (vacancy_id, title, company, status, datetime.now().isoformat()),
        )
        self.conn.commit()

    def stats(self) -> dict:
        rows = self.conn.execute(
            "SELECT status, COUNT(*) FROM applications GROUP BY status"
        ).fetchall()
        return dict(rows)

    def total(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) FROM applications").fetchone()
        return row[0] if row else 0

    def close(self):
        self.conn.close()
