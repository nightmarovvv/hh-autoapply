"""Тесты фильтрации вакансий и построения URL."""

import pytest
from hh_apply.filters import build_search_url, should_skip_vacancy
from hh_apply.search import Vacancy


def _vac(title="Python Developer", company="Tech Corp"):
    return Vacancy(vacancy_id="1", title=title, company=company, url="https://hh.ru/vacancy/1")


class TestBuildSearchUrl:
    def test_basic_query(self):
        url = build_search_url({"query": "python"})
        assert "text=python" in url
        assert url.startswith("https://hh.ru/search/vacancy?")

    def test_salary_filter(self):
        url = build_search_url({"query": "dev", "salary_from": 200000, "salary_only": True})
        assert "salary=200000" in url
        assert "only_with_salary=true" in url

    def test_experience_filter(self):
        url = build_search_url({"query": "dev", "experience": "between3And6"})
        assert "experience=between3And6" in url

    def test_schedule_filter(self):
        url = build_search_url({"query": "dev", "schedule": ["remote", "fullDay"]})
        assert "schedule=remote" in url
        assert "schedule=fullDay" in url

    def test_area_filter(self):
        url = build_search_url({"query": "dev", "area": 1})
        assert "area=1" in url

    def test_empty_query(self):
        url = build_search_url({"query": ""})
        assert "text=" not in url

    def test_always_has_enable_snippets(self):
        url = build_search_url({"query": "test"})
        assert "enable_snippets=true" in url

    def test_order_by(self):
        url = build_search_url({"query": "dev", "order_by": "publication_time"})
        assert "order_by=publication_time" in url

    def test_search_period(self):
        url = build_search_url({"query": "dev", "search_period": 7})
        assert "search_period=7" in url


class TestShouldSkipVacancy:
    def test_no_filters(self):
        assert should_skip_vacancy(_vac(), {}) is None

    def test_keyword_exclude(self):
        result = should_skip_vacancy(_vac("Junior Python"), {"exclude_keywords": ["junior"]})
        assert result is not None
        assert "junior" in result

    def test_keyword_case_insensitive(self):
        result = should_skip_vacancy(_vac("JUNIOR Dev"), {"exclude_keywords": ["junior"]})
        assert result is not None

    def test_company_exclude(self):
        result = should_skip_vacancy(_vac(company="Yandex Crowd"), {"exclude_companies": ["Yandex Crowd"]})
        assert result is not None
        assert "компания" in result

    def test_company_case_insensitive(self):
        result = should_skip_vacancy(_vac(company="YANDEX crowd"), {"exclude_companies": ["yandex crowd"]})
        assert result is not None

    def test_regex_exclude(self):
        result = should_skip_vacancy(_vac("Стажёр Python"), {"exclude_pattern": "стажёр|intern"})
        assert result is not None
        assert "regex" in result

    def test_regex_no_match(self):
        result = should_skip_vacancy(_vac("Senior Python"), {"exclude_pattern": "стажёр|intern"})
        assert result is None

    def test_invalid_regex(self):
        result = should_skip_vacancy(_vac(), {"exclude_pattern": "[invalid"})
        assert result is None  # Не падает, просто пропускает

    def test_company_pattern_exclude(self):
        result = should_skip_vacancy(
            _vac(company="КриптоСтартап"),
            {"exclude_company_pattern": "крипто|казино"},
        )
        assert result is not None
        assert "компания regex" in result

    def test_company_pattern_no_match(self):
        result = should_skip_vacancy(
            _vac(company="Яндекс"),
            {"exclude_company_pattern": "крипто|казино"},
        )
        assert result is None

    def test_no_false_positives(self):
        result = should_skip_vacancy(_vac("Senior Python Developer", "Good Company"), {
            "exclude_keywords": ["junior", "intern"],
            "exclude_companies": ["Bad Corp"],
            "exclude_pattern": "стажёр|bitrix",
        })
        assert result is None
