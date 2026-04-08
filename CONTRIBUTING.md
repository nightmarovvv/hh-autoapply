# Как внести вклад

Спасибо за интерес к проекту! Вот как можно помочь.

## Сообщить о проблеме

1. Проверьте [существующие issues](https://github.com/nightmarovvv/hh-autoapply/issues)
2. Создайте новый issue с описанием: ОС, версия Python, шаги воспроизведения

## Предложить улучшение

Создайте issue с тегом **feature request** и опишите идею.

## Разработка

### Настройка окружения

```bash
git clone https://github.com/nightmarovvv/hh-autoapply.git
cd hh-autoapply
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### Запуск тестов

```bash
pytest tests/ -v
```

### Стиль коммитов

Используем [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: новая функциональность
fix: исправление бага
fix(module): исправление в конкретном модуле
refactor: рефакторинг без изменения поведения
docs: изменения в документации
test: добавление/изменение тестов
chore: обновление зависимостей, CI и т.д.
```

### Структура проекта

```
hh_apply/
  cli.py          — CLI команды (Click + InquirerPy)
  runner.py       — Основной цикл: поиск → фильтр → отклик
  apply.py        — Логика клика по кнопке отклика
  auth.py         — Авторизация через нативный браузер
  search.py       — Парсинг вакансий со страницы поиска
  filters.py      — Построение URL + фильтрация вакансий
  config.py       — Загрузка и валидация YAML-конфига
  tracker.py      — SQLite база откликов
  stealth.py      — Антидетект (fingerprint, UA, wait)
  api_client.py   — Android API (boost, responses)
  api_apply.py    — Гибридная проверка типа вакансии
  captcha.py      — Отображение капчи в терминале
  report.py       — Отчёт сессии
  notifications.py — Звуковые уведомления
```

## Pull Request

1. Создайте ветку от `main`
2. Сделайте изменения
3. Убедитесь что тесты проходят: `pytest tests/ -v`
4. Создайте PR с описанием изменений
