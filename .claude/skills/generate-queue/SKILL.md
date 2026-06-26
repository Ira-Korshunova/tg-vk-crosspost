---
name: generate-queue
description: Читает queue.json, генерирует сразу все запланированные посты (JSON + PNG) с уникальными именами и обновляет очередь.
allowed-tools:
  - Read
  - Write(~/Desktop/claud_mod_3_2/posts/**)
  - Write(~/Desktop/claud_mod_3_2/queue.json)
  - Bash(python3 /Users/irina/Desktop/claud_mod_3_2/image_generator.py * /Users/irina/Desktop/claud_mod_3_2/posts/*)
  - Bash(mv /Users/irina/Desktop/claud_mod_3_2/posts/* /Users/irina/Desktop/claud_mod_3_2/posts/*)
  - Bash(ls /Users/irina/Desktop/claud_mod_3_2/posts)
  - Bash(date +%F)
  - WebFetch
---

# Generate Queue

Ты — планировщик контента. Твоя задача — сгенерировать сразу несколько постов по очереди `queue.json`, сохранить каждый под уникальным именем и прописать пути в очереди.

## Вход

Скилл не требует аргументов. Он всегда читает `/Users/irina/Desktop/claud_mod_3_2/queue.json`.

## Алгоритм

1. Прочитай `queue.json`.
2. Найди все item'ы со статусом `pending`, у которых `generate_at` уже наступило (или наступит сегодня/завтра — то есть генерация запланирована на ближайшее время).
3. Для каждого такого item по порядку:
   - Прочитай статью по `url` через `WebFetch`.
   - Сгенерируй JSON-пост по правилам `hypno-post-to-social`:
     - `source` с title, url, published_at;
     - `image_prompt`, адаптированный под конкретную статью;
     - `platforms.telegram.content`;
     - `platforms.vk.content`.
   - Сохрани JSON во временное имя `posts/YYYY-MM-DD-hypno-post-social.json`.
   - Сразу запусти `python3 /Users/irina/Desktop/claud_mod_3_2/image_generator.py <путь_к_JSON>`.
   - Дождись завершения. Если PNG появился — он будет рядом с тем же именем.
   - Переименуй JSON и PNG:
     - JSON: `posts/YYYY-MM-DD-hypno-post-social.json` → `posts/YYYY-MM-DD-<id>-hypno-post-social.json`.
     - PNG: `posts/YYYY-MM-DD-hypno-post-social.png` → `posts/YYYY-MM-DD-<id>-hypno-post-social.png` (только если PNG существует).
     - `YYYY-MM-DD` — дата создания файла (обычно сегодня).
     - Используй `Bash(mv ...)`, чтобы не перезаписать уже сохранённые файлы предыдущих item'ов.
   - Обнови `post_path` в item на новый путь к JSON.
   - Поставь статус `generated` и `generated_at` текущим временем.
4. Сохрани обновлённый `queue.json`.

## Правила генерации каждого поста

- Текст пиши на русском, ясно, без мистики и псевдонауки.
- Telegram: 700–1400 знаков, 3–6 абзацев, без хэштегов.
- VK: 600–1300 знаков, 3–5 абзацев, 3–7 хэштегов в конце.
- `image_prompt` визуализирует конкретную сцену из статьи, не generic образ гипноза.
- Не придумывай факты, цифры, имена.

## Имена файлов

Если сегодня 2026-06-27, а item id = `morning-1`:
- `posts/2026-06-27-morning-1-hypno-post-social.json`
- `posts/2026-06-27-morning-1-hypno-post-social.png`

## Выход

После завершения:
- все pending-посты в очереди должны иметь статус `generated`;
- в `post_path` должен быть корректный путь;
- рядом с каждым JSON должен лежать PNG (если генерация удалась).

Если для какого-то URL не удалось сгенерировать картинку, всё равно сохрани JSON и пропиши `post_path`. Публикация потом разберётся — текст опубликует без картинки.
