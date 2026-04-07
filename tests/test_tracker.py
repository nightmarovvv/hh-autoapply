"""Тесты SQLite трекера откликов."""

import pytest
import tempfile
from pathlib import Path

from hh_apply.tracker import Tracker


@pytest.fixture
def tracker(tmp_path):
    db_path = tmp_path / "test.db"
    t = Tracker(db_path)
    yield t
    t.close()


class TestApplications:
    def test_record_and_check(self, tracker):
        tracker.record("1", "Dev", "Corp", "sent")
        assert tracker.is_applied("1") is True

    def test_not_applied(self, tracker):
        assert tracker.is_applied("999") is False

    def test_error_not_counted_as_applied(self, tracker):
        tracker.record("1", "Dev", "Corp", "error")
        assert tracker.is_applied("1") is False

    def test_stats(self, tracker):
        tracker.record("1", "Dev1", "Corp1", "sent")
        tracker.record("2", "Dev2", "Corp2", "sent")
        tracker.record("3", "Dev3", "Corp3", "error")
        st = tracker.stats()
        assert st["sent"] == 2
        assert st["error"] == 1

    def test_total(self, tracker):
        tracker.record("1", "Dev1", "Corp1", "sent")
        tracker.record("2", "Dev2", "Corp2", "error")
        assert tracker.total() == 2

    def test_get_by_status(self, tracker):
        tracker.record("1", "Dev1", "Corp1", "sent")
        tracker.record("2", "Dev2", "Corp2", "error")
        results = tracker.get_by_status("sent")
        assert len(results) == 1
        assert results[0]["vacancy_id"] == "1"

    def test_upsert(self, tracker):
        tracker.record("1", "Dev", "Corp", "error")
        tracker.record("1", "Dev", "Corp", "sent")
        assert tracker.total() == 1
        assert tracker.is_applied("1") is True

    def test_stats_by_day(self, tracker):
        tracker.record("1", "Dev", "Corp", "sent")
        tracker.record("2", "Dev", "Corp", "error")
        days = tracker.stats_by_day(7)
        assert len(days) >= 1
        assert days[0]["sent"] >= 1

    def test_get_all_applications(self, tracker):
        tracker.record("1", "Dev1", "Corp1", "sent")
        tracker.record("2", "Dev2", "Corp2", "error")
        all_apps = tracker.get_all_applications()
        assert len(all_apps) == 2


class TestSkipped:
    def test_save_and_get(self, tracker):
        tracker.save_skipped("1", "Test Dev", "Corp", "https://hh.ru/1", "test_required")
        results = tracker.get_skipped("test_required")
        assert len(results) == 1
        assert results[0]["title"] == "Test Dev"

    def test_remove_skipped(self, tracker):
        tracker.save_skipped("1", "Dev", "Corp", "url", "test_required")
        assert tracker.remove_skipped("1") is True
        assert tracker.remove_skipped("1") is False

    def test_clear_skipped(self, tracker):
        tracker.save_skipped("1", "Dev1", "Corp", "url", "test_required")
        tracker.save_skipped("2", "Dev2", "Corp", "url", "extra_steps")
        tracker.clear_skipped("test_required")
        assert len(tracker.get_skipped("test_required")) == 0
        assert len(tracker.get_skipped("extra_steps")) == 1

    def test_clear_all_skipped(self, tracker):
        tracker.save_skipped("1", "Dev1", "Corp", "url", "test_required")
        tracker.save_skipped("2", "Dev2", "Corp", "url", "extra_steps")
        tracker.clear_skipped()
        assert len(tracker.get_skipped()) == 0


class TestExport:
    def test_export_csv(self, tracker, tmp_path):
        tracker.record("1", "Dev1", "Corp1", "sent")
        tracker.record("2", "Dev2", "Corp2", "error")
        path = tmp_path / "out.csv"
        count = tracker.export_csv(path)
        assert count == 2
        content = path.read_text(encoding="utf-8")
        assert "vacancy_id" in content
        assert "Dev1" in content

    def test_export_json(self, tracker, tmp_path):
        tracker.record("1", "Dev1", "Corp1", "sent")
        path = tmp_path / "out.json"
        count = tracker.export_json(path)
        assert count == 1
        import json
        data = json.loads(path.read_text(encoding="utf-8"))
        assert len(data) == 1
        assert data[0]["title"] == "Dev1"

    def test_export_empty(self, tracker, tmp_path):
        assert tracker.export_csv(tmp_path / "out.csv") == 0
        assert tracker.export_json(tmp_path / "out.json") == 0

    def test_export_skipped_tests(self, tracker, tmp_path):
        tracker.save_skipped("1", "Test Dev", "Corp", "https://hh.ru/1", "test_required")
        path = tmp_path / "tests.txt"
        count = tracker.export_skipped_tests(path)
        assert count == 1
        assert "Test Dev" in path.read_text(encoding="utf-8")


class TestRawQuery:
    def test_execute_query(self, tracker):
        tracker.record("1", "Dev", "Corp", "sent")
        cols, rows = tracker.execute_query("SELECT * FROM applications")
        assert len(cols) == 5
        assert len(rows) == 1

    def test_invalid_query(self, tracker):
        with pytest.raises(Exception):
            tracker.execute_query("INVALID SQL")
