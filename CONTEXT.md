# Контекст проекта: Claud Mod 3.2 — Контент-завод для соцсетей

## Цель
Создать систему для автоматической генерации и публикации постов по теме гипноза в Telegram и ВКонтакте.

## Структура проекта
```
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
├── vk_token_refresh.py              # Обновление VK access_token через refresh_token
├── vk_pkce_helper.py                # Генерация PKCE-параметров для первой VK ID авторизации
├── vk_exchange_code.py              # Обмен authorization code на access_token + refresh_token
├── .env.example                     # Шаблон для токенов
├── .gitignore                       # Исключает .env, JSON/PNG-посты, логи
└── CONTEXT.md                       # Этот файл
```

## Скиллы Claude Code

### 1. hypno-post-to-social
- Принимает на вход одну статью, ссылку или описание по теме гипноза.
- Генерирует:
  - `source` — данные об источнике;
  - `image_prompt` — промпт для картинки через Qwen API;
  - `platforms.telegram.content` — текст для Telegram;
  - `platforms.vk.content` — текст для ВКонтакте.
- Пытается сгенерировать PNG-картинку через `image_generator.py` и добавить `image_path` в JSON.
  - Если генерация изображения недоступна по API, JSON сохраняется без картинки — текст всё равно можно опубликовать.
- Сохраняет JSON в `/Users/irina/Desktop/claud_mod_3_2/posts/YYYY-MM-DD-hypno-post-social.json`.
  - `YYYY-MM-DD` — сегодняшняя дата создания поста, а не дата публикации оригинальной статьи.
- Не публикует самостоятельно.
- Пишет ясно, без мистики, псевдонауки и воды.
- **Промпт для картинки обязан быть адаптирован под конкретную статью**, не скопирован из примера и не generic.

### 2. publish-to-social
- Без аргументов: публикует последний JSON в `/posts`.
- С аргументом-путём: публикует конкретный JSON (этот режим использует оркестратор `/orchestrate`).
- Читает токены из `.env`, запускает `publish.py [--post <path>]`.
- Публикует пост в Telegram и ВКонтакте, с картинкой, если в JSON есть `image_path` и файл существует.
- Не публикует повторно, если в JSON уже есть `published_at`.

### 3. orchestrate
- Читает `queue.csv` (единственный источник правды).
- Для строк `pending`: вызывает `/hypno-post-to-social`, переименовывает файлы в `posts/YYYY-MM-DD-<id>-hypno-post-social.{json,png}`, ставит `status=generated`.
- Для строк `generated`: вызывает `/publish-to-social <post_path>`, ставит `status=published`.
- Двойной дедуп: по `url` в CSV + по `published_at` в JSON.
- При сбое генерации → `status=failed`; при сбое публикации → оставляет `generated` (ретрай следующим запуском).
- Ручной режим: работает, пока открыт Claude. Расписания/launchd нет.

## Очередь queue.csv
Единая CSV-таблица, формат:
```
id,url,status,post_path,generated_at,published_at
```
- `status`: `pending` → `generated` → `published` (`failed` при сбое генерации).
- Пользователь дописывает строку с `url` и `status=pending` (остальные поля пустыми), затем запускает `/orchestrate`.
- Промежуточный `generated` нужен, чтобы при сбое публикации следующий `/orchestrate` доретраил только публикацию, не перегенерируя пост.
- CSV плоский, без запятых в полях; редактируется руками и оркестратором.

## Скрипты
- `publish.py` — публикует конкретный пост (`--post <path>`) или последний JSON в `/posts`; публикует текст (и картинку, если есть) в Telegram и VK; добавляет `published_at`. Перед публикацией обновляет VK access_token через `vk_token_refresh.py`, если настроен `VK_REFRESH_TOKEN`.
- `image_generator.py` — читает `image_prompt` из JSON, вызывает Qwen/DashScope API, сохраняет PNG и прописывает `image_path` в JSON.
- `vk_token_refresh.py` — обновляет `VK_ACCESS_TOKEN` через `VK_REFRESH_TOKEN` и `VK_DEVICE_ID`.
- `vk_pkce_helper.py` — генерирует `code_verifier`, `code_challenge` и ссылку для первой авторизации VK ID.
- `vk_exchange_code.py` — обменивает `authorization code` на первую пару `access_token` + `refresh_token`.

