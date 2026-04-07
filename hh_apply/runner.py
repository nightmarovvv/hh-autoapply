"""Оркестратор автооткликов — основной цикл с Rich логами."""

from __future__ import annotations

import signal
import sys

from rich.console import Console
from patchright.sync_api import sync_playwright

from hh_apply.config import get_storage_path, get_db_path
from hh_apply.auth import create_context, login_if_needed, check_logged_in
from hh_apply.search import do_search, collect_vacancy_ids_from_page, go_next_page, dismiss_ads
from hh_apply.apply import apply_to_vacancy, human_delay, _check_captcha, _handle_captcha
from hh_apply.api_apply import check_vacancy_type
from hh_apply.tracker import Tracker
from hh_apply.filters import should_skip_vacancy
from hh_apply.report import SessionReport, print_report, export_report


# Эмодзи для логов (как у hh-applicant-tool)
LOG_ICONS = {
    "sent": "\U0001f4e8",           # 📨
    "cover_letter_sent": "\U0001f4e8",
    "test_required": "\U0001f9ea",   # 🧪
    "extra_steps": "\u2753",         # ❓
    "already_applied": "\u23e9",     # ⏩
    "filtered": "\u23e9",
    "error": "\u274c",               # ❌
    "no_button": "\u23e9",
    "captcha": "\u26a0\ufe0f",       # ⚠️
}

STATUS_COLORS = {
    "sent": "green",
    "cover_letter_sent": "green",
    "test_required": "yellow",
    "extra_steps": "yellow",
    "already_applied": "dim",
    "filtered": "dim",
    "error": "red",
    "no_button": "dim",
    "captcha": "yellow",
}

STATUS_LABELS = {
    "sent": "Отклик отправлен",
    "cover_letter_sent": "Отклик с письмом",
    "test_required": "Тест — сохранено",
    "extra_steps": "Доп. вопросы — скип",
    "already_applied": "Уже откликались",
    "filtered": "Отфильтровано",
    "error": "Ошибка",
    "no_button": "Нет кнопки",
    "captcha": "Капча",
}


