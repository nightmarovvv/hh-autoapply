"""CLI-интерфейс hh-apply с InquirerPy для интерактивных меню."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import click
import yaml
from InquirerPy import inquirer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from hh_apply import __version__

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


WELCOME_TEXT = f"""[bold blue]
  _     _                           _
 | |__ | |__         __ _ _ __  _ __| |_   _
 | '_ \\| '_ \\ ___  / _` | '_ \\| '_ \\ | | | |
 | | | | | | |___|  (_| | |_) | |_) | | |_| |
 |_| |_|_| |_|      \\__,_| .__/| .__/|_|\\__, |
                          |_|   |_|      |___/
[/bold blue]
  [dim]v{__version__} — автоматические отклики на hh.ru[/dim]

[bold]Быстрый старт:[/bold]
  [green]1.[/green] hh-apply init        Настроить поиск и фильтры
  [green]2.[/green] hh-apply login       Войти в hh.ru (откроется браузер)
  [green]3.[/green] hh-apply run         Запустить отклики

[bold]Утилиты:[/bold]
  hh-apply stats         Статистика откликов
  hh-apply responses     Мониторинг ответов рекрутеров
  hh-apply boost         Поднять резюме в поиске
  hh-apply schedule      Настроить автозапуск
  hh-apply done          Убрать тестовую вакансию
  hh-apply query         SQL-запросы к базе
  hh-apply doctor        Диагностика окружения
  hh-apply completions   Автодополнение для shell

[dim]Подробнее: hh-apply <команда> --help[/dim]"""


class RichHelpGroup(click.Group):
    """Click Group с Rich-форматированием help."""

    def format_help(self, ctx, formatter):
        Console().print(WELCOME_TEXT)


@click.group(cls=RichHelpGroup, invoke_without_command=True)
@click.version_option(__version__, prog_name="hh-apply")
@click.pass_context
def main(ctx):
    """hh-apply — массовые автоматические отклики на вакансии hh.ru"""
    if ctx.invoked_subcommand is None:
        Console().print(WELCOME_TEXT)


# ==================== INIT ====================

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
        console.print("[dim]  Переменные: {company}, {position}, {salary}[/dim]")
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


# ==================== LOGIN ====================

@main.command(epilog="""
Примеры:
  hh-apply login                 Войти (выбор способа)
  hh-apply login -c qa.yaml     Войти с другим конфигом
""")
@click.option("--config", "-c", default="config.yaml", help="Путь к конфигу")
def login(config):
    """Войти в hh.ru и сохранить сессию."""
    from hh_apply.config import load_config, get_storage_path
    from hh_apply.auth import login_native_browser

    console = Console()

    if not Path(config).exists():
        console.print(f"[red]Конфиг не найден: {config}[/red]")
        console.print("Запустите: [bold]hh-apply init[/bold]")
        return

    cfg = load_config(config)
    storage_path = get_storage_path(cfg)
    storage_path.parent.mkdir(parents=True, exist_ok=True)

    console.print("[bold blue]hh-apply login[/bold blue]\n")

    success = login_native_browser(cfg, console)

    if success:
        console.print(f"\n[green]Сессия сохранена![/green]")
        console.print("\n[bold]Следующий шаг:[/bold]")
        console.print("  [bold]hh-apply run --dry-run[/bold] — пробный запуск")
        console.print("  [bold]hh-apply run[/bold]           — боевые отклики")
    else:
        console.print("\n[red]Логин не подтверждён.[/red]")
        console.print("[dim]Убедитесь что вы полностью залогинились в браузере перед нажатием Enter.[/dim]")


# ==================== RUN ====================

@main.command(epilog="""
Примеры:
  hh-apply run                        Интерактивный режим
  hh-apply run --limit 10             Максимум 10 откликов
  hh-apply run --dry-run              Только посмотреть вакансии
  hh-apply run -c qa.yaml --headless  С другим профилем, без окна
  hh-apply run -e "junior|стажёр"     Исключить по regex
  hh-apply run -r report.txt          Сохранить отчёт в файл
""")
@click.option("--config", "-c", default="config.yaml", help="Путь к конфигу")
@click.option("--limit", "-l", type=int, help="Макс. количество откликов")
@click.option("--headless", is_flag=True, help="Скрытый режим браузера")
@click.option("--dry-run", is_flag=True, help="Только поиск, без откликов")
@click.option("--report", "-r", type=str, help="Сохранить отчёт в файл")
@click.option("--exclude", "-e", type=str, help="Regex исключение (напр. junior|стажёр)")
def run(config, limit, headless, dry_run, report, exclude):
    """Запустить автоотклики."""
    from hh_apply.config import load_config
    from hh_apply.runner import run as do_run

    console = Console()

    if not Path(config).exists():
        console.print(f"[red]Конфиг не найден: {config}[/red]")
        console.print("Запустите: [bold]hh-apply init[/bold]")
        return

    cfg = load_config(config)

    # Интерактивный режим если нет аргументов
    if not any([limit, headless, dry_run, report, exclude]):
        console.print("[bold blue]hh-apply run[/bold blue]\n")

        limit_str = inquirer.text(
            message="Сколько откликов? (Enter = из конфига)",
            default="",
        ).execute()
        if limit_str.strip().isdigit():
            limit = int(limit_str.strip())

        dry_run = inquirer.confirm(
            message="Пробный режим (без откликов)?",
            default=False,
        ).execute()

        exclude_input = inquirer.text(
            message="Regex исключение (Enter = пропустить):",
            default="",
        ).execute()
        if exclude_input.strip():
            exclude = exclude_input.strip()

        console.print()

    if limit:
        cfg["apply"]["max_applications"] = limit
    if headless:
        cfg["browser"]["headless"] = True

    do_run(cfg, dry_run=dry_run, report_path=report, exclude_pattern=exclude)


# ==================== STATS ====================

@main.command(epilog="""
Примеры:
  hh-apply stats                 Показать статистику
  hh-apply stats --csv -o out.csv  Экспорт в CSV
  hh-apply stats --json          Экспорт в JSON (stdout)
  hh-apply stats -c qa.yaml     Статистика по другому профилю
""")
@click.option("--config", "-c", default="config.yaml", help="Путь к конфигу")
@click.option("--csv", "csv_export", is_flag=True, help="Экспорт в CSV")
@click.option("--json", "json_export", is_flag=True, help="Экспорт в JSON")
@click.option("-o", "--output", type=str, help="Файл для экспорта")
def stats(config, csv_export, json_export, output):
    """Показать статистику откликов."""
    from hh_apply.config import load_config, get_db_path
    from hh_apply.tracker import Tracker
    import json as json_module

    console = Console()
    cfg = load_config(config)
    db_path = get_db_path(cfg)

    if not db_path.exists():
        console.print("[yellow]Нет данных. Запустите: hh-apply run[/yellow]")
        return

    with Tracker(db_path) as tracker:
        # CSV экспорт
        if csv_export:
            out = output or "applications.csv"
            count = tracker.export_csv(out)
            console.print(f"[green]Экспорт в CSV: {out} ({count} строк)[/green]")
            return

        # JSON экспорт
        if json_export:
            apps = tracker.get_all_applications()
            if output:
                tracker.export_json(output)
                console.print(f"[green]Экспорт в JSON: {output} ({len(apps)} строк)[/green]")
            else:
                print(json_module.dumps(apps, ensure_ascii=False, indent=2))
            return

        st = tracker.stats()
        total = tracker.total()

        # Основная таблица с цветами
        table = Table(title="Статистика откликов hh-apply", border_style="blue")
        table.add_column("Статус", style="bold")
        table.add_column("Кол-во", justify="right")
        table.add_column("", width=20)  # ASCII bar

        names = {
            "sent": ("[green]Отправлен[/green]", "green"),
            "cover_letter_sent": ("[green]С письмом[/green]", "green"),
            "letter_sent": ("[green]С письмом[/green]", "green"),
            "letter_required": ("[yellow]Требует письмо[/yellow]", "yellow"),
            "test_required": ("[yellow]Тестовое[/yellow]", "yellow"),
            "extra_steps": ("[yellow]Доп. вопросы[/yellow]", "yellow"),
            "already_applied": ("[dim]Уже откликались[/dim]", "dim"),
            "error": ("[red]Ошибка[/red]", "red"),
            "filtered": ("[dim]Отфильтровано[/dim]", "dim"),
            "captcha": ("[yellow]Капча[/yellow]", "yellow"),
        }

        for status, count in sorted(st.items(), key=lambda x: x[1], reverse=True):
            name_info = names.get(status, (status, "white"))
            bar_len = int(count / max(total, 1) * 20) if total > 0 else 0
            color = name_info[1]
            bar = f"[{color}]{'█' * bar_len}[/{color}]{'░' * (20 - bar_len)}"
            table.add_row(name_info[0], str(count), bar)

        table.add_section()
        table.add_row("[bold]Всего[/bold]", f"[bold]{total}[/bold]", "")
        console.print(table)

        # По дням
        daily = tracker.stats_by_day(7)
        if daily:
            console.print()
            day_table = Table(title="Последние 7 дней", border_style="dim")
            day_table.add_column("Дата", style="dim")
            day_table.add_column("Отправлено", style="green", justify="right")
            day_table.add_column("Тесты", style="yellow", justify="right")
            day_table.add_column("Ошибки", style="red", justify="right")
            day_table.add_column("Всего", style="bold", justify="right")

            for d in daily:
                day_table.add_row(
                    d["date"],
                    str(d["sent"]),
                    str(d["test"]),
                    str(d["error"]),
                    str(d["total"]),
                )
            console.print(day_table)


# ==================== DONE ====================

@main.command(epilog="""
Примеры:
  hh-apply done              Интерактивный выбор
  hh-apply done 12345678     По ID
  hh-apply done all          Очистить все
""")
@click.option("--config", "-c", default="config.yaml", help="Путь к конфигу")
@click.argument("vacancy_id", required=False)
def done(config, vacancy_id):
    """Убрать тестовую вакансию из списка."""
    from hh_apply.config import load_config, get_db_path, get_data_dir
    from hh_apply.tracker import Tracker

    console = Console()
    cfg = load_config(config)
    db_path = get_db_path(cfg)

    if not db_path.exists():
        console.print("[yellow]Нет данных.[/yellow]")
        return

    with Tracker(db_path) as tracker:
        test_path = get_data_dir(cfg) / "test_vacancies.txt"

        if vacancy_id == "all":
            tracker.clear_skipped("test_required")
            tracker.export_skipped_tests(test_path)
            console.print("[green]Все тестовые удалены.[/green]")
            return

        if vacancy_id:
            if tracker.remove_skipped(vacancy_id):
                console.print(f"[green]Вакансия {vacancy_id} убрана.[/green]")
            else:
                console.print(f"[yellow]Не найдена: {vacancy_id}[/yellow]")
            tracker.export_skipped_tests(test_path)
            return

        # Интерактивный — стрелочное меню
        tests = tracker.get_skipped("test_required")
        if not tests:
            console.print("[dim]Нет тестовых вакансий.[/dim]")
            return

        choices = [
            f"{t['title'][:50]} — {t['company'][:20]}  ({t['vacancy_id']})"
            for t in tests
        ]
        choices.append("Очистить все")
        choices.append("Отмена")

        selected = inquirer.select(
            message=f"Тестовые вакансии ({len(tests)} шт.):",
            choices=choices,
        ).execute()

        if selected == "Отмена":
            return
        if selected == "Очистить все":
            tracker.clear_skipped("test_required")
            console.print("[green]Все тестовые удалены.[/green]")
        else:
            # Находим ID
            idx = choices.index(selected)
            vid = tests[idx]["vacancy_id"]
            tracker.remove_skipped(vid)
            console.print(f"[green]Убрано: {tests[idx]['title']}[/green]")

        tracker.export_skipped_tests(test_path)


# ==================== API-LOGIN ====================

@main.command(name="api-login", epilog="""
Примеры:
  hh-apply api-login            OAuth через браузер
  hh-apply api-login -c qa.yaml С другим профилем
""")
@click.option("--config", "-c", default="config.yaml", help="Путь к конфигу")
def api_login(config):
    """OAuth авторизация для API-команд (whoami, boost)."""
    from urllib.parse import parse_qs, urlsplit
    from hh_apply.config import load_config, get_data_dir
    from hh_apply.api_client import HHApiClient
    from patchright.sync_api import sync_playwright

    console = Console()
    cfg = load_config(config)
    data_dir = get_data_dir(cfg)
    client = HHApiClient(data_dir / "api_token.json")

    console.print("[bold blue]hh-apply api-login[/bold blue]\n")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Linux; Android 14; SM-A556B) AppleWebKit/537.36 Chrome/136.0.0.0 Mobile Safari/537.36",
            viewport={"width": 412, "height": 915},
            is_mobile=True,
        )
        page = context.new_page()

        auth_code = None

        def handle_request(request):
            nonlocal auth_code
            url = request.url
            if url.startswith("hhandroid://"):
                sp = urlsplit(url)
                codes = parse_qs(sp.query).get("code", [])
                if codes:
                    auth_code = codes[0]

        page.on("request", handle_request)
        page.goto(client.authorize_url)

        console.print("Залогиньтесь в браузере.\n")

        try:
            for _ in range(300):
                page.wait_for_timeout(1000)
                if auth_code:
                    break
            else:
                if not auth_code:
                    input(">>> Нажмите Enter если залогинились: ")
        except (EOFError, KeyboardInterrupt):
            browser.close()
            return

        browser.close()

    if not auth_code:
        console.print("[red]Не удалось получить OAuth код.[/red]")
        return

    client.exchange_code(auth_code)
    console.print("[green]API авторизация успешна![/green]")
    console.print("Доступны: [bold]hh-apply whoami[/bold], [bold]hh-apply boost[/bold]")


# ==================== WHOAMI ====================

@main.command(epilog="""
Примеры:
  hh-apply whoami               Информация об аккаунте
  hh-apply whoami -c qa.yaml    С другим профилем
""")
@click.option("--config", "-c", default="config.yaml", help="Путь к конфигу")
def whoami(config):
    """Проверить аккаунт: ID, имя, резюме, просмотры.

    \b
    Требует: hh-apply api-login
    """
    from hh_apply.config import load_config, get_data_dir
    from hh_apply.api_client import HHApiClient

    console = Console()
    cfg = load_config(config)
    client = HHApiClient(get_data_dir(cfg) / "api_token.json")

    if not client.is_authenticated:
        console.print("[red]Запустите: hh-apply api-login[/red]")
        return

    try:
        me = client.whoami()
    except Exception as e:
        console.print(f"[red]Ошибка: {e}[/red]")
        return

    name = " ".join(filter(None, [me.get("last_name"), me.get("first_name"), me.get("middle_name")])) or "Аноним"
    c = me.get("counters", {})
    console.print(
        f"\U0001f194 {me.get('id', '?')} {name} "
        f"[ \U0001f4c4 {c.get('resumes_count', 0)} "
        f"| \U0001f441\ufe0f +{c.get('new_resume_views', 0)} "
        f"| \u2709\ufe0f +{c.get('unread_negotiations', 0)} ]"
    )


# ==================== BOOST ====================

@main.command(epilog="""
Примеры:
  hh-apply boost                Поднять все резюме
  hh-apply boost -c qa.yaml    С другим профилем
""")
@click.option("--config", "-c", default="config.yaml", help="Путь к конфигу")
def boost(config):
    """Поднять все резюме в поиске.

    \b
    Требует: hh-apply api-login
    """
    from hh_apply.config import load_config, get_data_dir
    from hh_apply.api_client import HHApiClient

    console = Console()
    cfg = load_config(config)
    client = HHApiClient(get_data_dir(cfg) / "api_token.json")

    if not client.is_authenticated:
        console.print("[red]Запустите: hh-apply api-login[/red]")
        return

    try:
        resumes = client.get_resumes()
    except Exception as e:
        console.print(f"[red]Ошибка: {e}[/red]")
        return

    if not resumes:
        console.print("[yellow]Нет резюме[/yellow]")
        return

    for resume in resumes:
        if resume.get("status", {}).get("id") != "published":
            continue
        if not resume.get("can_publish_or_update"):
            console.print(f"[yellow]Нельзя обновить: {resume.get('title', '?')}[/yellow]")
            continue
        try:
            client.boost_resume(resume["id"])
            console.print(f"\u2705 Обновлено {resume.get('alternate_url', '')} — {resume.get('title', '?')}")
        except Exception as e:
            console.print(f"[red]Ошибка: {e}[/red]")


# ==================== RESPONSES ====================

@main.command(epilog="""
Примеры:
  hh-apply responses             Посмотреть ответы рекрутеров
  hh-apply responses -c qa.yaml  С другим профилем
""")
@click.option("--config", "-c", default="config.yaml", help="Путь к конфигу")
def responses(config):
    """Мониторинг ответов рекрутеров (просмотры, приглашения, отказы)."""
    from hh_apply.config import load_config, get_data_dir
    from hh_apply.api_client import HHApiClient

    console = Console()
    cfg = load_config(config)
    client = HHApiClient(get_data_dir(cfg) / "api_token.json")

    if not client.is_authenticated:
        console.print("[red]Запустите: hh-apply api-login[/red]")
        return

    try:
        _show_responses(client, console)
    except Exception as e:
        console.print(f"[red]Ошибка: {e}[/red]")
        console.print("[dim]Попробуйте: hh-apply api-login[/dim]")


def _show_responses(client, console: Console) -> None:
    """Загружает и показывает ответы рекрутеров через API."""
    # Получаем список negotiations по статусам
    statuses = {
        "Приглашения": "invitation",
        "Отказы": "discard",
        "Ответы": "response",
    }

    total_apps = 0
    total_invitations = 0
    total_discards = 0

    results = {}

    for label, status in statuses.items():
        try:
            resp = client.get(f"/negotiations?status={status}&per_page=0")
            count = resp.get("found", 0)
            results[label] = count
            if status == "invitation":
                total_invitations = count
            elif status == "discard":
                total_discards = count
        except Exception:
            results[label] = "?"

    # Общее количество откликов
    try:
        resp = client.get("/negotiations?per_page=0")
        total_apps = resp.get("found", 0)
    except Exception:
        total_apps = 0

    # Красивая таблица
    table = Table(title="Ответы рекрутеров", border_style="blue")
    table.add_column("Метрика", style="bold")
    table.add_column("Кол-во", justify="right")

    table.add_row("[bold]Всего откликов[/bold]", str(total_apps))
    table.add_row("[green]Приглашения[/green]", str(results.get("Приглашения", "?")))
    table.add_row("[red]Отказы[/red]", str(results.get("Отказы", "?")))
    table.add_row("[yellow]Ответы[/yellow]", str(results.get("Ответы", "?")))

    console.print(table)

    # Конверсия
    if total_apps > 0 and isinstance(total_invitations, int):
        rate = total_invitations / total_apps * 100
        console.print(f"\n[dim]Конверсия: {rate:.1f}% приглашений из {total_apps} откликов[/dim]")


# ==================== SCHEDULE ====================

@main.command(epilog="""
Примеры:
  hh-apply schedule set 09:00            Запуск каждый день в 9:00
  hh-apply schedule set 09:00 --weekdays Только будни
  hh-apply schedule boost 4              Boost резюме каждые 4 часа
  hh-apply schedule status               Показать текущее расписание
  hh-apply schedule remove               Удалить расписание
""")
@click.argument("action", type=click.Choice(["set", "boost", "status", "remove"]))
@click.argument("value", required=False)
@click.option("--config", "-c", default="config.yaml", help="Путь к конфигу")
@click.option("--weekdays", is_flag=True, help="Только будни (пн-пт)")
def schedule(action, value, config, weekdays):
    """Настроить автозапуск по расписанию (через crontab)."""
    console = Console()

    if action == "status":
        _schedule_status(console)
        return

    if action == "remove":
        _schedule_remove(console)
        return

    if action == "set":
        if not value:
            console.print("[red]Укажите время: hh-apply schedule set 09:00[/red]")
            return
        _schedule_set(value, config, weekdays, console)
        return

    if action == "boost":
        hours = int(value) if value and value.isdigit() else 4
        _schedule_boost(hours, config, console)
        return


def _schedule_set(time_str: str, config_path: str, weekdays: bool, console: Console) -> None:
    """Добавляет cron-задачу для hh-apply run."""
    import subprocess

    parts = time_str.split(":")
    if len(parts) != 2:
        console.print("[red]Формат: HH:MM (напр. 09:00)[/red]")
        return

    hour, minute = parts[0], parts[1]
    try:
        h, m = int(hour), int(minute)
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError
    except ValueError:
        console.print("[red]Некорректное время. Формат: HH:MM (напр. 09:00)[/red]")
        return

    dow = "1-5" if weekdays else "*"
    config_abs = str(Path(config_path).resolve())
    cmd = f'cd "{Path.cwd()}" && hh-apply run --headless -c "{config_abs}"'
    cron_line = f"{minute} {hour} * * {dow} {cmd}"

    # Добавляем в crontab
    try:
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        existing = result.stdout if result.returncode == 0 else ""
        # Удаляем старые записи hh-apply run
        lines = [l for l in existing.splitlines() if "hh-apply run" not in l]
        lines.append(cron_line)
        new_crontab = "\n".join(lines) + "\n"
        subprocess.run(["crontab", "-"], input=new_crontab, text=True, check=True)
        console.print(f"[green]Расписание установлено: {time_str} {'(будни)' if weekdays else '(ежедневно)'}[/green]")
        console.print(f"[dim]{cron_line}[/dim]")
    except FileNotFoundError:
        console.print("[yellow]crontab недоступен. На Windows используйте Планировщик задач.[/yellow]")
        console.print(f"[dim]Команда: {cmd}[/dim]")
    except Exception as e:
        console.print(f"[red]Ошибка: {e}[/red]")


def _schedule_boost(hours: int, config_path: str, console: Console) -> None:
    """Добавляет cron-задачу для hh-apply boost."""
    import subprocess

    if hours < 1 or hours > 24:
        console.print("[red]Интервал: от 1 до 24 часов.[/red]")
        return

    config_abs = str(Path(config_path).resolve())
    cmd = f'cd "{Path.cwd()}" && hh-apply boost -c "{config_abs}"'
    cron_line = f"0 */{hours} * * * {cmd}"

    try:
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        existing = result.stdout if result.returncode == 0 else ""
        lines = [l for l in existing.splitlines() if "hh-apply boost" not in l]
        lines.append(cron_line)
        new_crontab = "\n".join(lines) + "\n"
        subprocess.run(["crontab", "-"], input=new_crontab, text=True, check=True)
        console.print(f"[green]Auto-boost установлен: каждые {hours} часа[/green]")
        console.print(f"[dim]{cron_line}[/dim]")
    except FileNotFoundError:
        console.print("[yellow]crontab недоступен.[/yellow]")
        console.print(f"[dim]Команда: {cmd}[/dim]")
    except Exception as e:
        console.print(f"[red]Ошибка: {e}[/red]")


def _schedule_status(console: Console) -> None:
    """Показывает текущие cron-задачи hh-apply."""
    import subprocess

    try:
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        if result.returncode != 0:
            console.print("[dim]Нет crontab записей.[/dim]")
            return

        lines = [l for l in result.stdout.splitlines() if "hh-apply" in l]
        if not lines:
            console.print("[dim]Нет запланированных задач hh-apply.[/dim]")
            return

        table = Table(title="Расписание hh-apply", border_style="blue")
        table.add_column("Задача", style="bold")
        table.add_column("Cron")

        for line in lines:
            if "hh-apply run" in line:
                table.add_row("[green]Автоотклики[/green]", line.strip())
            elif "hh-apply boost" in line:
                table.add_row("[yellow]Auto-boost[/yellow]", line.strip())
            else:
                table.add_row("Другое", line.strip())

        console.print(table)
    except FileNotFoundError:
        console.print("[yellow]crontab недоступен.[/yellow]")


def _schedule_remove(console: Console) -> None:
    """Удаляет все cron-задачи hh-apply."""
    import subprocess

    try:
        result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        if result.returncode != 0:
            console.print("[dim]Нет crontab записей.[/dim]")
            return

        lines = [l for l in result.stdout.splitlines() if "hh-apply" not in l]
        new_crontab = "\n".join(lines) + "\n" if lines else ""

        if new_crontab.strip():
            subprocess.run(["crontab", "-"], input=new_crontab, text=True, check=True)
        else:
            subprocess.run(["crontab", "-r"], check=True)

        console.print("[green]Расписание hh-apply удалено.[/green]")
    except FileNotFoundError:
        console.print("[yellow]crontab недоступен.[/yellow]")
    except Exception as e:
        console.print(f"[red]Ошибка: {e}[/red]")


# ==================== QUERY ====================

@main.command(epilog="""
Примеры:
  hh-apply query "SELECT * FROM applications"
  hh-apply query "SELECT * FROM skipped_vacancies"
  hh-apply query "SELECT * FROM applications" --csv -o out.csv
  hh-apply query "SELECT company, COUNT(*) c FROM applications GROUP BY company ORDER BY c DESC"
""")
@click.option("--config", "-c", default="config.yaml", help="Путь к конфигу")
@click.option("--csv", "csv_export", is_flag=True, help="Экспорт в CSV")
@click.option("-o", "--output", type=str, help="Файл для экспорта")
@click.argument("sql", required=False)
def query(config, csv_export, output, sql):
    """SQL-запросы к базе данных."""
    import csv as csv_module
    import io
    from hh_apply.config import load_config, get_db_path
    from hh_apply.tracker import Tracker

    console = Console()
    cfg = load_config(config)
    db_path = get_db_path(cfg)

    if not db_path.exists():
        console.print("[yellow]Нет данных.[/yellow]")
        return

    if not sql:
        console.print("[dim]Таблицы: applications, skipped_vacancies[/dim]")
        console.print('[dim]Пример: hh-apply query "SELECT * FROM applications"[/dim]')
        return

    # Защита от случайного DELETE/DROP
    if not sql.strip().upper().startswith("SELECT"):
        console.print("[red]Разрешены только SELECT запросы.[/red]")
        console.print('[dim]Пример: hh-apply query "SELECT * FROM applications"[/dim]')
        return

    with Tracker(db_path) as tracker:
        try:
            columns, rows = tracker.execute_query(sql)
        except Exception as e:
            console.print(f"[red]SQL ошибка: {e}[/red]")
            return

    if not rows:
        console.print("[dim]Нет результатов[/dim]")
        return

    if csv_export:
        buf = io.StringIO()
        writer = csv_module.writer(buf)
        writer.writerow(columns)
        writer.writerows(rows)
        if output:
            Path(output).write_text(buf.getvalue(), encoding="utf-8")
            console.print(f"[green]Экспорт: {output} ({len(rows)} строк)[/green]")
        else:
            print(buf.getvalue())
    else:
        table = Table(border_style="blue")
        for col in columns:
            table.add_column(col)
        for row in rows:
            table.add_row(*[str(v) for v in row])
        console.print(table)
        console.print(f"[dim]{len(rows)} строк[/dim]")


# ==================== COMPLETIONS ====================

@main.command(epilog="""
Примеры:
  hh-apply completions bash      Скрипт для bash
  hh-apply completions zsh       Скрипт для zsh
  hh-apply completions fish      Скрипт для fish

Установка:
  # Bash
  hh-apply completions bash >> ~/.bashrc

  # Zsh
  hh-apply completions zsh >> ~/.zshrc

  # Fish
  hh-apply completions fish > ~/.config/fish/completions/hh-apply.fish
""")
@click.argument("shell", type=click.Choice(["bash", "zsh", "fish"]))
def completions(shell):
    """Сгенерировать скрипт автодополнения для shell."""
    import subprocess

    env = os.environ.copy()

    if shell == "bash":
        env["_HH_APPLY_COMPLETE"] = "bash_source"
    elif shell == "zsh":
        env["_HH_APPLY_COMPLETE"] = "zsh_source"
    elif shell == "fish":
        env["_HH_APPLY_COMPLETE"] = "fish_source"

    result = subprocess.run(
        [sys.executable, "-m", "hh_apply.cli"],
        env=env,
        capture_output=True,
        text=True,
    )

    if result.stdout:
        print(result.stdout)
    else:
        # Fallback: генерируем через Click напрямую
        env_var = f"_HH_APPLY_COMPLETE={shell}_source"
        Console().print(f"[dim]Выполните: {env_var} hh-apply[/dim]")



# ==================== DOCTOR ====================

@main.command()
@click.option("-c", "--config", "config_path", default="config.yaml", help="Путь к конфигу")
def doctor(config_path):
    """Диагностика окружения — проверяет всё ли готово к запуску."""
    import sys
    import shutil
    from pathlib import Path
    from rich.console import Console

    console = Console()
    console.print("\n[bold blue]hh-apply doctor[/bold blue]\n")

    ok_count = 0
    total = 6

    # 1. Python
    v = sys.version_info
    if v >= (3, 9):
        console.print(f"  [green]\u2713[/green] Python {v.major}.{v.minor}.{v.micro}")
        ok_count += 1
    else:
        console.print(f"  [red]\u2717[/red] Python {v.major}.{v.minor} — нужен 3.9+")

    # 2. Patchright
    try:
        import patchright
        console.print(f"  [green]\u2713[/green] Patchright установлен")
        ok_count += 1
    except ImportError:
        console.print("  [red]\u2717[/red] Patchright не установлен: pip install patchright")

    # 3. Chromium (с таймаутом чтобы не зависнуть)
    chromium_found = False
    try:
        import subprocess as _sp
        result = _sp.run(
            [sys.executable, "-c", "from patchright.sync_api import sync_playwright; pw=sync_playwright().start(); b=pw.chromium.launch(headless=True); b.close(); pw.stop(); print('ok')"],
            capture_output=True, text=True, timeout=15,
        )
        chromium_found = result.stdout.strip() == "ok"
    except Exception:
        pass

    if chromium_found:
        console.print("  [green]\u2713[/green] Chromium доступен")
        ok_count += 1
    else:
        console.print("  [red]\u2717[/red] Chromium не найден: patchright install chromium")

    # 4. Config
    config_file = Path(config_path)
    if config_file.exists():
        try:
            from hh_apply.config import load_config
            load_config(str(config_file))
            console.print(f"  [green]\u2713[/green] Конфиг {config_path}")
            ok_count += 1
        except Exception as e:
            console.print(f"  [red]\u2717[/red] Конфиг битый: {e}")
    else:
        console.print(f"  [yellow]\u2717[/yellow] Конфиг не найден: hh-apply init")

    # 5. Auth
    try:
        from hh_apply.config import load_config, get_storage_path
        if config_file.exists():
            cfg = load_config(str(config_file))
            sp = get_storage_path(cfg)
            if sp.exists():
                console.print(f"  [green]\u2713[/green] Авторизация (storage_state)")
                ok_count += 1
            else:
                console.print("  [yellow]\u2717[/yellow] Не авторизован: hh-apply login")
        else:
            console.print("  [dim]-[/dim] Авторизация (нужен конфиг)")
    except Exception:
        console.print("  [dim]-[/dim] Авторизация (нужен конфиг)")

    # 6. Database
    try:
        from hh_apply.config import load_config, get_db_path
        if config_file.exists():
            cfg = load_config(str(config_file))
            db = get_db_path(cfg)
            from hh_apply.tracker import Tracker
            with Tracker(db) as t:
                total_apps = t.total()
            console.print(f"  [green]\u2713[/green] База данных ({total_apps} откликов)")
            ok_count += 1
        else:
            console.print("  [dim]-[/dim] База данных (нужен конфиг)")
    except Exception as e:
        console.print(f"  [red]\u2717[/red] База данных: {e}")

    console.print(f"\n  [{'green' if ok_count == total else 'yellow'}]{ok_count}/{total} проверок пройдено[/{'green' if ok_count == total else 'yellow'}]\n")


if __name__ == "__main__":
    main()
