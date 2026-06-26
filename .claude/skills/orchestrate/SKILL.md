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
   e. **Обнови `image_path` внутри JSON** на переименованный PNG: прочитай `posts/YYYY-MM-DD-<id>-hypno-post-social.json` (Read), поставь `image_path` = `/Users/irina/Desktop/claud_mod_3_2/posts/YYYY-MM-DD-<id>-hypno-post-social.png` (абсолютный путь), запиши файл обратно (Write). Это обязательно — иначе `publish.py` не найдёт картинку по старому пути и опубликует только текст. Если PNG не было — оставь `image_path` пустым или удали поле.
   f. Обнови строку: `post_path=posts/YYYY-MM-DD-<id>-hypno-post-social.json`, `generated_at=<ISO now из date +%FT%H:%M:%S>`, `status=generated`.
   g. Если генерация, переименование или обновление `image_path` упали — поставь `status=failed`, причину в отчёт, переходи к следующей строке.
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