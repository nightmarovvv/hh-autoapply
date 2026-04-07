"""Гибридные отклики: API-проверка типа + человеческий клик.

GET-проверка типа через fetch → знаем заранее: quickResponse, modal, test
"""

from __future__ import annotations

from patchright.sync_api import Page


def check_vacancy_type(page: Page, vacancy_id: str) -> dict:
    """Проверяет тип вакансии через API (без GIB-блокировки)."""
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
