# Автозапуск по очереди: генерация вечером + публикация по расписанию

## Идея

Каждый вечер в **22:00** генерируем сразу все посты на завтра (JSON + PNG).  
Затем launchd автоматически публикует их в нужное время: **10:00, 11:00, 12:00** или любые другие интервалы, которые ты задашь.

Это надёжнее, чем пытаться запускать Claude Code полностью без участия человека.

## Быстрый старт (копипаст)

```bash
cd /Users/irina/Desktop/claud_mod_3_2
mkdir -p logs

# 1. Убедиться, что .env заполнен (см. .env.example)

# 2. Загрузить launchd-задания
cp com.claud_mod_3_2.scheduler.plist ~/Library/LaunchAgents/
cp com.claud_mod_3_2.generator.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.claud_mod_3_2.scheduler.plist
launchctl load ~/Library/LaunchAgents/com.claud_mod_3_2.generator.plist
launchctl start com.claud_mod_3_2.scheduler
launchctl start com.claud_mod_3_2.generator

# 3. Проверить, что задания висят
launchctl list | grep com.claud_mod_3_2

# 4. В 22:00 вставить в Claude Code:
# /generate-queue

# 5. Утром launchd сам публикует посты в 10:00, 11:00, 12:00
```

---

## Формат очереди (`queue.json`)

```json
{
  "schema_version": "hypno-queue/v2",
  "items": [
    {
      "id": "morning-1",
      "url": "https://cyberleninka.ru/article/n/psihofiziologicheskie-harakteristiki-obektivizatsii-protsessov-vnusheniya",
      "generate_at": "2026-06-27T22:00:00",
      "publish_at": "2026-06-28T10:00:00",
      "status": "pending",
      "generated_at": null,
      "published_at": null,
      "post_path": null
    },
    {
      "id": "morning-2",
      "url": "https://cyberleninka.ru/article/n/vnushenie-i-gipnoz-v-sovremennyh-psihologicheskih-teoriyah",
      "generate_at": "2026-06-27T22:00:00",
      "publish_at": "2026-06-28T11:00:00",
      "status": "pending",
      "generated_at": null,
      "published_at": null,
      "post_path": null
    },
    {
      "id": "morning-3",
      "url": "https://www.techinsider.ru/science/8558-pod-gipnozom-pravda-i-mify-o-gipnoze/",
      "generate_at": "2026-06-27T22:00:00",
      "publish_at": "2026-06-28T12:00:00",
      "status": "pending",
      "generated_at": null,
      "published_at": null,
      "post_path": null
    }
  ]
}
```

### Как задавать интервалы?

Просто меняй `publish_at` для каждого item. Интервал может быть любым:

- через час: `10:00`, `11:00`, `12:00`
- через 30 минут: `10:00`, `10:30`, `11:00`
- с большим промежутком: `09:00`, `14:00`, `19:00`

Главное — чтобы `generate_at` был **до** всех `publish_at` (обычно вечером накануне).

---

## Режимы `scheduler.py`

### Генерация (вечером)

Проверяет, какие посты пора генерировать, и отправляет напоминание:

```bash
cd /Users/irina/Desktop/claud_mod_3_2
python3 scheduler.py --mode generate
```

При получении уведомления просто вставь в Claude Code:

```text
/generate-queue
```

Claude сгенерирует все 3 поста подряд, сохранит их с уникальными именами и обновит `queue.json`.

### Публикация (каждые 10 минут)

Автоматически публикует готовые посты, время которых наступило:

```bash
cd /Users/irina/Desktop/claud_mod_3_2
python3 scheduler.py --mode publish
```

---

## Автозапуск через `launchd`

### 1. Публикация — каждые 10 минут

```bash
cp /Users/irina/Desktop/claud_mod_3_2/com.claud_mod_3_2.scheduler.plist \
   ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.claud_mod_3_2.scheduler.plist
launchctl start com.claud_mod_3_2.scheduler
```

### 2. Генерация — каждый день в 22:00

```bash
cp /Users/irina/Desktop/claud_mod_3_2/com.claud_mod_3_2.generator.plist \
   ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.claud_mod_3_2.generator.plist
launchctl start com.claud_mod_3_2.generator
```

### Проверить статус

```bash
launchctl list | grep com.claud_mod_3_2
```

### Остановить

```bash
launchctl stop com.claud_mod_3_2.scheduler
launchctl unload ~/Library/LaunchAgents/com.claud_mod_3_2.scheduler.plist

launchctl stop com.claud_mod_3_2.generator
launchctl unload ~/Library/LaunchAgents/com.claud_mod_3_2.generator.plist
```

---

## Полностью автоматическая генерация (экспериментально)

Если хочешь попробовать запускать `/generate-queue` без ручного ввода:

```bash
python3 scheduler.py --mode generate --execute
```

Это попытается запустить `claude --message /generate-queue`.  
> ⚠️ Работает не во всех случаях, потому что Claude Code в первую очередь интерактивен. Надёжнее — нажать на уведомление и вставить `/generate-queue` вручную.

---

## Ежедневный рабочий процесс

1. **Вечером** получаешь уведомление «Run /generate-queue».
2. Вставляешь `/generate-queue` в Claude Code — он делает 3 поста.
3. **Утром** launchd сам публикует их в 10:00, 11:00, 12:00.
4. Когда захочешь запланировать следующий день — добавляешь/меняешь ссылки и времена в `queue.json`.

## Если что-то пошло не так

- **launchd не загрузился** — проверь, что пути в `.plist` правильные и файл `scheduler.py` существует.
- **Не приходит уведомление о генерации** — запусти вручную:
  ```bash
  python3 /Users/irina/Desktop/claud_mod_3_2/scheduler.py --mode generate
  ```
- **Пост не опубликовался** — проверь логи:
  ```bash
  tail -f /Users/irina/Desktop/claud_mod_3_2/logs/scheduler.err.log
  tail -f /Users/irina/Desktop/claud_mod_3_2/logs/generator.err.log
  ```
- **Токен ВК истёк** — убедись, что в `.env` настроены `VK_REFRESH_TOKEN`, `VK_CLIENT_ID`, `VK_DEVICE_ID`, или получи новый долгосрочный токен через `vkhost.github.io` с `scope=wall,photos,groups,offline`.
