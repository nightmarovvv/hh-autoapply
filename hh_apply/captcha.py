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
import webbrowser
from pathlib import Path

from patchright.sync_api import Page

from hh_apply.notifications import alert_captcha
from hh_apply.stealth import human_wait


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


def _render_sixel(image_bytes: bytes) -> bool:
    """Рендерит через Sixel. Возвращает True если удалось."""
    try:
        from PIL import Image
        import io

        img = Image.open(io.BytesIO(image_bytes))
        # Resize для терминала (макс 400px ширина)
        if img.width > 400:
            ratio = 400 / img.width
            img = img.resize((400, int(img.height * ratio)))

        # Sixel через PIL — конвертируем в палитру
        img = img.convert("P", palette=Image.ADAPTIVE, colors=256)

        # Генерируем Sixel escape sequence
        width, height = img.size
        pixels = list(img.getdata())
        palette = img.getpalette()

        # Sixel header
        output = "\033Pq"
        # Color registers
        for i in range(min(256, max(pixels) + 1)):
            r = palette[i * 3] * 100 // 255
            g = palette[i * 3 + 1] * 100 // 255
            b = palette[i * 3 + 2] * 100 // 255
            output += f"#{i};2;{r};{g};{b}"

        # Pixel data (6 rows at a time)
        for y_base in range(0, height, 6):
            for color in range(max(pixels) + 1):
                line = f"#{color}"
                has_data = False
                for x in range(width):
                    sixel = 0
                    for dy in range(6):
                        y = y_base + dy
                        if y < height and pixels[y * width + x] == color:
                            sixel |= 1 << dy
                    if sixel > 0:
                        has_data = True
                    line += chr(63 + sixel)
                if has_data:
                    output += line + "$"
            output += "-"

        output += "\033\\"
        sys.stdout.write(output)
        sys.stdout.write("\n")
        sys.stdout.flush()
        return True
    except ImportError:
        return False
    except Exception:
        return False


def render_captcha_in_terminal(image_bytes: bytes) -> None:
    """Показывает капчу: Kitty → Sixel → файл + браузер."""
    if _supports_kitty():
        print("\n[Капча — Kitty Graphics]")
        render_image_kitty(image_bytes)
    elif _supports_sixel():
        print("\n[Капча — Sixel]")
        if not _render_sixel(image_bytes):
            _fallback_file(image_bytes)
    else:
        _fallback_file(image_bytes)


def _fallback_file(image_bytes: bytes) -> None:
    """Fallback: сохранить в файл и открыть."""
    path = render_image_file(image_bytes)
    print(f"\n[Капча сохранена: {path}]")
    try:
        webbrowser.open(f"file://{path}")
    except Exception:
        pass
    print(f"Откройте файл для просмотра: {path}")


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
            human_wait(page, 2000)
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
            human_wait(page, 3000)
            if not _check_captcha_present(page):
                print("Капча решена!")
                return True
            else:
                print("[!] Неправильный текст, попробуйте ещё раз")
                return False

    # Если не нашли поле — может, это iframe-капча
    print("[!] Поле ввода капчи не найдено. Решите в браузере.")
    for _ in range(60):
        human_wait(page, 2000)
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
