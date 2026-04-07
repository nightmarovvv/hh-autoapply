# hh-apply

CLI для автоматических откликов на [hh.ru](https://hh.ru). Написан на Python, работает через браузер с антидетектом.

## Что делает

- Ищет вакансии по заданным фильтрам (запрос, регион, зарплата, опыт, график)
- Откликается через реальный браузер — isTrusted клики, не API
- Персонализирует сопроводительное письмо под каждую вакансию
- Приоритизирует свежие вакансии (сегодня → вчера → старые)
- Вакансии с тестами сохраняет отдельно — для ручного прохождения
- Показывает капчу прямо в терминале, если появится
- Поднимает резюме через Android API
- Ведёт базу данных всех откликов с экспортом в CSV/JSON
- Мониторит ответы рекрутеров (приглашения, отказы, конверсия)
- Автозапуск по расписанию через crontab

## Установка

```bash
pip install git+https://github.com/nightmarovvv/hh-autoapply.git
python -m patchright install chromium
```

## Быстрый старт

```bash
hh-apply init          # Настройка (стрелки + пробел)
hh-apply login         # Войти в hh.ru
hh-apply run --dry-run # Пробный запуск — посмотреть вакансии
hh-apply run           # Запустить отклики
```

## Команды

| Команда | Описание |
|---------|----------|
| `init` | Настройка — регион, зарплата, опыт, фильтры, письмо |
| `login` | Вход через браузер (сохраняются только куки, без паролей) |
| `run` | Запуск откликов с live-прогрессом |
| `stats` | Статистика по откликам (цветная + по дням) |
| `responses` | Мониторинг ответов рекрутеров |
| `schedule` | Настроить автозапуск по расписанию |
| `boost` | Поднять резюме в поиске рекрутеров |
| `done` | Убрать тестовую вакансию из списка |
| `whoami` | Информация об аккаунте |
| `query` | SQL-запросы к базе данных |
| `completions` | Автодополнение для bash/zsh/fish |

### Опции `run`

| Флаг | Описание |
|------|----------|
| `-c qa.yaml` | Использовать другой профиль конфига |
| `--limit N` | Максимум откликов |
| `--exclude "regex"` | Исключить вакансии (напр. `junior\|стажёр`) |
| `--dry-run` | Только поиск — таблица вакансий без откликов |
| `--headless` | Без окна браузера |
| `--report файл` | Сохранить отчёт |

Без флагов — интерактивный режим с вопросами.

### Несколько профилей

```bash
hh-apply init -o python.yaml   # Профиль для Python
hh-apply init -o qa.yaml       # Профиль для QA
hh-apply run -c python.yaml    # Запуск с конкретным профилем
```

### Расписание

```bash
hh-apply schedule set 09:00              # Каждый день в 9:00
hh-apply schedule set 09:00 --weekdays   # Только будни
hh-apply schedule boost 4                # Boost резюме каждые 4 часа
hh-apply schedule status                 # Текущее расписание
hh-apply schedule remove                 # Удалить расписание
```

### Экспорт данных

```bash
hh-apply stats --csv -o out.csv   # Экспорт в CSV
hh-apply stats --json              # Экспорт в JSON
```

## Как работает

**Поиск:** Формирует URL с фильтрами → открывает в браузере → собирает вакансии со страницы → сортирует свежие первыми.

**Проверка:** Для каждой вакансии API-запросом определяет тип — quickResponse (мгновенный отклик), modal (с письмом), test-required (с тестом).

**Отклик:** Кликает кнопку через `page.mouse` (isTrusted: true). Обрабатывает модалки, foreign warning, чат рекрутера. При ошибке — retry с экспоненциальной задержкой.

**Письмо:** Подставляет `{company}`, `{position}`, `{salary}` из данных вакансии.

**Тесты:** Пропускает, сохраняет ссылку в `~/.hh-apply/test_vacancies.txt`.

**Капча:** Скриншот в терминале (Kitty protocol), ввод текста → вставка в браузер.

**Прогресс:** Rich Live-дашборд — прогрессбар, счётчики, текущая вакансия.

## Антидетект

Используется [Patchright](https://github.com/Kaliiiiiiiiii-Vinyzu/patchright) — форк Playwright с патчами на уровне Chromium:

- Нет `Runtime.enable` — CDP невидим для антибот-скриптов
- Убраны `--enable-automation`, `--disable-popup-blocking` и другие флаги
- Canvas/Audio fingerprint noise
- WebGL vendor/renderer spoof
- 15+ User-Agent (Mac/Win/Linux) с реальной версией Chromium
- navigator.webdriver = undefined
- Playwright markers удалены

## Конфигурация

`hh-apply init` создаёт `config.yaml` через визард со стрелочными меню.

```yaml
search:
  query: "python developer"
  area: 1                               # 1=Москва, 2=СПб, 113=Россия
  salary_from: 200000
  experience: "between3And6"
  schedule: [remote]

filters:
  exclude_companies: ["Компания"]
  exclude_keywords: ["intern"]
  exclude_pattern: "junior|стажёр|bitrix"     # Regex по названию
  exclude_company_pattern: "аутсорс|крипто"   # Regex по компании
  skip_test_vacancies: true

apply:
  max_applications: 150
  use_cover_letter: true
  cover_letter: |
    Здравствуйте!
    Меня заинтересовала вакансия {position} в {company}.
    Буду рад обсудить детали.
    С уважением
  # Переменные: {company}, {position}, {salary}
  delay_min: 1.5
  delay_max: 4.0

browser:
  headless: false
  data_dir: "~/.hh-apply"
```

## Файлы данных

`~/.hh-apply/`:
- `storage_state.json` — куки браузера
- `applications.db` — SQLite база откликов
- `api_token.json` — токены для boost/whoami
- `test_vacancies.txt` — вакансии с тестами

## Безопасность

- Пароли не хранятся — логин через браузер, сохраняются только куки
- Запросы с вашего устройства и IP
- Прокси подхватывается из `HTTPS_PROXY` / `http_proxy`

## Разработка

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## Требования

- Python 3.9+
- Linux, macOS, Windows, WSL

## Лицензия

MIT
