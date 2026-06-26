# Orchestrate Skill + queue.csv Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Заменить старую очередь (`queue.json` + `scheduler.py` + launchd + скиллы `generate-queue`/`hypno-publish-pipeline`) одним ручным скиллом-оркестратором `/orchestrate`, который ведёт состояние в одной человекочитаемой `queue.csv` и вызывает уже существующие `/hypno-post-to-social` и `/publish-to-social`.

**Architecture:** Одна CSV-таблица (`id,url,status,post_path,generated_at,published_at`) — источник правды. Скилл `/orchestrate` читает её, для `pending` строк вызывает генератор и переименовывает файлы постов в `<id>`, для `generated` строк вызывает публикатор с путём, ведёт двойной дедуп (по `url` в CSV + по `published_at` в JSON) и пишет таблицу обратно. `publish-to-social` дорабатывается необязательным аргументом пути.

**Tech Stack:** Claude Code skills (Markdown `SKILL.md`), CSV (ручное Read/Write как текст), Python `publish.py`/`image_generator.py` (без изменений), Telegram/VK API.

**Важно про TDD/тесты:** в этом плане **нет новых исполняемых Python-модулей** — все изменения это Markdown-скиллы, CSV-данные и удаления файлов. Поэтому вместо pytest-юнит-тестов верификация — ручные end-to-end проверки (читаем файлы, запускаем скилл, смотрим результат), совпадающие с секцией «Тестирование» спеки. Коммит-шаги предполагают git-репозиторий (Task 1 его инициализирует).

**Спека:** `docs/superpowers/specs/2026-06-26-orchestrate-skill-design.md`

---

## File Structure

**Создать:**
- `queue.csv` — таблица-очередь (источник правды). Плоский CSV, редактируется руками и оркестратором.
- `.claude/skills/orchestrate/SKILL.md` — новый скилл-оркестратор.

**Изменить:**
- `.claude/skills/publish-to-social/SKILL.md` — добавить необязательный аргумент-путь и расширить `allowed-tools`.
- `CONTEXT.md` — переписать секции под новый источник правды (`queue.csv`) и список скиллов.
- `.gitignore` — добавить `queue.csv`? **НЕТ** — `queue.csv` это редактируемая пользователем таблица, она должна быть в git (трекается). Файл не добавляем в `.gitignore`.

**Удалить (после выгрузки launchd):**
- `queue.json`, `build_queue.py`, `scheduler.py`, `links.txt`, `README_QUEUE.md`
- `com.claud_mod_3_2.scheduler.plist`, `com.claud_mod_3_2.generator.plist`
- `.claude/skills/generate-queue/` (каталог)
- `.claude/skills/hypno-publish-pipeline/` (каталог)

---

### Task 1: Инициализировать git-репозиторий

**Files:**
- Create: `.git/` (через `git init`)

Чтобы работали коммит-шаги в последующих задачах и появился контроль версий.

- [ ] **Step 1: Инициализировать git**

```bash
cd /Users/irina/Desktop/claud_mod_3_2
git init
git add -A
git commit -m "chore: initial baseline before orchestrate-skill refactor"
```

- [ ] **Step 2: Проверить**

Run: `git log --oneline -1`
Expected: одна строка с хэшем и сообщением `chore: initial baseline before orchestrate-skill refactor`.

---

### Task 2: Создать `queue.csv` с заголовком и тестовыми строками

**Files:**
- Create: `/Users/irina/Desktop/claud_mod_3_2/queue.csv`

- [ ] **Step 1: Создать файл с заголовком и тремя строками**

Содержимое `queue.csv` (ровно так, без BOM, кодировка UTF-8):

```csv
id,url,status,post_path,generated_at,published_at
post-1,https://psy.education/novosti-proekta/news/?id=40,pending,,,
post-2,https://psy.su/feed/13163/,pending,,,
post-3,https://www.techinsider.ru/science/8558-pod-gipnozom-pravda-i-mify-o-gipnoze/,published,posts/2026-06-25-hypno-post-social.json,2026-06-25T22:00:00,2026-06-25T22:05:00
```

Пояснение по строкам:
- `post-1`, `post-2` — две новые `pending` ссылки для проверки генерации+публикации (неиспользованные тестовые URL из CONTEXT.md).
- `post-3` — уже `published`, ссылается на существующий опубликованный пост `posts/2026-06-25-hypno-post-social.json` (у него есть `published_at`). Нужна для проверки дедупа/пропуска.

