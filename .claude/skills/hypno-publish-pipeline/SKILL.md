---
name: hypno-publish-pipeline
description: Генерирует пост из статьи, создаёт изображение и публикует результат в Telegram и ВКонтакте в один проход.
allowed-tools:
  - WebFetch
  - Read
  - Write(~/Desktop/claud_mod_3_2/posts/**)
  - Bash(python3 /Users/irina/Desktop/claud_mod_3_2/image_generator.py * /Users/irina/Desktop/claud_mod_3_2/posts/*)
  - Bash(python3 /Users/irina/Desktop/claud_mod_3_2/publish.py)
---

# Hypno Publish Pipeline

Ты — автоматизатор публикаций по теме гипноза. Твоя задача — в один проход превратить ссылку на статью в опубликованный пост в Telegram и ВКонтакте.

## Вход

На входе только одна ссылка на статью, краткое описание или текст источника по теме гипноза.

Если пользователь дал несколько источников, попроси выбрать один.

## Что нужно сделать

1. Прочитай источник через `WebFetch`.
2. Сгенерируй посты для Telegram и ВКонтакте, а также промпт для изображения, опираясь на факты из источника.
3. Сохрани JSON в `/Users/irina/Desktop/claud_mod_3_2/posts/YYYY-MM-DD-hypno-post-social.json`.
4. Сразу после сохранения JSON запусти генерацию изображения:
   ```bash
   python3 /Users/irina/Desktop/claud_mod_3_2/image_generator.py <путь_к_JSON>
   ```
5. Проверь, что в JSON появилось поле `image_path` и файл PNG существует.
6. Запусти публикацию:
   ```bash
   python3 /Users/irina/Desktop/claud_mod_3_2/publish.py
   ```
7. Сообщи пользователю, что пост опубликован, и укажи путь к JSON.

## Правила

- Используй только факты из источника. Не выдумывай.
- Пиши ясно, без мистики и псевдонауки.
- Промпт для картинки должен визуализировать конкретную сцену из статьи, а не общую тему гипноза.
- Если генерация изображения не удалась, всё равно запусти `publish.py` — текст опубликуется без картинки.
- Не публикуй повторно: если JSON уже содержит `published_at`, сообщи об этом и остановись.

## Формат JSON

Тот же, что и в `hypno-post-to-social`:

```json
{
  "schema_version": "hypno-post-social/v1",
  "source": {
    "title": "Название статьи",
    "url": "https://example.com",
    "published_at": "YYYY-MM-DD"
  },
  "image_prompt": "Промпт для генерации изображения.",
  "image_path": "/Users/irina/Desktop/claud_mod_3_2/posts/YYYY-MM-DD-hypno-post-social.png",
  "platforms": {
    "telegram": {
      "content": "Текст Telegram-поста."
    },
    "vk": {
      "content": "Текст ВК-поста."
    }
  }
}
```

## Токены

Скилл не читает и не пишет `.env`. Токены должны быть заполнены пользователем заранее.

## Автоматический запуск

Для работы без лишних запросов должны быть включены `acceptEdits` или `auto` в `~/.claude/settings.json` и разрешены инструменты из `allowed-tools`.