def run(config: dict, dry_run: bool = False, report_path: "str | None" = None,
        exclude_pattern: "str | None" = None) -> None:
    """Запускает сессию автооткликов."""
    console = Console()
    report = SessionReport()

    apply_config = config.get("apply", {})
    filters_config = config.get("filters", {})
    search_config = config.get("search", {})

    # CLI --exclude перезаписывает конфиг
    if exclude_pattern:
        filters_config["exclude_pattern"] = exclude_pattern

    use_cover_letter = apply_config.get("use_cover_letter", True)
    cover_letter = apply_config.get("cover_letter", "").strip() if use_cover_letter else ""
    max_apps = apply_config.get("max_applications", 50)
    delay_min = apply_config.get("delay_min", 1.5)
    delay_max = apply_config.get("delay_max", 4.0)
    skip_test = filters_config.get("skip_test_vacancies", True)
    skip_foreign = filters_config.get("skip_foreign", False)

    storage_path = get_storage_path(config)
    db_path = get_db_path(config)

    console.print()
    console.print("[bold blue]hh-apply[/bold blue] v1.0.0")
    console.print(f"  Запрос:    [bold]{search_config.get('query', '')}[/bold]")
    console.print(f"  Лимит:     {max_apps}")
    console.print(f"  Режим:     {'DRY RUN' if dry_run else 'БОЕВОЙ'}")
    if filters_config.get("exclude_pattern"):
        console.print(f"  Exclude:   [dim]{filters_config['exclude_pattern']}[/dim]")
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

                console.print("[green]Авторизован[/green]\n")

                try:
                    do_search(page, config)
                except Exception as e:
                    console.print(f"[red]Ошибка поиска: {e}[/red]")
                    return

                if _check_captcha(page):
                    console.print("[yellow]Капча на странице поиска![/yellow]")
                    _handle_captcha(page)

                sent = 0
                processed = 0  # Общий счётчик (для dry-run лимита)
                page_num = 0
                max_pages = 30
                limit_exceeded = False

                while sent < max_apps and processed < max_apps and page_num < max_pages and not shutdown and not limit_exceeded:
                    dismiss_ads(page)
                    vacancies = collect_vacancy_ids_from_page(page)

                    if not vacancies:
                        if not go_next_page(page):
                            break
                        page_num += 1
                        continue

                    new = [v for v in vacancies if not tracker.is_applied(v.vacancy_id)]

                    for vacancy in new:
                        if sent >= max_apps or processed >= max_apps or shutdown or limit_exceeded:
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
                            tracker.save_skipped(vacancy.vacancy_id, vacancy.title, vacancy.company, vacancy.url, "excluded_filter")
                            report.add(vacancy.vacancy_id, vacancy.title, vacancy.company, "filtered")
                            _log_action(console, "filtered", vacancy)
                            skipped += 1
                            continue

                        if dry_run:
                            info = check_vacancy_type(page, vacancy.vacancy_id)
                            console.print(f"  [dim]{vacancy.title[:50]:50s} | {info.get('type','?')}[/dim]")
                            processed += 1
                            continue

                        # API-проверка типа
                        info = check_vacancy_type(page, vacancy.vacancy_id)
                        vtype = info.get("type", "unknown")

                        # Лимит откликов
                        if vtype == "negotiations-limit-exceeded" or info.get("error") == "negotiations-limit-exceeded":
                            console.print("\n[yellow bold]⚠️  Лимит откликов на сегодня исчерпан (200).[/yellow bold]")
                            console.print("[dim]Попробуйте завтра.[/dim]\n")
                            limit_exceeded = True
                            break

                        if vtype == "test-required" and skip_test:
                            tracker.save_skipped(vacancy.vacancy_id, vacancy.title, vacancy.company, vacancy.url, "test_required")
                            report.add(vacancy.vacancy_id, vacancy.title, vacancy.company, "test_required")
                            _log_action(console, "test_required", vacancy)
                            skipped += 1
                            continue
                        if vtype == "already-applied":
                            skipped += 1
                            continue

                        status = apply_to_vacancy(page, vacancy, cover_letter, use_cover_letter, skip_foreign)
                        tracker.record(vacancy.vacancy_id, vacancy.title, vacancy.company, status)
                        report.add(vacancy.vacancy_id, vacancy.title, vacancy.company, status)
                        _log_action(console, status, vacancy)

                        # Сохраняем пропущенные с доп. вопросами
                        if status == "extra_steps":
                            tracker.save_skipped(vacancy.vacancy_id, vacancy.title, vacancy.company, vacancy.url, "extra_steps")

                        if status in ("sent", "cover_letter_sent"):
                            sent += 1
                        processed += 1

                        if _check_captcha(page):
                            _handle_captcha(page)

                        human_delay(delay_min, delay_max)

                    if sent >= max_apps or processed >= max_apps or shutdown or limit_exceeded:
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

        # Экспорт тестовых вакансий
        test_export_path = get_storage_path(config).parent / "test_vacancies.txt"
        exported = tracker.export_skipped_tests(test_export_path)

    # Отчёт
    console.print()
    print_report(report, console)

    if exported > 0:
        console.print(f"\n[dim]🧪 Тестовые вакансии ({exported} шт.) сохранены: {test_export_path}[/dim]")

    if report_path:
        export_report(report, report_path)
        console.print(f"[dim]Отчёт сохранён: {report_path}[/dim]")


def _log_action(console: Console, status: str, vacancy) -> None:
    """Выводит цветную строку лога для каждого действия."""
    icon = LOG_ICONS.get(status, "")
    color = STATUS_COLORS.get(status, "white")
    label = STATUS_LABELS.get(status, status)
    title = vacancy.title[:45] if hasattr(vacancy, 'title') else ""
    url = vacancy.url if hasattr(vacancy, 'url') else ""
    console.print(f"  {icon} [{color}]{label}[/{color}] {url} ( {title} )")
