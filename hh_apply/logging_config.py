"""Настройка логирования: файл + консоль."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(data_dir: "str | Path", verbose: bool = False) -> None:
    """Настраивает логирование в файл и консоль.

    Файл: ~/.hh-apply/logs/hh-apply.log (5MB, 3 бекапа)
    Консоль: WARNING+ (не мешает Rich UI)
    verbose: переключает консоль на DEBUG
    """
    data_dir = Path(data_dir)
    log_dir = data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger("hh_apply")
    if root.handlers:
        return  # Already configured
    root.setLevel(logging.DEBUG)

    # File handler — всё в файл
    fh = RotatingFileHandler(
        log_dir / "hh-apply.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s %(name)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    root.addHandler(fh)

    # Console handler — только важное
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG if verbose else logging.WARNING)
    ch.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    root.addHandler(ch)
