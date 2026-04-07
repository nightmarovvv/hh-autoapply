"""Генерация отчёта после сессии автооткликов."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


@dataclass
class SessionResult:
    """Результат одного отклика."""
    vacancy_id: str
    title: str
    company: str
    status: str
    error: str = ""


@dataclass
class SessionReport:
    """Аккумулятор результатов сессии."""
    results: list[SessionResult] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)

    def add(self, vacancy_id: str, title: str, company: str, status: str, error: str = ""):
        self.results.append(SessionResult(
            vacancy_id=vacancy_id,
            title=title,
            company=company,
            status=status,
            error=error,
        ))

    @property
    def sent(self) -> int:
        return sum(1 for r in self.results if r.status in ("sent", "cover_letter_sent", "letter_sent"))

    @property
    def cover_letter_sent(self) -> int:
        return sum(1 for r in self.results if r.status == "cover_letter_sent")

    @property
    def already_applied(self) -> int:
        return sum(1 for r in self.results if r.status == "already_applied")

    @property
    def test_required(self) -> list[SessionResult]:
        return [r for r in self.results if r.status == "test_required"]

    @property
    def extra_steps(self) -> list[SessionResult]:
        return [r for r in self.results if r.status == "extra_steps"]

    @property
    def errors(self) -> list[SessionResult]:
        return [r for r in self.results if r.status == "error"]

    @property
    def filtered(self) -> int:
        return sum(1 for r in self.results if r.status == "filtered")

    @property
    def elapsed(self) -> float:
        return time.time() - self.start_time


def print_report(report: SessionReport, console: Console | None = None) -> None:
    """Выводит красивый отчёт в терминал."""
    if console is None:
        console = Console()

    elapsed = report.elapsed
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    # Основная статистика
    lines = []
    lines.append(f"[bold]Всего обработано:[/bold]     {len(report.results)} вакансий")
    lines.append(f"[bold green]Отклики отправлены:[/bold green]  {report.sent}")
    if report.cover_letter_sent > 0:
        lines.append(f"  [dim]С сопроводительным:[/dim]  {report.cover_letter_sent}")
    if report.already_applied > 0:
        lines.append(f"[dim]Уже откликались:[/dim]     {report.already_applied}")
    if report.test_required:
        lines.append(f"[yellow]Тестовое задание:[/yellow]    {len(report.test_required)}")
    if report.extra_steps:
        lines.append(f"[yellow]Доп. вопросы:[/yellow]        {len(report.extra_steps)}")
    if report.filtered > 0:
        lines.append(f"[dim]Отфильтровано:[/dim]       {report.filtered}")
    if report.errors:
        lines.append(f"[red]Ошибки:[/red]              {len(report.errors)}")
    lines.append("")
    lines.append(f"[dim]Время работы: {minutes} мин {seconds} сек[/dim]")

    panel_content = "\n".join(lines)
    console.print(Panel(panel_content, title="[bold]Отчёт сессии hh-apply[/bold]", border_style="blue"))

    # Тестовые вакансии
    if report.test_required:
        console.print()
        table = Table(title="Вакансии с тестовым заданием (откликнитесь сами)", border_style="yellow")
        table.add_column("#", style="dim", width=3)
        table.add_column("Вакансия", style="bold")
        table.add_column("Компания")
        table.add_column("Ссылка", style="cyan")

        for i, r in enumerate(report.test_required, 1):
            table.add_row(str(i), r.title[:50], r.company[:30], f"https://hh.ru/vacancy/{r.vacancy_id}")

        console.print(table)

    # Вакансии с доп. вопросами
    if report.extra_steps:
        console.print()
        table = Table(title="Вакансии с доп. вопросами", border_style="yellow")
        table.add_column("#", style="dim", width=3)
        table.add_column("Вакансия", style="bold")
        table.add_column("Компания")
        table.add_column("Ссылка", style="cyan")

        for i, r in enumerate(report.extra_steps, 1):
            table.add_row(str(i), r.title[:50], r.company[:30], f"https://hh.ru/vacancy/{r.vacancy_id}")

        console.print(table)

    # Ошибки
    if report.errors:
        console.print()
        table = Table(title="Ошибки", border_style="red")
        table.add_column("#", style="dim", width=3)
        table.add_column("Вакансия", style="bold")
        table.add_column("Компания")

        for i, r in enumerate(report.errors, 1):
            table.add_row(str(i), r.title[:50], r.company[:30])

        console.print(table)


def export_report(report: SessionReport, path: str) -> None:
    """Экспортирует отчёт в текстовый файл."""
    lines = []
    lines.append("=" * 60)
    lines.append("ОТЧЁТ СЕССИИ hh-apply")
    lines.append("=" * 60)
    lines.append(f"Всего обработано: {len(report.results)}")
    lines.append(f"Отклики отправлены: {report.sent}")
    lines.append(f"С сопроводительным: {report.cover_letter_sent}")
    lines.append(f"Уже откликались: {report.already_applied}")
    lines.append(f"Тестовое задание: {len(report.test_required)}")
    lines.append(f"Доп. вопросы: {len(report.extra_steps)}")
    lines.append(f"Ошибки: {len(report.errors)}")

    elapsed = report.elapsed
    lines.append(f"Время: {int(elapsed // 60)} мин {int(elapsed % 60)} сек")

    if report.test_required:
        lines.append("")
        lines.append("--- Тестовые задания ---")
        for r in report.test_required:
            lines.append(f"  {r.title} — {r.company}")
            lines.append(f"  https://hh.ru/vacancy/{r.vacancy_id}")

    if report.extra_steps:
        lines.append("")
        lines.append("--- Доп. вопросы ---")
        for r in report.extra_steps:
            lines.append(f"  {r.title} — {r.company}")
            lines.append(f"  https://hh.ru/vacancy/{r.vacancy_id}")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
