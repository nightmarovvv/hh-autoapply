"""Тесты загрузки и валидации конфигурации."""

import pytest
import tempfile
from pathlib import Path

import yaml

from hh_apply.config import load_config, render_cover_letter, DEFAULTS
from hh_apply.search import Vacancy


class TestLoadConfig:
    def test_load_minimal_config(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("search:\n  query: python\n", encoding="utf-8")
        cfg = load_config(config_file)
        assert cfg["search"]["query"] == "python"

    def test_defaults_applied(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("search:\n  query: test\n", encoding="utf-8")
        cfg = load_config(config_file)
        assert cfg["apply"]["max_applications"] == 50
        assert cfg["apply"]["delay_min"] == 1.5
        assert cfg["browser"]["headless"] is False

    def test_user_overrides_defaults(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({
            "search": {"query": "test"},
            "apply": {"max_applications": 100},
        }), encoding="utf-8")
        cfg = load_config(config_file)
        assert cfg["apply"]["max_applications"] == 100

    def test_data_dir_expanded(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump({
            "search": {"query": "test"},
            "browser": {"data_dir": "~/.hh-apply"},
        }), encoding="utf-8")
        cfg = load_config(config_file)
        assert "~" not in cfg["browser"]["data_dir"]

    def test_empty_config(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("", encoding="utf-8")
        cfg = load_config(config_file)
        assert cfg["search"]["query"] == ""
        assert cfg["apply"]["max_applications"] == 50

    def test_all_sections_present(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("search:\n  query: test\n", encoding="utf-8")
        cfg = load_config(config_file)
        assert "search" in cfg
        assert "filters" in cfg
        assert "apply" in cfg
        assert "browser" in cfg

    def test_filters_defaults(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        config_file.write_text("search:\n  query: test\n", encoding="utf-8")
        cfg = load_config(config_file)
        assert cfg["filters"]["exclude_companies"] == []
        assert cfg["filters"]["exclude_keywords"] == []
        assert cfg["filters"]["exclude_pattern"] == ""
        assert cfg["filters"]["exclude_company_pattern"] == ""
        assert cfg["filters"]["skip_test_vacancies"] is True


class TestRenderCoverLetter:
    def _vac(self, title="Python Dev", company="Yandex", salary="200000 руб"):
        return Vacancy(
            vacancy_id="1", title=title, company=company,
            url="https://hh.ru/vacancy/1", salary=salary,
        )

    def test_company_substitution(self):
        result = render_cover_letter("Привет, {company}!", self._vac())
        assert result == "Привет, Yandex!"

    def test_position_substitution(self):
        result = render_cover_letter("Вакансия: {position}", self._vac())
        assert result == "Вакансия: Python Dev"

    def test_salary_substitution(self):
        result = render_cover_letter("ЗП: {salary}", self._vac())
        assert result == "ЗП: 200000 руб"

    def test_salary_none(self):
        v = self._vac(salary=None)
        result = render_cover_letter("ЗП: {salary}", v)
        assert result == "ЗП: не указана"

    def test_all_variables(self):
        result = render_cover_letter(
            "{position} в {company}, ЗП {salary}",
            self._vac(),
        )
        assert result == "Python Dev в Yandex, ЗП 200000 руб"

    def test_no_variables(self):
        result = render_cover_letter("Простое письмо", self._vac())
        assert result == "Простое письмо"

    def test_multiple_same_variable(self):
        result = render_cover_letter("{company} и ещё раз {company}", self._vac())
        assert result == "Yandex и ещё раз Yandex"
