"""Оркестратор автооткликов — основной цикл с Rich Live-прогрессом."""

from __future__ import annotations

import logging
import signal
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn, SpinnerColumn, MofNCompleteColumn
from rich.layout import Layout
from rich.text import Text
from patchright.sync_api import sync_playwright

from hh_apply.config import get_storage_path, get_db_path
from hh_apply.auth import create_context, login_if_needed, check_logged_in
from hh_apply.search import (
    do_search, collect_vacancy_ids_from_page, go_next_page, dismiss_ads,
    sort_vacancies_fresh_first, count_search_results,
)
from hh_apply.apply import apply_to_vacancy, human_delay, _check_captcha, _handle_captcha, _dismiss_popups
from hh_apply.stealth import human_wait
from hh_apply.api_apply import check_vacancy_type
from hh_apply.tracker import Tracker
from hh_apply.filters import should_skip_vacancy
from hh_apply.report import SessionReport, print_report, export_report
from hh_apply.logging_config import setup_logging

logger = logging.getLogger("hh_apply.runner")


# Эмодзи для логов
LOG_ICONS = {
    "sent": "\U0001f4e8",           # 📨
    "cover_letter_sent": "\U0001f4e8",
    "test_required": "\U0001f9ea",   # 🧪
    "extra_steps": "\u2753",         # ❓
    "letter_required": "\u270f\ufe0f",  # ✏️
    "already_applied": "\u23e9",     # ⏩
    "filtered": "\u23e9",
    "error": "\u274c",               # ❌
    "no_button": "\u23e9",
    "captcha": "\u26a0\ufe0f",       # ⚠️
    "rate_limited": "\u26d4",        # ⛔
}

STATUS_COLORS = {
    "sent": "green",
    "cover_letter_sent": "green",
    "test_required": "yellow",
    "extra_steps": "yellow",
    "letter_required": "yellow",
    "already_applied": "dim",
    "filtered": "dim",
    "error": "red",
    "no_button": "dim",
    "captcha": "yellow",
    "rate_limited": "red bold",
}

STATUS_LABELS = {
    "sent": "Отклик отправлен",
    "cover_letter_sent": "Отклик с письмом",
    "test_required": "Тест — сохранено",
    "extra_steps": "Доп. вопросы — скип",
    "letter_required": "Требует письмо — скип",
    "already_applied": "Уже откликались",
    "filtered": "Отфильтровано",
    "error": "Ошибка",
    "no_button": "Нет кнопки",
    "captcha": "Капча",
    "rate_limited": "Rate limit",
}


