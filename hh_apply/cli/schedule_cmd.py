"""Команда schedule — настройка автозапуска через crontab."""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from hh_apply.cli import main


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
    log_file = str(Path(config_abs).parent / "hh-apply-cron.log")

    # Полный путь к hh-apply (cron не видит venv PATH)
    import shutil
    hh_path = shutil.which("hh-apply") or "hh-apply"
    cmd = f'cd "{Path.cwd()}" && {hh_path} run --headless -c "{config_abs}" >> "{log_file}" 2>&1'
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
    log_file = str(Path(config_abs).parent / "hh-apply-cron.log")

    import shutil
    hh_path = shutil.which("hh-apply") or "hh-apply"
    cmd = f'cd "{Path.cwd()}" && {hh_path} boost -c "{config_abs}" >> "{log_file}" 2>&1'
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
