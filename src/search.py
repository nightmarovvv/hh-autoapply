"""Поиск вакансий на hh.ru.

Логика:
1. Открыть страницу поиска
2. Закрыть куки-баннер (кликом, не удалением DOM)
3. Сбросить фильтры (кнопка "Сбросить все")
4. Ввести запрос в поле поиска
5. Нажать "Найти"
6. Пагинация через номера страниц (pager-page с aria-current)
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from playwright.sync_api import Page


@dataclass
class Vacancy:
    vacancy_id: str
    title: str
    company: str
    url: str


def do_search(page: Page, config: dict) -> None:
    """Сброс фильтров → ввод запроса → клик Найти.

    После вызова страница на первой странице результатов.
    """
    print("[search] Открываю страницу поиска...")
    page.goto("https://hh.ru/search/vacancy", wait_until="domcontentloaded", timeout=20000)
    page.wait_for_timeout(3000)

    _dismiss_cookies(page)

    if config.get("reset_filters", False):
        _reset_filters(page)

    _type_and_search(page, config["search_query"])


def collect_vacancy_ids_from_page(page: Page) -> list[Vacancy]:
    """Собирает все вакансии с текущей страницы через JS (без Playwright-локаторов).

    Возвращает список Vacancy с ID, названием, компанией.
    """
    raw = page.evaluate("""
        () => {
            const cards = document.querySelectorAll('[data-qa="vacancy-serp__vacancy"]');
            return Array.from(cards).map(card => {
                const titleEl = card.querySelector('[data-qa="serp-item__title"]');
                const companyEl = card.querySelector('[data-qa="vacancy-serp__vacancy-employer"]');
                const btnEl = card.querySelector('[data-qa="vacancy-serp__vacancy_response"]');

                if (!titleEl) return null;

                const href = titleEl.href || '';
                const match = href.match(/\\/vacancy\\/(\\d+)/);
                if (!match) return null;

                return {
                    vacancy_id: match[1],
                    title: titleEl.textContent.trim(),
                    company: companyEl ? companyEl.textContent.trim() : '—',
                    has_apply_btn: !!btnEl,
                    btn_text: btnEl ? btnEl.textContent.trim() : '',
                };
            }).filter(Boolean);
        }
    """)

    vacancies = []
    for item in raw:
        # Пропускаем если уже откликнулись (текст кнопки)
        if "отправлен" in item.get("btn_text", "").lower():
            continue
        if not item.get("has_apply_btn"):
            continue

        vacancies.append(Vacancy(
            vacancy_id=item["vacancy_id"],
            title=item["title"],
            company=item["company"],
            url=f"https://hh.ru/vacancy/{item['vacancy_id']}",
        ))

    return vacancies


def go_next_page(page: Page) -> bool:
    """Переход на следующую страницу результатов.

    Использует aria-current для определения текущей страницы,
    кликает следующую через href навигацию.
    """
    next_url = page.evaluate("""
        () => {
            const pages = document.querySelectorAll('[data-qa="pager-page"]');
            let foundCurrent = false;
            for (const p of pages) {
                if (foundCurrent) {
                    return p.href;  // Следующая после текущей
                }
                if (p.getAttribute('aria-current') === 'true') {
                    foundCurrent = true;
                }
            }
            return null;
        }
    """)

    if not next_url:
        return False

    page.goto(next_url, wait_until="domcontentloaded", timeout=20000)
    page.wait_for_timeout(3000)
    return True


def _dismiss_cookies(page: Page) -> None:
    """Кликает кнопку принятия куки (не удаляет DOM)."""
    btn = page.locator('[data-qa="cookies-policy-informer"] button')
    if btn.count() > 0:
        try:
            btn.first.click(timeout=3000)
            print("[search] Куки-баннер закрыт")
        except Exception:
            # Если кнопка не кликабельна — удаляем через JS как fallback
            page.evaluate('document.querySelector(\'[data-qa="cookies-policy-informer"]\')?.remove()')
        page.wait_for_timeout(500)


def _reset_filters(page: Page) -> None:
    """Сбрасывает все фильтры (точное совпадение 'Сбросить все')."""
    clicked = page.evaluate("""
        () => {
            const spans = document.querySelectorAll('[data-qa="link-text"]');
            for (const span of spans) {
                if (span.textContent.trim() === 'Сбросить все') {
                    span.scrollIntoView({block: 'center'});
                    span.click();
                    return true;
                }
            }
            return false;
        }
    """)
    if clicked:
        print("[search] Фильтры сброшены (Сбросить все)")
        page.wait_for_timeout(4000)
    else:
        print("[search] Кнопка 'Сбросить все' не найдена")


def _type_and_search(page: Page, query: str) -> None:
    """Вводит запрос и нажимает Найти."""
    search_input = page.locator('[data-qa="search-input"]')
    if search_input.count() == 0:
        print("[search] Поле поиска не найдено!")
        return

    search_input.first.click()
    page.wait_for_timeout(300)
    search_input.first.fill("")
    search_input.first.fill(query)
    print(f"[search] Запрос: {query}")
    page.wait_for_timeout(500)

    search_btn = page.locator('[data-qa="search-button"]')
    if search_btn.count() > 0:
        search_btn.first.click()
    else:
        search_input.first.press("Enter")

    print("[search] Поиск запущен")
    page.wait_for_timeout(4000)