- [ ] **Step 2: Проверить, что файл читается как таблица**

Run: `column -t -s, /Users/irina/Desktop/claud_mod_3_2/queue.csv` (или `cat`)
Expected: 4 строки (заголовок + 3 данных), 6 колонок, выравнивание по запятым. URL `?id=40` запятых не содержит → не ломает парсинг.

- [ ] **Step 3: Коммит**

```bash
cd /Users/irina/Desktop/claud_mod_3_2
git add queue.csv
git commit -m "feat: add queue.csv as the single source of truth for the post queue"
```

---

### Task 3: Доработать `publish-to-social` — аргумент-путь + `allowed-tools`

**Files:**
- Modify: `/Users/irina/Desktop/claud_mod_3_2/.claude/skills/publish-to-social/SKILL.md` (полная перезапись)

- [ ] **Step 1: Переписать `SKILL.md` новым содержимым**

Полное содержимое файла `.claude/skills/publish-to-social/SKILL.md`:

````markdown
---
name: publish-to-social
description: Публикует готовый JSON-пост (с изображением, если есть) в Telegram и ВКонтакте. Без аргументов — последний JSON в /posts; с путём — конкретный файл.
allowed-tools:
  - Read
  - Bash(python3 /Users/irina/Desktop/claud_mod_3_2/publish.py *)
---

# Publish to Social

Ты — публикатор контента. Твоя задача — опубликовать готовый пост в Telegram и ВКонтакте.

## Вход

- Без аргументов: берётся самый свежий JSON в `/Users/irina/Desktop/claud_mod_3_2/posts`.
- С аргументом-путём: публикуется указанный JSON-файл. Этот режим использует оркестратор `/orchestrate`.

## Что нужно сделать

1. Определи путь к JSON:
   - если путь передан как аргумент — используй его;
   - иначе найди последний JSON в `/posts` (самый свежий по mtime).
2. Проверь, что файл валиден и содержит `platforms.telegram.content` и `platforms.vk.content`. Если в JSON есть `image_path` и файл существует — публикация будет с картинкой.
3. Убедись, что в `.env` заданы `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID`, `VK_ACCESS_TOKEN`, `VK_GROUP_ID`.
4. Запусти публикацию:
   - путь передан → `python3 /Users/irina/Desktop/claud_mod_3_2/publish.py --post <путь>`;
   - путь не передан → `python3 /Users/irina/Desktop/claud_mod_3_2/publish.py`.
5. Если скрипт вернул ошибку — сообщи пользователю причину.
6. Если успешно — кратко сообщи, что пост (с картинкой, если была) опубликован в обеих соцсетях.

## Повторная публикация

Если JSON уже содержит `published_at`, не публикуй его повторно без явного запроса пользователя. `publish.py` тоже проверяет это и выходит без ошибки.

## Запреты

- Не публикуй без проверки содержимого.
- Не публикуй повторно без разрешения.
- Не сохраняй токены в код или в SKILL.md.
- Не публикуй, если токены не заданы в `.env`.
- Не читай и не пиши `queue.csv` — это задача оркестратора `/orchestrate`.
````

- [ ] **Step 2: Проверить содержимое**

Run: `head -20 /Users/irina/Desktop/claud_mod_3_2/.claude/skills/publish-to-social/SKILL.md`
Expected: frontmatter с `allowed-tools`, включающим `Bash(python3 .../publish.py *)`, и секция «Вход» с описанием аргумента-пути.

- [ ] **Step 3: Коммит**

```bash
cd /Users/irina/Desktop/claud_mod_3_2
git add .claude/skills/publish-to-social/SKILL.md
git commit -m "feat(publish-to-social): accept optional post path argument for orchestrator"
```

---

### Task 4: Создать скилл `/orchestrate`

**Files:**
- Create: `/Users/irina/Desktop/claud_mod_3_2/.claude/skills/orchestrate/SKILL.md`

- [ ] **Step 1: Создать каталог и файл `SKILL.md`**

```bash
mkdir -p /Users/irina/Desktop/claud_mod_3_2/.claude/skills/orchestrate
```

