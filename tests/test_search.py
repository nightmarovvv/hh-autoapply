"""Тесты поиска и сортировки вакансий."""

import pytest
from hh_apply.search import Vacancy, sort_vacancies_fresh_first


class TestSortVacanciesFreshFirst:
    def test_today_first(self):
        vacancies = [
            Vacancy("1", "Old", "C", "url", published_date="3 дня назад"),
            Vacancy("2", "New", "C", "url", published_date="сегодня"),
            Vacancy("3", "Yesterday", "C", "url", published_date="вчера"),
        ]
        sorted_v = sort_vacancies_fresh_first(vacancies)
        assert sorted_v[0].vacancy_id == "2"  # сегодня
        assert sorted_v[1].vacancy_id == "3"  # вчера
        assert sorted_v[2].vacancy_id == "1"  # 3 дня

    def test_minutes_ago_is_fresh(self):
        vacancies = [
            Vacancy("1", "Old", "C", "url", published_date="неделю назад"),
            Vacancy("2", "Fresh", "C", "url", published_date="15 минут назад"),
        ]
        sorted_v = sort_vacancies_fresh_first(vacancies)
        assert sorted_v[0].vacancy_id == "2"

    def test_hours_ago_is_fresh(self):
        vacancies = [
            Vacancy("1", "Old", "C", "url", published_date="5 дней назад"),
            Vacancy("2", "Fresh", "C", "url", published_date="2 час назад"),
        ]
        sorted_v = sort_vacancies_fresh_first(vacancies)
        assert sorted_v[0].vacancy_id == "2"

    def test_none_date_goes_after_fresh(self):
        vacancies = [
            Vacancy("1", "Old", "C", "url", published_date="3 дня назад"),
            Vacancy("2", "NoDate", "C", "url", published_date=None),
            Vacancy("3", "Fresh", "C", "url", published_date="сегодня"),
        ]
        sorted_v = sort_vacancies_fresh_first(vacancies)
        assert sorted_v[0].vacancy_id == "3"  # сегодня first
        # None и "3 дня" оба не свежие — порядок между ними не гарантирован

    def test_empty_list(self):
        assert sort_vacancies_fresh_first([]) == []

    def test_single_item(self):
        v = [Vacancy("1", "Dev", "C", "url")]
        assert len(sort_vacancies_fresh_first(v)) == 1
