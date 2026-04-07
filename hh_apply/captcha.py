"""Капча: скриншот в терминале + интерактивный ввод.

Поддержка:
- Kitty Graphics Protocol (Kitty, Konsole, Ghostty)
- Sixel (Windows Terminal 1.22+, многие Linux-терминалы)
- Fallback: сохранение в файл
"""

from __future__ import annotations

import base64
import os
import sys
import tempfile
from pathlib import Path

from patchright.sync_api import Page

from hh_apply.notifications import alert_captcha


def _supports_kitty() -> bool:
    """Проверяет поддержку Kitty Graphics Protocol."""
    term = os.environ.get("TERM", "")
    term_program = os.environ.get("TERM_PROGRAM", "")
    return "kitty" in term.lower() or "kitty" in term_program.lower() or "ghostty" in term_program.lower()


def _supports_sixel() -> bool:
    """Проверяет поддержку Sixel."""
    term = os.environ.get("TERM", "")
    term_program = os.environ.get("TERM_PROGRAM", "")
    # Sixel поддерживают: xterm, mlterm, foot, Windows Terminal 1.22+
    sixel_terms = ("xterm", "mlterm", "foot", "contour", "wezterm", "konsole")
    return any(t in term.lower() or t in term_program.lower() for t in sixel_terms)


def render_image_kitty(image_bytes: bytes) -> None:
    """Отрисовка через Kitty Graphics Protocol."""
    b64 = base64.b64encode(image_bytes).decode("ascii")
    # Kitty protocol: APC G ... ST
    chunk_size = 4096
    chunks = [b64[i:i + chunk_size] for i in range(0, len(b64), chunk_size)]
    for i, chunk in enumerate(chunks):
        is_last = i == len(chunks) - 1
        m = 0 if is_last else 1
        if i == 0:
            sys.stdout.write(f"\033_Ga=T,f=100,m={m};{chunk}\033\\")
        else:
            sys.stdout.write(f"\033_Gm={m};{chunk}\033\\")
    sys.stdout.write("\n")
    sys.stdout.flush()


def render_image_file(image_bytes: bytes) -> str:
    """Сохраняет в файл, возвращает путь."""
    path = Path(tempfile.gettempdir()) / "hh_apply_captcha.png"
    path.write_bytes(image_bytes)
    return str(path)


def render_captcha_in_terminal(image_bytes: bytes) -> None:
    """Показывает капчу: Kitty → Sixel → файл."""
    if _supports_kitty():
        print("\n[Капча — Kitty Graphics]")
        render_image_kitty(image_bytes)
    else:
        # Fallback: сохраняем в файл
        path = render_image_file(image_bytes)
        print(f"\n[Капча сохранена: {path}]")
        print(f"Откройте файл для просмотра: open {path}")


def solve_captcha_interactive(page: Page) -> bool:
    """Полный цикл: скриншот → терминал → ввод → браузер.

    Возвращает True если капча решена.
    """
    alert_captcha()

    print("\n" + "!" * 50)
    print("  КАПЧА! Решите капчу.")
    print("!" * 50)

    # Ищем элемент капчи
    captcha_selectors = [
        'img[data-qa="account-captcha-picture"]',
        'img[src*="captcha"]',
        '[data-qa="captcha"] img',
        'iframe[src*="captcha"]',
    ]

    screenshot_bytes = None
    for sel in captcha_selectors:
        el = page.locator(sel)
        if el.count() > 0:
            try:
                screenshot_bytes = el.first.screenshot()
                break
            except Exception:
                continue

    if screenshot_bytes:
        render_captcha_in_terminal(screenshot_bytes)
    else:
        print("[!] Не удалось сделать скриншот капчи.")
        print("[!] Решите капчу в окне браузера.")

    # Ввод текста
    captcha_input_selectors = [
        'input[data-qa="account-captcha-input"]',
        'input[data-qa="captcha"]',
        'input[name*="captcha"]',
    ]

    try:
        text = input("\n>>> Введите текст с картинки (или Enter для пропуска): ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nПропущено")
        return False

    if not text:
        # Ждём ручного решения в браузере
        print("Ожидаю решения в браузере...")
        for _ in range(60):
            page.wait_for_timeout(2000)
            if not _check_captcha_present(page):
                print("Капча решена!")
                return True
        return False

    # Вводим текст в поле капчи
    for sel in captcha_input_selectors:
        el = page.locator(sel)
        if el.count() > 0:
            el.first.fill(text)
            el.first.press("Enter")
            page.wait_for_timeout(3000)
            if not _check_captcha_present(page):
                print("Капча решена!")
                return True
            else:
                print("[!] Неправильный текст, попробуйте ещё раз")
                return False

    # Если не нашли поле — может, это iframe-капча
    print("[!] Поле ввода капчи не найдено. Решите в браузере.")
    for _ in range(60):
        page.wait_for_timeout(2000)
        if not _check_captcha_present(page):
            return True
    return False


def _check_captcha_present(page: Page) -> bool:
    """Проверяет наличие капчи на странице."""
    return page.evaluate("""
        () => {
            const sel = ['iframe[src*="captcha"]', '[class*="captcha"]',
                         'img[src*="captcha"]', '[data-qa="captcha"]'];
            for (const s of sel) { if (document.querySelector(s)) return true; }
            return document.body.innerText.includes('Подтвердите, что вы не робот');
        }
    """)
