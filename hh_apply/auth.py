"""Авторизация на hh.ru через Playwright."""

from __future__ import annotations

import os
from pathlib import Path

from patchright.sync_api import Page, Playwright

from hh_apply.stealth import apply_stealth, random_viewport, random_user_agent, get_chromium_version


def _get_launch_kwargs(config: dict) -> dict:
    """Базовые аргументы запуска Chromium с антидетектом."""
    browser_config = config.get("browser", {})

    launch_args = [
        "--disable-blink-features=AutomationControlled",
        "--disable-features=IsolateOrigins,site-per-process",
        "--no-first-run",
        "--no-default-browser-check",
    ]

    ignore_args = [
        "--enable-automation",
        "--disable-popup-blocking",
        "--disable-component-update",
        "--disable-default-apps",
    ]

    proxy = browser_config.get("proxy")
    if not proxy:
        proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy") or os.environ.get("ALL_PROXY") or os.environ.get("all_proxy")

    kwargs = dict(
        headless=browser_config.get("headless", False),
        args=launch_args,
        ignore_default_args=ignore_args,
    )
    if proxy:
        kwargs["proxy"] = {"server": proxy}

    return kwargs


def create_context(playwright: Playwright, config: dict) -> tuple:
    """Создаёт (browser, context) с антидетект-мерами."""
    from hh_apply.config import get_storage_path

    storage_path = get_storage_path(config)
    storage_path.parent.mkdir(parents=True, exist_ok=True)

    os.environ["TZ"] = "Europe/Moscow"

    browser = playwright.chromium.launch(**_get_launch_kwargs(config))

    viewport = random_viewport()
    ua = random_user_agent()

    real_version = get_chromium_version(browser)
    for ver in ("136", "135", "134", "133"):
        ua = ua.replace(f"Chrome/{ver}.0.0.0", f"Chrome/{real_version}.0.0.0")

    ctx_kwargs = dict(
        viewport=viewport,
        locale="ru-RU",
        timezone_id="Europe/Moscow",
        user_agent=ua,
        device_scale_factor=2,
    )

    if storage_path.exists():
        ctx_kwargs["storage_state"] = str(storage_path)

    context = browser.new_context(**ctx_kwargs)
    apply_stealth(context)

    return browser, context


def create_login_context(playwright: Playwright, config: dict) -> tuple:
    """Создаёт (browser, context) для логина — максимально чистый браузер.

    hh.ru усиленно защищает страницу авторизации. Любые stealth-патчи,
    кастомные launch args, user-agent подмена — всё это вызывает бесконечную
    загрузку после ввода номера телефона. Для логина используем Patchright
    как есть — пользователь всё равно логинится руками.
    """
    os.environ["TZ"] = "Europe/Moscow"

    browser = playwright.chromium.launch(
        headless=False,
        args=["--no-first-run", "--no-default-browser-check"],
    )

    context = browser.new_context(
        viewport=random_viewport(),
        locale="ru-RU",
        timezone_id="Europe/Moscow",
    )
    # НЕ применяем apply_stealth — ломает форму логина hh.ru
    # НЕ подменяем user_agent — hh.ru блокирует нестандартные
    # НЕ загружаем storage_state — начинаем с чистого листа

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
    """Проверяет авторизацию, при неудаче просит перезапустить login."""
    page.goto("https://hh.ru", wait_until="domcontentloaded", timeout=20000)
    page.wait_for_timeout(2000)

    if check_logged_in(page):
        return True

    page.goto("https://hh.ru/applicant/resumes", wait_until="domcontentloaded", timeout=20000)
    page.wait_for_timeout(2000)

    if "/account/login" not in page.url:
        return True

    return False
