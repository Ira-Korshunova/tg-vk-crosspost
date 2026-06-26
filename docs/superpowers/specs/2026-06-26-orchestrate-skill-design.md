# Дизайн: скилл-оркестратор `/orchestrate` + таблица `queue.csv`

**Дата:** 2026-06-26
**Проект:** Claud Mod 3.2 — контент-завод для соцсетей (гипноз → Telegram + VK)
**Статус:** согласован с пользователем, готов к плану реализации

## Цель

Автоматизировать цепочку «новая ссылка → сгенерированный пост → публикация» через один
ручной скилл `/orchestrate`, который вызывает уже существующие скиллы генерации и публикации
и ведёт состояние в одной человекочитаемой CSV-таблице. Без расписания (launchd/cron),
без headless-Claude: публикуем сразу, как только в таблице появилась новая `pending`-ссылка
и пользователь запустил `/orchestrate`.

## Контекст и мотивация

В проекте уже есть скиллы `hypno-post-to-social` (генерация JSON+PNG из ссылки) и
`publish-to-social` (публикация в TG/VK), а также скрипты `publish.py`, `image_generator.py`.
Прежняя очередь на `queue.json` + `scheduler.py` (launchd) + `build_queue.py` + скиллы
`generate-queue` и `hypno-publish-pipeline` оказалась избыточной для ручного режима и
слабо связала паблишер с конкретным постом: `publish-to-social` публикует «последний JSON
в `/posts`», что при нескольких постах в очереди публикует не тот файл.

Пересмотренные решения пользователя:
1. **Ручной скилл** `/orchestrate` (не launchd, не headless). Работает, пока открыт Claude.
2. **Публикация по появлению новой ссылки**, без `generate_at`/`publish_at`.
3. **Доработать `publish-to-social`** необязательным аргументом пути (не переписывать
   оркестратор напрямую через `publish.py`).
4. **Одна `queue.csv`** = список ссылок + стейт-машина (вместо `queue.json` + `links.txt`).
5. **Удалить старое**: `queue.json`, `build_queue.py`, `scheduler.py`, launchd-плагины
   `com.claud_mod_3_2.scheduler.plist` и `com.claud_mod_3_2.generator.plist`, скиллы
   `generate-queue` и `hypno-publish-pipeline`, файл `links.txt`, `README_QUEUE.md`.

## Архитектура

### Компоненты и зоны ответственности

| Компонент | Роль | Что делает | Чего не делает |
|---|---|---|---|
| `queue.csv` | источник правды | хранит ссылки и статусы; редактируется руками и оркестратором | не хранит контент постов |
| `/orchestrate` (новый скилл) | оркестратор | читает/пишет `queue.csv`, вызывает скиллы генерации и публикации, переименовывает файлы постов, ведёт статусы | не пишет текст постов, не лезет в API соцсетей |
| `/hypno-post-to-social` | генератор (не меняем) | по URL генерит JSON+PNG в `/posts` | не знает про CSV |
| `/publish-to-social` (дорабатываем) | публикатор | публикует конкретный JSON (`--post <path>`) или последний; ставит `published_at` в JSON | не пишет CSV |
| `publish.py` (не меняем) | публикация в TG/VK | уже умеет `--post <path>` и `published_at` | — |
| `image_generator.py` (не меняем) | PNG через Qwen | вызывается внутри генерации | — |

Принцип изоляции: каждый компонент имеет одну ответственность и общается через
well-defined интерфейсы (CSV-строка ↔ путь к JSON ↔ `published_at` в JSON). Внутренности
любого блока можно менять без ломания потребителей.

### Таблица `queue.csv`

Схема (плоская, без вложенности, безопасна для прямого Read/Write как текст — ни в одном
поле нет запятых):

```
id,url,status,post_path,generated_at,published_at
```

- `id` — стабильный идентификатор строки, используется в имени файла поста
  (`posts/YYYY-MM-DD-<id>-hypno-post-social.json`). Формат: `post-N`, где N — порядковый
  номер при добавлении (оркестратор назначает для новых строк без `id`, либо сохраняет
  введённый пользователем).
- `url` — ссылка на статью.
- `status` — `pending` | `generated` | `published` | `failed`.
- `post_path` — путь к JSON-посту (заполняется на этапе `generated`).
- `generated_at` — ISO-время завершения генерации.
- `published_at` — ISO-время публикации (дублирует значение из JSON-поста для удобства
  чтения таблицы; источник правды для дедупа — `published_at` в самом JSON).

