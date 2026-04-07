# hh-apply

CLI-инструмент для автоматических откликов на вакансии [hh.ru](https://hh.ru).

- **Patchright** вместо Playwright — обход CDP-детекта на уровне исходников
- Stealth: WebGL spoof, canvas/audio noise, реалистичные fingerprints
- Интерактивная настройка — не нужно вручную редактировать YAML
- Гибкие фильтры: зарплата, опыт, регион, график, исключения
- Тестовые вакансии в отчёте для ручного отклика
- Звуковое уведомление при капче
- Красивый Rich-отчёт по итогам

## Установка

```bash
pip install git+https://github.com/username/hh-apply.git
python -m patchright install chromium
```

## Быстрый старт

```bash
# 1. Интерактивная настройка (визард с вопросами)
hh-apply init

# 2. Войти в hh.ru
hh-apply login

# 3. Запустить
hh-apply run
```

## Команды

| Команда | Описание |
|---------|----------|
| `hh-apply init` | Интерактивная настройка (запрос, фильтры, сопроводительное) |
| `hh-apply login` | Войти в hh.ru (откроется браузер) |
| `hh-apply run` | Запустить автоотклики |
| `hh-apply stats` | Показать статистику |

### Опции `hh-apply run`

```
-c, --config    Путь к конфигу (по умолчанию: config.yaml)
-l, --limit     Макс. количество откликов
--headless      Скрытый режим браузера
--dry-run       Только поиск, без откликов
-r, --report    Сохранить отчёт в файл
```

## Как работает антидетект

| Уровень | Что делаем |
|---------|-----------|
| **CDP** | Patchright — нет Runtime.enable, нет Console.enable |
| **Browser args** | Убираем --enable-automation и другие флаги |
| **Fingerprint** | Canvas/Audio noise, WebGL spoof, 15+ User-Agent |
| **Поведение** | isTrusted mouse clicks, человеческие паузы, Bezier-движения |
| **Сессия** | Persistent cookies, проверка авторизации каждые 15 откликов |

## Конфигурация

`hh-apply init` создаст `config.yaml` через визард. Можно отредактировать вручную:

```yaml
search:
  query: "python developer"
  area: 1                       # 1=Москва, 2=СПб
  salary_from: 150000
  experience: "between3And6"
  schedule: ["remote"]

filters:
  exclude_companies: ["Компания"]
  exclude_keywords: ["стажёр"]
  skip_test_vacancies: true

apply:
  max_applications: 50
  use_cover_letter: true
  cover_letter: |
    Здравствуйте!
    Меня заинтересовала ваша вакансия.

browser:
  headless: false
  data_dir: "~/.hh-apply"
```

## Где хранятся данные

`~/.hh-apply/`:
- `storage_state.json` — сессия браузера
- `applications.db` — история откликов (SQLite)

## Лицензия

MIT
