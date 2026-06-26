# Отчёт по проекту «Claud Mod 3.2 — Контент-завод» (версия 2: оркестратор + queue.csv)

## 1. Цель проекта

Создать систему для генерации и публикации постов по теме гипноза в Telegram и ВКонтакте
по одной человекочитаемой таблице-очереди. Пользователь кладёт новую ссылку в таблицу,
запускает один скилл-оркестратор — и получает сгенерированный пост с картинкой, опубликованный
в обеих соцсетях, с автоматической защитой от дублей.

Режим ручной: работает, пока открыт Claude Code. Расписания, launchd и headless-вызовы
не используются — это сознательное упрощение, согласованное в ходе проектирования.

## 2. Архитектура (кто что делает)

Система состоит из трёх скиллов Claude Code, одного скрипта публикации, одного генератора
картинок и одной CSV-таблицы. Каждый компонент имеет одну зону ответственности и общается
с другими через простые интерфейсы (CSV-строка ↔ путь к JSON-файлу ↔ поле `published_at`).

```
                ┌──────────────┐
                │  queue.csv   │  ← пользователь дописывает строку: id,url,pending,,,
                │ (источник    │     редактируется руками + оркестратором
                │  правды)     │
                └──────┬───────┘
                       │ читает/пишет
                       ▼
            ┌────────────────────┐
            │  /orchestrate       │  оркестратор: ведёт статусы, дедуп, переименование
            └───┬─────────────┬───┘
   pending →    │             │  ← generated →
                ▼             ▼
   ┌──────────────────┐   ┌──────────────────────┐
   │ /hypno-post-     │   │ /publish-to-social   │
   │  to-social       │   │  (с путём к JSON)    │
   │ генерация поста  │   │  публикация в TG/VK │
   │ + PNG (Qwen)     │   │  через publish.py    │
   └────────┬─────────┘   └──────────┬───────────┘
            │ сохраняет                │ запускает
            ▼                          ▼
        posts/*.json + *.png      python3 publish.py --post <path>
                                   → Telegram + VK API, ставит published_at
```

### Принцип изоляции

| Компонент | Делает | НЕ делает |
|---|---|---|
| `queue.csv` | хранит ссылки и статусы | не хранит контент постов |
| `/orchestrate` | читает/пишет CSV, вызывает скиллы, переименовывает файлы, ведёт статусы и дедуп | не пишет текст постов, не лезет в API соцсетей |
| `/hypno-post-to-social` | генерирует текст поста (TG+VK), промпт картинки, сохраняет JSON+PNG | не знает про CSV, не публикует |
| `/publish-to-social` | публикует конкретный JSON (или последний) в TG/VK, проверяет `published_at` | не пишет CSV |
| `publish.py` | отправляет в Telegram/VK API, ставит `published_at` в JSON, автообновляет VK-токен | не трогает CSV |
| `image_generator.py` | генерит PNG через Qwen/DashScope по `image_prompt` из JSON | — |

## 3. Скиллы — подробное описание «кто что делает»

### 3.1. `hypno-post-to-social` — генератор (одна ссылка → пост)

- **Вход:** одна ссылка на статью / текст / описание по теме гипноза.
- **Что делает:**
  1. Читает статью через `WebFetch`.
  2. Пишет пост для Telegram (700–1400 знаков, без хэштегов) и для ВКонтакте (600–1300 знаков, 3–7 хэштегов в конце).
  3. Составляет `image_prompt` под **конкретную сцену из статьи** (не шаблон «человек со спиралью»).
  4. Сохраняет JSON в `posts/YYYY-MM-DD-hypno-post-social.json` (дата — сегодняшняя).
  5. Запускает `image_generator.py` → рядом появляется PNG, в JSON прописывается `image_path`.
- **Не публикует.** Если картинка не сгенерилась — JSON сохраняется без `image_path`, текст потом публикуется без картинки.
- Стиль: ясно, без мистики, псевдонауки и воды; факты только из источника.

### 3.2. `publish-to-social` — публикатор (JSON → Telegram + VK)

- **Вход:** без аргументов — последний JSON в `/posts`; **с аргументом-путём** — конкретный файл (этот режим использует оркестратор).
- **Что делает:**
  1. Определяет путь к JSON (аргумент или последний по mtime).
  2. Проверяет наличие `platforms.telegram.content` и `platforms.vk.content`, токенов в `.env`.
  3. Запускает `python3 publish.py --post <путь>` (или без `--post` для последнего).
  4. Сообщает результат; если в JSON уже есть `published_at` — не публикует повторно.
- **Не читает и не пишет `queue.csv`** — это задача оркестратора.

### 3.3. `orchestrate` — оркестратор (таблица → генерация → публикация)

