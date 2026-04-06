#!/usr/bin/env python3
"""Логин на hh.ru — сохранение сессии.

1. Открывается браузер с антидетект-мерами
2. Залогинься вручную
3. Вернись в терминал и нажми Enter
4. Скрипт проверит логин и сохранит сессию
"""

import sys
import yaml
from pathlib import Path
from playwright.sync_api import sync_playwright
from src.stealth import apply_stealth, random_viewport, random_user_agent
from src.auth import check_logged_in


def main():
    with open("config.yaml", "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    storage_path = config["storage_state_path"]
    Path(storage_path).parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            viewport=random_viewport(),
            locale="ru-RU",
            timezone_id="Europe/Moscow",
            user_agent=random_user_agent(),
        )
        apply_stealth(context)

        page = context.new_page()
        page.goto("https://hh.ru/account/login")

        print()
        print("=" * 50)
        print("Браузер открыт. Залогинься на hh.ru.")
        print("После логина вернись сюда и нажми Enter.")
        print("=" * 50)

        try:
            input("\n>>> Нажми Enter когда залогинишься: ")
        except (EOFError, KeyboardInterrupt):
            print("\nПрервано")
            browser.close()
            sys.exit(1)

        # Проверяем что действительно залогинился
        page.goto("https://hh.ru", wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        if check_logged_in(page):
            context.storage_state(path=storage_path)
            print(f"\nСессия сохранена в {storage_path}")
            print("Готово! Запускай: python3 main.py --dry-run")
        else:
            print("\nЛогин не подтверждён! Попробуй ещё раз.")

        browser.close()


if __name__ == "__main__":
    main()
