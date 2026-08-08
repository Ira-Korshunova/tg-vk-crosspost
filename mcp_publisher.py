"""
MCP-сервер над publish.py — выставляет кросс-постинг TG+VK как tools для любого
AI-клиента (Claude Desktop, Cursor, ChatGPT, VS Code).

Это "обёртка": существующий код publish.py НЕ меняется, поверх него добавляется
тонкий слой, переводящий tool-calls модели в вызовы Python-функций.

Tools:
  - list_queue()            — все строки queue.csv (источник правды)
  - list_pending_posts()    — строки в статусе pending/generated/failed
  - get_post_status(id)     — статус конкретного поста
  - check_tokens()          — проверка валидности токенов TG/VK (read-only, безопасно)
  - publish_post(post_path) — опубликовать один пост в TG+VK (ДЕЙСТВИЕ!)
  - publish_pending()       — опубликовать все pending/generated по очереди (ДЕЙСТВИЕ!)

Запуск:
  fastmcp run mcp_publisher.py            # stdio, для Claude Desktop/Cursor
  fastmcp dev mcp_publisher.py            # откроет MCP Inspector (дебаг в браузере)
  python3 mcp_publisher.py                # тоже stdio (через mcp.run())

Безопасность:
  - publish_post/publish_pending — side-effecting (реально постят в соцсети).
    Описания явно предупреждают модель.
  - post_path валидируется: должен быть .json под posts/, без path traversal.
  - check_tokens — read-only, безопасен, для диагностики.
"""

import csv
import os
import subprocess
from pathlib import Path

from fastmcp import FastMCP

BASE_DIR = Path(__file__).resolve().parent
POSTS_DIR = BASE_DIR / "posts"
QUEUE_CSV = BASE_DIR / "queue.csv"
PUBLISH_PY = BASE_DIR / "publish.py"

mcp = FastMCP("tg-vk-crosspost")


# ─────────────────────────────────────────────────────────────────────────────
# Вспомогательные функции (не tools)
# ─────────────────────────────────────────────────────────────────────────────