Полное содержимое `.claude/skills/orchestrate/SKILL.md`:

````markdown
---
name: orchestrate
description: Оркестратор: читает queue.csv, для новых pending-ссылок вызывает /hypno-post-to-social (генерация JSON+PNG) и публикует через /publish-to-social, ведёт статусы и двойной дедуп.
allowed-tools:
  - Read
  - Write(~/Desktop/claud_mod_3_2/queue.csv)
  - Write(~/Desktop/claud_mod_3_2/posts/**)
  - Bash(ls /Users/irina/Desktop/claud_mod_3_2/posts)
  - Bash(mv /Users/irina/Desktop/claud_mod_3_2/posts/* /Users/irina/Desktop/claud_mod_3_2/posts/*)
  - Bash(date +%F)
  - Bash(date +%FT%H:%M:%S)
  - Skill
  - WebFetch
---

# Orchestrate

Ты — оркестратор контент-завода по теме гипноза. Читаешь одну таблицу `queue.csv` и для каждой новой ссылки прогоняешь её через генерацию и публикацию, ведя статусы. Без расписания — публикуешь сразу, как появилась `pending`-ссылка и пользователь запустил `/orchestrate`.

## Таблица queue.csv

Путь: `/Users/irina/Desktop/claud_mod_3_2/queue.csv`. Формат (CSV, заголовок обязателен):

```
id,url,status,post_path,generated_at,published_at
```

Статусы: `pending` → `generated` → `published`; `failed` при сбое генерации. Промежуточный `generated` нужен, чтобы при сбое публикации следующий запуск доретраил только публикацию, не перегенерируя пост.

## Алгоритм

1. Прочитай `queue.csv` через Read. Если файл пуст или без заголовка `id,url,status,...` — сообщи об ошибке и остановись, НЕ затирая файл.
2. Разбери строки. Запомни множество URL строк со `status=published` — для дедупа по url.
3. Получи текущую дату для имён файлов: `Bash(date +%F)` → `YYYY-MM-DD`.
4. **Фаза генерации** — для каждой строки со `status=pending` по порядку `id`:
   a. Если `url` уже есть среди published-URL → пропусти (дедуп), в отчёт как «пропущен-дубль».
   b. Если `id` пуст — назначь `post-N`, где N — порядковый номер строки (1-based).
   c. Вызови скилл генерации: `Skill` с `skill="hypno-post-to-social"`, `args="<url>"`. Скилл сохранит `posts/YYYY-MM-DD-hypno-post-social.json` и, если генерация картинки удалась, `.png`.
   d. Переименуй файлы в уникальные с `<id>`:
      - `posts/YYYY-MM-DD-hypno-post-social.json` → `posts/YYYY-MM-DD-<id>-hypno-post-social.json`
      - `posts/YYYY-MM-DD-hypno-post-social.png` → `posts/YYYY-MM-DD-<id>-hypno-post-social.png` (только если PNG существует — проверь через `Bash(ls /Users/irina/Desktop/claud_mod_3_2/posts)`)
      Используй `Bash(mv ...)` — НЕ перезаписывай, если целевое имя уже занято.
   e. Обнови строку: `post_path=posts/YYYY-MM-DD-<id>-hypno-post-social.json`, `generated_at=<ISO now из date +%FT%H:%M:%S>`, `status=generated`.
   f. Если генерация или переименование упали — поставь `status=failed`, причину в отчёт, переходи к следующей строке.
5. **Фаза публикации** — для каждой строки со `status=generated` по порядку `id`:
   a. Прочитай JSON по `post_path` (Read). Если в нём уже есть `published_at` — поставь `status=published`, скопируй `published_at` в CSV, пропусти вызов публикатора.
   b. Иначе вызови скилл публикации: `Skill` с `skill="publish-to-social"`, `args="<post_path>"`. Скилл запустит `publish.py --post <post_path>`, опубликует в TG/VK и поставит `published_at` в JSON.
   c. После успеха: прочитай `published_at` из JSON (Read), поставь в CSV `status=published` и `published_at=<значение из JSON>`.
   d. Если публикация упала — оставь `status=generated` (ретрай следующим запуском), причину в отчёт.
6. Запиши `queue.csv` обратно через Write — полная перезапись таблицы, обязательно с заголовком первой строкой.
7. Напечатай отчёт:
   - сколько `pending` → `generated` → `published`;
   - сколько провалено (с причинами);
   - сколько пропущено как дубли / уже опубликованные.

## Правила

- Не пиши контент постов сам — это делает `/hypno-post-to-social`.
- Не лезь в API соцсетей сам — это делает `/publish-to-social` + `publish.py`.
- Не читай и не пиши `.env`.
- При записи CSV сохраняй заголовок и все строки; пустые поля — пустые (между запятыми ничего). URL запятых не содержит, экранирование не нужно.
- Если генерация картинки упала, но JSON сохранён — это НЕ ошибка: пост публикуется текстом.
- ISO-время: `YYYY-MM-DDTHH:MM:SS` (локальное), через `Bash(date +%FT%H:%M:%S)`. Для `published_at` бери значение из JSON-поста.
- Не перегенерируй уже `generated`/`published` строки.
````

- [ ] **Step 2: Проверить, что файл создан и фронтма́ттер валиден**

Run: `head -15 /Users/irina/Desktop/claud_mod_3_2/.claude/skills/orchestrate/SKILL.md`
Expected: frontmatter с `name: orchestrate` и `allowed-tools`, включающим `Skill`, `Write(~/Desktop/claud_mod_3_2/queue.csv)`, `Bash(mv ...)`.

- [ ] **Step 3: Коммит**

```bash
cd /Users/irina/Desktop/claud_mod_3_2
git add .claude/skills/orchestrate/SKILL.md
git commit -m "feat: add /orchestrate skill — CSV-driven generate+publish orchestrator"
```

---

### Task 5: Выгрузить launchd и удалить старые файлы

**Files:**
- Delete: `queue.json`, `build_queue.py`, `scheduler.py`, `links.txt`, `README_QUEUE.md`, `com.claud_mod_3_2.scheduler.plist`, `com.claud_mod_3_2.generator.plist`, `.claude/skills/generate-queue/`, `.claude/skills/hypno-publish-pipeline/`

**Важно:** launchd-задания `com.claud_mod_3_2.scheduler` и `com.claud_mod_3_2.generator` сейчас загружены (и падают с кодом 2, т.к. ссылаются на `scheduler.py`) и установлены в `~/Library/LaunchAgents/`. Сначала выгрузить и убрать оттуда — иначе launchd будет сыпать ошибки об отсутствующем файле.

- [ ] **Step 1: Выгрузить launchd-задания**

```bash
launchctl unload ~/Library/LaunchAgents/com.claud_mod_3_2.scheduler.plist 2>/dev/null || true
launchctl unload ~/Library/LaunchAgents/com.claud_mod_3_2.generator.plist 2>/dev/null || true
launchctl remove com.claud_mod_3_2.scheduler 2>/dev/null || true
launchctl remove com.claud_mod_3_2.generator 2>/dev/null || true
```

- [ ] **Step 2: Убрать plist'ы из LaunchAgents**

```bash
rm -f ~/Library/LaunchAgents/com.claud_mod_3_2.scheduler.plist
rm -f ~/Library/LaunchAgents/com.claud_mod_3_2.generator.plist
```

- [ ] **Step 3: Проверить, что launchd больше не держит задания**

Run: `launchctl list | grep -i claud_mod || echo "none loaded"`
Expected: `none loaded`.

- [ ] **Step 4: Удалить старые файлы и скиллы из проекта**

```bash
cd /Users/irina/Desktop/claud_mod_3_2
rm -f queue.json build_queue.py scheduler.py links.txt README_QUEUE.md
rm -f com.claud_mod_3_2.scheduler.plist com.claud_mod_3_2.generator.plist
rm -rf .claude/skills/generate-queue .claude/skills/hypno-publish-pipeline
```

- [ ] **Step 5: Проверить, что удалилось, а нужное осталось**

Run:
```bash
cd /Users/irina/Desktop/claud_mod_3_2
ls .claude/skills/
echo "---"
ls queue.csv publish.py image_generator.py 2>&1
```
Expected: в `.claude/skills/` остались `orchestrate`, `hypno-post-to-social`, `publish-to-social` (плюс возможно `.DS_Store`); `queue.csv`, `publish.py`, `image_generator.py` существуют.

- [ ] **Step 6: Коммит**

```bash
cd /Users/irina/Desktop/claud_mod_3_2
git add -A
git commit -m "refactor: remove old queue.json/scheduler/launchd and generate-queue/pipeline skills"
```

---

### Task 6: Обновить `CONTEXT.md`

**Files:**
- Modify: `/Users/irina/Desktop/claud_mod_3_2/CONTEXT.md`

Структура проекта и список скиллов в CONTEXT.md устарели — нужно привести в соответствие новому виду.

- [ ] **Step 1: Обновить секцию «Структура проекта»**

В блоке дерева (строки ~7–33) заменить содержимое на:

````
claud_mod_3_2/
├── .claude/
│   └── skills/
│       ├── hypno-post-to-social/    # Скилл генерации поста + картинка из одной ссылки
│       │   └── SKILL.md
│       ├── publish-to-social/       # Скилл публикации JSON (+необязательный путь)
│       │   └── SKILL.md
│       └── orchestrate/             # Скилл-оркестратор: читает queue.csv, генерит + публикует
│           └── SKILL.md
├── posts/                           # Сюда сохраняются JSON-посты и PNG
├── queue.csv                        # Единая таблица-очередь (источник правды)
├── publish.py                       # Публикация в Telegram и VK (поддерживает --post <path>)
├── image_generator.py               # Генерация PNG через Qwen/DashScope
├── vk_token_refresh.py              # Обновление VK access_token
├── vk_pkce_helper.py                # PKCE-параметры для первой VK ID авторизации
├── vk_exchange_code.py              # Обмен authorization code на access/refresh token
├── .env.example                     # Шаблон для токенов
├── .gitignore                       # Исключает .env, JSON/PNG-посты, логи
└── CONTEXT.md                       # Этот файл
````

- [ ] **Step 2: Обновить секцию «Скиллы Claude Code»**

Заменить описание трёх скиллов (был `hypno-publish-pipeline` и `generate-queue`) на актуальные три:

````
### 1. hypno-post-to-social
- Принимает на вход одну статью, ссылку или описание по теме гипноза.
- Генерирует `source`, `image_prompt`, `platforms.telegram.content`, `platforms.vk.content`.
- Пытается сгенерировать PNG через `image_generator.py`, добавляет `image_path`.
- Сохраняет JSON в `/posts/YYYY-MM-DD-hypno-post-social.json`. Не публикует.

### 2. publish-to-social
- Без аргументов: публикует последний JSON в `/posts`.
- С аргументом-путём: публикует конкретный JSON (используется оркестратором).
- Читает токены из `.env`, запускает `publish.py [--post <path>]`.
- Не публикует повторно, если в JSON есть `published_at`.

### 3. orchestrate
- Читает `queue.csv` (единственный источник правды).
- Для строк `pending`: вызывает `/hypno-post-to-social`, переименовывает файлы в `posts/YYYY-MM-DD-<id>-hypno-post-social.{json,png}`, ставит `status=generated`.
- Для строк `generated`: вызывает `/publish-to-social <post_path>`, ставит `status=published`.
- Двойной дедуп: по `url` в CSV + по `published_at` в JSON. При сбое публикации оставляет `generated` для ретрая.
````

- [ ] **Step 3: Обновить секцию про очередь/`queue.json`/`scheduler.py`**

Удалить/заменить упоминания `queue.json`, `build_queue.py`, `scheduler.py`, launchd, `links.txt`, `README_QUEUE.md`. Добавить краткую секцию:

````
## Очередь queue.csv
Единая CSV-таблица: `id,url,status,post_path,generated_at,published_at`.
Статусы: `pending` → `generated` → `published` (`failed` при сбое).
Пользователь дописывает строку с `url` и `status=pending`, затем запускает `/orchestrate`.
Ручной режим: работает, пока открыт Claude. Расписания/launchd нет.
````

- [ ] **Step 4: Обновить «Что уже сделано» / «Что нужно сделать дальше»**

Добавить в «Что уже сделано» пункт:
- `[x] Внедрён скилл-оркестратор /orchestrate + queue.csv; удалены queue.json, scheduler.py, launchd, generate-queue, hypno-publish-pipeline.`

- [ ] **Step 5: Коммит**

```bash
cd /Users/irina/Desktop/claud_mod_3_2
git add CONTEXT.md
git commit -m "docs: update CONTEXT.md for orchestrate-skill + queue.csv architecture"
```

---

### Task 7: End-to-end проверка

**Files:** (без изменений — это ручной запуск)

**Внимание:** этот шаг **публикует в реальные каналы Telegram и VK** (так делали и раньше). Убедись, что `.env` указывает на нужные каналы, или будь готов к реальным постам. Перед запуском — перезапусти Claude Code, чтобы новый скилл `/orchestrate` и изменения `publish-to-social` подхватились.

- [ ] **Step 1: Перезапустить Claude Code и открыть проект**

```bash
cd /Users/irina/Desktop/claud_mod_3_2
ollama launch claude   # выбрать облачную модель; либо: claude --permission-mode acceptEdits
```
Убедиться, что режим `accept edits on` включён (`Shift+Tab`).

- [ ] **Step 2: Запустить оркестратор**

В Claude Code ввести:
```text
/orchestrate
```

- [ ] **Step 3: Проверить результат**

Ожидания (согласно seed `queue.csv` из Task 2):
- `post-1` и `post-2`: `pending` → `generated` → `published`. В `/posts` появились `2026-06-26-post-1-hypno-post-social.json/.png` и `2026-06-26-post-2-hypno-post-social.json/.png`. Посты ушли в TG и VK.
- `post-3`: уже `published` → пропущен (дедуп).
- `queue.csv` перезаписан корректно: заголовок на месте, у `post-1`/`post-2` заполнены `post_path`, `generated_at`, `published_at`, `status=published`; `post-3` unchanged.

Проверить командой:
```bash
cd /Users/irina/Desktop/claud_mod_3_2
column -t -s, queue.csv
ls posts/2026-06-26-post-*-hypno-post-social.*
```
Expected: 3 строки в таблице все `published`; 4 файла постов (2 json + 2 png) с `post-1`/`post-2` в имени.

- [ ] **Step 4: Негативный кейс — ретрай публикации при сбое (опционально)**

1. В `queue.csv` добавить новую `pending` строку `post-4,<url>,,,,` и запустить `/orchestrate` — она дойдёт до `generated` (JSON+PNG созданы).
2. Временно испортить токен в `.env` (например, дописать `X` в `VK_ACCESS_TOKEN`).
3. Снова `/orchestrate`: публикация `post-4` падает → строка остаётся `generated`, отчёт содержит причину.
4. Вернуть корректный токен, снова `/orchestrate`: `post-4` → `published` без перегенерации (файл поста не пересоздаётся).

- [ ] **Step 5: Дедуп по URL (опционально)**

Добавить в `queue.csv` строку `post-5,<тот же URL что у post-3>,pending,,,,` и запустить `/orchestrate`.
Expected: `post-5` пропущен как дубль уже опубликованного URL.

- [ ] **Step 6: Финальный коммит (если состояние таблицы/постов хочется зафиксировать)**

```bash
cd /Users/irina/Desktop/claud_mod_3_2
git add queue.csv
git commit -m "test: end-to-end verification of /orchestrate" || echo "nothing to commit"
```
Примечание: `posts/*.json` и `posts/*.png` исключены из git через `.gitignore`, поэтому сами посты не коммитятся — это нормально.

---

## Self-Review (выполнен автором плана)

**Spec coverage:**
- Одна `queue.csv` схема → Task 2. ✅
- Скилл `/orchestrate` (фазы generate/publish, переименование в `<id>`, двойной дедуп, статусы, отчёт) → Task 4. ✅
- Доработка `publish-to-social` (+путь, `allowed-tools` с `*`) → Task 3. ✅
- Удаление старого + выгрузка launchd → Task 5. ✅
- Обновление CONTEXT.md → Task 6. ✅
- Тест-кейсы спеки (2 pending + 1 published, ретрай публикации, дедуп URL) → Task 7. ✅

**Placeholder scan:** плейсхолдеров/TBD нет; все Markdown-содержимое скиллов и CSV приведено полностью.

**Type/имя consistency:** `queue.csv` колонки `id,url,status,post_path,generated_at,published_at` едины во всём плане; статусы `pending|generated|published|failed` едины; имя файла поста `YYYY-MM-DD-<id>-hypno-post-social.json` едино; `publish.py --post <path>` едино.