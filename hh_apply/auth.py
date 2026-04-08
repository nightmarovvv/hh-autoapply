"""Авторизация на hh.ru через нативный браузер + Patchright для откликов."""

from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path

from rich.console import Console
from patchright.sync_api import Page, Playwright

from hh_apply.stealth import apply_stealth, random_viewport, random_user_agent, get_chromium_version, human_wait

import logging

logger = logging.getLogger("hh_apply.auth")


# === Поиск браузеров на компе ===

def _find_browser() -> tuple[str, str] | None:
    """Находит любой Chromium-based браузер. Возвращает (путь, название) или None."""
    system = platform.system()

    if system == "Windows":
        browsers = [
            ("Google Chrome", [
                os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
                os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
                os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
            ]),
            ("Microsoft Edge", [
                os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
                os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
            ]),
            ("Brave", [
                os.path.expandvars(r"%ProgramFiles%\BraveSoftware\Brave-Browser\Application\brave.exe"),
                os.path.expandvars(r"%LocalAppData%\BraveSoftware\Brave-Browser\Application\brave.exe"),
            ]),
            ("Vivaldi", [
                os.path.expandvars(r"%LocalAppData%\Vivaldi\Application\vivaldi.exe"),
            ]),
            ("Yandex Browser", [
                os.path.expandvars(r"%LocalAppData%\Yandex\YandexBrowser\Application\browser.exe"),
            ]),
        ]
    elif system == "Darwin":
        browsers = [
            ("Google Chrome", ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]),
            ("Brave", ["/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"]),
            ("Microsoft Edge", ["/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"]),
            ("Vivaldi", ["/Applications/Vivaldi.app/Contents/MacOS/Vivaldi"]),
            ("Yandex Browser", ["/Applications/Yandex.app/Contents/MacOS/Yandex"]),
            ("Chromium", ["/Applications/Chromium.app/Contents/MacOS/Chromium"]),
        ]
    else:
        browsers = [
            ("Google Chrome", ["/usr/bin/google-chrome", "/usr/bin/google-chrome-stable"]),
            ("Chromium", ["/usr/bin/chromium-browser", "/usr/bin/chromium"]),
            ("Brave", ["/usr/bin/brave-browser", "/usr/bin/brave-browser-stable"]),
            ("Microsoft Edge", ["/usr/bin/microsoft-edge", "/usr/bin/microsoft-edge-stable"]),
            ("Vivaldi", ["/usr/bin/vivaldi", "/usr/bin/vivaldi-stable"]),
        ]

    for name, paths in browsers:
        for path in paths:
            if os.path.isfile(path):
                return path, name

    # Fallback: ищем через which/where
    cmd = "where" if system == "Windows" else "which"
    search_names = {
        "google-chrome": "Google Chrome",
        "chrome": "Google Chrome",
        "chromium": "Chromium",
        "brave-browser": "Brave",
        "msedge": "Microsoft Edge",
        "vivaldi": "Vivaldi",
    }
    for binary, name in search_names.items():
        try:
            result = subprocess.run([cmd, binary], capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip().split("\n")[0], name
        except Exception:
            pass

    return None


# === Логин через нативный браузер ===

def login_native_browser(config: dict, console: Console) -> bool:
    """Логин через нативный браузер БЕЗ Playwright.

    Запускает настоящий браузер как обычный процесс (subprocess),
    без CDP, без автоматизации. hh.ru не может отличить от обычного
    юзера. Пользователь логинится сам, потом мы забираем куки из профиля.
    """
    from hh_apply.config import get_data_dir, get_storage_path

    found = _find_browser()
    if not found:
        console.print("[red]Не найден ни один браузер (Chrome, Edge, Brave, Vivaldi, Yandex Browser).[/red]")
        console.print("[dim]Установите любой Chromium-браузер и попробуйте снова.[/dim]")
        return False

    browser_path, browser_name = found
    data_dir = get_data_dir(config)
    profile_dir = str(data_dir / "browser_profile")
    storage_path = get_storage_path(config)

    console.print(f"[dim]Запускаю {browser_name}...[/dim]")

    proc = subprocess.Popen([
        browser_path,
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "https://hh.ru/account/login",
    ])

    console.print()
    console.print(f"[bold]{browser_name} открыт.[/bold]\n")
    console.print("  [bold]1.[/bold] В браузере нажмите [bold]Войти[/bold]")
    console.print("  [bold]2.[/bold] Введите номер телефона и код из SMS (или email + пароль)")
    console.print("  [bold]3.[/bold] Дождитесь полной загрузки страницы профиля")
    console.print("  [bold]4.[/bold] Вернитесь сюда и нажмите Enter\n")
    console.print("[dim]  Не закрывайте браузер сами — hh-apply сделает это автоматически.[/dim]\n")

    try:
        input(">>> Нажмите Enter когда ПОЛНОСТЬЮ залогинитесь: ")
    except (EOFError, KeyboardInterrupt):
        proc.terminate()
        return False

    console.print("[dim]Закрываю браузер и сохраняю сессию...[/dim]")
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()

    # Открываем тот же профиль через Playwright headless чтобы экспортировать storage_state
    from patchright.sync_api import sync_playwright

    try:
        with sync_playwright() as pw:
            timezone = config.get("browser", {}).get("timezone", "Europe/Moscow")
            context = pw.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                headless=True,
                viewport=random_viewport(),
                locale="ru-RU",
                timezone_id=timezone,
            )
            page = context.pages[0] if context.pages else context.new_page()

            page.goto("https://hh.ru", wait_until="domcontentloaded", timeout=30000)
            human_wait(page, 2000)

            if check_logged_in(page):
                context.storage_state(path=str(storage_path))
                context.close()
                return True
            else:
                context.close()
                return False
    except Exception as e:
        logger.error("Ошибка при сохранении сессии: %s", e)
        console.print(f"[red]Ошибка при сохранении сессии: {e}[/red]")
        return False


# === Контексты для откликов (Patchright со стелсом) ===

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
    """Создаёт (browser, context) с антидетект-мерами для откликов."""
    from hh_apply.config import get_storage_path

    storage_path = get_storage_path(config)
    storage_path.parent.mkdir(parents=True, exist_ok=True)

    browser = playwright.chromium.launch(**_get_launch_kwargs(config))

    viewport = random_viewport()
    ua = random_user_agent()

    real_version = get_chromium_version(browser)
    for ver in ("136", "135", "134", "133"):
        ua = ua.replace(f"Chrome/{ver}.0.0.0", f"Chrome/{real_version}.0.0.0")

    ctx_kwargs = dict(
        viewport=viewport,
        locale="ru-RU",
        timezone_id=config.get("browser", {}).get("timezone", "Europe/Moscow"),
        user_agent=ua,
        device_scale_factor=2,
    )

    if storage_path.exists():
        ctx_kwargs["storage_state"] = str(storage_path)

    context = browser.new_context(**ctx_kwargs)
    apply_stealth(context)

    return browser, context


# === Проверка авторизации ===

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
    except Exception as e:
        logger.debug("check_logged_in exception: %s", e)
        return False


def login_if_needed(page: Page, config: dict) -> bool:
    """Проверяет авторизацию, при неудаче просит перезапустить login."""
    page.goto("https://hh.ru", wait_until="domcontentloaded", timeout=20000)
    human_wait(page, 2000)

    if check_logged_in(page):
        return True

    page.goto("https://hh.ru/applicant/resumes", wait_until="domcontentloaded", timeout=20000)
    human_wait(page, 2000)

    if "/account/login" not in page.url:
        return True

    return False