def _read_queue() -> list[dict]:
    """Прочитать queue.csv как список словарей. Пустой список если файла нет."""
    if not QUEUE_CSV.exists():
        return []
    with open(QUEUE_CSV, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _resolve_post_path(post_path: str) -> Path:
    """
    Нормализовать и провалидировать путь к посту.
    Принимает как относительный (posts/x.json), так и абсолютный.
    Кидает ValueError если путь вне posts/ или не .json.
    """
    p = Path(post_path)
    if not p.is_absolute():
        p = BASE_DIR / p
    p = p.resolve()
    # Path traversal защита: итоговый путь должен быть внутри posts/
    try:
        p.relative_to(POSTS_DIR.resolve())
    except ValueError:
        raise ValueError(
            f"путь вне posts/: {p}. Допускаются только .json-файлы из posts/."
        )
    if p.suffix != ".json":
        raise ValueError(f"ожидался .json, получено: {p.name}")
    return p


# ─────────────────────────────────────────────────────────────────────────────
# Read-only tools (безопасны — можно вызывать свободно)
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def list_queue() -> list[dict]:
    """Вернуть все строки таблицы-очереди queue.csv.

    queue.csv — источник правды: id,url,status,post_path,generated_at,published_at.
    Статусы: pending → generated → published (failed при сбое генерации).
    Используй когда спрашивают 'что в очереди' / 'какие посты есть'.
    Возвращает список строк с полями id, url, status, post_path, published_at.
    """
    return _read_queue()


@mcp.tool()
def list_pending_posts() -> list[dict]:
    """Вернуть посты, ожидающие публикации (status в pending/generated/failed).

    Используй когда спрашивают 'что ещё не опубликовано' / 'что осталось'.
    НЕ вызывает публикацию — только показывает список.
    Для фактической публикации вызови publish_pending() или publish_post().
    """
    rows = _read_queue()
    pending = [r for r in rows if r.get("status") in ("pending", "generated", "failed")]
    return pending


@mcp.tool()
def get_post_status(post_id: str) -> dict:
    """Вернуть статус конкретного поста по его id (например 'post-4').

    Используй когда спрашивают 'какой статус у поста X' / 'опубликован ли post-4'.
    Возвращает строку из queue.csv или {error: 'не найден'} если id нет.
    """
    for r in _read_queue():
        if r.get("id") == post_id:
            return r
    return {"error": f"пост с id={post_id} не найден в queue.csv"}


@mcp.tool()
def check_tokens() -> dict:
    """Проверить валидность токенов Telegram и VK (READ-ONLY, безопасно).

    Используй ПЕРЕД публикацией, чтобы убедиться что токены живы, или когда
    пользователь жалуется 'не публикуется'. Ничего не постит, только проверяет.
    Возвращает {telegram: {ok, error}, vk: {ok, error}}.
    """
    # Импортируем publish.py — он при импорте подгрузит .env (load_dotenv).
    import publish

    tg_ok, tg_err = publish.check_telegram_token()
    vk_ok, vk_err = publish.check_vk_token()
    return {
        "telegram": {"ok": tg_ok, "error": tg_err},
        "vk": {"ok": vk_ok, "error": vk_err},
    }


# ─────────────────────────────────────────────────────────────────────────────
# Side-effecting tools (РЕАЛЬНО ПОСТЯТ в соцсети — модель должна знать)
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def publish_post(post_path: str) -> dict:
    """Опубликовать один пост в Telegram и VK (ДЕЙСТВИЕ — реально постит!).

    Используй когда пользователь ЯВНО просит опубликовать конкретный пост.
    На вход — путь к posts/<id>.json (относительный или абсолютный).
    Идемпотентно: если у поста уже есть published_at, ничего не делает.
    Перед постингом проверяет токены; при сбое не делает частичной публикации.
    Возвращает {ok: true, post_path, output} или {ok: false, error}.
    """
    try:
        path = _resolve_post_path(post_path)
    except ValueError as e:
        return {"ok": False, "error": str(e)}

    if not path.exists():
        return {"ok": False, "error": f"файл не найден: {path}"}

    try:
        result = subprocess.run(
            ["python3", str(PUBLISH_PY), "--post", str(path)],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(BASE_DIR),
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "таймаут 120с при публикации"}

    output = (result.stdout or "").strip()
    if result.returncode == 0:
        return {"ok": True, "post_path": str(path), "output": output[-800:]}
    return {
        "ok": False,
        "error": (result.stderr or output or "неизвестная ошибка")[-800:],
    }


@mcp.tool()
def publish_pending() -> dict:
    """Опубликовать ВСЕ посты в статусе pending/generated по очереди (ДЕЙСТВИЕ).

    Используй когда пользователь просит 'опубликуй всё что осталось' /
    'опубликуй очередь'. Идёт по строкам queue.csv в порядке строк,
    для каждой вызывает publish_post. Останавливается на первой ошибке,
    остальные НЕ публикует (чтобы не плодить partial-публикации).
    Возвращает {published: [...], failed: ..., stopped_at: ...}.
    """
    pending = list_pending_posts()
    if not pending:
        return {"published": [], "note": "нет постов в статусе pending/generated"}

    published = []
    for row in pending:
        post_path = row.get("post_path", "")
        if not post_path:
            continue
        res = publish_post(post_path)
        if res.get("ok"):
            published.append({"id": row.get("id"), "post_path": post_path})
        else:
            return {
                "published": published,
                "failed": {"id": row.get("id"), "error": res.get("error")},
                "stopped_at": row.get("id"),
                "note": "остановлено на первом сбое, остальные не публиковались",
            }
    return {"published": published, "failed": None}


if __name__ == "__main__":
    mcp.run()