- **Вход:** без аргументов. Всегда читает `queue.csv`.
- **Что делает за один запуск:**
  1. Читает `queue.csv`; запоминает URL уже опубликованных строк (для дедупа).
  2. **Фаза генерации** — для каждой строки `pending`:
     - пропускает дубли URL;
     - вызывает `/hypno-post-to-social <url>`;
     - переименовывает `posts/YYYY-MM-DD-hypno-post-social.{json,png}` → `posts/YYYY-MM-DD-<id>-hypno-post-social.{json,png}`;
     - **обновляет `image_path` внутри JSON** на переименованный PNG (иначе публикация уйдёт без картинки);
     - ставит в CSV `status=generated`, `post_path`, `generated_at`; при сбое — `status=failed`.
  3. **Фаза публикации** — для каждой строки `generated`:
     - если в JSON уже есть `published_at` → сразу `status=published`;
     - иначе вызывает `/publish-to-social <post_path>`, после успеха берёт `published_at` из JSON и ставит `status=published`;
     - при сбое публикации оставляет `status=generated` (ретрай следующим запуском, без перегенерации).
  4. Перезаписывает `queue.csv` и печатает отчёт: сколько сгенерировано/опубликовано/провалено/пропущено.
- **Двойной дедуп:** по `url` в CSV + по `published_at` в JSON.

## 4. Таблица `queue.csv` (источник правды)

Формат — плоский CSV:

```
id,url,status,post_path,generated_at,published_at
post-1,https://psy.education/novosti-proekta/news/?id=40,pending,,,
post-2,https://psy.su/feed/13163/,published,posts/2026-06-26-post-2-hypno-post-social.json,2026-06-26T19:17:48,2026-06-26T19:18:56
```

- `id` — стабильный идентификатор, используется в имени файла поста.
- `url` — ссылка на статью.
- `status` — `pending` → `generated` → `published`; `failed` при сбое генерации.
- `post_path` — путь к JSON-посту (заполняется на этапе `generated`).
- `generated_at` — время завершения генерации.
- `published_at` — время публикации (дублирует значение из JSON-поста; источник правды для дедупа — `published_at` в самом JSON).

Промежуточный `generated` нужен, чтобы при сбое публикации (например, протух токен VK)
следующий `/orchestrate` доретраил только публикацию, не перегенерируя пост.

## 5. Как пользоваться (пошаговая инструкция)

### Шаг 1. Подготовить `.env` (один раз)

Создать `.env` рядом с `.env.example` и заполнить реальными значениями:

```bash
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHANNEL_ID=@your_channel_or_numeric_id
VK_ACCESS_TOKEN=...
VK_GROUP_ID=...
VK_REFRESH_TOKEN=...   # опционально, для автообновления VK-токена
VK_CLIENT_ID=...        # нужно для refresh_token
VK_DEVICE_ID=...       # нужно для refresh_token
QWEN_API_KEY=...
BASE_URL=https://dashscope-intl.aliyuncs.com
IMAGE_MODEL=wan2.6-t2i
```

> Скиллы никогда не читают и не пишут `.env`. Файл исключён из git через `.gitignore`.

### Шаг 2. Открыть проект и включить auto-approve

```bash
cd /Users/irina/Desktop/claud_mod_3_2
ollama launch claude      # выбрать облачную модель
```
Включить режим `accept edits on` (несколько раз `Shift+Tab`, пока не появится).
Это нужно, чтобы скиллы работали в один проход без подтверждений на каждый инструмент.

### Шаг 3. Положить новую ссылку в `queue.csv`

Дописать строку (остальные поля пустыми):

```csv
post-4,https://example.com/article,pending,,,
```

### Шаг 4. Запустить оркестратор

В Claude Code ввести:

```text
/orchestrate
```

Оркестратор:
- найдёт строку `pending`,
- сгенерирует пост + картинку (`/hypno-post-to-social`),
- опубликует в Telegram и VK (`/publish-to-social`),
- поставит в `queue.csv` `status=published` и заполнит `post_path`, `generated_at`, `published_at`.

### Шаг 5. Проверить результат

```bash
cd /Users/irina/Desktop/claud_mod_3_2
column -t -s, queue.csv        # таблица: статус должен стать published
ls posts/                      # рядом с JSON лежит PNG с тем же именем
```

Посты появятся в Telegram-канале и группе ВКонтакте.

### Ретрай при сбое публикации

Если публикация упала (например, протух токен):
- строка в `queue.csv` останется `generated`;
- починить токен в `.env`;
- снова запустить `/orchestrate` — он доретраит только публикацию, не перегенерируя пост.

## 6. Где лежат файлы

```
/Users/irina/Desktop/claud_mod_3_2/
├── .claude/skills/
│   ├── hypno-post-to-social/SKILL.md   # генератор поста
│   ├── publish-to-social/SKILL.md      # публикатор (+аргумент-путь)
│   └── orchestrate/SKILL.md            # оркестратор
├── posts/                              # JSON-посты и PNG (не в git)
├── queue.csv                           # таблица-очередь (источник правды)
├── publish.py                          # публикация в TG/VK (--post <path>)
├── image_generator.py                  # генерация PNG (Qwen/DashScope)
├── vk_token_refresh.py                 # обновление VK access_token
├── vk_pkce_helper.py                   # PKCE для первой VK ID авторизации
├── vk_exchange_code.py                 # обмен code на access/refresh token
├── .env / .env.example                 # токены / шаблон
├── .gitignore                          # исключает .env, posts/*, логи
├── CONTEXT.md                          # технический контекст проекта
├── HOMEWORK_REPORT.md                  # этот отчёт
└── screenshots/                        # скриншоты для сдачи
```

