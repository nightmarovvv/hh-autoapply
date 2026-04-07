"""CLI-интерфейс hh-apply."""

from __future__ import annotations

import sys
from pathlib import Path

import click
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.table import Table

from hh_apply import __version__

# Справочники для визарда
AREAS = {
    "Москва": 1,
    "Санкт-Петербург": 2,
    "Россия (вся)": 113,
    "Новосибирск": 4,
    "Екатеринбург": 3,
    "Казань": 88,
    "Краснодар": 53,
    "Нижний Новгород": 66,
    "Удалённо (без региона)": None,
}

EXPERIENCE_OPTIONS = {
    "Без опыта": "noExperience",
    "1-3 года": "between1And3",
    "3-6 лет": "between3And6",
    "Более 6 лет": "moreThan6",
    "Любой": None,
}

SCHEDULE_OPTIONS = {
    "Удалённая работа": "remote",
    "Полный день": "fullDay",
    "Сменный график": "shift",
    "Гибкий график": "flexible",
    "Вахта": "flyInFlyOut",
}

EMPLOYMENT_OPTIONS = {
    "Полная занятость": "full",
    "Частичная": "part",
    "Проектная работа": "project",
    "Стажировка": "probation",
}


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
        console = Console()
        console.print(HELP_TEXT)


