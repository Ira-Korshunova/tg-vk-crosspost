# tg-vk-crosspost — контент-фабрика кросс-постинга в Telegram и VK

Система берёт ссылку на статью → генерирует пост (текст + картинка) → публикует **одновременно** в Telegram и ВКонтакте. Управляется одной человекочитаемой таблицей-очередью (`queue.csv`): положил ссылку → запустил оркестратор → пост ушёл в обе соцсети с защитой от дублей и ретраем.

Архитектура построена на **скиллах Claude Code** (оркестрация) и **Python-скриптах** (публикация, генерация картинок, OAuth VK). Режим ручной: работает, пока открыт Claude Code.

> **Демо-домен:** в качестве источника контента использованы статьи по теме гипноза (psy.education, psy.su, techinsider) — система доменно-независима, на входе просто ссылка на статью. Подробное описание курса и проверочный прогон — в [`HOMEWORK_REPORT.md`](HOMEWORK_REPORT.md).

---

## Что делает система

```
                ┌──────────────┐
                │  queue.csv   │  ← положил строку: id,url,pending,,,
                │ (источник    │     редактируется руками + оркестратором
                │  правды)     │
                └──────┬───────┘
                       │ читает/пишет
                       ▼
            ┌────────────────────┐
            │  /orchestrate       │  оркестратор: статусы, дедуп, переименование
            └───┬─────────────┬───┘
   pending →    │             │  ← generated →
                ▼             ▼
   ┌──────────────────┐   ┌──────────────────────┐
   │ /hypno-post-     │   │ /publish-to-social   │
   │  to-social       │   │  (с путём к JSON)    │
   │ генерация поста  │   │  публикация в TG/VK  │
   │ + PNG (Qwen)     │   │  через publish.py    │
   └────────┬─────────┘   └──────────┬───────────┘
            │ сохраняет                │ запускает
            ▼                          ▼
        posts/*.json + *.png      python3 publish.py --post <path>
                                   → Telegram + VK API, ставит published_at
```

- **`queue.csv`** — источник правды: `id,url,status,post_path,generated_at,published_at`. Статусы: `pending → generated → published` (`failed` при сбое генерации).
- **Двойной дедуп:** по `url` в CSV + по `published_at` в JSON.
- **Ретрай без перегенерации:** при сбое публикации (протух токен) строка остаётся `generated`, следующий `/orchestrate` доретраит только публикацию.

---

## Стек

| Слой | Технология |
|---|---|
| Оркестрация | Claude Code Skills (`/orchestrate`, `/hypno-post-to-social`, `/publish-to-social`) |
| Генерация текста | LLM (через скилл, читает статью через WebFetch) |
| Генерация картинок | **Qwen / DashScope** (`wan2.6-t2i`, async-задача + поллинг) |
| Публикация TG | Telegram Bot API (`sendPhoto`/`sendMessage`) |
| Публикация VK | VK API (`wall.post` + 3-шаговая загрузка фото: `getWallUploadServer → upload → saveWallPhoto`) |
| Авторизация VK | **VK ID OAuth 2.1 с PKCE** + авто-обновление `access_token` через `refresh_token` |
| Хранение | CSV (`queue.csv`), JSON-посты в `posts/` |

---

## Структура проекта

```
.
├── .claude/skills/
│   ├── hypno-post-to-social/SKILL.md   # генератор: ссылка → JSON-пост + PNG
│   ├── publish-to-social/SKILL.md      # публикатор: JSON → Telegram + VK
│   └── orchestrate/SKILL.md            # оркестратор: queue.csv → генерация → публикация
├── publish.py              # публикация в TG/VK (--post <path>), проверка токенов, идемпотентность
├── mcp_publisher.py        # MCP-сервер (FastMCP): publish.py как tools для AI-клиентов
├── image_generator.py      # генерация PNG через Qwen/DashScope
├── vk_token_refresh.py      # обновление VK access_token
├── vk_pkce_helper.py       # PKCE для первой VK ID OAuth 2.1 авторизации
├── vk_exchange_code.py     # обмен code на access/refresh token
├── queue.csv               # таблица-очередь (источник правды)
├── posts/                  # JSON-посты и PNG (не в git)
├── .env.example            # шаблон ключей
├── HOMEWORK_REPORT.md      # подробный отчёт по архитектуре и проверочному прогону
├── CONTEXT.md              # технический контекст
└── screenshots/            # скриншоты опубликованных постов
```

---

## Установка и запуск

### 1. Зависимости

```bash
pip install -r requirements.txt  # requests, python-dotenv
```

