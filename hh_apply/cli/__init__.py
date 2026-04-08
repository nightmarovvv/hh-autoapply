"""CLI-интерфейс hh-apply с InquirerPy для интерактивных меню."""

from __future__ import annotations

import click
from rich.console import Console

from hh_apply import __version__


WELCOME_TEXT = f"""[bold blue]
  _     _                           _
 | |__ | |__         __ _ _ __  _ __| |_   _
 | '_ \\| '_ \\ ___  / _` | '_ \\| '_ \\ | | | |
 | | | | | | |___|  (_| | |_) | |_) | | |_| |
 |_| |_|_| |_|      \\__,_| .__/| .__/|_|\\__, |
                          |_|   |_|      |___/
[/bold blue]
  [dim]v{__version__} — автоматические отклики на hh.ru[/dim]

[bold]Быстрый старт:[/bold]
  [green]1.[/green] hh-apply init        Настроить поиск и фильтры
  [green]2.[/green] hh-apply login       Войти в hh.ru (откроется браузер)
  [green]3.[/green] hh-apply run         Запустить отклики

[bold]Утилиты:[/bold]
  hh-apply stats         Статистика откликов
  hh-apply responses     Мониторинг ответов рекрутеров
  hh-apply boost         Поднять резюме в поиске
  hh-apply schedule      Настроить автозапуск
  hh-apply done          Убрать тестовую вакансию
  hh-apply query         SQL-запросы к базе
  hh-apply doctor        Диагностика окружения
  hh-apply completions   Автодополнение для shell

[dim]Подробнее: hh-apply <команда> --help[/dim]"""


class RichHelpGroup(click.Group):
    """Click Group с Rich-форматированием help."""

    def format_help(self, ctx, formatter):
        Console().print(WELCOME_TEXT)


@click.group(cls=RichHelpGroup, invoke_without_command=True)
@click.version_option(__version__, prog_name="hh-apply")
@click.pass_context
def main(ctx):
    """hh-apply — массовые автоматические отклики на вакансии hh.ru"""
    if ctx.invoked_subcommand is None:
        Console().print(WELCOME_TEXT)


# Импортируем субмодули, чтобы зарегистрировать команды на main
from hh_apply.cli import init_cmd  # noqa: E402, F401
from hh_apply.cli import run_cmd  # noqa: E402, F401
from hh_apply.cli import stats_cmd  # noqa: E402, F401
from hh_apply.cli import api_cmd  # noqa: E402, F401
from hh_apply.cli import schedule_cmd  # noqa: E402, F401
from hh_apply.cli import utils_cmd  # noqa: E402, F401


if __name__ == "__main__":
    main()