**Жизненный цикл строки:**
```
pending  --генерация OK-->  generated  --публикация OK-->  published
pending  --генерация fail-> failed
generated --публикация fail-> generated   (ретрай следующим запуском)
```

Промежуточный `generated` нужен, чтобы при сбое публикации (например, протух токен VK)
следующий `/orchestrate` доретраил только публикацию, не перегенерируя пост.

**Ручное редактирование:** пользователь дописывает строку вида
`post-3,https://example.com/article,pending,,,` (остальные поля пустые) и запускает
`/orchestrate`. Конкуренции нет: скилл запускается по запросу, не параллельно с ручным
редактированием.

### Скилл `/orchestrate`

**Вход:** без аргументов. Всегда читает `/Users/irina/Desktop/claud_mod_3_2/queue.csv`.

**Алгоритм:**
1. Прочитать `queue.csv` (Read).
2. Для каждой строки со `status=pending` (порядок по `id`):
   a. Если `url` уже встречается в другой строке со `status=published` — пропустить как дубль
      (дедуп по url).
   b. Вызвать `/hypno-post-to-social <url>` (через Skill tool). Скилл сохранит
      `posts/YYYY-MM-DD-hypno-post-social.json` и сгенерит PNG.
   c. Переименовать `posts/YYYY-MM-DD-hypno-post-social.{json,png}` →
      `posts/YYYY-MM-DD-<id>-hypno-post-social.{json,png}` (PNG — только если существует),
      через `Bash(mv ...)`, чтобы не перезаписать чужие файлы.
   d. Заполнить строку: `post_path`, `generated_at` = now, `status=generated`.
   e. При сбое генерации → `status=failed`, продолжить следующую строку.
3. Для каждой строки со `status=generated` (порядок по `id`):
   a. Прочитать JSON по `post_path`; если в нём уже есть `published_at` — считать опубликованным,
      поставить `status=published`, `published_at` из JSON, пропустить вызов публикатора.
   b. Иначе вызвать `/publish-to-social <post_path>` (через Skill tool). Скилл запустит
      `publish.py --post <post_path>`, который публикует и ставит `published_at` в JSON.
   c. При успехе: `status=published`, `published_at` = значение из JSON.
   d. При сбое публикации: оставить `status=generated` (ретрай следующим запуском),
      записать причину в отчёт.
4. Записать `queue.csv` обратно (Write).
5. Напечатать отчёт: N сгенерировано, M опубликовано, K провалено (с причинами),
   L пропущено как дубли/уже опубликованные.

**Дедуп — двойной:**
- по `url` в CSV (строки `published` с тем же url пропускаются);
- по `published_at` в JSON-посте (publish.py сам не публикует повторно).

**Имена файлов:** `YYYY-MM-DD` — дата создания файла (обычно сегодня), как уже принято
в проекте. `<id>` гарантирует уникальность между строками.

### Доработка `publish-to-social`

- В `SKILL.md`: добавить необязательный аргумент — путь к JSON.
  - путь передан → `python3 .../publish.py --post <путь>`;
  - не передан → старое поведение `python3 .../publish.py` (последний JSON в `/posts`).
- В `allowed-tools` расширить Bash-разрешение до
  `Bash(python3 /Users/irina/Desktop/claud_mod_3_2/publish.py *)`, чтобы `--post <путь>`
  не запрашивал подтверждение.
- Поведение «не публиковать повторно, если есть `published_at`» уже есть — сохранить.
- Скилл НЕ пишет `queue.csv`; обновление статуса — задача оркестратора.

### `allowed-tools` для `/orchestrate`

```yaml
allowed-tools:
  - Read
  - Write(~/Desktop/claud_mod_3_2/queue.csv)
  - Write(~/Desktop/claud_mod_3_2/posts/**)
  - Bash(ls /Users/irina/Desktop/claud_mod_3_2/posts)
  - Bash(mv /Users/irina/Desktop/claud_mod_3_2/posts/* /Users/irina/Desktop/claud_mod_3_2/posts/*)
  - Bash(date +%F)
  - Skill
  - WebFetch
```

