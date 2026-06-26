# Контекст проекта: Claud Mod 3.2 — Контент-завод для соцсетей

## Цель
Создать систему для автоматической генерации и публикации постов по теме гипноза в Telegram и ВКонтакте.

## Структура проекта
```
claud_mod_3_2/
├── .claude/
│   └── skills/
│       ├── hypno-post-to-social/    # Скилл генерации постов + картинка
│       │   └── SKILL.md
│       ├── publish-to-social/       # Скилл публикации готового JSON + картинки
│       │   └── SKILL.md
│       ├── hypno-publish-pipeline/  # Скилл «всё в одном»: генерация + картинка + публикация
│       │   └── SKILL.md
│       └── generate-queue/          # Скилл массовой генерации по queue.json
│           └── SKILL.md
├── posts/                             # Сюда сохраняются JSON-посты и PNG
├── publish.py                         # Скрипт публикации в Telegram и VK
├── image_generator.py                 # Генерация PNG через Qwen/DashScope
├── vk_token_refresh.py                # Обновление VK access_token через refresh_token
├── vk_pkce_helper.py                  # Генерация PKCE-параметров для первой VK ID авторизации
├── vk_exchange_code.py                # Обмен authorization code на access_token + refresh_token
├── .env.example                       # Шаблон для токенов
├── queue.json                         # Очередь ссылок с generate_at / publish_at
├── scheduler.py                       # Планировщик: generate (вечером) и publish (авто)
├── com.claud_mod_3_2.scheduler.plist  # launchd: авто-публикация каждые 10 минут
├── com.claud_mod_3_2.generator.plist  # launchd: напоминание о генерации в 22:00
├── README_QUEUE.md                    # Инструкция по работе с очередью
├── .gitignore                         # Исключает .env, JSON/PNG-посты, логи
└── CONTEXT.md                         # Этот файл
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
- Находит последний JSON в `/posts`.
- Проверяет, что он не был опубликован ранее (нет `published_at`).
- Читает токены из `.env`.
- Запускает `python /Users/irina/Desktop/claud_mod_3_2/publish.py`.
- Публикует пост в Telegram и ВКонтакте.
- Если в JSON есть `image_path` и файл PNG существует, публикует пост с картинкой.

### 3. hypno-publish-pipeline
- Принимает на вход одну ссылку на статью.
- Запускает всю цепочку: генерацию поста, генерацию изображения, публикацию в Telegram и VK.
- Сохраняет JSON и PNG в `/posts`.
- Если изображение не удалось сгенерировать, публикует только текст.
- Не публикует повторно, если JSON уже содержит `published_at`.

## Скрипты
- `publish.py` — находит последний JSON в `/posts`, публикует текст (и картинку, если есть) в Telegram и VK, добавляет `published_at`. Перед публикацией обновляет VK access_token через `vk_token_refresh.py`, если настроен `VK_REFRESH_TOKEN`.
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
Чтобы `/hypno-post-to-social` не спрашивал подтверждение на каждое действие, на стороне пользователя должны быть настроены разрешения Claude Code:

1. **Режим `acceptEdits`** (или `auto`, если модель и аккаунт поддерживают auto mode) выставлен в глобальных настройках `~/.claude/settings.json`. Проектные файлы `.claude/settings.json` и `~/.claude/settings.local.json` **не могут** назначить режим `auto`.
2. В `permissions.allow` разрешены инструменты, которые использует скилл.
3. В `SKILL.md` скилла добавлен `allowed-tools:` — это разрешает указанные инструменты именно во время работы скилла.

Пример `~/.claude/settings.json`:
```json
{
  "permissions": {
    "defaultMode": "acceptEdits",
    "allow": [
      "WebFetch",
      "Read",
      "Write(~/Desktop/claud_mod_3_2/posts/**)",
      "Bash(python3 *)"
    ],
    "deny": [
      "Write(~/Desktop/claud_mod_3_2/.env)",
      "Write(~/Desktop/claud_mod_3_2/.env.*)"
    ]
  }
}
```

Это позволяет скиллу работать в один проход: читать статью, генерировать пост и сохранять JSON без лишних запросов. Запись в `.env` и файлы рядом с ним запрещена.

Если режим `auto` недоступен (например, используется неподдерживаемая модель), используй `acceptEdits` — он не зависит от модели и тоже автоматически одобряет чтение/запись в рабочей директории.

## Что уже сделано
- [x] Первый скилл генерации постов.
- [x] Второй скилл публикации.
- [x] Скрипт публикации publish.py.
- [x] .env.example и .gitignore.
- [x] Пример сгенерированного поста: `posts/2026-06-24-hypno-post-social.json`.
- [x] Исправлен `image_prompt` — теперь он адаптируется под статью, а не копируется из примера.
- [x] Обновлён `SKILL.md` — добавлено правило адаптации промпта и секция про `.env`.
- [x] Настроено автоодобрение инструментов в `~/.claude/settings.json` (`acceptEdits` + `permissions.allow`).
- [x] Очищены некорректные настройки `permissionMode` из `~/.claude/settings.local.json` и `.claude/settings.json`.
- [x] Убрана фиксированная модель `haiku` из `~/.claude/settings.json`, чтобы при запуске использовалась выбранная в `ollama launch claude` облачная модель.
- [x] Добавлен `allowed-tools` в `SKILL.md` обоих скиллов.
- [x] Убран Stable Horde из `.env.example`; оставлен только Qwen/DashScope.
- [x] Уточнено правило именования файлов: дата в имени — сегодняшняя, дата публикации источника — внутри `source.published_at`.
- [x] Исправлен формат `allowed-tools` в обоих `SKILL.md` с однострочного на YAML-список (25.06.2026).
- [x] Добавлен `image_generator.py` для генерации PNG через Qwen/DashScope.
- [x] Обновлён `publish.py`: публикация с изображением, проверка токенов перед отправкой, автообновление VK-токена.
- [x] Обновлены оба `SKILL.md` и `CONTEXT.md` под генерацию изображений.
- [x] Протестирован `/publish-to-social` — пост ушёл в Telegram и VK.
- [x] Создан скилл `/hypno-publish-pipeline` — генерация + картинка + публикация в один вызов.

## Что нужно сделать дальше
- [x] Перезапустить Claude Code CLI и проверить, что `/hypno-post-to-social` отрабатывает без лишних подтверждений.
- [x] Заполнить `.env` реальными токенами (самостоятельно).
- [x] Протестировать `/publish-to-social`.
- [x] Добавить генерацию изображения прямо в `hypno-post-to-social` (по API Qwen/DashScope).
- [x] Проблема `Model.AccessDenied` решена созданием нового ключа после активации сервиса Image Generation.
- [x] Проверена генерация и публикация постов с картинкой.
- [x] Создана очередь `queue.json` с тремя ссылками и интервалами на завтра.
- [x] Добавлен скилл `/generate-queue` для массовой генерации по очереди.
- [x] `scheduler.py` переделан на два режима: `--mode generate` (вечером) и `--mode publish` (авто).
- [x] `publish.py` научился принимать `--post <path>`.
- [x] launchd-задания: публикация каждые 10 минут + генерация в 22:00.
- [ ] Протестировать end-to-end автозапуск по очереди.

## Тестовые ссылки (уже использовались)
- https://mip.institute/journal/gipnoz-v-psikhoterapii-i-ego-ehffektivnost
- https://snob.ru/society/meditsinskii-gipnoz-sharlatanstvo-ili-sposob-preodoleniia-psikhotravm/
- https://medgz.ru/stati/article_post/gipnoz
- https://psy.education/novosti-proekta/news/?id=40
- https://psy.su/feed/13163/
- https://ria.ru/20171028/1507709530.html
- https://www.techinsider.ru/science/8558-pod-gipnozom-pravda-i-mify-o-gipnoze/
- https://cyberleninka.ru/article/n/vnushenie-i-gipnoz-v-sovremennyh-psihologicheskih-teoriyah

## Текущая сессия (2026-06-25)
- Исправлен `~/.claude/settings.json`: добавлен `permissions.defaultMode: acceptEdits` и нужные `permissions.allow/deny`.
- Убран некорректный `permissionMode` из `.claude/settings.json` и `~/.claude/settings.local.json`.
- В `SKILL.md` обоих скиллов добавлен `allowed-tools`.
- Убрана фиксированная модель `haiku` из `~/.claude/settings.json`.
- **Исправлен формат `allowed-tools` на YAML-список** в `hypno-post-to-social/SKILL.md` и `publish-to-social/SKILL.md`.
- **Требуется перезапуск Claude Code** для применения новых разрешений и перезагрузки скиллов.

### Чек-лист после перезапуска
1. Закрыть текущую сессию Claude Code.
2. Запустить заново:
   ```bash
   ollama launch claude
   ```
   и выбрать облачную модель из списка.
3. Убедиться, что режим `accept edits on` включён (смотреть статус-бар или нажать `Shift+Tab`, пока не появится).
4. Перейти в папку проекта:
   ```bash
   cd /Users/irina/Desktop/claud_mod_3_2
   ```
5. Проверить скилл:
   ```text
   /hypno-post-to-social https://www.techinsider.ru/science/8558-pod-gipnozom-pravda-i-mify-o-gipnoze/
   ```
   Ожидаемый результат: `WebFetch` и `Write` проходят без вопросов, файл сохраняется в `posts/2026-06-25-hypno-post-social.json`.
6. Если всё равно спрашивает разрешения — посмотреть, на каком инструменте (`WebFetch`, `Read`, `Write` или `Bash`), и сообщить об этом.
7. Если скилл «молчит» и не сохраняет файл — сообщить об этом; возможно, нужно уточнить формат `allowed-tools` или сделать скилл более явным в плане вызовов инструментов.

### Альтернативный запуск
Если режим не включился автоматически:
```bash
cd /Users/irina/Desktop/claud_mod_3_2
claude --permission-mode acceptEdits
```

### Тестовая очередь
`queue.json` содержит 3 ссылки с интервалом в час:
- `morning-1` → https://cyberleninka.ru/article/n/psihofiziologicheskie-harakteristiki-obektivizatsii-protsessov-vnusheniya в `10:00`
- `morning-2` → https://cyberleninka.ru/article/n/vnushenie-i-gipnoz-v-sovremennyh-psihologicheskih-teoriyah в `11:00`
- `morning-3` → https://www.techinsider.ru/science/8558-pod-gipnozom-pravda-i-mify-o-gipnoze/ в `12:00`

Все генерируются в `22:00` предыдущего дня.

Ручная публикация:
```bash
cd /Users/irina/Desktop/claud_mod_3_2
python3 scheduler.py --mode publish --interval 10
```

Ручная генерация:
```bash
python3 scheduler.py --mode generate
# затем в Claude Code:
/generate-queue
```

Автозапуск через launchd:
```bash
cp /Users/irina/Desktop/claud_mod_3_2/com.claud_mod_3_2.scheduler.plist ~/Library/LaunchAgents/
cp /Users/irina/Desktop/claud_mod_3_2/com.claud_mod_3_2.generator.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.claud_mod_3_2.scheduler.plist
launchctl load ~/Library/LaunchAgents/com.claud_mod_3_2.generator.plist
launchctl start com.claud_mod_3_2.scheduler
launchctl start com.claud_mod_3_2.generator
```

Подробности в `README_QUEUE.md`.

### Последняя сохранённая ссылка
https://www.techinsider.ru/science/8558-pod-gipnozom-pravda-i-mify-o-gipnoze/ → `posts/2026-06-25-hypno-post-social.json`
https://cyberleninka.ru/article/n/istoricheskie-aspekty-kriminalnogo-gipnoza → `posts/2026-06-25-hypno-post-social.json` (перезаписан)

### Известные проблемы
- Последний пост (`2026-06-25-hypno-post-social.json`) уже отмечен `published_at`. Для повторного теста публикации с картинкой нужно сгенерировать новый пост.

