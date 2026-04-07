"""SQLite трекер откликов + пропущенные вакансии.

Таблицы:
- applications — отклики с дедупликацией
- skipped_vacancies — пропущенные с причиной (тесты, фильтры, ошибки)
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path


SUCCESS_STATUSES = ("sent", "cover_letter_sent", "letter_sent")


class Tracker:
    def __init__(self, db_path: "str | Path"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = str(db_path)
        self.conn = sqlite3.connect(self.db_path)
        self._init_db()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _init_db(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS applications (
                vacancy_id TEXT PRIMARY KEY,
                title TEXT,
                company TEXT,
                status TEXT,
                applied_at TEXT
            );

            CREATE TABLE IF NOT EXISTS skipped_vacancies (
                vacancy_id TEXT,
                title TEXT,
                company TEXT,
                url TEXT,
                reason TEXT,
                created_at TEXT,
                PRIMARY KEY (vacancy_id, reason)
            );
        """)
        self.conn.commit()

    # === Applications ===

    def is_applied(self, vacancy_id: str) -> bool:
        placeholders = ",".join("?" for _ in SUCCESS_STATUSES)
        row = self.conn.execute(
            f"SELECT 1 FROM applications WHERE vacancy_id = ? AND status IN ({placeholders})",
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

    def get_by_status(self, status: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT vacancy_id, title, company, applied_at FROM applications WHERE status = ?",
            (status,),
        ).fetchall()
        return [
            {"vacancy_id": r[0], "title": r[1], "company": r[2], "applied_at": r[3]}
            for r in rows
        ]

    # === Skipped Vacancies ===

    def save_skipped(self, vacancy_id: str, title: str, company: str, url: str, reason: str):
        self.conn.execute(
            """INSERT OR REPLACE INTO skipped_vacancies
               (vacancy_id, title, company, url, reason, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (vacancy_id, title, company, url, reason, datetime.now().isoformat()),
        )
        self.conn.commit()

    def get_skipped(self, reason: "str | None" = None) -> list[dict]:
        if reason:
            rows = self.conn.execute(
                "SELECT vacancy_id, title, company, url, reason, created_at FROM skipped_vacancies WHERE reason = ? ORDER BY created_at DESC",
                (reason,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT vacancy_id, title, company, url, reason, created_at FROM skipped_vacancies ORDER BY created_at DESC"
            ).fetchall()
        return [
            {"vacancy_id": r[0], "title": r[1], "company": r[2], "url": r[3], "reason": r[4], "created_at": r[5]}
            for r in rows
        ]

    def clear_skipped(self, reason: "str | None" = None):
        if reason:
            self.conn.execute("DELETE FROM skipped_vacancies WHERE reason = ?", (reason,))
        else:
            self.conn.execute("DELETE FROM skipped_vacancies")
        self.conn.commit()

    def export_skipped_tests(self, path: "str | Path") -> int:
        """Экспортирует тестовые вакансии в текстовый файл. Возвращает количество."""
        tests = self.get_skipped("test_required")
        if not tests:
            return 0

        lines = [
            "=== Вакансии с тестовым заданием ===",
            f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"Всего: {len(tests)}",
            "",
        ]
        for i, t in enumerate(tests, 1):
            lines.append(f"{i}. {t['title']} — {t['company']}")
            lines.append(f"   {t['url']}")
            lines.append("")

        Path(path).write_text("\n".join(lines), encoding="utf-8")
        return len(tests)

    # === Raw SQL ===

    def execute_query(self, sql: str) -> tuple:
        """Выполняет произвольный SQL. Возвращает (columns, rows)."""
        cursor = self.conn.execute(sql)
        columns = [d[0] for d in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        return columns, rows

    def close(self):
        self.conn.close()
