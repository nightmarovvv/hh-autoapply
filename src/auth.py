"""Авторизация на hh.ru через Playwright.

Создаёт browser context со stealth, проверяет авторизацию.
"""

from __future__ import annotations

import os
from pathlib import Path

from playwright.sync_api import BrowserContext, Page, Playwright

from src.stealth import apply_stealth, random_viewport, random_user_agent, get_chromium_version


def create_context(playwright: Playwright, config: dict) -> tuple:
    """Создаёт (browser, context) с антидетект-мерами."""
    storage_path = config["storage_state_path"]
    Path(storage_path).parent.mkdir(parents=True, exist_ok=True)

    # Timezone через env — надёжнее чем Playwright option
    os.environ["TZ"] = "Europe/Moscow"

    browser = playwright.chromium.launch(
        headless=config.get("headless", False),
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
            "--no-default-browser-check",
        ],
    )

    viewport = random_viewport()
    ua = random_user_agent()

    # Подставляем реальную версию Chromium в UA
    real_version = get_chromium_version(browser)
    ua = ua.replace("Chrome/134.0.0.0", f"Chrome/{real_version}.0.0.0")
    ua = ua.replace("Chrome/133.0.0.0", f"Chrome/{real_version}.0.0.0")

    ctx_kwargs = dict(
        viewport=viewport,
        locale="ru-RU",
        timezone_id="Europe/Moscow",
        user_agent=ua,
        device_scale_factor=2,  # Retina Mac
    )

    if Path(storage_path).exists():
        ctx_kwargs["storage_state"] = storage_path
        print(f"[auth] Сессия загружена из {storage_path}")
    else:
        print("[auth] Нет сохранённой сессии")

    context = browser.new_context(**ctx_kwargs)
    apply_stealth(context)  # ПЕРЕД new_page()!

    print(f"[auth] Chromium {real_version}, viewport {viewport['width']}x{viewport['height']}")
    return browser, context


def check_logged_in(page: Page) -> bool:
    """Проверяет авторизацию на текущей странице."""
    try:
        login_btn = page.locator('[data-qa="login"]')
        if login_btn.count() > 0 and login_btn.is_visible():
            return False

        for sel in [
            '[data-qa="mainmenu_applicantProfile"]',
            '[data-qa="mainmenu_myResumes"]',
            'a[href*="/applicant/"]',
            'a[href*="/resume"]',
        ]:
            if page.locator(sel).count() > 0:
                return True

        for cookie in page.context.cookies():
            if cookie["name"] in ("_hhtoken", "hhtoken", "hhuid"):
                return True

        return False
    except Exception:
        return False


def login_if_needed(page: Page, config: dict) -> bool:
    """Проверяет авторизацию."""
    page.goto("https://hh.ru", wait_until="domcontentloaded", timeout=20000)
    page.wait_for_timeout(2000)

    if check_logged_in(page):
        print("[auth] Авторизован")
        return True

    page.goto("https://hh.ru/applicant/resumes", wait_until="domcontentloaded", timeout=20000)
    page.wait_for_timeout(2000)

    if "/account/login" not in page.url:
        print("[auth] Авторизован (по URL)")
        return True

    print("[auth] НЕ авторизован. Запусти: python3 login.py")
    return False