## 7. Жизненный цикл строки в `queue.csv`

```
pending  --/hypno-post-to-social OK-->  generated  --/publish-to-social OK-->  published
pending  --генерация упала------------>  failed
generated --публикация упала---------->  generated   (ретрай следующим /orchestrate)
```

## 8. Что реализовано (компоненты)

| № | Компонент | Описание |
|---|---|---|
| 1 | `orchestrate` | Скилл-оркестратор: читает `queue.csv`, генерит + публикует, ведёт статусы и двойной дедуп. |
| 2 | `hypno-post-to-social` | Скилл генерации: статья → JSON-пост (TG+VK) + промпт картинки + PNG. |
| 3 | `publish-to-social` | Скилл публикации: конкретный JSON (или последний) → Telegram + VK. |
| 4 | `publish.py` | Python-скрипт публикации в Telegram и VK, поддерживает `--post <path>`, ставит `published_at`, автообновляет VK-токен. |
| 5 | `image_generator.py` | Генерация PNG через Qwen/DashScope (`wan2.6-t2i`). |
| 6 | `vk_token_refresh.py` | Обновление VK access_token через refresh_token. |
| 7 | `vk_pkce_helper.py` / `vk_exchange_code.py` | Помощники для первой VK ID OAuth 2.1 авторизации. |
| 8 | `queue.csv` | Единая таблица-очередь: `id,url,status,post_path,generated_at,published_at`. |
| 9 | `.env.example` + `.env` | Хранение токенов и ключей API (`.env` не в git). |
| 10 | git-репозиторий | Контроль версий; посты и `.env` исключены через `.gitignore`. |

## 9. Что было удалено по сравнению с версией 1

Раньше использовалась очередь на `queue.json` + планировщик `scheduler.py` + launchd-задания
+ скиллы `generate-queue` и `hypno-publish-pipeline`. В версии 2 это всё удалено как избыточное
для ручного режима: `queue.json`, `build_queue.py`, `scheduler.py`, launchd-plist'ы
(`com.claud_mod_3_2.scheduler.plist`, `com.claud_mod_3_2.generator.plist`), `links.txt`,
`README_QUEUE.md`, скиллы `generate-queue` и `hypno-publish-pipeline`. launchd-задания
выгружены из системы до удаления файлов.

## 10. Скриншоты

Скриншоты для проверки лежат в папке `screenshots/` и пронумерованы:

| № | Имя файла | Что показывает |
|---|---|---|
| 1 | `01-project-folder.png` | Структура проекта (новая: `queue.csv`, три скилла, без scheduler/launchd) |
| 2 | `02-env-file.png` | Заполненный `.env` (токены замазаны) |
| 3 | `03-queue-csv.png` | Содержимое `queue.csv` (строки pending/published) |
| 4 | `04-skills-folder.png` | Скиллы Claude Code: `hypno-post-to-social`, `publish-to-social`, `orchestrate` |
| 5 | `05-orchestrate-run.png` | Запуск `/orchestrate` |
| 6 | `06-generated-posts.png` | Сгенерированные JSON + PNG в `posts/` с `<id>` в имени |
| 7 | `07-queue-csv-updated.png` | `queue.csv` после прогона: статусы `published` |
| 8 | `08-telegram-post.png` | Опубликованный пост в Telegram |
| 9 | `09-vk-post.png` | Опубликованный пост в ВКонтакте |

> Положи свои скриншоты в `screenshots/` с именами из таблицы — тогда отчёт будет актуальным.

## 11. Проверочный прогон (2026-06-26)

End-to-end тест выполнен на реальных каналах:

| ID | URL | Результат |
|---|---|---|
| `post-1` | https://psy.education/novosti-proekta/news/?id=40 | сгенерирован JSON+PNG → опубликован в TG и VK |
| `post-2` | https://psy.su/feed/13163/ | сгенерирован JSON+PNG → опубликован в TG и VK |
| `post-3` | https://www.techinsider.ru/science/8558-pod-gipnozom-pravda-i-mify-o-gipnoze/ | уже `published` → пропущен (дедуп) |

Все три строки в `queue.csv` — `published`. Посты с картинками ушли в Telegram-канал и группу ВКонтакте.

Во время прогона найден и исправлен баг: шаг переименования файлов в `<id>` не обновлял
`image_path` внутри JSON — публикация уходила бы без картинки. Скилл `orchestrate` дополнен
шагом обновления `image_path` (коммит `3658b6f`).

## 12. Источники

- [Teleport — автопостинг](https://teleport.ru)
- [Neironica — AI + автопостинг](https://neironica.ru/autoposting.php)
- [VK Постинг](https://vk-posting.ru)
- [SMMplanner](https://smmplanner.com)
- [SmmBox](https://smmbox.com)
- [Spark.ru — автопостинг в Telegram и VK](https://spark.ru/user/65400/blog/262653/avtoposting-v-telegram-i-vk-nastrojka-za-15-minut-bez-programmista)