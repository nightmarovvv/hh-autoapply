"""Загрузка и валидация конфигурации."""

from __future__ import annotations

import sys
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
        "exclude_pattern": "",
        "exclude_company_pattern": "",
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

# Переменные для подстановки в cover letter
COVER_LETTER_VARS = {
    "{company}": "Название компании",
    "{position}": "Название вакансии",
    "{salary}": "Зарплата (если указана)",
}


def load_config(path: "str | Path") -> dict:
    """Загружает YAML конфиг и мержит с дефолтами.

    Обрабатывает: битый YAML, невалидные типы, отсутствующие секции.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        from rich.console import Console
        Console().print(f"[red]Ошибка в конфиге {path}:[/red]")
        Console().print(f"[red]{e}[/red]")
        Console().print("[dim]Проверьте синтаксис YAML или пересоздайте: hh-apply init[/dim]")
        sys.exit(1)
    except FileNotFoundError:
        from rich.console import Console
        Console().print(f"[red]Конфиг не найден: {path}[/red]")
        Console().print("[dim]Создайте: hh-apply init[/dim]")
        sys.exit(1)

    if not isinstance(raw, dict):
        raw = {}

    config = {}
    for section, defaults in DEFAULTS.items():
        user_section = raw.get(section, {})
        if not isinstance(user_section, dict):
            user_section = {}
        config[section] = {**defaults, **user_section}

    # Валидация типов
    _validate_config(config)

    # Раскрываем ~ в data_dir
    data_dir = Path(config["browser"]["data_dir"]).expanduser()
    config["browser"]["data_dir"] = str(data_dir)

    return config


def _validate_config(config: dict) -> None:
    """Приводит значения к правильным типам, исправляет невалидные."""
    apply_cfg = config.get("apply", {})

    # max_applications — должно быть int > 0
    try:
        val = int(apply_cfg.get("max_applications", 50))
        apply_cfg["max_applications"] = max(1, min(val, 500))
    except (TypeError, ValueError):
        apply_cfg["max_applications"] = 50

    # delay_min / delay_max — float >= 0
    for key, default in [("delay_min", 1.5), ("delay_max", 4.0)]:
        try:
            apply_cfg[key] = max(0.0, float(apply_cfg.get(key, default)))
        except (TypeError, ValueError):
            apply_cfg[key] = default

    # salary_from — int или None
    search_cfg = config.get("search", {})
    salary = search_cfg.get("salary_from")
    if salary is not None:
        try:
            search_cfg["salary_from"] = int(salary)
        except (TypeError, ValueError):
            search_cfg["salary_from"] = None

    # exclude_companies / exclude_keywords — должны быть списками
    filters_cfg = config.get("filters", {})
    for key in ("exclude_companies", "exclude_keywords"):
        val = filters_cfg.get(key, [])
        if not isinstance(val, list):
            filters_cfg[key] = [str(val)] if val else []


def render_cover_letter(template: str, vacancy) -> str:
    """Подставляет переменные {company}, {position}, {salary} в шаблон письма."""
    text = template
    text = text.replace("{company}", getattr(vacancy, "company", "") or "")
    text = text.replace("{position}", getattr(vacancy, "title", "") or "")
    salary = getattr(vacancy, "salary", None)
    text = text.replace("{salary}", salary if salary else "не указана")
    return text


def get_data_dir(config: dict) -> Path:
    """Возвращает путь к директории данных, создаёт при необходимости."""
    data_dir = Path(config["browser"]["data_dir"])
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        from rich.console import Console
        Console().print(f"[red]Нет доступа к папке: {data_dir}[/red]")
        Console().print("[dim]Проверьте права или укажите другой data_dir в конфиге[/dim]")
        sys.exit(1)
    return data_dir


def get_storage_path(config: dict) -> Path:
    return get_data_dir(config) / "storage_state.json"


def get_db_path(config: dict) -> Path:
    return get_data_dir(config) / "applications.db"