@main.command()
def init():
    """Настроить hh-apply через интерактивный визард."""
    console = Console()
    target = Path.cwd() / "config.yaml"

    existing_config = None
    edit_mode = False

    if target.exists():
        # Загружаем текущий конфиг для дефолтов
        with open(target, "r", encoding="utf-8") as f:
            existing_config = yaml.safe_load(f) or {}

        console.print("[yellow]config.yaml уже существует.[/yellow]")
        console.print("[dim]Ваш логин и куки в безопасности — они хранятся отдельно в ~/.hh-apply/[/dim]\n")

        choice = Prompt.ask(
            "  Что сделать?",
            choices=["edit", "new", "cancel"],
            default="edit",
            console=console,
        )
        if choice == "cancel":
            return
        if choice == "edit":
            edit_mode = True
        # choice == "new" → полная перезапись

    # Дефолты из существующего конфига
    def _get(section, key, fallback=""):
        if existing_config and edit_mode:
            return existing_config.get(section, {}).get(key, fallback)
        return fallback

    console.print()
    console.print(Panel("[bold blue]hh-apply[/bold blue] — настройка автооткликов", border_style="blue"))
    if edit_mode:
        console.print("[dim]Нажмите Enter чтобы оставить текущее значение[/dim]")
    console.print()

    # === Поиск ===
    console.print("[bold]1. Поиск[/bold]")
    default_query = _get("search", "query", "python developer")
    query = Prompt.ask("  Поисковый запрос", default=str(default_query), console=console)

    # Регион
    console.print()
    console.print("  [dim]Регион:[/dim]")
    area_names = list(AREAS.keys())
    for i, name in enumerate(area_names, 1):
        console.print(f"    {i}. {name}")
    # Находим текущий регион если есть
    current_area = _get("search", "area", None)
    default_area_idx = 1
    if current_area:
        for i, (name, aid) in enumerate(AREAS.items(), 1):
            if aid == current_area:
                default_area_idx = i
                break
    area_idx = IntPrompt.ask("  Номер региона", default=default_area_idx, console=console)
    area_idx = max(1, min(area_idx, len(area_names)))
    area_name = area_names[area_idx - 1]
    area_id = AREAS[area_name]
    console.print(f"  [green]Регион: {area_name}[/green]")

    # Зарплата
    console.print()
    default_salary = _get("search", "salary_from", "")
    salary_str = Prompt.ask("  Минимальная зарплата (или Enter — без фильтра)", default=str(default_salary) if default_salary else "", console=console)
    salary_from = int(salary_str) if salary_str.strip().isdigit() else None
    salary_only = False
    if salary_from:
        salary_only = Confirm.ask("  Только вакансии с указанной зарплатой?", default=True, console=console)

    # Опыт
    console.print()
    console.print("  [dim]Опыт:[/dim]")
    exp_names = list(EXPERIENCE_OPTIONS.keys())
    for i, name in enumerate(exp_names, 1):
        console.print(f"    {i}. {name}")
    # Находим текущий опыт
    current_exp = _get("search", "experience", None)
    default_exp_idx = 5
    if current_exp:
        for i, (name, val) in enumerate(EXPERIENCE_OPTIONS.items(), 1):
            if val == current_exp:
                default_exp_idx = i
                break
    exp_idx = IntPrompt.ask("  Номер", default=default_exp_idx, console=console)
    exp_idx = max(1, min(exp_idx, len(exp_names)))
    experience = EXPERIENCE_OPTIONS[exp_names[exp_idx - 1]]
    console.print(f"  [green]Опыт: {exp_names[exp_idx - 1]}[/green]")

    # График
    console.print()
    console.print("  [dim]График (можно несколько через запятую):[/dim]")
    sched_names = list(SCHEDULE_OPTIONS.keys())
    for i, name in enumerate(sched_names, 1):
        console.print(f"    {i}. {name}")
    # Текущие номера графика
    current_scheds = _get("search", "schedule", [])
    default_sched = ""
    if current_scheds:
        nums = []
        for s in current_scheds:
            for i, (name, val) in enumerate(SCHEDULE_OPTIONS.items(), 1):
                if val == s:
                    nums.append(str(i))
        default_sched = ",".join(nums)
    sched_input = Prompt.ask("  Номера через запятую (или Enter — любой)", default=default_sched, console=console)
    schedule = []
    if sched_input.strip():
        for s in sched_input.split(","):
            s = s.strip()
            if s.isdigit():
                idx = int(s)
                if 1 <= idx <= len(sched_names):
                    schedule.append(SCHEDULE_OPTIONS[sched_names[idx - 1]])

    # === Фильтры ===
    console.print()
    console.print("[bold]2. Фильтры[/bold]")
    default_kw = ", ".join(_get("filters", "exclude_keywords", []))
    exclude_kw = Prompt.ask(
        "  Исключить слова из названий (через запятую, или Enter — не исключать)",
        default=default_kw, console=console,
    )
    exclude_keywords = [w.strip() for w in exclude_kw.split(",") if w.strip()] if exclude_kw.strip() else []

    default_comp = ", ".join(_get("filters", "exclude_companies", []))
    exclude_comp = Prompt.ask(
        "  Исключить компании (через запятую, или Enter — не исключать)",
        default=default_comp, console=console,
    )
    exclude_companies = [c.strip() for c in exclude_comp.split(",") if c.strip()] if exclude_comp.strip() else []

    # === Отклик ===
    console.print()
    console.print("[bold]3. Отклик[/bold]")
    default_max = _get("apply", "max_applications", 50)
    max_apps = IntPrompt.ask("  Максимум откликов за запуск", default=int(default_max), console=console)

    default_use_letter = _get("apply", "use_cover_letter", True)
    use_cover_letter = Confirm.ask("  Использовать сопроводительное письмо?", default=bool(default_use_letter), console=console)
    cover_letter = ""
    if use_cover_letter:
        console.print("  [dim]Введите текст (Enter для шаблона по умолчанию):[/dim]")
        default_letter = _get("apply", "cover_letter", "")
        cover_input = Prompt.ask("  Сопроводительное", default=str(default_letter).strip() if default_letter else "", console=console)
        if cover_input.strip():
            cover_letter = cover_input.strip()
        else:
            cover_letter = "Здравствуйте!\n\nМеня заинтересовала ваша вакансия. Буду рад обсудить детали.\n\nС уважением"

    # === Собираем конфиг ===
    config = {
        "search": {"query": query},
        "filters": {
            "exclude_companies": exclude_companies,
            "exclude_keywords": exclude_keywords,
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

    # Сохраняем
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
        console.print("Сначала запустите: [bold]hh-apply init[/bold]")
        return

    cfg = load_config(config)
    storage_path = get_storage_path(cfg)
    storage_path.parent.mkdir(parents=True, exist_ok=True)

    console.print("[bold blue]hh-apply login[/bold blue]")
    console.print()

    with sync_playwright() as pw:
        # Для логина — чистый браузер, минимум аргументов.
        # Stealth-патчи и кастомные args нужны для откликов, не для логина.
        # hh.ru усиленно защищает страницу авторизации.
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
            console.print("[yellow]Если видите страницу — продолжайте логин.[/yellow]")

        console.print()
        console.print("Браузер открыт. Залогиньтесь на hh.ru.")
        console.print("Не торопитесь — введите код, дождитесь загрузки.")
        console.print("Когда увидите главную страницу hh.ru — вернитесь сюда.")
        console.print()

        try:
            input(">>> Нажмите Enter когда залогинитесь: ")
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]Прервано[/yellow]")
            try:
                browser.close()
            except Exception:
                pass
            sys.exit(1)

        # Проверяем логин — с мягкой навигацией
        try:
            page.goto("https://hh.ru", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)
        except Exception:
            console.print("[dim]Навигация медленная, проверяю текущую страницу...[/dim]")

        if check_logged_in(page):
            context.storage_state(path=str(storage_path))
            console.print(f"\n[green]Сессия сохранена![/green]")
            console.print("Запускайте: [bold]hh-apply run[/bold]")
        else:
            console.print("\n[red]Логин не подтверждён.[/red]")
            console.print("[dim]Убедитесь что вы залогинены и попробуйте ещё раз.[/dim]")

        try:
            browser.close()
        except Exception:
            pass


@main.command()
@click.option("--config", "-c", default="config.yaml", help="Путь к конфигу")
@click.option("--limit", "-l", type=int, help="Макс. количество откликов")
@click.option("--headless", is_flag=True, help="Скрытый режим браузера")
@click.option("--dry-run", is_flag=True, help="Только поиск, без откликов")
@click.option("--report", "-r", type=str, help="Сохранить отчёт в файл")
@click.option("--exclude", "-e", type=str, help="Regex для исключения вакансий (напр. junior|стажёр)")
def run(config, limit, headless, dry_run, report, exclude):
    """Запустить автоотклики.

    \b
    Примеры:
      hh-apply run                        # Запуск с настройками из config.yaml
      hh-apply run --limit 10             # Максимум 10 откликов
      hh-apply run --dry-run              # Только посмотреть вакансии
      hh-apply run -e "junior|стажёр"     # Исключить по regex
      hh-apply run --limit 5 --dry-run    # Посмотреть 5 вакансий
    """
    from hh_apply.config import load_config
    from hh_apply.runner import run as do_run

    console = Console()

    if not Path(config).exists():
        console.print(f"[red]Конфиг не найден: {config}[/red]")
        console.print("Сначала запустите: [bold]hh-apply init[/bold]")
        return

    cfg = load_config(config)

    # Интерактивный режим — если не передали ни одного аргумента
    has_any_option = any([limit, headless, dry_run, report, exclude])
    if not has_any_option:
        console.print("[bold blue]hh-apply run[/bold blue] — интерактивный режим\n")

        # Лимит
        limit_input = Prompt.ask(
            "  Сколько откликов? (Enter = из конфига)",
            default="", console=console,
        )
        if limit_input.strip().isdigit():
            limit = int(limit_input.strip())

        # Dry run
        dry_run = Confirm.ask("  Пробный режим (без откликов)?", default=False, console=console)

        # Exclude
        exclude_input = Prompt.ask(
            "  Исключить вакансии по regex? (Enter = пропустить)",
            default="", console=console,
        )
        if exclude_input.strip():
            exclude = exclude_input.strip()

        console.print()

    if limit:
        cfg["apply"]["max_applications"] = limit
    if headless:
        cfg["browser"]["headless"] = True

    do_run(cfg, dry_run=dry_run, report_path=report, exclude_pattern=exclude)


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
        console.print("[yellow]База данных не найдена. Сначала запустите: hh-apply run[/yellow]")
        return

    with Tracker(db_path) as tracker:
        st = tracker.stats()
        total = tracker.total()

        table = Table(title="Статистика откликов hh-apply", border_style="blue")
        table.add_column("Статус", style="bold")
        table.add_column("Количество", justify="right")

        status_names = {
            "sent": "[green]Отправлен[/green]",
            "cover_letter_sent": "[green]С письмом[/green]",
            "letter_sent": "[green]С письмом[/green]",
            "test_required": "[yellow]Тестовое[/yellow]",
            "extra_steps": "[yellow]Доп. вопросы[/yellow]",
            "already_applied": "[dim]Уже откликались[/dim]",
            "error": "[red]Ошибка[/red]",
            "filtered": "[dim]Отфильтровано[/dim]",
            "captcha": "[yellow]Капча[/yellow]",
            "no_button": "[dim]Нет кнопки[/dim]",
        }

        for status, count in sorted(st.items(), key=lambda x: x[1], reverse=True):
            name = status_names.get(status, status)
            table.add_row(name, str(count))

        table.add_section()
        table.add_row("[bold]Всего[/bold]", f"[bold]{total}[/bold]")

        console.print(table)


@main.command()
@click.option("--config", "-c", default="config.yaml", help="Путь к конфигу")
@click.argument("vacancy_id", required=False)
def done(config, vacancy_id):
    """Отметить тестовую вакансию как решённую (убрать из списка).

    \b
    Использование:
      hh-apply done                  # Интерактивный выбор
      hh-apply done 12345678         # Убрать по ID вакансии
      hh-apply done all              # Очистить все тестовые
    """
    from hh_apply.config import load_config, get_db_path, get_data_dir
    from hh_apply.tracker import Tracker

    console = Console()
    cfg = load_config(config)
    db_path = get_db_path(cfg)

    if not db_path.exists():
        console.print("[yellow]База данных не найдена.[/yellow]")
        return

    with Tracker(db_path) as tracker:
        if vacancy_id == "all":
            tracker.clear_skipped("test_required")
            console.print("[green]Все тестовые вакансии удалены из списка.[/green]")
            # Обновляем файл
            test_path = get_data_dir(cfg) / "test_vacancies.txt"
            tracker.export_skipped_tests(test_path)
            return

        if vacancy_id:
            if tracker.remove_skipped(vacancy_id):
                console.print(f"[green]Вакансия {vacancy_id} убрана из списка.[/green]")
            else:
                console.print(f"[yellow]Вакансия {vacancy_id} не найдена в пропущенных.[/yellow]")
            # Обновляем файл
            test_path = get_data_dir(cfg) / "test_vacancies.txt"
            tracker.export_skipped_tests(test_path)
            return

        # Интерактивный режим — показываем список тестовых
        tests = tracker.get_skipped("test_required")
        if not tests:
            console.print("[dim]Нет тестовых вакансий в списке.[/dim]")
            return

        console.print(f"[bold]Тестовые вакансии ({len(tests)} шт.):[/bold]\n")
        for i, t in enumerate(tests, 1):
            console.print(f"  {i}. {t['title']} — {t['company']}")
            console.print(f"     [cyan]{t['url']}[/cyan]")
            console.print(f"     [dim]ID: {t['vacancy_id']}[/dim]")
            console.print()

        choice = Prompt.ask(
            "Номер вакансии для удаления (или 'all' для очистки, Enter — отмена)",
            default="", console=console,
        )

        if not choice.strip():
            return

        if choice.strip().lower() == "all":
            tracker.clear_skipped("test_required")
            console.print("[green]Все тестовые вакансии удалены.[/green]")
        elif choice.strip().isdigit():
            idx = int(choice.strip())
            if 1 <= idx <= len(tests):
                vid = tests[idx - 1]["vacancy_id"]
                tracker.remove_skipped(vid)
                console.print(f"[green]Убрано: {tests[idx - 1]['title']}[/green]")
            else:
                console.print("[red]Неверный номер.[/red]")

        # Обновляем файл
        test_path = get_data_dir(cfg) / "test_vacancies.txt"
        tracker.export_skipped_tests(test_path)


@main.command(name="api-login")
@click.option("--config", "-c", default="config.yaml", help="Путь к конфигу")
def api_login(config):
    """OAuth авторизация для API-команд (whoami, boost)."""
    import asyncio
    from urllib.parse import parse_qs, urlsplit
    from hh_apply.config import load_config, get_data_dir
    from hh_apply.api_client import HHApiClient, ANDROID_CLIENT_ID
    from patchright.sync_api import sync_playwright

    console = Console()
    cfg = load_config(config)
    data_dir = get_data_dir(cfg)
    client = HHApiClient(data_dir / "api_token.json")

    console.print("[bold blue]hh-apply api-login[/bold blue]")
    console.print("Откроется браузер для OAuth авторизации.\n")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)
        # Эмулируем Android-устройство
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

        console.print("Залогиньтесь в браузере.")
        console.print("После логина вернитесь сюда и нажмите [bold]Enter[/bold].")

        try:
            # Ждём OAuth код или ручной ввод
            for _ in range(300):  # 5 минут
                page.wait_for_timeout(1000)
                if auth_code:
                    break
            else:
                if not auth_code:
                    input("\n>>> Нажмите Enter если залогинились: ")
        except (EOFError, KeyboardInterrupt):
            browser.close()
            return

        browser.close()

    if not auth_code:
        console.print("[red]Не удалось получить OAuth код.[/red]")
        return

    client.exchange_code(auth_code)
    console.print("[green]API авторизация успешна![/green]")
    console.print("Теперь доступны: [bold]hh-apply whoami[/bold], [bold]hh-apply boost[/bold]")


