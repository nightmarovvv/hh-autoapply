"""Логика автоотклика на вакансии hh.ru.

Ключевые отличия от наивного подхода:
- Кнопка "Откликнуться" — тег <A> с href и onclick. JS-клик работает.
- После клика проверяем: снэкбар, модалка с письмом, редирект, капча.
- Вместо индекса карточки — ищем по vacancy_id (устойчиво к DOM-мутациям).
- Верифицируем отправку перед записью в трекер.
"""

from __future__ import annotations

import random
import time
import math

from playwright.sync_api import Page

from src.search import Vacancy


STATUS_SENT = "sent"
STATUS_COVER_LETTER = "cover_letter_sent"
STATUS_TEST_REQUIRED = "test_required"
STATUS_EXTRA_STEPS = "extra_steps"
STATUS_ALREADY_APPLIED = "already_applied"
STATUS_NO_BUTTON = "no_button"
STATUS_CAPTCHA = "captcha"
STATUS_ERROR = "error"


def apply_to_vacancy(page: Page, vacancy: Vacancy,
                     cover_letter: str, use_cover_letter: bool) -> str:
    """Откликается на вакансию по vacancy_id (не по индексу!).

    Находит карточку по vacancy_id в DOM, кликает кнопку отклика.
    """
    try:
        original_url = page.url

        # Ищем кнопку отклика по vacancy_id
        btn_info = page.evaluate(f"""
            () => {{
                const cards = document.querySelectorAll('[data-qa="vacancy-serp__vacancy"]');
                for (const card of cards) {{
                    const link = card.querySelector('[data-qa="serp-item__title"]');
                    if (!link || !link.href.includes('/vacancy/{vacancy.vacancy_id}')) continue;

                    const btn = card.querySelector('[data-qa="vacancy-serp__vacancy_response"]');
                    if (!btn) return {{status: 'no_button'}};

                    const text = btn.textContent.trim().toLowerCase();
                    if (text.includes('отправлен')) return {{status: 'already_applied'}};

                    return {{status: 'ready', text: btn.textContent.trim()}};
                }}
                return {{status: 'not_found'}};
            }}
        """)

        status = btn_info.get("status", "error")

        if status == "no_button":
            print(f"  [apply] {vacancy.title} — нет кнопки отклика")
            return STATUS_NO_BUTTON

        if status == "already_applied":
            print(f"  [apply] {vacancy.title} — уже откликались")
            return STATUS_ALREADY_APPLIED

        if status == "not_found":
            print(f"  [apply] {vacancy.title} — карточка не найдена на странице")
            return STATUS_ERROR

        # Скроллим к карточке и кликаем через mouse (isTrusted: true)
        box = page.evaluate(f"""
            () => {{
                const cards = document.querySelectorAll('[data-qa="vacancy-serp__vacancy"]');
                for (const card of cards) {{
                    const link = card.querySelector('[data-qa="serp-item__title"]');
                    if (!link || !link.href.includes('/vacancy/{vacancy.vacancy_id}')) continue;
                    const btn = card.querySelector('[data-qa="vacancy-serp__vacancy_response"]');
                    if (!btn) return null;
                    card.scrollIntoView({{block: 'center', behavior: 'smooth'}});
                    return null; // Вернём координаты после скролла
                }}
                return null;
            }}
        """)
        page.wait_for_timeout(600)

        # Получаем координаты после скролла
        box = page.evaluate(f"""
            () => {{
                const cards = document.querySelectorAll('[data-qa="vacancy-serp__vacancy"]');
                for (const card of cards) {{
                    const link = card.querySelector('[data-qa="serp-item__title"]');
                    if (!link || !link.href.includes('/vacancy/{vacancy.vacancy_id}')) continue;
                    const btn = card.querySelector('[data-qa="vacancy-serp__vacancy_response"]');
                    if (!btn) return null;
                    const rect = btn.getBoundingClientRect();
                    return {{x: rect.x, y: rect.y, w: rect.width, h: rect.height}};
                }}
                return null;
            }}
        """)

        if box and box.get("w", 0) > 0:
            # Mouse click — isTrusted: true!
            import random as _rnd
            cx = box["x"] + box["w"] / 2 + _rnd.uniform(-10, 10)
            cy = box["y"] + box["h"] / 2 + _rnd.uniform(-3, 3)
            page.mouse.move(cx, cy, steps=_rnd.randint(5, 12))
            page.wait_for_timeout(_rnd.randint(80, 250))
            page.mouse.click(cx, cy)
            print(f"  [apply] {vacancy.title} — кликнул (mouse, isTrusted)")
        else:
            # Fallback — JS click
            page.evaluate(f"""
                () => {{
                    const cards = document.querySelectorAll('[data-qa="vacancy-serp__vacancy"]');
                    for (const card of cards) {{
                        const link = card.querySelector('[data-qa="serp-item__title"]');
                        if (!link || !link.href.includes('/vacancy/{vacancy.vacancy_id}')) continue;
                        const btn = card.querySelector('[data-qa="vacancy-serp__vacancy_response"]');
                        if (btn) btn.click();
                        return;
                    }}
                }}
            """)
            print(f"  [apply] {vacancy.title} — кликнул (JS fallback)")

        page.wait_for_timeout(3000)

        # Проверяем редирект (тестовое задание, страница отклика)
        if page.url != original_url:
            return _handle_redirect(page, vacancy, original_url)

        # Проверяем капчу
        if _check_captcha(page):
            return _handle_captcha(page)

        # Проверяем снэкбар
        if _check_sent(page):
            print(f"  [apply] {vacancy.title} — ОТКЛИК ОТПРАВЛЕН")
            return STATUS_SENT

        # Проверяем модалку с сопроводительным
        letter_input = page.locator('[data-qa="vacancy-response-popup-form-letter-input"]')
        if letter_input.count() > 0:
            if use_cover_letter and cover_letter:
                return _fill_and_submit(page, vacancy, cover_letter, letter_input)
            else:
                return _submit_modal(page, vacancy)

        # Foreign warning — модалка "Вы откликаетесь на вакансию в другой стране"
        # Кнопка: "Все равно откликнуться" (без ё!) и "Отменить"
        has_foreign = page.evaluate("""
            () => document.body.innerText.includes('другой стране') ||
                  document.body.innerText.includes('другую страну')
        """)
        if has_foreign:
            print(f"  [apply] {vacancy.title} — другая страна, подтверждаю...")
            # Кликаем "Все равно откликнуться" (mouse click для isTrusted)
            confirm_box = page.evaluate("""
                () => {
                    const btns = document.querySelectorAll('button');
                    for (const b of btns) {
                        const t = b.textContent.trim().toLowerCase();
                        if (t.includes('все равно') || t.includes('всё равно')) {
                            const rect = b.getBoundingClientRect();
                            return {x: rect.x + rect.width/2, y: rect.y + rect.height/2};
                        }
                    }
                    return null;
                }
            """)
            if confirm_box:
                import random as _rnd2
                page.mouse.click(
                    confirm_box["x"] + _rnd2.uniform(-5, 5),
                    confirm_box["y"] + _rnd2.uniform(-2, 2),
                )
                page.wait_for_timeout(3000)

                if _check_sent(page):
                    print(f"  [apply] {vacancy.title} — ОТКЛИК ОТПРАВЛЕН (другая страна)")
                    return STATUS_SENT

                # Может появиться модалка с письмом после подтверждения
                letter_input2 = page.locator('[data-qa="vacancy-response-popup-form-letter-input"]')
                if letter_input2.count() > 0:
                    if use_cover_letter and cover_letter:
                        return _fill_and_submit(page, vacancy, cover_letter, letter_input2)
                    else:
                        return _submit_modal(page, vacancy)

                # Проверяем кнопку — изменилась ли
                btn_after = page.evaluate(f"""
                    () => {{
                        const cards = document.querySelectorAll('[data-qa="vacancy-serp__vacancy"]');
                        for (const card of cards) {{
                            const link = card.querySelector('[data-qa="serp-item__title"]');
                            if (link && link.href.includes('/vacancy/{vacancy.vacancy_id}')) {{
                                const btn = card.querySelector('[data-qa="vacancy-serp__vacancy_response"]');
                                return btn ? btn.textContent.trim() : 'gone';
                            }}
                        }}
                        return 'not_found';
                    }}
                """)
                if "отправлен" in btn_after.lower() or btn_after == "gone":
                    print(f"  [apply] {vacancy.title} — ОТКЛИК ОТПРАВЛЕН (кнопка после foreign)")
                    return STATUS_SENT

        # Проверяем доп. вопросы
        if page.locator('[data-qa="form-helper-description"]').count() > 0:
            print(f"  [apply] {vacancy.title} — доп.вопросы, пропускаю")
            _close_modal(page)
            return STATUS_EXTRA_STEPS

        # Финальная проверка
        page.wait_for_timeout(2000)
        if _check_sent(page):
            print(f"  [apply] {vacancy.title} — ОТКЛИК ОТПРАВЛЕН (задержка)")
            return STATUS_SENT

        # Проверяем изменилась ли кнопка
        new_text = page.evaluate(f"""
            () => {{
                const cards = document.querySelectorAll('[data-qa="vacancy-serp__vacancy"]');
                for (const card of cards) {{
                    const link = card.querySelector('[data-qa="serp-item__title"]');
                    if (!link || !link.href.includes('/vacancy/{vacancy.vacancy_id}')) continue;
                    const btn = card.querySelector('[data-qa="vacancy-serp__vacancy_response"]');
                    return btn ? btn.textContent.trim() : 'gone';
                }}
                return 'not_found';
            }}
        """)

        if "отправлен" in str(new_text).lower() or new_text == "gone":
            print(f"  [apply] {vacancy.title} — ОТКЛИК ОТПРАВЛЕН (кнопка изменилась)")
            return STATUS_SENT

        print(f"  [apply] {vacancy.title} — статус неясен")
        return STATUS_ERROR

    except Exception as e:
        print(f"  [apply] {vacancy.title} — ОШИБКА: {e}")
        return STATUS_ERROR


