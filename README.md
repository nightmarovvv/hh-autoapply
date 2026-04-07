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

### Шаг 2. Создайте папку и виртуальное окружение

Виртуальное окружение — это изолированная песочница. Все команды (`hh-apply`, `patchright`) будут работать внутри неё без проблем с PATH.

**macOS / Linux:**

```bash
mkdir ~/hh-apply && cd ~/hh-apply
```

```bash
python3 -m venv .venv
```

```bash
source .venv/bin/activate
```

**Windows:**

```
mkdir %USERPROFILE%\hh-apply && cd %USERPROFILE%\hh-apply
```

```
python -m venv .venv
```

```
.venv\Scripts\activate
```

> После активации в начале строки терминала появится `(.venv)` — это значит окружение включено.

---

### Шаг 3. Установите hh-apply

```bash
pip install git+https://github.com/nightmarovvv/hh-autoapply.git
```

> Побегут строки — это скачивание. Дождитесь `Successfully installed`.

<details>
<summary><b>Если пишет pip: command not found</b></summary>

macOS / Linux:
```bash
python3 -m pip install git+https://github.com/nightmarovvv/hh-autoapply.git
```

Windows:
```
python -m pip install git+https://github.com/nightmarovvv/hh-autoapply.git
```

Если и это не работает — pip не установлен:
```bash
python3 -m ensurepip --upgrade
```
И повторите установку.

</details>

---

### Шаг 4. Скачайте браузер

hh-apply работает через скрытый браузер Chromium. Скачайте его один раз:

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

---

### Как запускать в следующий раз

Каждый раз когда хотите запустить hh-apply — сначала активируйте окружение:

**macOS / Linux:**
```bash
cd ~/hh-apply && source .venv/bin/activate
```

**Windows:**
```
cd %USERPROFILE%\hh-apply && .venv\Scripts\activate
```

После этого `hh-apply` работает как обычно.

---

### Обновление до последней версии

Активируйте окружение (см. выше), затем:

```bash
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
<summary><b>"python" / "python3" не найден</b></summary>

**macOS / Linux:** команда называется `python3`, не `python`:
```bash
python3 --version
```

**Windows:** если `python` открывает Microsoft Store — Python не установлен. Скачайте с [python.org/downloads](https://www.python.org/downloads/). При установке **обязательно поставьте галочку "Add python.exe to PATH"**. Потом **перезапустите PowerShell**.

Если забыли галочку — удалите Python через **Параметры → Приложения**, скачайте заново и поставьте.

</details>

<details>
<summary><b>"hh-apply" не найдена / не является командой</b></summary>

Скорее всего вы не активировали виртуальное окружение. Перед запуском выполните:

**macOS / Linux:**
```bash
cd ~/hh-apply && source .venv/bin/activate
```

**Windows:**
```
cd %USERPROFILE%\hh-apply && .venv\Scripts\activate
```

В начале строки должно появиться `(.venv)`. После этого `hh-apply` будет работать.

Если папки `~/hh-apply` нет — вернитесь к [Шагу 2 установки](#шаг-2-создайте-папку-и-виртуальное-окружение).

</details>

<details>
<summary><b>Бесконечная загрузка при логине</b></summary>

Если после ввода номера телефона страница зависает и не переходит к вводу кода — обновите hh-apply:

```bash
pip install --upgrade git+https://github.com/nightmarovvv/hh-autoapply.git
```

В новой версии логин использует антидетект-браузер, который не блокируется hh.ru.

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

Установите [Windows Terminal](https://apps.microsoft.com/detail/9n0dx20hk701) из Microsoft Store — он поддерживает русские символы из коробки.

Или выполните перед запуском:
```
chcp 65001
```

</details>

<details>
<summary><b>Ошибка при установке Chromium на Linux</b></summary>

Нужны системные зависимости:
```bash
patchright install-deps chromium
```

Затем повторите:
```bash
patchright install chromium
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
