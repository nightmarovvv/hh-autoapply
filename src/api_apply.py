"""Гибридные отклики: API-проверка типа + человеческий клик.

GET-проверка типа через fetch (работает) → знаем заранее: quickResponse, modal, test
Клик через page.mouse (isTrusted: true) → настоящий человеческий клик, GIB не блокирует

Типы вакансий:
- quickResponse (74%) — мгновенный отклик одним кликом
- modal (10%) — модалка с письмом
- test-required (16%) — тестовое, пропускаем
"""

from __future__ import annotations

import json
import random
import time

from playwright.sync_api import Page

from src.search import Vacancy


STATUS_SENT = "sent"
STATUS_LETTER_SENT = "letter_sent"
STATUS_TEST = "test_required"
STATUS_ALREADY = "already_applied"
STATUS_ERROR = "error"
STATUS_SKIPPED = "skipped"

_resume_hash_cache = None


def check_vacancy_type(page: Page, vacancy_id: str) -> dict:
    """Проверяет тип через fetch (GET — работает без GIB-блокировки)."""
    result = page.evaluate(f"""
        async () => {{
            try {{
                const resp = await fetch(
                    '/applicant/vacancy_response/popup?vacancyId={vacancy_id}&isTest=no&withoutTest=no&lux=true&alreadyApplied=false',
                    {{headers: {{'x-requested-with': 'XMLHttpRequest', 'accept': 'application/json'}}, credentials: 'include'}}
                );
                if (!resp.ok) return {{type: 'error', status: resp.status}};
                const data = await resp.json();
                const body = data.body || {{}};
                const short = (body.responseStatus || {{}}).shortVacancy || {{}};
                return {{
                    type: data.type || 'unknown',
                    resume_hash: body.resume_hash || '',
                    letter_required: body.letterRequired || short['@responseLetterRequired'] || false,
                    area: (short.area || {{}}).name || '',
                    country_id: ((short.company || {{}})['@countryId']) || 0,
                }};
            }} catch (e) {{
                return {{type: 'error', error: e.message}};
            }}
        }}
    """)
    return result


def smart_apply(page: Page, vacancy: Vacancy,
                cover_letter: str, use_cover_letter: bool) -> str:
    """Проверяет тип через API, кликает через page.mouse."""
    global _resume_hash_cache

    # 1. Проверяем тип
    info = check_vacancy_type(page, vacancy.vacancy_id)
    vtype = info.get("type", "error")

    if info.get("resume_hash"):
        _resume_hash_cache = info["resume_hash"]

    if vtype == "already-applied":
        print(f"  [apply] {vacancy.title} — уже откликались")
        return STATUS_ALREADY

    if vtype == "test-required":
        print(f"  [apply] {vacancy.title} — тестовое, пропускаю")
        return STATUS_TEST

    if vtype == "error":
        print(f"  [apply] {vacancy.title} — ошибка API: {info}")
        return STATUS_ERROR

    if vtype not in ("quickResponse", "modal"):
        print(f"  [apply] {vacancy.title} — неизвестный тип: {vtype}")
        return STATUS_SKIPPED

    # 2. Находим кнопку и кликаем по-человечески
    return _human_click_apply(page, vacancy, cover_letter, use_cover_letter, vtype, info)


