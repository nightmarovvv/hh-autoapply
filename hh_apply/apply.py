"""Логика автоотклика на вакансии hh.ru.

Кнопка "Откликнуться" — тег <A> с href и onclick.
После клика: снэкбар, модалка с письмом, редирект, капча.
Поиск по vacancy_id (устойчиво к DOM-мутациям).
"""

from __future__ import annotations

import random
import time

from patchright.sync_api import Page

from hh_apply.search import Vacancy
from hh_apply.captcha import solve_captcha_interactive, _check_captcha_present
from hh_apply.stealth import human_mouse_move

STATUS_SENT = "sent"
STATUS_COVER_LETTER = "cover_letter_sent"
STATUS_TEST_REQUIRED = "test_required"
STATUS_EXTRA_STEPS = "extra_steps"
STATUS_ALREADY_APPLIED = "already_applied"
STATUS_NO_BUTTON = "no_button"
STATUS_CAPTCHA = "captcha"
STATUS_ERROR = "error"
STATUS_FILTERED = "filtered"


def apply_to_vacancy(page: Page, vacancy: Vacancy,
                     cover_letter: str, use_cover_letter: bool,
                     skip_foreign: bool = False) -> str:
    """Откликается на вакансию по vacancy_id."""
    try:
        original_url = page.url

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
            return STATUS_NO_BUTTON
        if status == "already_applied":
            return STATUS_ALREADY_APPLIED
        if status == "not_found":
            return STATUS_ERROR

        # Скроллим к карточке
        page.evaluate(f"""
            () => {{
                const cards = document.querySelectorAll('[data-qa="vacancy-serp__vacancy"]');
                for (const card of cards) {{
                    const link = card.querySelector('[data-qa="serp-item__title"]');
                    if (!link || !link.href.includes('/vacancy/{vacancy.vacancy_id}')) continue;
                    card.scrollIntoView({{block: 'center', behavior: 'smooth'}});
                    return;
                }}
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
            cx = box["x"] + box["w"] / 2 + random.uniform(-10, 10)
            cy = box["y"] + box["h"] / 2 + random.uniform(-3, 3)
            human_mouse_move(page, cx, cy)
            page.mouse.click(cx, cy)
        else:
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

        page.wait_for_timeout(3000)

        # Закрываем рекламные вкладки
        if len(page.context.pages) > 1:
            for p in page.context.pages:
                if p != page:
                    p.close()

        # Проверяем редирект
        if page.url != original_url:
            return _handle_redirect(page, vacancy, original_url)

        # Капча
        if _check_captcha(page):
            return _handle_captcha(page)

        # Снэкбар
        if _check_sent(page):
            return STATUS_SENT

        # Модалка с сопроводительным
        letter_input = page.locator('[data-qa="vacancy-response-popup-form-letter-input"]')
        if letter_input.count() > 0:
            if use_cover_letter and cover_letter:
                return _fill_and_submit(page, vacancy, cover_letter, letter_input)
            else:
                return _submit_modal(page, vacancy)

        # Foreign warning
        has_foreign = page.evaluate("""
            () => document.body.innerText.includes('другой стране') ||
                  document.body.innerText.includes('другую страну')
        """)
        if has_foreign and skip_foreign:
            _close_modal(page)
            return STATUS_FILTERED
        if has_foreign:
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
                page.mouse.click(
                    confirm_box["x"] + random.uniform(-5, 5),
                    confirm_box["y"] + random.uniform(-2, 2),
                )
                page.wait_for_timeout(3000)

                if _check_sent(page):
                    return STATUS_SENT

                letter_input2 = page.locator('[data-qa="vacancy-response-popup-form-letter-input"]')
                if letter_input2.count() > 0:
                    if use_cover_letter and cover_letter:
                        return _fill_and_submit(page, vacancy, cover_letter, letter_input2)
                    else:
                        return _submit_modal(page, vacancy)

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
                    return STATUS_SENT

        # Доп. вопросы
        if page.locator('[data-qa="form-helper-description"]').count() > 0:
            _close_modal(page)
            return STATUS_EXTRA_STEPS

        # Финальная проверка
        page.wait_for_timeout(2000)
        if _check_sent(page):
            return STATUS_SENT

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
            return STATUS_SENT

        return STATUS_ERROR

    except Exception as e:
        return STATUS_ERROR


def _handle_redirect(page: Page, vacancy: Vacancy, original_url: str) -> str:
    current = page.url
    test_words = ["test", "question", "quiz", "assessment"]

    if any(w in current.lower() for w in test_words):
        page.goto(original_url, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(2000)
        return STATUS_TEST_REQUIRED

    if "vacancy_response" in current:
        if _check_sent(page):
            page.goto(original_url, wait_until="domcontentloaded", timeout=20000)
            page.wait_for_timeout(2000)
            return STATUS_SENT

    page.goto(original_url, wait_until="domcontentloaded", timeout=20000)
    page.wait_for_timeout(2000)
    return STATUS_EXTRA_STEPS


def _check_sent(page: Page) -> bool:
    return page.evaluate("""
        () => {
            const snackbars = document.querySelectorAll(
                '[class*="snackbar"], [class*="notification"], [class*="toast"], [role="alert"]'
            );
            for (const el of snackbars) {
                if (el.textContent.includes('Отклик отправлен')) return true;
            }
            return document.body.innerText.includes('Отклик отправлен');
        }
    """)


def _fill_and_submit(page: Page, vacancy: Vacancy, cover_letter: str, letter_input) -> str:
    letter_input.click()
    page.wait_for_timeout(200)
    letter_input.fill(cover_letter)
    page.wait_for_timeout(500)

    submitted = _click_submit(page)
    if not submitted:
        _close_modal(page)
        return STATUS_ERROR

    page.wait_for_timeout(3000)

    if _check_sent(page):
        return STATUS_COVER_LETTER

    return STATUS_COVER_LETTER


def _submit_modal(page: Page, vacancy: Vacancy) -> str:
    submitted = _click_submit(page)
    if not submitted:
        _close_modal(page)
        return STATUS_ERROR

    page.wait_for_timeout(3000)

    if _check_sent(page):
        return STATUS_SENT

    return STATUS_SENT


def _click_submit(page: Page) -> bool:
    btn = page.locator('[data-qa="vacancy-response-submit-popup"]')
    if btn.count() > 0:
        box = btn.first.bounding_box()
        if box:
            page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        else:
            btn.first.click()
        return True

    alt = page.locator('button:has-text("Откликнуться")')
    if alt.count() > 0:
        alt.first.click()
        return True

    return False


def _check_captcha(page: Page) -> bool:
    return _check_captcha_present(page)


def _handle_captcha(page: Page) -> str:
    """Интерактивное решение капчи: картинка в терминале + ввод."""
    solved = solve_captcha_interactive(page)
    return STATUS_CAPTCHA


def _close_modal(page: Page) -> None:
    page.evaluate("""
        () => {
            const btn = document.querySelector('[data-qa="bloko-modal-close"]');
            if (btn) btn.click();
        }
    """)
    page.wait_for_timeout(500)


def human_delay(delay_min: float, delay_max: float) -> None:
    """Пауза между откликами с иногда длинными перерывами."""
    delay = random.uniform(delay_min, delay_max)
    if random.random() < 0.10:
        delay += random.uniform(3, 8)
    time.sleep(delay)
