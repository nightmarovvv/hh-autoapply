"""Оркестратор автооткликов — основной цикл."""

from __future__ import annotations

import signal
import sys

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn
from patchright.sync_api import sync_playwright

from hh_apply.config import get_storage_path, get_db_path
from hh_apply.auth import create_context, login_if_needed, check_logged_in
from hh_apply.search import do_search, collect_vacancy_ids_from_page, go_next_page, dismiss_ads
from hh_apply.apply import apply_to_vacancy, human_delay, _check_captcha, _handle_captcha
from hh_apply.api_apply import check_vacancy_type
from hh_apply.tracker import Tracker
from hh_apply.filters import should_skip_vacancy
from hh_apply.report import SessionReport, print_report, export_report


def run(config: dict, dry_run: bool = False, report_path: "str | None" = None) -> None:
    """Запускает сессию автооткликов."""
    console = Console()
    report = SessionReport()

    apply_config = config.get("apply", {})
    filters_config = config.get("filters", {})
    search_config = config.get("search", {})

    use_cover_letter = apply_config.get("use_cover_letter", True)
    cover_letter = apply_config.get("cover_letter", "").strip() if use_cover_letter else ""
    max_apps = apply_config.get("max_applications", 50)
    delay_min = apply_config.get("delay_min", 1.5)
    delay_max = apply_config.get("delay_max", 4.0)
    skip_test = filters_config.get("skip_test_vacancies", True)
    skip_foreign = filters_config.get("skip_foreign", False)

    storage_path = get_storage_path(config)
    db_path = get_db_path(config)

    console.print(f"[bold blue]hh-apply[/bold blue] v1.0.0")
    console.print(f"  Запрос:  [bold]{search_config.get('query', '')}[/bold]")
    console.print(f"  Лимит:   {max_apps}")
    console.print(f"  Режим:   {'DRY RUN' if dry_run else 'БОЕВОЙ'}")
    console.print()

    # Graceful shutdown
    shutdown = False

    def _signal_handler(sig, frame):
        nonlocal shutdown
        if shutdown:
            sys.exit(1)
        shutdown = True
        console.print("\n[yellow]Завершаю... (Ctrl+C ещё раз для немедленного выхода)[/yellow]")

    signal.signal(signal.SIGINT, _signal_handler)

    with Tracker(db_path) as tracker:
        with sync_playwright() as pw:
            browser, context = create_context(pw, config)
            try:
                page = context.new_page()

                if not login_if_needed(page, config):
                    console.print("[red]Не авторизован. Запустите: hh-apply login[/red]")
                    return

                console.print("[green]Авторизован[/green]")

                try:
                    do_search(page, config)
                except Exception as e:
                    console.print(f"[red]Ошибка поиска: {e}[/red]")
                    return

                if _check_captcha(page):
                    console.print("[yellow]Капча на странице поиска![/yellow]")
                    _handle_captcha(page)

                sent = 0
                skipped = 0
                page_num = 0
                max_pages = 30

                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    MofNCompleteColumn(),
                    console=console,
                ) as progress:
                    task = progress.add_task("Отклики", total=max_apps)

                    while sent < max_apps and page_num < max_pages and not shutdown:
                        dismiss_ads(page)
                        vacancies = collect_vacancy_ids_from_page(page)

                        if not vacancies:
                            if not go_next_page(page):
                                break
                            page_num += 1
                            continue

                        new = [v for v in vacancies if not tracker.is_applied(v.vacancy_id)]

                        for vacancy in new:
                            if sent >= max_apps or shutdown:
                                break

                            # Session check каждые 15 откликов
                            if (sent + skipped) > 0 and (sent + skipped) % 15 == 0:
                                if not check_logged_in(page):
                                    console.print("[red]Сессия истекла.[/red]")
                                    shutdown = True
                                    break

                            # Фильтры
                            skip_reason = should_skip_vacancy(vacancy, filters_config)
                            if skip_reason:
                                report.add(vacancy.vacancy_id, vacancy.title, vacancy.company, "filtered")
                                skipped += 1
                                continue

                            if dry_run:
                                info = check_vacancy_type(page, vacancy.vacancy_id)
                                console.print(f"  {vacancy.title[:45]:45s} | {info.get('type','?'):15s}")
                                skipped += 1
                                continue

                            # API-проверка типа
                            info = check_vacancy_type(page, vacancy.vacancy_id)
                            vtype = info.get("type", "unknown")

                            if vtype == "test-required" and skip_test:
                                report.add(vacancy.vacancy_id, vacancy.title, vacancy.company, "test_required")
                                skipped += 1
                                continue
                            if vtype == "already-applied":
                                skipped += 1
                                continue

                            progress.update(task, description=f"[{sent + 1}/{max_apps}] {vacancy.title[:40]}")

                            status = apply_to_vacancy(page, vacancy, cover_letter, use_cover_letter, skip_foreign)
                            tracker.record(vacancy.vacancy_id, vacancy.title, vacancy.company, status)
                            report.add(vacancy.vacancy_id, vacancy.title, vacancy.company, status)

                            if status in ("sent", "cover_letter_sent"):
                                sent += 1
                                progress.update(task, advance=1)
                            else:
                                skipped += 1

                            if _check_captcha(page):
                                console.print("[yellow]Капча![/yellow]")
                                _handle_captcha(page)

                            human_delay(delay_min, delay_max)

                        if sent >= max_apps or shutdown:
                            break

                        try:
                            if not go_next_page(page):
                                break
                        except Exception:
                            break

                        page_num += 1

                        if _check_captcha(page):
                            _handle_captcha(page)

            finally:
                try:
                    context.storage_state(path=str(storage_path))
                except Exception:
                    pass
                context.close()
                browser.close()

    # Отчёт
    console.print()
    print_report(report, console)

    if report_path:
        export_report(report, report_path)
        console.print(f"\n[dim]Отчёт сохранён: {report_path}[/dim]")
