"""CLI-интерфейс hh-apply с InquirerPy для интерактивных меню."""

from __future__ import annotations

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


HELP_TEXT = """
[bold blue]hh-apply[/bold blue] — массовые автоотклики на hh.ru

[bold]Начало работы:[/bold]
  hh-apply init        Настроить поиск и фильтры
  hh-apply login       Войти в hh.ru (откроется браузер)
  hh-apply run         Запустить отклики

[bold]Дополнительно:[/bold]
  hh-apply boost       Поднять резюме в поиске
  hh-apply whoami      Проверить аккаунт
  hh-apply stats       Статистика откликов
  hh-apply done        Убрать решённую тестовую вакансию
  hh-apply query       SQL-запросы к базе

[bold]Опции run:[/bold]
  --limit 50           Максимум откликов
  --dry-run            Только посмотреть, не откликаться
  --exclude "regex"    Исключить вакансии по regex
  --headless           Без окна браузера
"""


@click.group(invoke_without_command=True)
@click.version_option(__version__, prog_name="hh-apply")
@click.pass_context
def main(ctx):
    """hh-apply — массовые автоматические отклики на вакансии hh.ru"""
    if ctx.invoked_subcommand is None:
        Console().print(HELP_TEXT)


# ==================== INIT ====================

@main.command()
def init():
    """Настроить hh-apply через интерактивный визард."""
    console = Console()
    target = Path.cwd() / "config.yaml"

    existing_config = None
    edit_mode = False

    if target.exists():
        with open(target, "r", encoding="utf-8") as f:
            existing_config = yaml.safe_load(f) or {}

        console.print("[yellow]config.yaml уже существует.[/yellow]")
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
        message="Минимальная зарплата (пусто = без фильтра):",
        default=str(default_salary) if default_salary else "",
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
    exclude_pattern = inquirer.text(
        message="Regex исключение (напр. junior|стажёр|bitrix):",
        default=str(default_pattern) if default_pattern else "",
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
        cover_letter = inquirer.text(
            message="Текст письма (Enter = шаблон по умолчанию):",
            default=default_letter if default_letter else "",
        ).execute()
        if not cover_letter.strip():
            cover_letter = "Здравствуйте!\n\nМеня заинтересовала ваша вакансия. Буду рад обсудить детали.\n\nС уважением"

    # === Собираем конфиг ===
    config = {
        "search": {"query": query},
        "filters": {
            "exclude_companies": exclude_companies,
            "exclude_keywords": exclude_keywords,
            "exclude_pattern": exclude_pattern.strip() if exclude_pattern else "",
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
        f"Следующий шаг:\n"
        f"  [bold]hh-apply login[/bold]  — войти в hh.ru\n"
        f"  [bold]hh-apply run[/bold]    — запустить отклики",
        title="Готово",
        border_style="green",
    ))


# ==================== LOGIN ====================

@main.command()
@click.option("--config", "-c", default="config.yaml", help="Путь к конфигу")
def login(config):
    """Войти в hh.ru и сохранить сессию."""
    from hh_apply.config import load_config, get_storage_path
    from hh_apply.stealth import random_viewport
    from hh_apply.auth import check_logged_in
    from patchright.sync_api import sync_playwright

    console = Console()

    if not Path(config).exists():
        console.print(f"[red]Конфиг не найден: {config}[/red]")
        console.print("Запустите: [bold]hh-apply init[/bold]")
        return

    cfg = load_config(config)
    storage_path = get_storage_path(cfg)
    storage_path.parent.mkdir(parents=True, exist_ok=True)

    console.print("[bold blue]hh-apply login[/bold blue]\n")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=False,
            args=["--no-first-run", "--no-default-browser-check"],
        )
        context = browser.new_context(
            viewport=random_viewport(),
            locale="ru-RU",
            timezone_id="Europe/Moscow",
        )

        page = context.new_page()

        try:
            page.goto("https://hh.ru/account/login", timeout=60000, wait_until="domcontentloaded")
        except Exception:
            console.print("[yellow]Страница загружается медленно, но браузер открыт.[/yellow]")

        console.print("Браузер открыт. Залогиньтесь на hh.ru.")
        console.print("Не торопитесь — введите код, дождитесь загрузки.\n")

        try:
            input(">>> Нажмите Enter когда залогинитесь: ")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]Прервано[/yellow]")
            try:
                browser.close()
            except Exception:
                pass
            sys.exit(1)

        try:
            page.goto("https://hh.ru", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)
        except Exception:
            pass

        if check_logged_in(page):
            context.storage_state(path=str(storage_path))
            console.print(f"\n[green]Сессия сохранена![/green]")
            console.print("Запускайте: [bold]hh-apply run[/bold]")
        else:
            console.print("\n[red]Логин не подтверждён.[/red]")

        try:
            browser.close()
        except Exception:
            pass


