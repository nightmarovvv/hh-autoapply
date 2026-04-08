"""Команды doctor, completions — утилиты и диагностика."""

from __future__ import annotations

import os
import sys

import click
from rich.console import Console

from hh_apply.cli import main


@main.command()
@click.option("-c", "--config", "config_path", default="config.yaml", help="Путь к конфигу")
def doctor(config_path):
    """Диагностика окружения — проверяет всё ли готово к запуску."""
    import sys
    import shutil
    from pathlib import Path
    from rich.console import Console

    console = Console()
    console.print("\n[bold blue]hh-apply doctor[/bold blue]\n")

    ok_count = 0
    total = 6

    # 1. Python
    v = sys.version_info
    if v >= (3, 9):
        console.print(f"  [green]\u2713[/green] Python {v.major}.{v.minor}.{v.micro}")
        ok_count += 1
    else:
        console.print(f"  [red]\u2717[/red] Python {v.major}.{v.minor} — нужен 3.9+")

    # 2. Patchright
    try:
        import patchright
        console.print(f"  [green]\u2713[/green] Patchright установлен")
        ok_count += 1
    except ImportError:
        console.print("  [red]\u2717[/red] Patchright не установлен: pip install patchright")

    # 3. Chromium (с таймаутом чтобы не зависнуть)
    chromium_found = False
    try:
        import subprocess as _sp
        result = _sp.run(
            [sys.executable, "-c", "from patchright.sync_api import sync_playwright; pw=sync_playwright().start(); b=pw.chromium.launch(headless=True); b.close(); pw.stop(); print('ok')"],
            capture_output=True, text=True, timeout=15,
        )
        chromium_found = result.stdout.strip() == "ok"
    except Exception:
        pass

    if chromium_found:
        console.print("  [green]\u2713[/green] Chromium доступен")
        ok_count += 1
    else:
        console.print("  [red]\u2717[/red] Chromium не найден: patchright install chromium")

    # 4. Config
    config_file = Path(config_path)
    if config_file.exists():
        try:
            from hh_apply.config import load_config
            load_config(str(config_file))
            console.print(f"  [green]\u2713[/green] Конфиг {config_path}")
            ok_count += 1
        except Exception as e:
            console.print(f"  [red]\u2717[/red] Конфиг битый: {e}")
    else:
        console.print(f"  [yellow]\u2717[/yellow] Конфиг не найден: hh-apply init")

    # 5. Auth
    try:
        from hh_apply.config import load_config, get_storage_path
        if config_file.exists():
            cfg = load_config(str(config_file))
            sp = get_storage_path(cfg)
            if sp.exists():
                console.print(f"  [green]\u2713[/green] Авторизация (storage_state)")
                ok_count += 1
            else:
                console.print("  [yellow]\u2717[/yellow] Не авторизован: hh-apply login")
        else:
            console.print("  [dim]-[/dim] Авторизация (нужен конфиг)")
    except Exception:
        console.print("  [dim]-[/dim] Авторизация (нужен конфиг)")

    # 6. Database
    try:
        from hh_apply.config import load_config, get_db_path
        if config_file.exists():
            cfg = load_config(str(config_file))
            db = get_db_path(cfg)
            from hh_apply.tracker import Tracker
            with Tracker(db) as t:
                total_apps = t.total()
            console.print(f"  [green]\u2713[/green] База данных ({total_apps} откликов)")
            ok_count += 1
        else:
            console.print("  [dim]-[/dim] База данных (нужен конфиг)")
    except Exception as e:
        console.print(f"  [red]\u2717[/red] База данных: {e}")

    console.print(f"\n  [{'green' if ok_count == total else 'yellow'}]{ok_count}/{total} проверок пройдено[/{'green' if ok_count == total else 'yellow'}]\n")


@main.command(epilog="""
Примеры:
  hh-apply completions bash      Скрипт для bash
  hh-apply completions zsh       Скрипт для zsh
  hh-apply completions fish      Скрипт для fish

Установка:
  # Bash
  hh-apply completions bash >> ~/.bashrc

  # Zsh
  hh-apply completions zsh >> ~/.zshrc

  # Fish
  hh-apply completions fish > ~/.config/fish/completions/hh-apply.fish
""")
@click.argument("shell", type=click.Choice(["bash", "zsh", "fish"]))
def completions(shell):
    """Сгенерировать скрипт автодополнения для shell."""
    import subprocess

    env = os.environ.copy()

    if shell == "bash":
        env["_HH_APPLY_COMPLETE"] = "bash_source"
    elif shell == "zsh":
        env["_HH_APPLY_COMPLETE"] = "zsh_source"
    elif shell == "fish":
        env["_HH_APPLY_COMPLETE"] = "fish_source"

    result = subprocess.run(
        [sys.executable, "-m", "hh_apply.cli"],
        env=env,
        capture_output=True,
        text=True,
    )

    if result.stdout:
        print(result.stdout)
    else:
        # Fallback: генерируем через Click напрямую
        env_var = f"_HH_APPLY_COMPLETE={shell}_source"
        Console().print(f"[dim]Выполните: {env_var} hh-apply[/dim]")
