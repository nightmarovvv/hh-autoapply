"""Тесты генерации отчётов."""

import pytest
from hh_apply.report import SessionReport


class TestSessionReport:
    def test_empty_report(self):
        r = SessionReport()
        assert r.sent == 0
        assert r.filtered == 0
        assert len(r.errors) == 0
        assert len(r.results) == 0

    def test_sent_count(self):
        r = SessionReport()
        r.add("1", "Dev1", "Corp1", "sent")
        r.add("2", "Dev2", "Corp2", "cover_letter_sent")
        assert r.sent == 2

    def test_cover_letter_count(self):
        r = SessionReport()
        r.add("1", "Dev1", "Corp1", "sent")
        r.add("2", "Dev2", "Corp2", "cover_letter_sent")
        assert r.cover_letter_sent == 1

    def test_filtered_count(self):
        r = SessionReport()
        r.add("1", "Dev1", "Corp1", "filtered")
        r.add("2", "Dev2", "Corp2", "filtered")
        assert r.filtered == 2

    def test_errors_list(self):
        r = SessionReport()
        r.add("1", "Dev1", "Corp1", "error")
        assert len(r.errors) == 1
        assert r.errors[0].vacancy_id == "1"

    def test_test_required_list(self):
        r = SessionReport()
        r.add("1", "Dev1", "Corp1", "test_required")
        assert len(r.test_required) == 1

    def test_extra_steps_list(self):
        r = SessionReport()
        r.add("1", "Dev1", "Corp1", "extra_steps")
        assert len(r.extra_steps) == 1

    def test_already_applied(self):
        r = SessionReport()
        r.add("1", "Dev1", "Corp1", "already_applied")
        assert r.already_applied == 1

    def test_elapsed(self):
        r = SessionReport()
        assert r.elapsed >= 0

    def test_mixed_results(self):
        r = SessionReport()
        r.add("1", "D1", "C1", "sent")
        r.add("2", "D2", "C2", "cover_letter_sent")
        r.add("3", "D3", "C3", "test_required")
        r.add("4", "D4", "C4", "error")
        r.add("5", "D5", "C5", "filtered")
        assert len(r.results) == 5
        assert r.sent == 2
        assert len(r.test_required) == 1
        assert len(r.errors) == 1
        assert r.filtered == 1