# ==================== RUN ====================

@main.command()
@click.option("--config", "-c", default="config.yaml", help="Путь к конфигу")
@click.option("--limit", "-l", type=int, help="Макс. количество откликов")
@click.option("--headless", is_flag=True, help="Скрытый режим браузера")
@click.option("--dry-run", is_flag=True, help="Только поиск, без откликов")
@click.option("--report", "-r", type=str, help="Сохранить отчёт в файл")
@click.option("--exclude", "-e", type=str, help="Regex исключение (напр. junior|стажёр)")
def run(config, limit, headless, dry_run, report, exclude):
    """Запустить автоотклики.

    \b
    Примеры:
      hh-apply run                        # Интерактивный режим
      hh-apply run --limit 10             # Максимум 10 откликов
      hh-apply run --dry-run              # Только посмотреть вакансии
      hh-apply run -e "junior|стажёр"     # Исключить по regex
    """
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

@main.command()
@click.option("--config", "-c", default="config.yaml", help="Путь к конфигу")
def stats(config):
    """Показать статистику откликов."""
    from hh_apply.config import load_config, get_db_path
    from hh_apply.tracker import Tracker

    console = Console()
    cfg = load_config(config)
    db_path = get_db_path(cfg)

    if not db_path.exists():
        console.print("[yellow]Нет данных. Запустите: hh-apply run[/yellow]")
        return

    with Tracker(db_path) as tracker:
        st = tracker.stats()
        total = tracker.total()

        table = Table(title="Статистика откликов hh-apply", border_style="blue")
        table.add_column("Статус", style="bold")
        table.add_column("Кол-во", justify="right")

        names = {
            "sent": "[green]Отправлен[/green]",
            "cover_letter_sent": "[green]С письмом[/green]",
            "letter_sent": "[green]С письмом[/green]",
            "test_required": "[yellow]Тестовое[/yellow]",
            "extra_steps": "[yellow]Доп. вопросы[/yellow]",
            "already_applied": "[dim]Уже откликались[/dim]",
            "error": "[red]Ошибка[/red]",
            "filtered": "[dim]Отфильтровано[/dim]",
            "captcha": "[yellow]Капча[/yellow]",
        }
        for status, count in sorted(st.items(), key=lambda x: x[1], reverse=True):
            table.add_row(names.get(status, status), str(count))
        table.add_section()
        table.add_row("[bold]Всего[/bold]", f"[bold]{total}[/bold]")
        console.print(table)


# ==================== DONE ====================

@main.command()
@click.option("--config", "-c", default="config.yaml", help="Путь к конфигу")
@click.argument("vacancy_id", required=False)
def done(config, vacancy_id):
    """Убрать тестовую вакансию из списка.

    \b
      hh-apply done              # Интерактивный выбор
      hh-apply done 12345678     # По ID
      hh-apply done all          # Очистить все
    """
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

@main.command(name="api-login")
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

@main.command()
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

@main.command()
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


# ==================== QUERY ====================

@main.command()
@click.option("--config", "-c", default="config.yaml", help="Путь к конфигу")
@click.option("--csv", "csv_export", is_flag=True, help="Экспорт в CSV")
@click.option("-o", "--output", type=str, help="Файл для экспорта")
@click.argument("sql", required=False)
def query(config, csv_export, output, sql):
    """SQL-запросы к базе данных.

    \b
    Примеры:
      hh-apply query "SELECT * FROM applications"
      hh-apply query "SELECT * FROM skipped_vacancies"
      hh-apply query "SELECT * FROM applications" --csv -o out.csv
    """
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
