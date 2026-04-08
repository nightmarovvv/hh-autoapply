"""Команда init — интерактивный визард настройки."""

from __future__ import annotations

from pathlib import Path

import click
import yaml
from InquirerPy import inquirer
from rich.console import Console
from rich.panel import Panel

from hh_apply.cli import main

# Справочники
AREAS = [
    ("Москва", 1),
    ("Санкт-Петербург", 2),
    ("Россия (вся)", 113),
    ("Новосибирск", 4),
    ("Екатеринбург", 3),
    ("Казань", 88),
    ("Краснодар", 53),
    ("Нижний Новгород", 66),
    ("Удалённо (без региона)", None),
]

EXPERIENCE = [
    ("Без опыта", "noExperience"),
    ("1-3 года", "between1And3"),
    ("3-6 лет", "between3And6"),
    ("Более 6 лет", "moreThan6"),
    ("Любой", None),
]

SCHEDULE = [
    ("Удалённая работа", "remote"),
    ("Полный день", "fullDay"),
    ("Сменный график", "shift"),
    ("Гибкий график", "flexible"),
    ("Вахта", "flyInFlyOut"),
]


@main.command(epilog="""
Примеры:
  hh-apply init                  Интерактивный визард
  hh-apply init -o python.yaml   Сохранить как python.yaml
  hh-apply init -o qa.yaml       Отдельный профиль для QA
""")
@click.option("--output", "-o", default="config.yaml", help="Имя файла конфига")
def init(output):
    """Настроить hh-apply через интерактивный визард."""
    console = Console()
    target = Path.cwd() / output

    existing_config = None
    edit_mode = False

    if target.exists():
        with open(target, "r", encoding="utf-8") as f:
            existing_config = yaml.safe_load(f) or {}

        console.print(f"[yellow]{output} уже существует.[/yellow]")
        console.print("[dim]Логин и куки в безопасности — хранятся отдельно в ~/.hh-apply/[/dim]\n")

        action = inquirer.select(
            message="Что сделать?",
            choices=["Редактировать текущий", "Создать новый", "Отмена"],
            default="Редактировать текущий",
        ).execute()

        if action == "Отмена":
            return
        if action == "Редактировать текущий":
            edit_mode = True

    _MISSING = object()

    def _get(section, key, fallback=""):
        if existing_config and edit_mode:
            val = existing_config.get(section, {}).get(key, _MISSING)
            if val is not _MISSING:
                return val
        return fallback

    console.print()
    console.print(Panel("[bold blue]hh-apply[/bold blue] — настройка", border_style="blue"))
    console.print()
    console.print("[dim]Подсказки:[/dim]")
    console.print("[dim]  Стрелки ↑↓  — выбрать вариант[/dim]")
    console.print("[dim]  Пробел      — отметить/снять (в списках с галочками)[/dim]")
    console.print("[dim]  Enter       — подтвердить выбор или пропустить (оставить пустым)[/dim]")
    console.print()

    # === 1. Поиск ===
    console.print("[bold]1. Поиск[/bold]\n")

    default_query = _get("search", "query", "python developer")
    query = inquirer.text(
        message="Поисковый запрос:",
        default=str(default_query),
    ).execute()

    # Регион — стрелочное меню
    current_area = _get("search", "area", None)
    default_area = "Удалённо (без региона)"
    if edit_mode:
        for name, aid in AREAS:
            if aid == current_area:
                default_area = name
                break
    area_name = inquirer.select(
        message="Регион:",
        choices=[name for name, _ in AREAS],
        default=default_area,
    ).execute()
    area_id = dict(AREAS)[area_name]

    # Зарплата
    default_salary = _get("search", "salary_from", "")
    salary_str = inquirer.text(
        message="Минимальная зарплата в рублях (пусто = без фильтра):",
        default=str(default_salary) if default_salary else "",
        validate=lambda x: x.strip() == "" or x.strip().isdigit(),
        invalid_message="Только цифры (напр. 150000) или пустое поле",
    ).execute()
    salary_from = int(salary_str) if salary_str.strip().isdigit() else None
    salary_only = False
    if salary_from:
        salary_only = inquirer.confirm(
            message="Только вакансии с указанной зарплатой?",
            default=True,
        ).execute()

    # Опыт — стрелочное меню
    current_exp = _get("search", "experience", None)
    default_exp = "Любой"
    if edit_mode:
        for name, val in EXPERIENCE:
            if val == current_exp:
                default_exp = name
                break
    exp_name = inquirer.select(
        message="Опыт работы:",
        choices=[name for name, _ in EXPERIENCE],
        default=default_exp,
    ).execute()
    experience = dict(EXPERIENCE)[exp_name]

    # График — checkbox (пробелом отмечаешь несколько)
    current_scheds = _get("search", "schedule", []) or []
    default_checked = []
    for name, val in SCHEDULE:
        if val in current_scheds:
            default_checked.append(name)

    sched_names = inquirer.checkbox(
        message="График (пробел — выбрать, Enter — подтвердить):",
        choices=[name for name, _ in SCHEDULE],
        default=default_checked if default_checked else None,
    ).execute()
    schedule = [dict(SCHEDULE)[n] for n in sched_names]

    # === 2. Фильтры ===
    console.print("\n[bold]2. Фильтры[/bold]\n")

    default_kw = ", ".join(_get("filters", "exclude_keywords", []) or [])
    exclude_kw = inquirer.text(
        message="Исключить слова из названий (через запятую):",
        default=default_kw,
    ).execute()
    exclude_keywords = [w.strip() for w in exclude_kw.split(",") if w.strip()]

    default_comp = ", ".join(_get("filters", "exclude_companies", []) or [])
    exclude_comp = inquirer.text(
        message="Исключить компании (через запятую):",
        default=default_comp,
    ).execute()
    exclude_companies = [c.strip() for c in exclude_comp.split(",") if c.strip()]

    default_pattern = _get("filters", "exclude_pattern", "")
    def _valid_regex(x):
        if not x.strip():
            return True
        try:
            import re
            re.compile(x.strip())
            return True
        except re.error:
            return False

    exclude_pattern = inquirer.text(
        message="Regex исключение по названию (напр. junior|стажёр|bitrix, Enter = пропустить):",
        default=str(default_pattern) if default_pattern else "",
        validate=_valid_regex,
        invalid_message="Неверный regex. Используйте | для ИЛИ (напр. junior|стажёр)",
    ).execute()

    default_company_pattern = _get("filters", "exclude_company_pattern", "")
    exclude_company_pattern = inquirer.text(
        message="Regex исключение по компании (напр. аутсорс|крипто, Enter = пропустить):",
        default=str(default_company_pattern) if default_company_pattern else "",
        validate=_valid_regex,
        invalid_message="Неверный regex. Используйте | для ИЛИ (напр. аутсорс|крипто)",
    ).execute()

    # === 3. Отклик ===
    console.print("\n[bold]3. Отклик[/bold]\n")

    default_max = _get("apply", "max_applications", 50)
    max_str = inquirer.text(
        message="Максимум откликов за запуск:",
        default=str(int(default_max)),
        validate=lambda x: x.isdigit() and int(x) > 0,
        invalid_message="Введите число > 0",
    ).execute()
    max_apps = int(max_str)

    default_use_letter = _get("apply", "use_cover_letter", True)
    use_cover_letter = inquirer.confirm(
        message="Использовать сопроводительное письмо?",
        default=bool(default_use_letter),
    ).execute()

    cover_letter = ""
    if use_cover_letter:
        default_letter = str(_get("apply", "cover_letter", "")).strip()
        console.print("[dim]  Переменные: {company}, {position}[/dim]")
        cover_letter = inquirer.text(
            message="Текст письма (Enter = шаблон по умолчанию):",
            default=default_letter if default_letter else "",
        ).execute()
        if not cover_letter.strip():
            cover_letter = "Здравствуйте!\n\nМеня заинтересовала вакансия {position} в {company}. Буду рад обсудить детали.\n\nС уважением"
            console.print("[dim]  Используется шаблон по умолчанию[/dim]")

    # === Собираем конфиг ===
    config = {
        "search": {"query": query},
        "filters": {
            "exclude_companies": exclude_companies,
            "exclude_keywords": exclude_keywords,
            "exclude_pattern": exclude_pattern.strip() if exclude_pattern else "",
            "exclude_company_pattern": exclude_company_pattern.strip() if exclude_company_pattern else "",
            "skip_foreign": False,
            "skip_test_vacancies": True,
        },
        "apply": {
            "max_applications": max_apps,
            "use_cover_letter": use_cover_letter,
            "cover_letter": cover_letter,
            "delay_min": 1.5,
            "delay_max": 4.0,
        },
        "browser": {
            "headless": False,
            "data_dir": "~/.hh-apply",
        },
    }

    if area_id:
        config["search"]["area"] = area_id
    if salary_from:
        config["search"]["salary_from"] = salary_from
        config["search"]["salary_only"] = salary_only
    if experience:
        config["search"]["experience"] = experience
    if schedule:
        config["search"]["schedule"] = schedule

    with open(target, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    console.print()
    console.print(Panel(
        f"[green]Конфиг сохранён:[/green] {target}\n\n"
        f"[bold]Следующий шаг:[/bold]\n"
        f"  [bold]hh-apply login[/bold]  — войти в hh.ru\n"
        f"  [bold]hh-apply run --dry-run[/bold] — пробный запуск",
        title="Готово",
        border_style="green",
    ))

    # Валидация: проверяем сколько вакансий
    _validate_config_search(config, console)


def _validate_config_search(config: dict, console: Console) -> None:
    """Проверяет количество вакансий по фильтрам (без браузера, через requests)."""
    try:
        from hh_apply.filters import build_search_url
        import requests

        search_url = build_search_url(config.get("search", {}))
        api_url = search_url.replace("https://hh.ru/search/vacancy", "https://api.hh.ru/vacancies")
        resp = requests.get(api_url, headers={"User-Agent": "hh-apply/1.0"}, timeout=10)
        if resp.ok:
            data = resp.json()
            found = data.get("found", 0)
            if found == 0:
                console.print("\n[yellow]Внимание: по вашим фильтрам не найдено вакансий.[/yellow]")
                console.print("[dim]Попробуйте расширить запрос или убрать фильтры.[/dim]")
            else:
                console.print(f"\n[dim]По вашим фильтрам найдено вакансий: {found}[/dim]")
    except Exception:
        pass
