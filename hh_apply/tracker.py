"""SQLite трекер откликов + пропущенные вакансии.

Таблицы:
- applications — отклики с дедупликацией
- skipped_vacancies — пропущенные с причиной (тесты, фильтры, ошибки)
"""

from __future__ import annotations

import csv
import io
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path


SUCCESS_STATUSES = ("sent", "cover_letter_sent", "letter_sent")


class Tracker:
    def __init__(self, db_path: "str | Path"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = str(db_path)
        try:
            self.conn = sqlite3.connect(self.db_path, timeout=10)
        except sqlite3.OperationalError as e:
            if "locked" in str(e).lower():
                raise RuntimeError(
                    f"База данных заблокирована: {db_path}\n"
                    "Возможно, запущен другой экземпляр hh-apply. "
                    "Закройте его и попробуйте снова."
                ) from e
            raise

        # Проверка целостности (только если БД не пустая)
        try:
            tables = self.conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
            ).fetchone()
            if tables and tables[0] > 0:
                result = self.conn.execute("PRAGMA integrity_check").fetchone()
                if result and result[0] != "ok":
                    raise sqlite3.DatabaseError(f"DB corrupted: {result[0]}")
        except sqlite3.DatabaseError:
            self.conn.close()
            backup = Path(db_path).with_suffix(".db.bak")
            Path(db_path).rename(backup)
            self.conn = sqlite3.connect(self.db_path, timeout=10)

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

        # WAL mode для лучшей производительности
        self.conn.execute("PRAGMA journal_mode=WAL")

        # Индексы
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_skipped_vacancy_id ON skipped_vacancies(vacancy_id)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status)")
        self.conn.commit()

    # === Applications ===

    def is_applied(self, vacancy_id: str) -> bool:
        placeholders = ",".join("?" for _ in SUCCESS_STATUSES)
        row = self.conn.execute(
            f"SELECT 1 FROM applications WHERE vacancy_id = ? AND status IN ({placeholders})",
            (vacancy_id, *SUCCESS_STATUSES),
        ).fetchone()
        return row is not None

    def is_skipped(self, vacancy_id: str) -> bool:
        """Проверяет, была ли вакансия пропущена ранее."""
        row = self.conn.execute(
            "SELECT 1 FROM skipped_vacancies WHERE vacancy_id = ?",
            (vacancy_id,),
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

    def stats_by_day(self, days: int = 7) -> list[dict]:
        """Возвращает статистику по дням за последние N дней."""
        since = (datetime.now() - timedelta(days=days)).isoformat()
        rows = self.conn.execute(
            """SELECT DATE(applied_at) as day, status, COUNT(*) as cnt
               FROM applications
               WHERE applied_at >= ?
               GROUP BY day, status
               ORDER BY day""",
            (since,),
        ).fetchall()

        by_day: dict[str, dict] = {}
        for day, status, cnt in rows:
            if day not in by_day:
                by_day[day] = {"date": day, "sent": 0, "test": 0, "error": 0, "other": 0, "total": 0}
            if status in SUCCESS_STATUSES:
                by_day[day]["sent"] += cnt
            elif status == "test_required":
                by_day[day]["test"] += cnt
            elif status == "error":
                by_day[day]["error"] += cnt
            else:
                by_day[day]["other"] += cnt
            by_day[day]["total"] += cnt

        return list(by_day.values())

    def get_all_applications(self) -> list[dict]:
        """Возвращает все отклики для экспорта."""
        rows = self.conn.execute(
            "SELECT vacancy_id, title, company, status, applied_at FROM applications ORDER BY applied_at DESC"
        ).fetchall()
        return [
            {"vacancy_id": r[0], "title": r[1], "company": r[2], "status": r[3], "applied_at": r[4]}
            for r in rows
        ]

    def export_csv(self, path: "str | Path") -> int:
        """Экспортирует все отклики в CSV. Возвращает количество строк."""
        apps = self.get_all_applications()
        if not apps:
            return 0
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["vacancy_id", "title", "company", "status", "applied_at"])
            writer.writeheader()
            writer.writerows(apps)
        return len(apps)

    def export_json(self, path: "str | Path") -> int:
        """Экспортирует все отклики в JSON. Возвращает количество строк."""
        apps = self.get_all_applications()
        if not apps:
            return 0
        with open(path, "w", encoding="utf-8") as f:
            json.dump(apps, f, ensure_ascii=False, indent=2)
        return len(apps)

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

    def remove_skipped(self, vacancy_id: str) -> bool:
        """Удаляет конкретную вакансию из пропущенных. Возвращает True если удалено."""
        cursor = self.conn.execute(
            "DELETE FROM skipped_vacancies WHERE vacancy_id = ?", (vacancy_id,)
        )
        self.conn.commit()
        return cursor.rowcount > 0

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
