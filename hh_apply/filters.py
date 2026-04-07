"""Построение URL поиска hh.ru из конфигурации и фильтрация вакансий."""

from __future__ import annotations

from urllib.parse import urlencode


# Маппинг параметров конфига → GET-параметры hh.ru
EXPERIENCE_MAP = {
    "noExperience": "noExperience",
    "between1And3": "between1And3",
    "between3And6": "between3And6",
    "moreThan6": "moreThan6",
}

EMPLOYMENT_MAP = {
    "full": "full",
    "part": "part",
    "project": "project",
    "volunteer": "volunteer",
    "probation": "probation",
}

SCHEDULE_MAP = {
    "remote": "remote",
    "fullDay": "fullDay",
    "shift": "shift",
    "flexible": "flexible",
    "flyInFlyOut": "flyInFlyOut",
}

ORDER_MAP = {
    "relevance": "relevance",
    "publication_time": "publication_time",
    "salary_desc": "salary_desc",
    "salary_asc": "salary_asc",
}

PERIOD_MAP = {
    1: 1,
    3: 3,
    7: 7,
    30: 30,
}


def build_search_url(search_config: dict) -> str:
    """Формирует URL поиска hh.ru из параметров конфига."""
    params: list[tuple[str, str]] = []

    query = search_config.get("query", "").strip()
    if query:
        params.append(("text", query))

    area = search_config.get("area")
    if area:
        params.append(("area", str(area)))

    salary_from = search_config.get("salary_from")
    if salary_from:
        params.append(("salary", str(salary_from)))
        if search_config.get("salary_only"):
            params.append(("only_with_salary", "true"))

    experience = search_config.get("experience")
    if experience and experience in EXPERIENCE_MAP:
        params.append(("experience", EXPERIENCE_MAP[experience]))

    for emp in search_config.get("employment", []):
        if emp in EMPLOYMENT_MAP:
            params.append(("employment", EMPLOYMENT_MAP[emp]))

    for sched in search_config.get("schedule", []):
        if sched in SCHEDULE_MAP:
            params.append(("schedule", SCHEDULE_MAP[sched]))

    period = search_config.get("search_period")
    if period and period in PERIOD_MAP:
        params.append(("search_period", str(PERIOD_MAP[period])))

    order = search_config.get("order_by", "relevance")
    if order and order in ORDER_MAP:
        params.append(("order_by", ORDER_MAP[order]))

    # Всегда показываем с кнопкой отклика
    params.append(("enable_snippets", "true"))

    base = "https://hh.ru/search/vacancy"
    if params:
        return f"{base}?{urlencode(params)}"
    return base


def should_skip_vacancy(vacancy, filters_config: dict) -> str | None:
    """Проверяет, нужно ли пропустить вакансию по фильтрам.

    Возвращает причину пропуска или None.
    """
    title_lower = vacancy.title.lower()
    company_lower = vacancy.company.lower()

    for keyword in filters_config.get("exclude_keywords", []):
        if keyword.lower() in title_lower:
            return f"ключевое слово: {keyword}"

    for company in filters_config.get("exclude_companies", []):
        if company.lower() in company_lower:
            return f"компания: {company}"

    return None