def _human_click_apply(page: Page, vacancy: Vacancy,
                       cover_letter: str, use_cover_letter: bool,
                       vtype: str, info: dict) -> str:
    """Кликает на кнопку отклика через page.mouse (isTrusted: true)."""
    vid = vacancy.vacancy_id
    original_url = page.url

    # Находим bounding box кнопки
    box = page.evaluate(f"""
        () => {{
            const cards = document.querySelectorAll('[data-qa="vacancy-serp__vacancy"]');
            for (const card of cards) {{
                const link = card.querySelector('[data-qa="serp-item__title"]');
                if (!link || !link.href.includes('/vacancy/{vid}')) continue;
                const btn = card.querySelector('[data-qa="vacancy-serp__vacancy_response"]');
                if (!btn) return null;
                const text = btn.textContent.trim().toLowerCase();
                if (text.includes('отправлен')) return {{already: true}};
                const rect = btn.getBoundingClientRect();
                return {{x: rect.x, y: rect.y, w: rect.width, h: rect.height}};
            }}
            return null;
        }}
    """)

    if not box:
        print(f"  [apply] {vacancy.title} — кнопка не найдена")
        return STATUS_ERROR

    if box.get("already"):
        print(f"  [apply] {vacancy.title} — уже откликались (кнопка)")
        return STATUS_ALREADY

    # Скроллим к кнопке если нужно
    page.evaluate(f"""
        () => {{
            const cards = document.querySelectorAll('[data-qa="vacancy-serp__vacancy"]');
            for (const card of cards) {{
                const link = card.querySelector('[data-qa="serp-item__title"]');
                if (link && link.href.includes('/vacancy/{vid}')) {{
                    card.scrollIntoView({{block: 'center', behavior: 'smooth'}});
                    return;
                }}
            }}
        }}
    """)
    page.wait_for_timeout(500)

    # Перечитываем координаты после скролла
    box = page.evaluate(f"""
        () => {{
            const cards = document.querySelectorAll('[data-qa="vacancy-serp__vacancy"]');
            for (const card of cards) {{
                const link = card.querySelector('[data-qa="serp-item__title"]');
                if (!link || !link.href.includes('/vacancy/{vid}')) continue;
                const btn = card.querySelector('[data-qa="vacancy-serp__vacancy_response"]');
                if (!btn) return null;
                const rect = btn.getBoundingClientRect();
                return {{x: rect.x, y: rect.y, w: rect.width, h: rect.height}};
            }}
            return null;
        }}
    """)

    if not box:
        return STATUS_ERROR

    # Кликаем через page.mouse — isTrusted: true!
    cx = box["x"] + box["w"] / 2 + random.uniform(-10, 10)
    cy = box["y"] + box["h"] / 2 + random.uniform(-5, 5)

    page.mouse.move(cx, cy, steps=random.randint(5, 15))
    page.wait_for_timeout(random.randint(100, 300))
    page.mouse.click(cx, cy)

    print(f"  [apply] {vacancy.title} — кликнул (mouse, isTrusted)")
    page.wait_for_timeout(3000)

    # Проверяем навигацию
    if page.url != original_url:
        return _handle_redirect(page, vacancy, original_url)

    # Проверяем снэкбар
    if _check_sent(page):
        print(f"  [apply] {vacancy.title} — ОТКЛИК ОТПРАВЛЕН")
        return STATUS_SENT

    # Проверяем модалку
    has_letter = page.locator('[data-qa="vacancy-response-popup-form-letter-input"]').count() > 0
    has_submit = page.locator('[data-qa="vacancy-response-submit-popup"]').count() > 0

    if has_letter or has_submit:
        return _handle_modal(page, vacancy, cover_letter, use_cover_letter, has_letter)

    # Проверяем foreign warning
    has_foreign = page.evaluate("() => document.body.innerText.includes('другой стране') || document.body.innerText.includes('другую страну')")
    if has_foreign:
        return _handle_foreign(page, vacancy, cover_letter, use_cover_letter)

    # Финальная проверка
    page.wait_for_timeout(2000)
    if _check_sent(page):
        print(f"  [apply] {vacancy.title} — ОТКЛИК ОТПРАВЛЕН (задержка)")
        return STATUS_SENT

    # Кнопка изменилась?
    btn_text = page.evaluate(f"""
        () => {{
            const cards = document.querySelectorAll('[data-qa="vacancy-serp__vacancy"]');
            for (const card of cards) {{
                const link = card.querySelector('[data-qa="serp-item__title"]');
                if (link && link.href.includes('/vacancy/{vid}')) {{
                    const btn = card.querySelector('[data-qa="vacancy-serp__vacancy_response"]');
                    return btn ? btn.textContent.trim() : 'gone';
                }}
            }}
            return 'not found';
        }}
    """)
    if "отправлен" in btn_text.lower() or btn_text == "gone":
        print(f"  [apply] {vacancy.title} — ОТКЛИК ОТПРАВЛЕН (кнопка)")
        return STATUS_SENT

    print(f"  [apply] {vacancy.title} — статус неясен")
    return STATUS_ERROR