Примечание: оркестратор вызывает вложенные скиллы через `Skill` tool; генерация внутри
`/hypno-post-to-social` сама использует `WebFetch`, `Write` в `/posts`, `Bash(image_generator.py)`,
что разрешено её собственным `allowed-tools`.

### Удаляемое старое

- `queue.json` — заменён на `queue.csv`.
- `build_queue.py` — строил `queue.json` из `links.txt`; больше не нужен.
- `scheduler.py` — launchd-планировщик; режим ручной.
- `com.claud_mod_3_2.scheduler.plist`, `com.claud_mod_3_2.generator.plist` — launchd-задания.
  **Важно:** перед удалением проверить, не загружены ли они в `~/Library/LaunchAgents/`, и
  выгрузить (`launchctl unload`), иначе launchd будет падать на отсутствие файла.
- `.claude/skills/generate-queue/` — заменён на `/orchestrate`.
- `.claude/skills/hypno-publish-pipeline/` — заменён на `/orchestrate`.
- `links.txt` — роль поглощена первой колонкой `queue.csv`.
- `README_QUEUE.md` — документировал старую очередь; удалить (или заменить краткой
  заметкой про `queue.csv` в `CONTEXT.md`).

`RESEARCH_AUTOPOSTING.md` и `HOMEWORK_REPORT.md` — исследовательские заметки, оставляем.

## Обработка ошибок и граничные случаи

- **Дубль URL:** строка с `url`, уже присутствующим как `published`, пропускается.
- **Генерация картинки упала:** `hypno-post-to-social` сохраняет JSON без PNG; публикация
  идёт текстом (существующее поведение `publish.py`).
- **Публикация упала (токен VK/Telegram):** `status=generated` сохраняется, причина в отчёте;
  следующий `/orchestrate` доретраит.
- **Генерация упала (статья не fetched / LLM сбой):** `status=failed`, переход к следующей
  строке.
- **Мак спал / Claude был закрыт:** ничего не теряется — строки в CSV ждут следующего
  ручного `/orchestrate`.
- **Пустой/битый CSV:** оркестратор сообщает об ошибке чтения и останавливается, не затирая
  файл.
- **`post_path` указывает на несуществующий файл:** оркестратор сообщает, ставит `failed`
  (или оставляет `generated` для ручного разбора), не падает.

## Поток данных (пример, 2 новые + 1 опубликованная)

```
queue.csv до:
  post-1,https://a,pending,,,
  post-2,https://b,pending,,,
  post-3,https://c,published,posts/2026-06-25-post-3-hypno-post-social.json,2026-06-25T22:00,2026-06-25T22:05

запуск /orchestrate:
  post-1: /hypno-post-to-social https://a → mv → posts/2026-06-26-post-1-hypno-post-social.json
          → status=generated, generated_at=2026-06-26T14:00
          → /publish-to-social <path> → published_at в JSON → status=published
  post-2: аналогично → published
  post-3: уже published → пропущен

queue.csv после: все три published, post_path и времена заполнены.
```

## Тестирование

1. Подготовить `queue.csv`: 2 строки `pending` (новые URL) + 1 строка `published`
   (существующий пост) + 1 строка `generated` (пост есть, но не опубликован — для проверки
   ретрая публикации).
2. Запустить `/orchestrate`.
3. Ожидаемый результат:
   - 2 `pending` → `generated` → `published`; в `/posts` появились файлы с `<id>` в имени;
     посты ушли в TG и VK.
   - `generated`-строка → `published` (ретрай публикации без перегенерации).
   - `published`-строка пропущена.
   - `queue.csv` корректно перезаписан, формат CSV не сломан (открывается как таблица).
   - В JSON-постах появилось `published_at`.
4. Негативный кейс: временно портим токен в `.env` → запуск → публикация падает, строки
   остаются `generated`, отчёт содержит причину; чиним токен → повторный `/orchestrate`
   дорабатывает до `published`.
5. Дедуп: добавить в CSV `pending`-строку с URL, уже опубликованным → `/orchestrate`
   пропускает её как дубль.

## Что не входит в скоуп (YAGNI)

- Расписание / launchd / cron.
- Headless-вызов Claude.
- Поля `generate_at` / `publish_at` / интервалы.
- Хранение контента постов в CSV (контент живёт в JSON в `/posts`).
- База данных (SQLite и т.п.) — CSV достаточно для плоской таблицы.
- Авто-импорт ссылок из внешних источников.