"""Тесты для stealth-модуля."""

from unittest.mock import MagicMock

from hh_apply.stealth import random_viewport, random_user_agent, human_wait, VIEWPORTS


def test_random_viewport():
    vp = random_viewport()
    assert "width" in vp and "height" in vp
    assert vp in VIEWPORTS


def test_random_user_agent():
    ua = random_user_agent()
    assert "Chrome" in ua
    assert "Mozilla" in ua


def test_human_wait_calls_timeout():
    """human_wait вызывает page.wait_for_timeout с variance."""
    page = MagicMock()

    calls = []
    for _ in range(100):
        human_wait(page, 1000, variance=0.3)
        calls.append(page.wait_for_timeout.call_args[0][0])

    # Все значения должны быть в пределах 700..1300
    assert all(700 <= c <= 1300 for c in calls)
    # Должна быть реальная вариативность (не все одинаковые)
    assert len(set(calls)) > 5