def _handle_modal(page: Page, vacancy: Vacancy, cover_letter: str,
                  use_cover_letter: bool, has_letter: bool) -> str:
    """Обрабатывает модалку с сопроводительным."""
    if has_letter and cover_letter and use_cover_letter:
        print(f"  [apply] {vacancy.title} — вставляю письмо...")
        letter_input = page.locator('[data-qa="vacancy-response-popup-form-letter-input"]')
        letter_input.fill(cover_letter)
        page.wait_for_timeout(500)

    submit = page.locator('[data-qa="vacancy-response-submit-popup"]')
    if submit.count() > 0:
        box = submit.first.bounding_box()
        if box:
            page.mouse.click(box["x"] + box["width"]/2, box["y"] + box["height"]/2)
        else:
            submit.first.click()
    else:
        btn = page.locator('button:has-text("Откликнуться")')
        if btn.count() > 0:
            btn.first.click()

    page.wait_for_timeout(3000)

    if _check_sent(page):
        status = STATUS_LETTER_SENT if (has_letter and cover_letter and use_cover_letter) else STATUS_SENT
        print(f"  [apply] {vacancy.title} — ОТКЛИК ОТПРАВЛЕН (модалка)")
        return status

    print(f"  [apply] {vacancy.title} — отправил модалку, подтверждение не найдено")
    return STATUS_SENT


def _handle_foreign(page: Page, vacancy: Vacancy, cover_letter: str, use_cover_letter: bool) -> str:
    """Подтверждает отклик в другую страну."""
    print(f"  [apply] {vacancy.title} — другая страна, подтверждаю...")
    page.evaluate("""
        () => {
            const btns = document.querySelectorAll('button');
            for (const b of btns) {
                const t = b.textContent.toLowerCase();
                if (t.includes('всё равно') || t.includes('продолжить')) {
                    b.click(); return;
                }
            }
        }
    """)
    page.wait_for_timeout(3000)

    if _check_sent(page):
        print(f"  [apply] {vacancy.title} — ОТКЛИК ОТПРАВЛЕН (другая страна)")
        return STATUS_SENT

    # Может появиться модалка после подтверждения
    has_letter = page.locator('[data-qa="vacancy-response-popup-form-letter-input"]').count() > 0
    has_submit = page.locator('[data-qa="vacancy-response-submit-popup"]').count() > 0
    if has_letter or has_submit:
        return _handle_modal(page, vacancy, cover_letter, use_cover_letter, has_letter)

    return STATUS_ERROR


def _handle_redirect(page: Page, vacancy: Vacancy, original_url: str) -> str:
    """Навигация после клика."""
    current = page.url
    if any(w in current.lower() for w in ["test", "question", "quiz"]):
        print(f"  [apply] {vacancy.title} — тестовое, возвращаюсь")
        page.goto(original_url, wait_until="domcontentloaded", timeout=20000)
        page.wait_for_timeout(2000)
        return STATUS_TEST

    print(f"  [apply] {vacancy.title} — редирект: {current}")
    page.goto(original_url, wait_until="domcontentloaded", timeout=20000)
    page.wait_for_timeout(2000)
    return STATUS_SKIPPED


def _check_sent(page: Page) -> bool:
    return page.evaluate("""
        () => document.body.innerText.includes('Отклик отправлен')
    """)


def human_delay(delay_min: int, delay_max: int) -> None:
    mean = (delay_min + delay_max) / 2
    std = (delay_max - delay_min) / 4
    delay = random.gauss(mean, std)
    delay = max(delay_min, min(delay_max * 1.5, delay))

    if random.random() < 0.08:
        delay += random.uniform(15, 30)
        print(f"  [delay] Длинная пауза {delay:.1f} сек")
    else:
        print(f"  [delay] {delay:.1f} сек")

    time.sleep(delay)