@main.command()
@click.option("--config", "-c", default="config.yaml", help="Путь к конфигу")
def whoami(config):
    """Проверить аккаунт: ID, имя, резюме, просмотры.

    \b
    Требует предварительной OAuth-авторизации:
      hh-apply api-login
    """
    from hh_apply.config import load_config, get_data_dir
    from hh_apply.api_client import HHApiClient

    console = Console()
    cfg = load_config(config)
    data_dir = get_data_dir(cfg)
    client = HHApiClient(data_dir / "api_token.json")

    if not client.is_authenticated:
        console.print("[red]Не авторизован. Запустите: hh-apply api-login[/red]")
        return

    try:
        me = client.whoami()
    except Exception as e:
        console.print(f"[red]Ошибка: {e}[/red]")
        console.print("Попробуйте: [bold]hh-apply api-login[/bold]")
        return

    full_name = " ".join(filter(None, [
        me.get("last_name"),
        me.get("first_name"),
        me.get("middle_name"),
    ])) or "Аноним"

    counters = me.get("counters", {})
    resumes = counters.get("resumes_count", 0)
    views = counters.get("new_resume_views", 0)
    unread = counters.get("unread_negotiations", 0)

    console.print(
        f"\U0001f194 {me.get('id', '?')} {full_name} "
        f"[ \U0001f4c4 {resumes} | \U0001f441\ufe0f +{views} | \u2709\ufe0f +{unread} ]"
    )


