"""Звуковые и терминальные уведомления."""

from __future__ import annotations

import platform
import subprocess
import sys
import time


def beep() -> None:
    """Системный звук — кросс-платформенный с fallback."""
    system = platform.system()

    if system == "Darwin":
        # macOS: afplay с системным звуком (работает всегда)
        try:
            subprocess.Popen(
                ["afplay", "/System/Library/Sounds/Glass.aiff"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
        except Exception:
            pass

    elif system == "Windows":
        # Windows: встроенный winsound
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            return
        except Exception:
            pass

    elif system == "Linux":
        # Linux: paplay (PulseAudio) или aplay (ALSA)
        for cmd in [
            ["paplay", "/usr/share/sounds/freedesktop/stereo/bell.oga"],
            ["aplay", "/usr/share/sounds/freedesktop/stereo/bell.oga"],
        ]:
            try:
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
            except Exception:
                continue

    # Fallback: BEL character (может не с��аботать, но хуже не будет)
    sys.stdout.write("\a")
    sys.stdout.flush()


def alert_captcha() -> None:
    """Звуковой сигнал при капче — повторяется 3 раза."""
    for _ in range(3):
        beep()
        time.sleep(0.5)
