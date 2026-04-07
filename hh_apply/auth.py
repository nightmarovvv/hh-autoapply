"""Авторизация на hh.ru через Playwright."""

from __future__ import annotations

import getpass
import os
from pathlib import Path

from rich.console import Console
from patchright.sync_api import Page, Playwright

from hh_apply.stealth import apply_stealth, random_viewport, random_user_agent, get_chromium_version


# === Селекторы формы логина hh.ru (с fallback-цепочками) ===

PHONE_INPUT_SELECTORS = [
    'input[data-qa="login-input-username"]',
    'input[name="username"]',
    'input[type="tel"]',
    'input[autocomplete="tel"]',
    'input[placeholder*="телефон" i]',
    'input[placeholder*="phone" i]',
]

CODE_INPUT_SELECTORS = [
    'input[data-qa="login-input-code"]',
    'input[name="code"]',
    'input[inputmode="numeric"]',
    'input[autocomplete="one-time-code"]',
    'input[data-qa="otp-code-input"]',
]

EMAIL_INPUT_SELECTORS = [
    'input[data-qa="login-input-username"]',
    'input[name="username"]',
    'input[type="email"]',
    'input[autocomplete="email"]',
    'input[placeholder*="почт" i]',
    'input[placeholder*="email" i]',
]

PASSWORD_INPUT_SELECTORS = [
    'input[data-qa="login-input-password"]',
    'input[name="password"]',
    'input[type="password"]',
    'input[autocomplete="current-password"]',
]

SUBMIT_SELECTORS = [
    'button[data-qa="account-login-submit"]',
    'button[data-qa="login-button-submit"]',
    'button[type="submit"]',
]

PASSWORD_TAB_SELECTORS = [
    '[data-qa="expand-login-by-password"]',
    'button:has-text("По паролю")',
    'a:has-text("По паролю")',
    'span:has-text("По паролю")',
    '[data-qa="login-by-password"]',
]


def _find_element(page: Page, selectors: list[str], timeout: int = 3000):
    """Находит первый видимый элемент из списка селекторов."""
    for sel in selectors:
        el = page.locator(sel)
        try:
            if el.count() > 0 and el.first.is_visible(timeout=timeout):
                return el.first
        except Exception:
            continue
    return None


def _click_submit(page: Page) -> bool:
    """Кликает кнопку отправки формы."""
    btn = _find_element(page, SUBMIT_SELECTORS)
    if btn:
        btn.click()
        return True
    # Fallback: ищем кнопку по тексту
    for text in ["Войти", "Продолжить", "Получить код", "Далее"]:
        fallback = page.locator(f'button:has-text("{text}")')
        if fallback.count() > 0:
            fallback.first.click()
            return True
    return False


# Кнопки которые нужно нажать чтобы попасть на форму логина
LOGIN_PAGE_ENTRY_SELECTORS = [
    '[data-qa="login"]',
    '[data-qa="account-login"]',
    'a[href*="/account/login"]',
    'button:has-text("Войти")',
    'a:has-text("Войти")',
]


