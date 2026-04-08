"""Команды stats, done, query — статистика и работа с базой."""

from __future__ import annotations

from pathlib import Path

import click
from InquirerPy import inquirer
from rich.console import Console
from rich.table import Table

from hh_apply.cli import main


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

    # Защита от случайного DELETE/DROP/UPDATE
    sql_upper = sql.strip().upper()
    if not sql_upper.startswith("SELECT"):
        console.print("[red]Разрешены только SELECT запросы.[/red]")
        console.print('[dim]Пример: hh-apply query "SELECT * FROM applications"[/dim]')
        return
    dangerous = ("DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "ATTACH", "DETACH")
    for kw in dangerous:
        if kw in sql_upper:
            console.print(f"[red]Запрещённая операция: {kw}[/red]")
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
