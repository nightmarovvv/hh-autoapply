"""Авторизация на hh.ru через Playwright.

Создаёт browser context со стелс-мерами.
Проверяет авторизацию по нескольким признакам.
"""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import BrowserContext, Page, Playwright

from src.stealth import apply_stealth, random_viewport, random_user_agent


def create_context(playwright: Playwright, config: dict) -> BrowserContext:
    """Создаёт browser context с антидетект-мерами и сессией."""
    storage_path = config["storage_state_path"]
    Path(storage_path).parent.mkdir(parents=True, exist_ok=True)

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

    ctx_kwargs = dict(
        viewport=viewport,
        locale="ru-RU",
        timezone_id="Europe/Moscow",
        user_agent=ua,
    )

    if Path(storage_path).exists():
        ctx_kwargs["storage_state"] = storage_path
        print(f"[auth] Сессия загружена из {storage_path}")
    else:
        print("[auth] Сохранённой сессии нет")

    context = browser.new_context(**ctx_kwargs)
    apply_stealth(context)

    print(f"[auth] Viewport: {viewport['width']}x{viewport['height']}, UA: {ua[:50]}...")
    return context


def check_logged_in(page: Page) -> bool:
    """Проверяет авторизацию. Не навигирует — проверяет текущую страницу."""
    try:
        # Кнопка «Войти» — однозначный признак НЕ залогинен
        login_btn = page.locator('[data-qa="login"]')
        if login_btn.count() > 0 and login_btn.is_visible():
            return False

        # Элементы залогиненного юзера
        for sel in [
            '[data-qa="mainmenu_applicantProfile"]',
            '[data-qa="mainmenu_myResumes"]',
            'a[href*="/applicant/"]',
            'a[href*="/resume"]',
        ]:
            if page.locator(sel).count() > 0:
                return True

        # Проверяем по куке
        for cookie in page.context.cookies():
            if cookie["name"] in ("_hhtoken", "hhtoken", "hhuid"):
                return True

        return False
    except Exception:
        return False


def login_if_needed(page: Page, config: dict) -> bool:
    """Проверяет авторизацию. Если нет — говорит запустить login.py."""
    page.goto("https://hh.ru", wait_until="domcontentloaded", timeout=20000)
    page.wait_for_timeout(2000)

    if check_logged_in(page):
        print("[auth] Авторизован")
        return True

    # Пробуем перейти на страницу резюме — hh.ru редиректнет на логин если не залогинен
    page.goto("https://hh.ru/applicant/resumes", wait_until="domcontentloaded", timeout=20000)
    page.wait_for_timeout(2000)

    if "/account/login" not in page.url:
        print("[auth] Авторизован (по URL)")
        return True

    print("[auth] НЕ авторизован. Запусти: python3 login.py")
    return False
