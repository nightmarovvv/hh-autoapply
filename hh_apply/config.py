"""Загрузка и валидация конфигурации."""

from __future__ import annotations

from pathlib import Path

import yaml


DEFAULTS = {
    "search": {
        "query": "",
        "area": None,
        "salary_from": None,
        "salary_only": False,
        "experience": None,
        "employment": [],
        "schedule": [],
        "search_period": None,
        "order_by": "relevance",
    },
    "filters": {
        "exclude_companies": [],
        "exclude_keywords": [],
        "skip_foreign": False,
        "skip_test_vacancies": True,
    },
    "apply": {
        "max_applications": 50,
        "cover_letter": "",
        "use_cover_letter": True,
        "delay_min": 1.5,
        "delay_max": 4.0,
    },
    "browser": {
        "headless": False,
        "proxy": None,
        "data_dir": "~/.hh-apply",
    },
}


def load_config(path: "str | Path") -> dict:
    """Загружает YAML конфиг и мержит с дефолтами."""
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    config = {}
    for section, defaults in DEFAULTS.items():
        user_section = raw.get(section, {})
        if not isinstance(user_section, dict):
            user_section = {}
        config[section] = {**defaults, **user_section}

    # Раскрываем ~ в data_dir
    data_dir = Path(config["browser"]["data_dir"]).expanduser()
    config["browser"]["data_dir"] = str(data_dir)

    return config


def get_data_dir(config: dict) -> Path:
    """Возвращает путь к директории данных, создаёт при необходимости."""
    data_dir = Path(config["browser"]["data_dir"])
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_storage_path(config: dict) -> Path:
    return get_data_dir(config) / "storage_state.json"


def get_db_path(config: dict) -> Path:
    return get_data_dir(config) / "applications.db"
