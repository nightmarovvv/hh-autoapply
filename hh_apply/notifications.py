"""Звуковые и терминальные уведомления."""

from __future__ import annotations

import sys
import time


def beep() -> None:
    """Системный beep — работает на всех платформах."""
    sys.stdout.write("\a")
    sys.stdout.flush()


def alert_captcha() -> None:
    """Звуковой сигнал при капче — повторяется 3 раза."""
    for _ in range(3):
        beep()
        time.sleep(0.3)
