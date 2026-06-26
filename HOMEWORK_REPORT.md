# Отчёт по проекту «Claud Mod 3.2 — Контент-завод»

## 1. Цель проекта

Создать систему для автоматической генерации и публикации постов по теме гипноза в Telegram и ВКонтакте по заданному расписанию.

## 2. Что реализовано

| № | Компонент | Описание |
|---|---|---|
| 1 | `hypno-post-to-social` | Скилл Claude Code: читает статью, генерирует посты для Telegram и VK, делает промпт для картинки, сохраняет JSON. |
| 2 | `publish-to-social` | Скилл Claude Code: находит последний пост и публикует его. |
| 3 | `hypno-publish-pipeline` | Скилл «всё в одном»: генерация + картинка + публикация по одной ссылке. |
| 4 | `generate-queue` | Скилл массовой генерации: берёт 3 ссылки из `queue.json` и делает 3 поста (JSON + PNG) с уникальными именами. |
| 5 | `publish.py` | Python-скрипт публикации в Telegram и VK. Поддерживает `--post <путь>`. |
| 6 | `image_generator.py` | Генерация PNG через Qwen/DashScope (`wan2.6-t2i`). |
| 7 | `vk_token_refresh.py` | Обновление VK access_token через refresh_token. |
| 8 | `vk_pkce_helper.py` / `vk_exchange_code.py` | Помощники для получения первой пары VK ID OAuth 2.1 токенов. |
| 9 | `queue.json` | Очередь ссылок с полями `generate_at` и `publish_at`. |
| 10 | `scheduler.py` | Планировщик в двух режимах: `--mode generate` и `--mode publish`. |
| 11 | launchd-задания | `com.claud_mod_3_2.generator.plist` (22:00) + `com.claud_mod_3_2.scheduler.plist` (каждые 10 минут). |
| 12 | `.env.example` + `.env` | Хранение токенов и ключей API. |
| 13 | `README_QUEUE.md` | Полная инструкция по запуску и управлению очередью. |

## 3. Тестовая очередь

Файл `queue.json` содержит 3 ссылки с интервалом в час:

| № | ID | URL | Генерация | Публикация |
|---|---|---|---|---|
| 1 | `morning-1` | CyberLeninka — психофизиологические характеристики внушения | 26.06 в 22:00 | 27.06 в 10:00 |
| 2 | `morning-2` | CyberLeninka — внушение и гипноз в современных психологических теориях | 26.06 в 22:00 | 27.06 в 11:00 |
| 3 | `morning-3` | TechInsider — правда и мифы о гипнозе | 26.06 в 22:00 | 27.06 в 12:00 |

## 4. Как запускать (краткая инструкция)

### Шаг 1. Подготовить `.env`

Создать файл `.env` рядом с `.env.example` и заполнить:

```bash
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHANNEL_ID=...
VK_ACCESS_TOKEN=...
VK_GROUP_ID=...
VK_REFRESH_TOKEN=...          # опционально, для автообновления
VK_CLIENT_ID=...              # нужен для refresh_token
VK_DEVICE_ID=...              # нужен для refresh_token
QWEN_API_KEY=...
BASE_URL=https://dashscope-intl.aliyuncs.com
IMAGE_MODEL=wan2.6-t2i
```

### Шаг 2. Загрузить launchd-задания

```bash
cd /Users/irina/Desktop/claud_mod_3_2
mkdir -p logs
cp com.claud_mod_3_2.scheduler.plist ~/Library/LaunchAgents/
cp com.claud_mod_3_2.generator.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.claud_mod_3_2.scheduler.plist
launchctl load ~/Library/LaunchAgents/com.claud_mod_3_2.generator.plist
launchctl start com.claud_mod_3_2.scheduler
launchctl start com.claud_mod_3_2.generator
```

### Шаг 3. В 22:00 запустить генерацию

Когда придёт уведомление «Hypno Factory: generate posts», вставить в Claude Code:

```text
/generate-queue
```

Claude сгенерирует 3 поста (JSON + PNG) и обновит `queue.json`.

### Шаг 4. Публикация произойдёт автоматически

В 10:00, 11:00, 12:00 launchd сам запустит `scheduler.py --mode publish` и опубликует каждый пост.

## 5. Где лежат файлы

```
/Users/irina/Desktop/claud_mod_3_2/
├── .env                              # токены (не в git)
├── .env.example                      # шаблон токенов
├── queue.json                        # очередь ссылок
├── scheduler.py                      # планировщик
├── publish.py                        # публикация
├── image_generator.py                # генерация PNG
├── vk_token_refresh.py               # обновление VK токена
├── com.claud_mod_3_2.scheduler.plist # launchd: публикация
├── com.claud_mod_3_2.generator.plist # launchd: генерация в 22:00
├── README_QUEUE.md                   # полная инструкция
├── HOMEWORK_REPORT.md                # этот отчёт
├── screenshots/                      # сюда класть скриншоты
└── posts/                            # сюда сохраняются посты и картинки
```

## 6. Скриншоты

Скриншоты для проверки лежат в папке `screenshots/` и пронумерованы:

| № | Имя файла | Что показывает |
|---|---|---|
| 1 | `01-project-folder.png` | Структура проекта |
| 2 | `02-env-file.png` | Заполненный файл `.env` (токены замазаны/скрыты) |
| 3 | `03-queue-json.png` | Содержимое `queue.json` |
| 4 | `04-skills-folder.png` | Скиллы Claude Code |
| 5 | `05-launchd-loaded.png` | `launchctl list` — задания загружены |
| 6 | `06-generate-queue.png` | Запуск `/generate-queue` |
| 7 | `07-generated-posts.png` | Сгенерированные JSON + PNG в папке `posts/` |
| 8 | `08-scheduler-publish.png` | Публикация через `scheduler.py --mode publish` |
| 9 | `09-telegram-post.png` | Опубликованный пост в Telegram |
| 10 | `10-vk-post.png` | Опубликованный пост в ВКонтакте |

> Папка `screenshots/` сейчас пуста — пользователь самостоятельно добавит нужные скриншоты.

> Положи свои скриншоты в `screenshots/` с именами из таблицы — тогда отчёт будет актуальным.

## 7. Источники

- [Teleport — автопостинг](https://teleport.ru)
- [Neironica — AI + автопостинг](https://neironica.ru/autoposting.php)
- [VK Постинг](https://vk-posting.ru)
- [SMMplanner](https://smmplanner.com)
- [SmmBox](https://smmbox.com)
- [Spark.ru — автопостинг в Telegram и VK](https://spark.ru/user/65400/blog/262653/avtoposting-v-telegram-i-vk-nastrojka-za-15-minut-bez-programmista)
