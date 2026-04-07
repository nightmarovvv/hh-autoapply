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

Копируйте каждую команду и вставляйте в терминал по одной.

> **Не знаете как открыть терминал?**
> - **macOS:** нажмите **Cmd + Пробел**, введите **Terminal**, нажмите Enter
> - **Windows:** нажмите клавишу **Win**, введите **powershell**, нажмите Enter
> - **Linux:** нажмите **Ctrl + Alt + T**

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

Если показывает `Python 3.9` или выше — переходите к **Шагу 2**.

Если пишет "не найдено" или открывается Microsoft Store:

<details>
<summary><b>Как установить Python</b></summary>

**macOS:**

Сначала установите Homebrew (менеджер пакетов). Вставьте в терминал:
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```
> Попросит пароль от Mac — это нормально. При вводе пароль не отображается — просто введите и нажмите Enter. Если в конце написано `Add Homebrew to your PATH` — выполните те команды которые он показал.

Затем установите Python:
```bash
brew install python
```

---

**Windows:**

1. Откройте [python.org/downloads](https://www.python.org/downloads/)
2. Нажмите жёлтую кнопку **"Download Python"**
3. Запустите скачанный файл
4. **ВАЖНО:** на первом экране внизу есть галочка **"Add python.exe to PATH"** — **поставьте её**. Без неё ничего не будет работать
5. Нажмите **"Install Now"**
6. **Закройте PowerShell и откройте заново**

> Если забыли галочку — удалите Python через **Параметры → Приложения**, скачайте заново и поставьте.

---

**Ubuntu / Debian / WSL:**
```bash
sudo apt update && sudo apt install -y python3 python3-pip python3-venv
```

</details>

---

### Шаг 2. Проверьте Git

Git нужен чтобы скачать hh-apply с GitHub.

```bash
git --version
```

Если показывает версию — переходите к **Шагу 3**.

<details>
<summary><b>Как установить Git</b></summary>

**macOS:**
```bash
brew install git
```

**Windows:**
1. Откройте [git-scm.com/download/win](https://git-scm.com/download/win) — скачивание начнётся автоматически
2. Запустите установщик, нажимайте **Next** во всех окнах, в конце **Install**
3. **Закройте PowerShell и откройте заново**

**Linux:**
```bash
sudo apt install -y git
```

</details>

---

### Шаг 3. Установите hh-apply

macOS / Linux:
```bash
pip3 install git+https://github.com/nightmarovvv/hh-autoapply.git
```

Windows:
```
pip install git+https://github.com/nightmarovvv/hh-autoapply.git
```

> Побегут строки — это скачивание. Дождитесь `Successfully installed`.

---

### Шаг 4. Скачайте браузер

hh-apply работает через скрытый браузер Chromium. Его нужно скачать один раз:

```bash
patchright install chromium
```

> На Linux также выполните: `patchright install-deps chromium`

---

### Шаг 5. Проверьте

```bash
hh-apply --version
```

Видите номер версии (например `1.1.0`)? Всё работает! Переходите к [быстрому старту](#быстрый-старт).

> Если пишет "не найдено" / "не является командой" — смотрите [Частые проблемы](#частые-проблемы).

---

### Обновление до последней версии

macOS / Linux:
```bash
pip3 install --upgrade git+https://github.com/nightmarovvv/hh-autoapply.git
```

Windows:
```
pip install --upgrade git+https://github.com/nightmarovvv/hh-autoapply.git
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

## Частые проблемы

<details>
<summary><b>"python" / "pip" не найден (macOS / Linux)</b></summary>

На macOS и Linux команда называется `python3`, а не `python`. Используйте:

```bash
python3 --version
```

```bash
python3 -m pip install ...
```

Если `python3` тоже не найден — Python не установлен. Вернитесь к [разделу установки](#установка).

</details>

<details>
<summary><b>"python" открывает Microsoft Store (Windows)</b></summary>

Это значит Python не установлен. Скачайте его с [python.org/downloads](https://www.python.org/downloads/).

При установке **обязательно** поставьте галочку **"Add python.exe to PATH"**. Если забыли — удалите Python через "Установка и удаление программ", скачайте заново и на этот раз поставьте.

После установки **перезапустите PowerShell**.

</details>

<details>
<summary><b>"hh-apply" не является внутренней или внешней командой (Windows)</b></summary>

Python установил hh-apply в папку которую Windows не видит. Исправим за одну команду — **закройте PowerShell, откройте заново** и выполните:

```
pip install --force-reinstall git+https://github.com/nightmarovvv/hh-autoapply.git
```

После этого попробуйте снова:

```
hh-apply --version
```

Всё ещё не работает? Тогда используйте альтернативный запуск (работает всегда):

```
python -m hh_apply.cli --version
```

```
python -m hh_apply.cli init
```

```
python -m hh_apply.cli run
```

</details>

<details>
<summary><b>hh-apply: command not found (macOS / Linux)</b></summary>

pip установил программу в папку которая не в PATH. Выполните одну команду и всё заработает:

**macOS (zsh):**
```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc
```

**Linux (bash):**
```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc && source ~/.bashrc
```

Проверьте:
```bash
hh-apply --version
```

Всё ещё не работает? Используйте альтернативный запуск:

```bash
python3 -m hh_apply.cli --version
```

```bash
python3 -m hh_apply.cli init
```

```bash
python3 -m hh_apply.cli run
```

</details>

<details>
<summary><b>"git" не найден</b></summary>

Git нужен для установки. Установите:

**macOS:**
```bash
brew install git
```

**Windows:** скачайте с [git-scm.com](https://git-scm.com/download/win) и установите. Потом **перезапустите PowerShell**.

**Linux:**
```bash
sudo apt install git
```

</details>

<details>
<summary><b>Ошибка при установке Chromium</b></summary>

Если `patchright install chromium` выдаёт ошибку:

**Проверьте что patchright установлен:**
```bash
pip3 install patchright
```

**Повторите установку браузера:**
```bash
patchright install chromium
```

**На Linux нужны системные зависимости:**
```bash
patchright install-deps chromium
```

</details>

<details>
<summary><b>Капча при первом запуске</b></summary>

hh.ru иногда показывает капчу новым посетителям. hh-apply покажет её в терминале — введите текст и продолжайте. Если появляется слишком часто — подождите 10-15 минут и попробуйте снова.

</details>

<details>
<summary><b>"Не авторизован" при запуске</b></summary>

Куки hh.ru живут около 2 недель. Перелогиньтесь:

```bash
hh-apply login
```

</details>

<details>
<summary><b>Кракозябры / UnicodeDecodeError (Windows)</b></summary>

Терминал Windows не всегда поддерживает русские символы. Решения:

**Лучшее:** установите [Windows Terminal](https://apps.microsoft.com/detail/9n0dx20hk701) из Microsoft Store — он поддерживает UTF-8 из коробки.

**Быстрое:** выполните перед запуском:
```
chcp 65001
```

</details>

## Разработка

```bash
git clone https://github.com/nightmarovvv/hh-autoapply.git
```

```bash
cd hh-autoapply
```

```bash
python3 -m pip install -e ".[dev]"
```

```bash
python3 -m pytest tests/ -v
```

## Требования

- Python 3.9+
- Linux, macOS, Windows, WSL

## Лицензия

MIT
