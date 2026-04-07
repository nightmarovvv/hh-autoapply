"""Поиск вакансий на hh.ru."""

from __future__ import annotations

from dataclasses import dataclass, field

from patchright.sync_api import Page

from hh_apply.filters import build_search_url


@dataclass
class Vacancy:
    vacancy_id: str
    title: str
    company: str
    url: str
    salary: str | None = None
    published_date: str | None = None


def do_search(page: Page, config: dict) -> None:
    """Открывает страницу поиска с параметрами из конфига."""
    search_config = config.get("search", {})
    query = search_config.get("query", "").strip()

    if not query:
        raise ValueError("search.query не указан в конфиге")

    # Формируем URL с фильтрами
    search_url = build_search_url(search_config)
    page.goto(search_url, wait_until="domcontentloaded", timeout=20000)
    page.wait_for_timeout(3000)

    _dismiss_cookies(page)


def collect_vacancy_ids_from_page(page: Page) -> list[Vacancy]:
    """Собирает все вакансии с текущей страницы."""
    raw = page.evaluate("""
        () => {
            const cards = document.querySelectorAll('[data-qa="vacancy-serp__vacancy"]');
            return Array.from(cards).map(card => {
                const titleEl = card.querySelector('[data-qa="serp-item__title"]');
                const companyEl = card.querySelector('[data-qa="vacancy-serp__vacancy-employer"]');
                const btnEl = card.querySelector('[data-qa="vacancy-serp__vacancy_response"]');
                const salaryEl = card.querySelector('[data-qa="vacancy-serp__vacancy-compensation"]');
                const dateEl = card.querySelector('[data-qa="vacancy-serp__vacancy-date"]');

                if (!titleEl) return null;

                const href = titleEl.href || '';
                const match = href.match(/\\/vacancy\\/(\\d+)/);
                if (!match) return null;

                return {
                    vacancy_id: match[1],
                    title: titleEl.textContent.trim(),
                    company: companyEl ? companyEl.textContent.trim() : '\u2014',
                    has_apply_btn: !!btnEl,
                    btn_text: btnEl ? btnEl.textContent.trim() : '',
                    salary: salaryEl ? salaryEl.textContent.trim() : null,
                    published_date: dateEl ? dateEl.textContent.trim() : null,
                };
            }).filter(Boolean);
        }
    """)

    vacancies = []
    for item in raw:
        if "отправлен" in item.get("btn_text", "").lower():
            continue
        if not item.get("has_apply_btn"):
            continue

        vacancies.append(Vacancy(
            vacancy_id=item["vacancy_id"],
            title=item["title"],
            company=item["company"],
            url=f"https://hh.ru/vacancy/{item['vacancy_id']}",
            salary=item.get("salary"),
            published_date=item.get("published_date"),
        ))

    return vacancies


def sort_vacancies_fresh_first(vacancies: list[Vacancy]) -> list[Vacancy]:
    """Сортирует вакансии — свежие (сегодня/вчера) первыми."""
    today_words = ("сегодня", "только что", "час назад", "минут назад")

    def freshness_key(v: Vacancy) -> int:
        if not v.published_date:
            return 2
        date_lower = v.published_date.lower()
        if any(w in date_lower for w in today_words):
            return 0
        if "вчера" in date_lower:
            return 1
        return 2

    return sorted(vacancies, key=freshness_key)


def count_search_results(page: Page) -> int | None:
    """Считает общее количество найденных вакансий со страницы поиска."""
    count = page.evaluate("""
        () => {
            const el = document.querySelector('[data-qa="vacancies-total-count"]');
            if (!el) return null;
            const text = el.textContent.replace(/\\s/g, '');
            const match = text.match(/(\\d+)/);
            return match ? parseInt(match[1]) : null;
        }
    """)
    return count


def go_next_page(page: Page) -> bool:
    """Переход на следующую страницу результатов."""
    next_url = page.evaluate("""
        () => {
            const pages = document.querySelectorAll('[data-qa="pager-page"]');
            let foundCurrent = false;
            for (const p of pages) {
                if (foundCurrent) {
                    return p.href;
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


def dismiss_ads(page: Page) -> None:
    """Закрывает рекламные попапы и оверлеи."""
    page.evaluate("""
        () => {
            document.querySelectorAll('[class*="close"], [class*="dismiss"], [aria-label="close"]')
                .forEach(el => { if (el.offsetParent) el.click(); });
            document.querySelectorAll('[class*="banner"], [class*="promo"], [id*="adv"]')
                .forEach(el => el.remove());
        }
    """)


def _dismiss_cookies(page: Page) -> None:
    """Кликает кнопку принятия куки."""
    btn = page.locator('[data-qa="cookies-policy-informer"] button')
    if btn.count() > 0:
        try:
            btn.first.click(timeout=3000)
        except Exception:
            page.evaluate('document.querySelector(\'[data-qa="cookies-policy-informer"]\')?.remove()')
        page.wait_for_timeout(500)