def _handle_redirect(page: Page, vacancy: Vacancy, original_url: str) -> str:
    """Обрабатывает навигацию после клика."""
    current = page.url
    test_words = ["test", "question", "quiz", "assessment"]

    if any(w in current.lower() for w in test_words):
        print(f"  [apply] {vacancy.title} — тестовое задание, пропускаю")
        page.goto(original_url, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(2000)
        return STATUS_TEST_REQUIRED

    # Страница отклика — проверяем отправку
    if "vacancy_response" in current:
        if _check_sent(page):
            page.goto(original_url, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(2000)
            print(f"  [apply] {vacancy.title} — ОТКЛИК ОТПРАВЛЕН (со страницы отклика)")
            return STATUS_SENT

    print(f"  [apply] {vacancy.title} — неизвестный редирект: {current}")
    page.goto(original_url, wait_until="domcontentloaded", timeout=20000)
    page.wait_for_timeout(2000)
    return STATUS_EXTRA_STEPS


def _check_sent(page: Page) -> bool:
    """Проверяет снэкбар подтверждения отклика."""
    return page.evaluate("""
        () => {
            // Ищем в конкретных контейнерах, не по всему body
            const snackbars = document.querySelectorAll(
                '[class*="snackbar"], [class*="notification"], [class*="toast"], [role="alert"]'
            );
            for (const el of snackbars) {
                if (el.textContent.includes('Отклик отправлен')) return true;
            }
            // Fallback — по всей странице, но только видимый текст
            return document.body.innerText.includes('Отклик отправлен');
        }
    """)


def _fill_and_submit(page: Page, vacancy: Vacancy, cover_letter: str, letter_input) -> str:
    """Заполняет сопроводительное и отправляет. Верифицирует результат."""
    print(f"  [apply] {vacancy.title} — вставляю сопроводительное...")
    letter_input.fill(cover_letter)
    page.wait_for_timeout(500)

    # Кнопка отправки
    submitted = _click_submit(page)
    if not submitted:
        print(f"  [apply] {vacancy.title} — не нашёл кнопку отправки в модалке")
        _close_modal(page)
        return STATUS_ERROR

    page.wait_for_timeout(3000)

    # Верифицируем
    if _check_sent(page):
        print(f"  [apply] {vacancy.title} — ОТКЛИК С ПИСЬМОМ ОТПРАВЛЕН")
        return STATUS_COVER_LETTER

    print(f"  [apply] {vacancy.title} — отправил письмо, но подтверждение не найдено")
    return STATUS_COVER_LETTER  # Оптимистично, но с логом


def _submit_modal(page: Page, vacancy: Vacancy) -> str:
    """Отправляет модалку без письма."""
    print(f"  [apply] {vacancy.title} — отправляю без письма")
    submitted = _click_submit(page)
    if not submitted:
        _close_modal(page)
        return STATUS_ERROR

    page.wait_for_timeout(3000)

    if _check_sent(page):
        print(f"  [apply] {vacancy.title} — ОТКЛИК ОТПРАВЛЕН")
        return STATUS_SENT

    return STATUS_SENT


def _click_submit(page: Page) -> bool:
    """Кликает кнопку отправки в модалке."""
    btn = page.locator('[data-qa="vacancy-response-submit-popup"]')
    if btn.count() > 0:
        btn.first.click()
        return True

    alt = page.locator('button:has-text("Откликнуться")')
    if alt.count() > 0:
        alt.first.click()
        return True

    return False


def _check_captcha(page: Page) -> bool:
    return page.evaluate("""
        () => {
            const sel = ['iframe[src*="captcha"]', '[class*="captcha"]',
                         'img[src*="captcha"]', '[data-qa="captcha"]'];
            for (const s of sel) { if (document.querySelector(s)) return true; }
            return document.body.innerText.includes('Подтвердите, что вы не робот');
        }
    """)


def _handle_captcha(page: Page) -> str:
    """Ждёт решения капчи (поллит каждые 2 сек, макс 2 мин)."""
    print("\n" + "!" * 60)
    print("КАПЧА! Реши капчу в браузере.")
    print("!" * 60 + "\n")

    for _ in range(60):  # 2 минуты
        page.wait_for_timeout(2000)
        if not _check_captcha(page):
            print("[captcha] Капча решена!")
            return STATUS_CAPTCHA  # Пометить что была капча, ретрай вакансии
    print("[captcha] Таймаут — капча не решена за 2 мин")
    return STATUS_CAPTCHA


def _close_modal(page: Page) -> None:
    page.evaluate("""
        () => {
            const btn = document.querySelector('[data-qa="bloko-modal-close"]');
            if (btn) btn.click();
        }
    """)
    page.wait_for_timeout(500)


def human_delay(delay_min: int, delay_max: int) -> None:
    """Пауза с нормальным распределением (имитация человека)."""
    mean = (delay_min + delay_max) / 2
    std = (delay_max - delay_min) / 4
    delay = random.gauss(mean, std)
    delay = max(delay_min, min(delay_max * 1.5, delay))

    # Раз в ~10 откликов — длинная пауза
    if random.random() < 0.08:
        delay += random.uniform(15, 30)
        print(f"  [delay] Длинная пауза {delay:.1f} сек (имитация)")
    else:
        print(f"  [delay] Пауза {delay:.1f} сек")

    time.sleep(delay)