## Переменные окружения (.env)
```bash
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
TELEGRAM_CHANNEL_ID=@your_channel_or_numeric_id
VK_ACCESS_TOKEN=your_vk_access_token_here
VK_GROUP_ID=your_vk_group_id_here
QWEN_API_KEY=your_qwen_api_key_here
BASE_URL=https://dashscope-intl.aliyuncs.com
IMAGE_MODEL=wan2.6-t2i
```

**Важно:** реальные токены и ключи пользователь вносит в `.env` самостоятельно. Скиллы не читают и не записывают `.env`. Файл `.env` исключён из git через `.gitignore`.

## Генерация без внешних ресурсов
- Текст постов пишется внутри Claude на основе предоставленного источника.
- Скрипт публикации — локальный Python.
- Токены не утекают: хранятся в `.env`, который в `.gitignore`.

## Автоматический запуск скилла
Чтобы `/orchestrate` и вложенные скиллы не спрашивали подтверждение на каждое действие, на стороне пользователя должны быть настроены разрешения Claude Code:

1. **Режим `acceptEdits`** (или `auto`, если модель и аккаунт поддерживают auto mode) выставлен в глобальных настройках `~/.claude/settings.json`. Проектные файлы `.claude/settings.json` и `~/.claude/settings.local.json` **не могут** назначить режим `auto`.
2. В `permissions.allow` разрешены инструменты, которые используют скиллы.
3. В `SKILL.md` каждого скилла добавлен `allowed-tools:` — это разрешает указанные инструменты именно во время работы скилла.

Если режим `auto` недоступен (например, используется неподдерживаемая модель), используй `acceptEdits` — он не зависит от модели и тоже автоматически одобряет чтение/запись в рабочей директории.

## Использование
1. Открой Claude Code в папке проекта, включи `accept edits on` (`Shift+Tab`).
2. Допиши в `queue.csv` строку: `<id>,<url>,pending,,,`.
3. Запусти `/orchestrate`. Оркестратор сгенерирует пост(ы) и опубликует их, обновив статусы в `queue.csv`.

## Что уже сделано
- [x] Скилл генерации постов `hypno-post-to-social`.
- [x] Скилл публикации `publish-to-social` (с поддержкой аргумента-пути).
- [x] Скрипт публикации `publish.py` (с `--post <path>` и `published_at`).
- [x] `.env.example` и `.gitignore`.
- [x] `image_generator.py` для генерации PNG через Qwen/DashScope.
- [x] Автоодобрение инструментов в `~/.claude/settings.json` (`acceptEdits` + `permissions.allow`).
- [x] Протестированы генерация и публикация постов с картинкой.
- [x] Внедрён скилл-оркестратор `/orchestrate` + `queue.csv` как единый источник правды.
- [x] Удалены старые `queue.json`, `build_queue.py`, `scheduler.py`, launchd-задания, `links.txt`, `README_QUEUE.md`, скиллы `generate-queue` и `hypno-publish-pipeline`.

## Что нужно сделать дальше
- [ ] Протестировать end-to-end: дописать `pending`-ссылку в `queue.csv`, запустить `/orchestrate`, проверить генерацию + публикацию + обновление статусов.
- [ ] Проверить ретрай публикации: при сбое (например, протухший токен) строка остаётся `generated` и дорабатывает следующим `/orchestrate`.

## Тестовые ссылки (уже использовались)
- https://mip.institute/journal/gipnoz-v-psikhoterapii-i-ego-ehffektivnost
- https://snob.ru/society/meditsinskii-gipnoz-sharlatanstvo-ili-sposob-preodoleniia-psikhotravm/
- https://medgz.ru/stati/article_post/gipnoz
- https://psy.education/novosti-proekta/news/?id=40
- https://psy.su/feed/13163/
- https://ria.ru/20171028/1507709530.html
- https://www.techinsider.ru/science/8558-pod-gipnozom-pravda-i-mify-o-gipnoze/
- https://cyberleninka.ru/article/n/vnushenie-i-gipnoz-v-sovremennyh-psihologicheskih-teoriyah