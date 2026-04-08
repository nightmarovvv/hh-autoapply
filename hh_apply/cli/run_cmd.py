"""Команда run — запуск автооткликов."""

from __future__ import annotations

from pathlib import Path

import click
from InquirerPy import inquirer
from rich.console import Console

from hh_apply.cli import main


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