def _navigate_to_login_form(page: Page, console: Console) -> bool:
    """Открывает hh.ru и добирается до формы ввода телефона/email.

    hh.ru может показать главную страницу где нужно сначала нажать "Войти",
    а потом уже появится форма. Обрабатываем это.
    """
    try:
        page.goto("https://hh.ru/account/login", timeout=60000, wait_until="domcontentloaded")
    except Exception:
        console.print("[yellow]Страница загружается медленно...[/yellow]")

    page.wait_for_timeout(2000)

    # Проверяем — уже на странице с полем ввода?
    phone_input = _find_element(page, PHONE_INPUT_SELECTORS, timeout=2000)
    if phone_input:
        return True

    # Нет поля — ищем кнопку "Войти" и кликаем
    entry_btn = _find_element(page, LOGIN_PAGE_ENTRY_SELECTORS, timeout=3000)
    if entry_btn:
        entry_btn.click()
        page.wait_for_timeout(3000)

    # Пробуем ещё раз перейти напрямую
    if not _find_element(page, PHONE_INPUT_SELECTORS, timeout=2000):
        try:
            page.goto("https://hh.ru/account/login?backurl=%2F", timeout=30000, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
        except Exception:
            pass

    return _find_element(page, PHONE_INPUT_SELECTORS, timeout=3000) is not None


def _check_login_error(page: Page) -> str | None:
    """Проверяет наличие ошибки на странице логина."""
    error_selectors = [
        '[data-qa="login-error-message"]',
        '[class*="login-error"]',
        '[class*="form-error"]',
        '[role="alert"]',
    ]
    for sel in error_selectors:
        el = page.locator(sel)
        if el.count() > 0:
            text = el.first.text_content()
            if text and text.strip():
                return text.strip()
    return None


# === Три способа логина ===

def login_manual(page: Page, console: Console) -> bool:
    """Ручной логин — пользователь сам вводит данные в браузере."""
    try:
        page.goto("https://hh.ru/account/login", timeout=60000, wait_until="domcontentloaded")
    except Exception:
        console.print("[yellow]Страница загружается медленно, но браузер открыт.[/yellow]")

    console.print("Браузер открыт. Залогиньтесь на hh.ru.")
    console.print("Не торопитесь — введите код, дождитесь загрузки.\n")

    try:
        input(">>> Нажмите Enter когда залогинитесь: ")
    except (EOFError, KeyboardInterrupt):
        return False

    try:
        page.goto("https://hh.ru", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)
    except Exception:
        pass

    return check_logged_in(page)


def login_phone(page: Page, console: Console) -> bool:
    """Логин по номеру телефона + SMS-код из терминала."""
    console.print("[dim]Открываю страницу логина...[/dim]")

    if not _navigate_to_login_form(page, console):
        console.print("[red]Не удалось открыть форму логина.[/red]")
        console.print("[dim]Попробуйте 'Сам в браузере'.[/dim]")
        return False

    # 1. Ввод номера телефона
    try:
        phone = input("\n>>> Номер телефона (например +79991234567): ").strip()
    except (EOFError, KeyboardInterrupt):
        return False

    if not phone:
        console.print("[red]Номер не введён.[/red]")
        return False

    phone_input = _find_element(page, PHONE_INPUT_SELECTORS)
    if not phone_input:
        console.print("[red]Не удалось найти поле ввода телефона.[/red]")
        console.print("[dim]Попробуйте 'Сам в браузере'.[/dim]")
        return False

    phone_input.fill(phone)
    page.wait_for_timeout(500)

    # 2. Нажимаем кнопку
    if not _click_submit(page):
        console.print("[red]Не удалось нажать кнопку отправки.[/red]")
        return False

    console.print("[dim]Отправлено. Ожидаем SMS...[/dim]")
    page.wait_for_timeout(3000)

    # Проверяем ошибку
    error = _check_login_error(page)
    if error:
        console.print(f"[red]Ошибка: {error}[/red]")
        return False

    # 3. Ввод SMS-кода
    code_input = _find_element(page, CODE_INPUT_SELECTORS, timeout=10000)
    if not code_input:
        # Может быть, сразу залогинило (уже авторизован)
        if check_logged_in(page):
            return True
        console.print("[red]Не удалось найти поле ввода кода.[/red]")
        console.print("[dim]Попробуйте 'Сам в браузере'.[/dim]")
        return False

    try:
        sms_code = input(">>> SMS-код: ").strip()
    except (EOFError, KeyboardInterrupt):
        return False

    if not sms_code:
        console.print("[red]Код не введён.[/red]")
        return False

    code_input.fill(sms_code)
    page.wait_for_timeout(500)

    # Нажимаем подтвердить
    _click_submit(page)
    page.wait_for_timeout(5000)

    # Проверяем ошибку
    error = _check_login_error(page)
    if error:
        console.print(f"[red]Ошибка: {error}[/red]")
        return False

    # Проверяем логин
    try:
        page.goto("https://hh.ru", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)
    except Exception:
        pass

    return check_logged_in(page)


def login_password(page: Page, console: Console) -> bool:
    """Логин по email + паролю из терминала."""
    console.print("[dim]Открываю страницу логина...[/dim]")

    if not _navigate_to_login_form(page, console):
        console.print("[red]Не удалось открыть форму логина.[/red]")
        console.print("[dim]Попробуйте 'Сам в браузере'.[/dim]")
        return False

    # Переключаемся на вкладку "По паролю" если есть
    password_tab = _find_element(page, PASSWORD_TAB_SELECTORS, timeout=3000)
    if password_tab:
        password_tab.click()
        page.wait_for_timeout(1500)

    # 1. Ввод email
    try:
        email = input("\n>>> Email: ").strip()
    except (EOFError, KeyboardInterrupt):
        return False

    if not email:
        console.print("[red]Email не введён.[/red]")
        return False

    email_input = _find_element(page, EMAIL_INPUT_SELECTORS)
    if not email_input:
        console.print("[red]Не удалось найти поле email.[/red]")
        console.print("[dim]Попробуйте 'Сам в браузере'.[/dim]")
        return False

    email_input.fill(email)
    page.wait_for_timeout(500)

    # 2. Ввод пароля
    try:
        password = getpass.getpass(">>> Пароль (не отображается): ")
    except (EOFError, KeyboardInterrupt):
        return False

    if not password:
        console.print("[red]Пароль не введён.[/red]")
        return False

    password_input = _find_element(page, PASSWORD_INPUT_SELECTORS)
    if not password_input:
        # Может поле пароля появляется после ввода email + submit
        _click_submit(page)
        page.wait_for_timeout(2000)
        password_input = _find_element(page, PASSWORD_INPUT_SELECTORS)

    if not password_input:
        console.print("[red]Не удалось найти поле пароля.[/red]")
        console.print("[dim]Возможно, для этого аккаунта доступен только вход по SMS.[/dim]")
        return False

    password_input.fill(password)
    page.wait_for_timeout(500)

    # 3. Отправляем
    _click_submit(page)
    page.wait_for_timeout(5000)

    # Проверяем ошибку
    error = _check_login_error(page)
    if error:
        console.print(f"[red]Ошибка: {error}[/red]")
        return False

    # Проверяем логин
    try:
        page.goto("https://hh.ru", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)
    except Exception:
        pass

    return check_logged_in(page)


# === Контексты ===

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
    """Создаёт persistent browser context для логина.

    Persistent context = реальный профиль браузера с сохранением на диск.
    На Windows использует системный Chrome (channel="chrome") потому что
    Patchright Chromium палится hh.ru и вызывает бесконечную загрузку.

    Браузер всегда видимый (headless=False) — hh.ru блокирует headless.

    Возвращает (browser=None, context).
    Закрывать через context.close().
    """
    import platform
    from hh_apply.config import get_data_dir

    os.environ["TZ"] = "Europe/Moscow"

    data_dir = get_data_dir(config)
    profile_dir = str(data_dir / "browser_profile")

    launch_kwargs = dict(
        user_data_dir=profile_dir,
        headless=False,
        args=["--no-first-run", "--no-default-browser-check"],
        viewport=random_viewport(),
        locale="ru-RU",
        timezone_id="Europe/Moscow",
    )

    # На Windows Patchright Chromium палится hh.ru — используем системный Chrome
    if platform.system() == "Windows":
        try:
            context = playwright.chromium.launch_persistent_context(
                channel="chrome",
                **launch_kwargs,
            )
            return None, context
        except Exception:
            pass  # Chrome не установлен — fallback на Patchright

    context = playwright.chromium.launch_persistent_context(**launch_kwargs)

    return None, context


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