### 2. Ключи (`.env` по шаблону `.env.example`)

```bash
cp .env.example .env
# заполнить:
#   TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID
#   VK_ACCESS_TOKEN, VK_GROUP_ID
#   VK_CLIENT_ID, VK_REFRESH_TOKEN, VK_DEVICE_ID   # для автообновления VK-токена
#   QWEN_API_KEY, BASE_URL, IMAGE_MODEL
```

Скиллы никогда не читают и не пишут `.env` — только Python-скрипты через `python-dotenv`. `.env` исключён из git.

### 3. Положить ссылку в очередь

Дописать строку в `queue.csv` (остальные поля пустыми):

```csv
post-4,https://example.com/article,pending,,,
```

### 4. Запустить оркестратор

В Claude Code (с `accept edits on`):

```text
/orchestrate
```

Оркестратор найдёт строку `pending`, сгенерирует пост + картинку (`/hypno-post-to-social`), опубликует в TG и VK (`/publish-to-social`), поставит в `queue.csv` `status=published`.

### 5. Проверить

```bash
column -t -s, queue.csv     # статус должен стать published
ls posts/                   # рядом с JSON лежит PNG с тем же именем
```

---

## Жизненный цикл строки

```
pending  --генерация OK-->  generated  --публикация OK-->  published
pending  --генерация упала-->  failed
generated --публикация упала-->  generated   (ретрай следующим /orchestrate, без перегенерации)
```

---

## Что реализовано

- **Оркестратор** на скиллах: CSV-очередь, фазы генерации/публикации, двойной дедуп, ретрай.
- **Публикатор** `publish.py`: TG + VK, проверка токенов **до** постинга (чтобы не было частичной публикации), идемпотентность по `published_at`, CLI `--post`.
- **MCP-сервер** `mcp_publisher.py`: те же возможности выставлены как tools для любого AI-клиента (см. ниже).
- **VK-фото**: полная 3-шаговая загрузка (`getWallUploadServer → upload → saveWallPhoto`).
- **VK ID OAuth 2.1**: PKCE-авторизация + авто-`refresh_token`.
- **Генерация картинок**: Qwen/DashScope `wan2.6-t2i`, async-задача с поллингом результата.
- Проверочный end-to-end прогон на реальных каналах — см. [`HOMEWORK_REPORT.md`](HOMEWORK_REPORT.md), секция 11.

---

## MCP-интерфейс (`mcp_publisher.py`)

Поверх `publish.py` есть тонкий [MCP](https://modelcontextprotocol.io)-сервер (~150 строк на **FastMCP**) — «обёртка», которая выставляет кросс-постинг как **tools** для любого AI-клиента: Claude Desktop, Cursor, VS Code, ChatGPT. Код `publish.py` при этом **не меняется** — сервер просто переводит tool-calls модели в вызовы Python-функций.

### Tools

| Tool | Тип | Что делает |
|---|---|---|
| `list_queue()` | read-only | все строки `queue.csv` |
| `list_pending_posts()` | read-only | посты в статусе `pending`/`generated`/`failed` |
| `get_post_status(post_id)` | read-only | статус конкретного поста по id |
| `check_tokens()` | read-only | проверка валидности токенов TG/VK (`getMe`/`groups.getById`, без постинга) |
| `publish_post(post_path)` | **действие** | опубликовать один пост в TG+VK (идемпотентно) |
| `publish_pending()` | **действие** | опубликовать все pending-посты по очереди |

Безопасность: `publish_post`/`publish_pending` — side-effecting (реально постят), описания явно предупреждают модель; `post_path` валидируется (должен быть `.json` под `posts/`, защита от path traversal); `check_tokens` — read-only для диагностики.

### Запуск

```bash
pip install -r requirements.txt   # добавлен fastmcp

fastmcp dev mcp_publisher.py      # дебаг в MCP Inspector (браузер)
fastmcp run mcp_publisher.py      # stdio-сервер для Claude Desktop/Cursor
```

### Подключение к Claude Desktop

`~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "tg-vk-crosspost": {
      "command": "python3",
      "args": ["/Users/irina/Desktop/claud_mod_3_2/mcp_publisher.py"]
    }
  }
}
```

Перезапустить Claude Desktop → модель видит все 6 tools и сама решает когда их звать (например: «опубликуй всё что в очереди» → `list_pending_posts` → `publish_pending`).

---

## Скриншоты

Скриншоты опубликованных постов в Telegram и ВКонтакте — в `screenshots/` (подписи в `screenshots/captions.md`).

---

## Лицензия

MIT.