class LiveProgress:
    """Rich Live-дашборд для отображения прогресса откликов."""

    def __init__(self, console: Console, max_apps: int):
        self.console = console
        self.max_apps = max_apps
        self.sent = 0
        self.tests = 0
        self.skipped = 0
        self.errors = 0
        self.current_vacancy = ""
        self.current_company = ""
        self.log_lines: list[Text] = []
        self.max_log_lines = 12
        self.start_time = time.time()

    def build_display(self) -> Panel:
        # Счётчики
        total_processed = self.sent + self.tests + self.skipped + self.errors
        pct = (self.sent / self.max_apps * 100) if self.max_apps > 0 else 0
        bar_filled = int(pct / 100 * 30)
        bar = f"[green]{'█' * bar_filled}[/green][dim]{'░' * (30 - bar_filled)}[/dim]"

        # ETA
        elapsed = time.time() - self.start_time
        total_processed = self.sent + self.tests + self.skipped + self.errors
        eta_str = ""
        if total_processed > 0 and self.sent < self.max_apps:
            avg_per_item = elapsed / total_processed
            remaining_items = self.max_apps - self.sent
            eta_seconds = avg_per_item * remaining_items
            eta_min = int(eta_seconds // 60)
            eta_sec = int(eta_seconds % 60)
            eta_str = f"  [dim]ETA: ~{eta_min} мин {eta_sec} сек[/dim]"

        header = (
            f"  {bar}  [bold green]{self.sent}[/bold green]/{self.max_apps}{eta_str}\n"
            f"\n"
            f"  [green]Отправлено: {self.sent}[/green]  "
            f"[yellow]Тесты: {self.tests}[/yellow]  "
            f"[dim]Пропущено: {self.skipped}[/dim]  "
            f"[red]Ошибки: {self.errors}[/red]"
        )

        if self.current_vacancy:
            header += f"\n\n  [bold]>> {self.current_vacancy[:55]}[/bold] — [dim]{self.current_company[:25]}[/dim]"

        # Лог последних действий
        if self.log_lines:
            header += "\n"
            for line in self.log_lines[-self.max_log_lines:]:
                header += f"\n  {line}"

        return Panel(header, title="[bold blue]hh-apply[/bold blue]", border_style="blue")

    def log(self, status: str, vacancy) -> None:
        icon = LOG_ICONS.get(status, "")
        color = STATUS_COLORS.get(status, "white")
        label = STATUS_LABELS.get(status, status)
        title = vacancy.title[:40] if hasattr(vacancy, 'title') else ""
        company = vacancy.company[:25] if hasattr(vacancy, 'company') else ""
        self.log_lines.append(Text.from_markup(
            f"{icon} [{color}]{label}[/{color}] {title} — {company}"
        ))

        if status in ("sent", "cover_letter_sent"):
            self.sent += 1
        elif status == "test_required":
            self.tests += 1
        elif status in ("error", "rate_limited"):
            self.errors += 1
        elif status in ("filtered", "already_applied", "extra_steps", "no_button"):
            self.skipped += 1

    def set_current(self, vacancy) -> None:
        self.current_vacancy = vacancy.title if hasattr(vacancy, 'title') else ""
        self.current_company = vacancy.company if hasattr(vacancy, 'company') else ""


def _retry_apply(page, vacancy, cover_letter, use_cover_letter, skip_foreign,
                 max_retries: int = 2) -> str:
    """Откликается с retry и экспоненциальной задержкой."""
    last_status = "error"
    for attempt in range(max_retries + 1):
        status = apply_to_vacancy(page, vacancy, cover_letter, use_cover_letter, skip_foreign)
        if status != "error" or attempt >= max_retries:
            return status
        last_status = status
        delay = 2 ** (attempt + 1)  # 2s, 4s
        time.sleep(delay)
    return last_status


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

    setup_logging(Path(config.get("browser", {}).get("data_dir", "~/.hh-apply")).expanduser())
    logger.info("Сессия: query=%s, limit=%d, dry_run=%s", search_config.get("query", ""), max_apps, dry_run)
    skip_test = filters_config.get("skip_test_vacancies", True)
    skip_foreign = filters_config.get("skip_foreign", False)

    storage_path = get_storage_path(config)
    db_path = get_db_path(config)

    console.print()
    from hh_apply import __version__
    console.print(f"[bold blue]hh-apply[/bold blue] v{__version__}")
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

                try:
                    if not login_if_needed(page, config):
                        console.print("[red]Не авторизован.[/red]")
                        console.print("[dim]Запустите: [bold]hh-apply login[/bold][/dim]")
                        return
                except Exception as e:
                    logger.error("Ошибка авторизации: %s", e)
                    console.print("[red]Не удалось проверить авторизацию (проблема с сетью).[/red]")
                    console.print("[dim]Проверьте интернет и попробуйте снова.[/dim]")
                    return

                console.print("[green]Авторизован[/green]\n")

                try:
                    do_search(page, config)
                except Exception as e:
                    console.print(f"[red]Ошибка поиска: {e}[/red]")
                    console.print("[dim]Проверьте интернет или измените фильтры в конфиге.[/dim]")
                    return

                if _check_captcha(page):
                    console.print("[yellow]Капча на странице поиска![/yellow]")
                    _handle_captcha(page)

                # Показываем количество найденных вакансий
                total_found = count_search_results(page)
                if total_found is not None:
                    console.print(f"[dim]Найдено вакансий: {total_found}[/dim]\n")

                search_url = page.url
                sent = 0
                skipped = 0
                processed = 0
                page_num = 0
                max_pages = 30
                limit_exceeded = False
                consecutive_rate_limits = 0

                # Dry-run: собираем все вакансии в таблицу
                if dry_run:
                    _run_dry(page, config, tracker, filters_config, console, max_apps, max_pages)
                    return

                # Live progress dashboard
                progress = LiveProgress(console, max_apps)

                with Live(progress.build_display(), console=console, refresh_per_second=4) as live:
                    while sent < max_apps and processed < max_apps and page_num < max_pages and not shutdown and not limit_exceeded:
                        dismiss_ads(page)
                        vacancies = collect_vacancy_ids_from_page(page)

                        if not vacancies:
                            if not go_next_page(page):
                                break
                            page_num += 1
                            continue

                        # Приоритизация: свежие вакансии первыми
                        vacancies = sort_vacancies_fresh_first(vacancies)

                        new = [v for v in vacancies if not tracker.is_applied(v.vacancy_id) and not tracker.is_skipped(v.vacancy_id)]

                        for vacancy in new:
                            if sent >= max_apps or processed >= max_apps or shutdown or limit_exceeded:
                                break

                            progress.set_current(vacancy)
                            live.update(progress.build_display())

                            # Session check каждые 15 откликов
                            if (sent + skipped) > 0 and (sent + skipped) % 15 == 0:
                                try:
                                    logged_in = check_logged_in(page)
                                except Exception as e:
                                    logger.warning("Ошибка проверки сессии: %s", e)
                                    logged_in = True  # Лучше продолжить чем остановиться
                                if not logged_in:
                                    # Retry авторизации
                                    if not login_if_needed(page, config):
                                        progress.log_lines.append(Text.from_markup("[red]Сессия истекла. Запустите: hh-apply login[/red]"))
                                        live.update(progress.build_display())
                                        shutdown = True
                                        break
                                    # Вернуться на страницу поиска
                                    try:
                                        page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
                                        human_wait(page, 2000)
                                    except Exception as e:
                                        logger.warning("Не удалось вернуться на страницу поиска: %s", e)

                            # Фильтры
                            skip_reason = should_skip_vacancy(vacancy, filters_config)
                            if skip_reason:
                                tracker.save_skipped(vacancy.vacancy_id, vacancy.title, vacancy.company, vacancy.url, "excluded_filter")
                                report.add(vacancy.vacancy_id, vacancy.title, vacancy.company, "filtered")
                                progress.log("filtered", vacancy)
                                live.update(progress.build_display())
                                skipped += 1
                                continue

                            # API-проверка типа
                            try:
                                info = check_vacancy_type(page, vacancy.vacancy_id)
                            except Exception as e:
                                logger.warning("API check_vacancy_type failed для %s: %s", vacancy.vacancy_id, e)
                                info = {"type": "unknown"}
                            vtype = info.get("type", "unknown")

                            # Лимит откликов
                            if vtype == "negotiations-limit-exceeded" or info.get("error") == "negotiations-limit-exceeded":
                                progress.log_lines.append(Text.from_markup(
                                    "[yellow bold]Лимит откликов на сегодня исчерпан (200)[/yellow bold]"
                                ))
                                live.update(progress.build_display())
                                limit_exceeded = True
                                break

                            if vtype == "test-required" and skip_test:
                                tracker.save_skipped(vacancy.vacancy_id, vacancy.title, vacancy.company, vacancy.url, "test_required")
                                report.add(vacancy.vacancy_id, vacancy.title, vacancy.company, "test_required")
                                progress.log("test_required", vacancy)
                                live.update(progress.build_display())
                                skipped += 1
                                continue
                            if vtype == "already-applied":
                                tracker.record(vacancy.vacancy_id, vacancy.title, vacancy.company, "already_applied")
                                skipped += 1
                                continue

                            # Закрываем попапы ПЕРЕД откликом
                            _dismiss_popups(page)

                            status = _retry_apply(page, vacancy, cover_letter, use_cover_letter, skip_foreign)

                            # Circuit breaker: 3 rate limit подряд → пауза 5 мин
                            if status == "rate_limited":
                                consecutive_rate_limits += 1
                                if consecutive_rate_limits >= 3:
                                    progress.log_lines.append(Text.from_markup(
                                        "[red bold]3 rate-limit подряд — пауза 5 мин[/red bold]"
                                    ))
                                    live.update(progress.build_display())
                                    time.sleep(300)
                                    consecutive_rate_limits = 0
                                    continue
                            else:
                                consecutive_rate_limits = 0

                            tracker.record(vacancy.vacancy_id, vacancy.title, vacancy.company, status)
                            report.add(vacancy.vacancy_id, vacancy.title, vacancy.company, status)
                            progress.log(status, vacancy)
                            live.update(progress.build_display())

                            # Сохраняем пропущенные
                            if status == "extra_steps":
                                tracker.save_skipped(vacancy.vacancy_id, vacancy.title, vacancy.company, vacancy.url, "extra_steps")
                            elif status == "letter_required":
                                tracker.save_skipped(vacancy.vacancy_id, vacancy.title, vacancy.company, vacancy.url, "letter_required")

                            if status in ("sent", "cover_letter_sent"):
                                sent += 1
                            processed += 1

                            # Страховка: если мы не на странице поиска — вернуться
                            if "/search/vacancy" not in page.url:
                                try:
                                    page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
                                    human_wait(page, 2000)
                                except Exception as e:
                                    logger.warning("Не удалось вернуться на поиск: %s", e)

                            if _check_captcha(page):
                                _handle_captcha(page)

                            human_delay(delay_min, delay_max)

                        if sent >= max_apps or processed >= max_apps or shutdown or limit_exceeded:
                            break

                        try:
                            if not go_next_page(page):
                                break
                        except Exception as e:
                            logger.warning("Ошибка пагинации: %s", e)
                            break

                        page_num += 1

                        if _check_captcha(page):
                            _handle_captcha(page)

            finally:
                try:
                    context.storage_state(path=str(storage_path))
                except Exception as e:
                    logger.warning("Не удалось сохранить сессию: %s", e)
                context.close()
                browser.close()

        # Экспорт тестовых вакансий
        test_export_path = get_storage_path(config).parent / "test_vacancies.txt"
        exported = tracker.export_skipped_tests(test_export_path)

    # Отчёт
    console.print()
    print_report(report, console)

    if exported > 0:
        console.print(f"\n[dim]Тестовые вакансии ({exported} шт.) сохранены: {test_export_path}[/dim]")

    if report_path:
        export_report(report, report_path)
        console.print(f"[dim]Отчёт сохранён: {report_path}[/dim]")

    console.print("\n[dim]Совет: hh-apply stats — посмотреть общую статистику[/dim]")

    logger.info("Сессия завершена: sent=%d, total=%d", report.sent, report.total)


def _run_dry(page, config, tracker, filters_config, console, max_apps, max_pages):
    """Dry-run: собирает вакансии и показывает таблицу."""
    from InquirerPy import inquirer

    all_vacancies = []
    page_num = 0
    skipped_applied = 0
    skipped_filtered = 0
    skipped_prev = 0
    filter_reasons = {}

    console.print("[bold]Собираю вакансии...[/bold]")

    while len(all_vacancies) < max_apps and page_num < max_pages:
        dismiss_ads(page)
        vacancies = collect_vacancy_ids_from_page(page)

        if not vacancies:
            if not go_next_page(page):
                break
            page_num += 1
            continue

        vacancies = sort_vacancies_fresh_first(vacancies)

        for v in vacancies:
            if len(all_vacancies) >= max_apps:
                break
            if tracker.is_applied(v.vacancy_id):
                skipped_applied += 1
                continue
            if tracker.is_skipped(v.vacancy_id):
                skipped_prev += 1
                continue
            skip = should_skip_vacancy(v, filters_config)
            if skip:
                filter_reasons[skip] = filter_reasons.get(skip, 0) + 1
                skipped_filtered += 1
                continue
            all_vacancies.append(v)

        if not go_next_page(page):
            break
        page_num += 1

    if not all_vacancies:
        console.print("[yellow]Нет подходящих вакансий.[/yellow]")
        return

    # Rich таблица
    table = Table(title=f"[bold]Найдено {len(all_vacancies)} вакансий (dry-run)[/bold]", border_style="blue")
    table.add_column("#", style="dim", width=4)
    table.add_column("Вакансия", style="bold", max_width=50)
    table.add_column("Компания", max_width=25)
    table.add_column("Зарплата", style="green", max_width=25)
    table.add_column("Дата", style="dim", max_width=12)

    salary_from = config.get("search", {}).get("salary_from")

    for i, v in enumerate(all_vacancies, 1):
        # Цветная зарплата
        salary_display = v.salary or "[dim]—[/dim]"
        if v.salary and salary_from:
            try:
                num = int("".join(c for c in v.salary if c.isdigit()))
                if num >= salary_from:
                    salary_display = f"[bold green]{v.salary}[/bold green]"
            except (ValueError, TypeError):
                pass

        table.add_row(
            str(i),
            v.title[:50],
            v.company[:25],
            salary_display,
            v.published_date or "[dim]—[/dim]",
        )

    console.print(table)

    # Итоги фильтрации
    if skipped_applied or skipped_filtered or skipped_prev:
        console.print()
        parts = []
        if skipped_applied:
            parts.append(f"уже откликались: {skipped_applied}")
        if skipped_prev:
            parts.append(f"ранее пропущены: {skipped_prev}")
        if skipped_filtered:
            reasons_str = ", ".join(f"{r}: {c}" for r, c in sorted(filter_reasons.items(), key=lambda x: -x[1]))
            parts.append(f"отфильтровано: {skipped_filtered} ({reasons_str})")
        console.print(f"[dim]Пропущено: {' | '.join(parts)}[/dim]")

    console.print(f"\n[green]Найдено {len(all_vacancies)} вакансий для отклика.[/green]")
    console.print("\n[dim]Это пробный режим — отклики НЕ отправлены.[/dim]")

    # Интерактивный выбор
    proceed = inquirer.confirm(
        message="Откликнуться на выбранные вакансии?",
        default=False,
    ).execute()

    if not proceed:
        console.print("[dim]Запустите [bold]hh-apply run[/bold] чтобы откликнуться на все вакансии.[/dim]")
        return

    choices = [f"{i}. {v.title[:45]} — {v.company[:20]}" for i, v in enumerate(all_vacancies, 1)]
    selected = inquirer.checkbox(
        message="Выберите вакансии (пробел — отметить, Enter — подтвердить):",
        choices=choices,
    ).execute()

    if not selected:
        console.print("[dim]Ничего не выбрано.[/dim]")
        return

    selected_indices = set()
    for s in selected:
        try:
            idx = int(s.split(".")[0]) - 1
            selected_indices.add(idx)
        except (ValueError, IndexError):
            pass

    selected_vacancies = [v for i, v in enumerate(all_vacancies) if i in selected_indices]
    console.print(f"\n[bold]Откликаюсь на {len(selected_vacancies)} вакансий...[/bold]")

    from hh_apply.apply import apply_to_vacancy, human_delay
    apply_config = config.get("apply", {})
    use_cover_letter = apply_config.get("use_cover_letter", True)
    cover_letter = apply_config.get("cover_letter", "").strip() if use_cover_letter else ""
    skip_foreign = config.get("filters", {}).get("skip_foreign", False)
    delay_min = apply_config.get("delay_min", 1.5)
    delay_max = apply_config.get("delay_max", 4.0)

    sent = 0
    for v in selected_vacancies:
        status = apply_to_vacancy(page, v, cover_letter, use_cover_letter, skip_foreign)
        tracker.record(v.vacancy_id, v.title, v.company, status)
        icon = LOG_ICONS.get(status, "")
        color = STATUS_COLORS.get(status, "white")
        label = STATUS_LABELS.get(status, status)
        console.print(f"  {icon} [{color}]{label}[/{color}] {v.title[:45]} — {v.company[:20]}")
        if status in ("sent", "cover_letter_sent"):
            sent += 1
        human_delay(delay_min, delay_max)

    console.print(f"\n[green]Отправлено: {sent}/{len(selected_vacancies)}[/green]")
