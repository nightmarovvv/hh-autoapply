[![Tests](https://github.com/nightmarovvv/hh-autoapply/actions/workflows/test.yml/badge.svg)](https://github.com/nightmarovvv/hh-autoapply/actions/workflows/test.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

# hh-apply

**Автоматические отклики на [hh.ru](https://hh.ru) из терминала.**

Ищет вакансии, фильтрует, откликается через настоящий браузер с антидетектом. Вы настраиваете один раз — дальше работает само.

---

> Этот проект полностью бесплатный и open-source. Я сделал его для всех, кто устал вручную кликать «Откликнуться» на сотни вакансий. Если hh-apply вам помог — поставьте звёздочку, это лучшая мотивация продолжать развивать проект.

---

## Возможности

- **Умный поиск** — фильтры по запросу, региону, зарплате, опыту, графику
- **Реальный браузер** — isTrusted клики через Patchright, не API-запросы
- **Сопроводительное письмо** — автоподстановка `{company}`, `{position}`, `{salary}`
- **Свежие первыми** — приоритизация: сегодня > вчера > старые
- **Тестовые вакансии** — пропускает, сохраняет ссылки для ручного прохождения
- **Капча в терминале** — показывает картинку, вводите текст не выходя из терминала
- **Автоподъём резюме** — boost через Android API по расписанию
- **База данных** — все отклики в SQLite с экспортом в CSV/JSON
- **Ответы рекрутеров** — мониторинг приглашений, отказов, конверсии
- **Расписание** — автозапуск через crontab (ежедневно, по будням)
- **Диагностика** — `hh-apply doctor` проверит что всё настроено
- **Антидетект** — Patchright + fingerprint masking + человеческие паузы

## Быстрый старт

```bash
hh-apply init          # Настройка (стрелки + пробел)
hh-apply login         # Войти в hh.ru через браузер
hh-apply run --dry-run # Посмотреть вакансии без откликов
hh-apply run           # Запустить отклики
```

## Установка

Копируйте каждую команду и вставляйте в терминал по одной.

> **Не знаете как открыть терминал?**
> - **macOS:** Cmd + Пробел → Terminal → Enter
> - **Windows:** Win → cmd → Enter
> - **Linux:** Ctrl + Alt + T

---

### Шаг 1. Проверьте Python

macOS / Linux:
```bash
python3 --version
```

Windows:
```
python --version
```

Нужен `Python 3.9` или выше.

<details>
<summary><b>Как установить Python</b></summary>

**macOS:**

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```
```bash
brew install python
```

**Windows:**

1. Откройте [python.org/downloads](https://www.python.org/downloads/)
2. Скачайте и запустите установщик
3. **Поставьте галочку "Add python.exe to PATH"**
4. Install Now → закройте и откройте cmd заново

**Ubuntu / Debian / WSL:**
```bash
sudo apt update && sudo apt install -y python3 python3-pip python3-venv
```

</details>

---

### Шаг 2. Создайте виртуальное окружение

**macOS / Linux:**
```bash
mkdir ~/hh-apply && cd ~/hh-apply
python3 -m venv .venv
source .venv/bin/activate
```

**Windows:**
```
mkdir %USERPROFILE%\hh-apply && cd %USERPROFILE%\hh-apply
python -m venv .venv
.venv\Scripts\activate
```

В начале строки появится `(.venv)` — окружение активно.

---

### Шаг 3. Установите hh-apply

```bash
pip install git+https://github.com/nightmarovvv/hh-autoapply.git
```

<details>
<summary><b>pip: command not found?</b></summary>

```bash
python3 -m pip install git+https://github.com/nightmarovvv/hh-autoapply.git
```

Если и это не работает:
```bash
python3 -m ensurepip --upgrade
```

</details>

---

### Шаг 4. Скачайте браузер

```bash
patchright install chromium
```

> Linux: также выполните `patchright install-deps chromium`

---

### Шаг 5. Проверьте

```bash
hh-apply doctor
```

Все пункты зелёные? Готово!

---

### Как запускать в следующий раз

**macOS / Linux:**
```bash
cd ~/hh-apply && source .venv/bin/activate
```

**Windows:**
```
cd %USERPROFILE%\hh-apply && .venv\Scripts\activate
```

### Обновление

```bash
pip install --no-cache-dir --force-reinstall git+https://github.com/nightmarovvv/hh-autoapply.git
```

## Команды

| Команда | Описание |
|---------|----------|
| `init` | Настройка — регион, зарплата, опыт, фильтры, письмо |
| `login` | Вход через браузер (Chrome, Edge, Brave, Yandex Browser) |
| `run` | Запуск откликов с live-прогрессом |
| `run --dry-run` | Посмотреть вакансии без откликов |
| `stats` | Статистика откликов (цветная + по дням) |
| `doctor` | Диагностика окружения |
| `api-login` | OAuth для boost, responses, whoami |
| `boost` | Поднять резюме в поиске рекрутеров |
| `responses` | Мониторинг ответов рекрутеров |
| `schedule` | Автозапуск по расписанию |
| `done` | Убрать тестовую вакансию |
| `whoami` | Информация об аккаунте |
| `query` | SQL-запросы к базе |

### Опции `run`

| Флаг | Описание |
|------|----------|
| `-c qa.yaml` | Другой профиль конфига |
| `--limit N` | Максимум откликов |
| `--exclude "regex"` | Исключить вакансии (напр. `junior\|стажёр`) |
| `--dry-run` | Только показать вакансии |
| `--headless` | Без окна браузера |
| `--report файл` | Сохранить отчёт |

### Несколько профилей

```bash
hh-apply init -o python.yaml   # Профиль для Python
hh-apply init -o qa.yaml       # Профиль для QA
hh-apply run -c python.yaml    # Запуск с профилем
```

### Расписание

```bash
hh-apply schedule set 09:00              # Каждый день в 9:00
hh-apply schedule set 09:00 --weekdays   # Только будни
hh-apply schedule boost 4                # Boost каждые 4 часа
hh-apply schedule status                 # Текущее расписание
hh-apply schedule remove                 # Удалить
```

### Экспорт

```bash
hh-apply stats --csv -o out.csv
hh-apply stats --json
```

## Как работает

**Поиск** — формирует URL с фильтрами, открывает в браузере, собирает вакансии, сортирует свежие первыми.

**Проверка** — для каждой вакансии API-запросом определяет тип: мгновенный отклик, модалка с письмом или тестовое задание.

**Отклик** — кликает кнопку через `page.mouse` (isTrusted: true). Обрабатывает модалки, предупреждения, чат рекрутера. При ошибке — retry.

**Письмо** — подставляет `{company}`, `{position}`, `{salary}` в шаблон.

**Капча** — скриншот в терминале (Kitty/Sixel/файл), вводите текст, отправляется в браузер.

**Антидетект** — [Patchright](https://github.com/Kaliiiiiiiiii-Vinyzu/patchright) (форк Playwright с патчами Chromium) + fingerprint noise + человеческие паузы (±30% вариативность).

## Конфигурация

`hh-apply init` создаёт `config.yaml` через визард.

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
  exclude_pattern: "junior|стажёр|bitrix"
  exclude_company_pattern: "аутсорс|крипто"
  skip_test_vacancies: true

apply:
  max_applications: 150
  use_cover_letter: true
  cover_letter: |
    Здравствуйте!
    Меня заинтересовала вакансия {position} в {company}.
    Буду рад обсудить детали.
    С уважением
  delay_min: 1.5
  delay_max: 4.0

browser:
  headless: false
  data_dir: "~/.hh-apply"
  # timezone: "Europe/Moscow"
  # proxy: "http://user:pass@host:port"
```

## Безопасность

- Пароли не хранятся — логин через браузер, сохраняются только куки
- Токены хранятся с правами `0600` (только владелец)
- Все запросы с вашего устройства и IP
- Прокси: `HTTPS_PROXY` / `http_proxy` или `browser.proxy` в конфиге

## Частые проблемы

<details>
<summary><b>"python" / "python3" не найден</b></summary>

**macOS / Linux:** команда `python3`, не `python`.

**Windows:** если `python` открывает Microsoft Store — установите Python с [python.org](https://www.python.org/downloads/). Галочка **"Add to PATH"** обязательна.

</details>

<details>
<summary><b>"hh-apply" не найдена</b></summary>

Не активировано окружение:

**macOS / Linux:** `cd ~/hh-apply && source .venv/bin/activate`

**Windows:** `cd %USERPROFILE%\hh-apply && .venv\Scripts\activate`

</details>

<details>
<summary><b>Бесконечная загрузка при логине</b></summary>

Обновите: `pip install --upgrade git+https://github.com/nightmarovvv/hh-autoapply.git`

</details>

<details>
<summary><b>Капча</b></summary>

hh.ru иногда показывает капчу. hh-apply покажет её в терминале — введите текст. Если часто — подождите 10-15 минут.

</details>

<details>
<summary><b>"Не авторизован"</b></summary>

Куки живут ~2 недели. Перелогиньтесь: `hh-apply login`

</details>

<details>
<summary><b>Кракозябры на Windows</b></summary>

Установите [Windows Terminal](https://apps.microsoft.com/detail/9n0dx20hk701) или выполните `chcp 65001`.

</details>

<details>
<summary><b>Chromium не ставится на Linux</b></summary>

```bash
patchright install-deps chromium
patchright install chromium
```

</details>

## Разработка

```bash
git clone https://github.com/nightmarovvv/hh-autoapply.git
cd hh-autoapply
pip install -e ".[dev]"
pytest tests/ -v
```

Подробнее — в [CONTRIBUTING.md](CONTRIBUTING.md).

## Требования

- Python 3.9+
- macOS, Linux, Windows, WSL

## Лицензия

MIT