@main.command()
@click.option("--config", "-c", default="config.yaml", help="Путь к конфигу")
def boost(config):
    """Поднять все резюме в поиске.

    \b
    Поднимает резюме наверх в выдаче рекрутеров.
    Требует: hh-apply api-login
    """
    from hh_apply.config import load_config, get_data_dir
    from hh_apply.api_client import HHApiClient

    console = Console()
    cfg = load_config(config)
    data_dir = get_data_dir(cfg)
    client = HHApiClient(data_dir / "api_token.json")

    if not client.is_authenticated:
        console.print("[red]Не авторизован. Запустите: hh-apply api-login[/red]")
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
        status = resume.get("status", {}).get("id", "")
        if status != "published":
            console.print(f"[dim]Пропуск (не опубликовано): {resume.get('title', '?')}[/dim]")
            continue

        if not resume.get("can_publish_or_update"):
            console.print(f"[yellow]Нельзя обновить: {resume.get('title', '?')}[/yellow]")
            continue

        try:
            client.boost_resume(resume["id"])
            url = resume.get("alternate_url", "")
            title = resume.get("title", "?")
            console.print(f"\u2705 Обновлено {url} — {title}")
        except Exception as e:
            console.print(f"[red]Ошибка: {e}[/red]")


@main.command()
@click.option("--config", "-c", default="config.yaml", help="Путь к конфигу")
@click.option("--csv", "csv_export", is_flag=True, help="Экспорт в CSV")
@click.option("-o", "--output", type=str, help="Файл для экспорта")
@click.argument("sql", required=False)
def query(config, csv_export, output, sql):
    """SQL-запросы к базе данных.

    \b
    Примеры:
      hh-apply query                                              # Показать подсказку
      hh-apply query "SELECT * FROM applications"                 # Все отклики
      hh-apply query "SELECT * FROM skipped_vacancies"            # Пропущенные
      hh-apply query "SELECT * FROM applications" --csv -o f.csv  # Экспорт CSV
    """
    import csv as csv_module
    import io
    from hh_apply.config import load_config, get_db_path
    from hh_apply.tracker import Tracker

    console = Console()
    cfg = load_config(config)
    db_path = get_db_path(cfg)

    if not db_path.exists():
        console.print("[yellow]База данных не найдена.[/yellow]")
        return

    if not sql:
        console.print("[dim]Доступные таблицы: applications, skipped_vacancies[/dim]")
        console.print("[dim]Пример: hh-apply query \"SELECT * FROM skipped_vacancies WHERE reason='test_required'\"[/dim]")
        return

    with Tracker(db_path) as tracker:
        try:
            columns, rows = tracker.execute_query(sql)
        except Exception as e:
            console.print(f"[red]Ошибка SQL: {e}[/red]")
            return

    if not rows:
        console.print("[dim]Нет результатов[/dim]")
        return

    if csv_export:
        buf = io.StringIO()
        writer = csv_module.writer(buf)
        writer.writerow(columns)
        writer.writerows(rows)
        csv_text = buf.getvalue()

        if output:
            Path(output).write_text(csv_text, encoding="utf-8")
            console.print(f"[green]Экспорт: {output} ({len(rows)} строк)[/green]")
        else:
            print(csv_text)
    else:
        table = Table(border_style="blue")
        for col in columns:
            table.add_column(col)
        for row in rows:
            table.add_row(*[str(v) for v in row])
        console.print(table)
        console.print(f"[dim]{len(rows)} строк[/dim]")
