"""Команды login, api-login, whoami, boost, responses — авторизация и API."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from hh_apply.cli import main


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
    """Загружает и показывает ответы рекрутеров с воронкой конверсии."""
    statuses = {
        "invitation": "Приглашения",
        "discard": "Отказы",
        "response": "Ответы",
    }

    total_apps = 0
    total_invitations = 0
    total_discards = 0
    total_responses = 0

    # Считаем по статусам
    for status, label in statuses.items():
        try:
            resp = client.get(f"/negotiations?status={status}&per_page=0")
            count = resp.get("found", 0)
            if status == "invitation":
                total_invitations = count
            elif status == "discard":
                total_discards = count
            elif status == "response":
                total_responses = count
        except Exception:
            pass

    # Общее количество
    try:
        resp = client.get("/negotiations?per_page=0")
        total_apps = resp.get("found", 0)
    except Exception:
        total_apps = 0

    # Без ответа = total - invitations - discards - responses
    no_response = max(0, total_apps - total_invitations - total_discards - total_responses)

    # Воронка конверсии
    console.print()
    console.print("[bold]Воронка откликов[/bold]\n")

    funnel_items = [
        ("Отправлено", total_apps, "blue"),
        ("Без ответа", no_response, "dim"),
        ("Ответы", total_responses, "yellow"),
        ("Приглашения", total_invitations, "green"),
        ("Отказы", total_discards, "red"),
    ]

    max_count = max(total_apps, 1)
    for label, count, color in funnel_items:
        bar_len = int(count / max_count * 30)
        pct = count / max(total_apps, 1) * 100
        bar = f"[{color}]{'█' * bar_len}[/{color}]{'░' * (30 - bar_len)}"
        console.print(f"  {label:<15} {bar}  [{color}]{count}[/{color}] ({pct:.0f}%)")

    # Таблица с деталями
    console.print()
    table = Table(title="Статистика ответов", border_style="blue")
    table.add_column("Метрика", style="bold")
    table.add_column("Кол-во", justify="right")
    table.add_column("% от откликов", justify="right")

    table.add_row("[bold]Всего откликов[/bold]", str(total_apps), "100%")
    if total_apps > 0:
        table.add_row("[green]Приглашения[/green]", str(total_invitations),
                      f"[green]{total_invitations / total_apps * 100:.1f}%[/green]")
        table.add_row("[red]Отказы[/red]", str(total_discards),
                      f"[red]{total_discards / total_apps * 100:.1f}%[/red]")
        table.add_row("[yellow]Ответы[/yellow]", str(total_responses),
                      f"[yellow]{total_responses / total_apps * 100:.1f}%[/yellow]")
        table.add_row("[dim]Без ответа[/dim]", str(no_response),
                      f"[dim]{no_response / total_apps * 100:.1f}%[/dim]")
    else:
        table.add_row("[green]Приглашения[/green]", str(total_invitations), "—")
        table.add_row("[red]Отказы[/red]", str(total_discards), "—")
        table.add_row("[yellow]Ответы[/yellow]", str(total_responses), "—")

    console.print(table)

    # Итоговая конверсия
    if total_apps > 0 and total_invitations > 0:
        rate = total_invitations / total_apps * 100
        console.print(f"\n[bold green]Конверсия в приглашения: {rate:.1f}%[/bold green]")
    elif total_apps > 0:
        console.print("\n[dim]Приглашений пока нет. Продолжайте откликаться![/dim]")
