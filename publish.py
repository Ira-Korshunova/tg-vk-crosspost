import os
import json
import glob
import subprocess
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

POSTS_DIR = "/Users/irina/Desktop/claud_mod_3_2/posts"


def ensure_vk_token_fresh():
    """If VK token is missing or expired and refresh credentials exist, refresh it."""
    token = os.getenv("VK_ACCESS_TOKEN")
    refresh_token = os.getenv("VK_REFRESH_TOKEN")
    if not refresh_token:
        return  # No refresh token configured, skip

    # Check current token validity
    group_id = os.getenv("VK_GROUP_ID")
    if token and group_id:
        try:
            response = requests.get(
                "https://api.vk.com/method/groups.getById",
                params={"group_id": group_id, "access_token": token, "v": "5.199"},
                timeout=15,
            )
            data = response.json()
            if "error" not in data:
                return  # Token is valid
        except Exception:
            pass

    # Token invalid or missing, try to refresh
    try:
        result = subprocess.run(
            ["python3", "/Users/irina/Desktop/claud_mod_3_2/vk_token_refresh.py"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        print(result.stdout.strip())
        if result.returncode != 0:
            print("VK token refresh failed:", result.stderr.strip())
    except Exception as e:
        print(f"Could not run vk_token_refresh.py: {e}")


def get_latest_post():
    files = glob.glob(os.path.join(POSTS_DIR, "*.json"))
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def load_post(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def check_telegram_token():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    channel_id = os.getenv("TELEGRAM_CHANNEL_ID")
    if not token or not channel_id:
        return False, "TELEGRAM_BOT_TOKEN или TELEGRAM_CHANNEL_ID не заданы в .env"
    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()
        if data.get("ok"):
            return True, None
        return False, f"Telegram token invalid: {data}"
    except Exception as e:
        return False, f"Telegram token check failed: {e}"


def publish_telegram(text, image_path=None):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    channel_id = os.getenv("TELEGRAM_CHANNEL_ID")
    if not token or not channel_id:
        raise ValueError("TELEGRAM_BOT_TOKEN или TELEGRAM_CHANNEL_ID не заданы в .env")

    url = f"https://api.telegram.org/bot{token}/sendPhoto" if image_path else f"https://api.telegram.org/bot{token}/sendMessage"

    if image_path and os.path.exists(image_path):
        with open(image_path, "rb") as photo:
            payload = {"chat_id": channel_id, "caption": text}
            files = {"photo": photo}
            response = requests.post(url, data=payload, files=files, timeout=60)
    else:
        payload = {"chat_id": channel_id, "text": text}
        response = requests.post(url, json=payload, timeout=30)

    response.raise_for_status()
    data = response.json()
    if not data.get("ok"):
        raise Exception(f"Telegram API error: {data}")
    return data


def check_vk_token():
    token = os.getenv("VK_ACCESS_TOKEN")
    group_id = os.getenv("VK_GROUP_ID")
    if not token or not group_id:
        return False, "VK_ACCESS_TOKEN или VK_GROUP_ID не заданы в .env"
    url = "https://api.vk.com/method/groups.getById"
    params = {"group_id": group_id, "access_token": token, "v": "5.199"}
    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            return False, f"VK token invalid: {data['error']}"
        return True, None
    except Exception as e:
        return False, f"VK token check failed: {e}"


def upload_vk_photo(image_path, group_id, token):
    """Upload photo to VK wall and return attachment string."""
    # 1. Get upload server
    upload_url_response = requests.get(
        "https://api.vk.com/method/photos.getWallUploadServer",
        params={"group_id": group_id, "access_token": token, "v": "5.199"},
        timeout=30,
    )
    upload_url_response.raise_for_status()
    upload_data = upload_url_response.json()
    if "error" in upload_data:
        raise Exception(f"VK API error (photos.getWallUploadServer): {upload_data['error']}")

    upload_url = upload_data["response"]["upload_url"]

    # 2. Upload file
    with open(image_path, "rb") as photo:
        files = {"photo": photo}
        upload_file_response = requests.post(upload_url, files=files, timeout=60)
    upload_file_response.raise_for_status()
    file_data = upload_file_response.json()

    # 3. Save photo
    save_response = requests.get(
        "https://api.vk.com/method/photos.saveWallPhoto",
        params={
            "group_id": group_id,
            "photo": file_data["photo"],
            "server": file_data["server"],
            "hash": file_data["hash"],
            "access_token": token,
            "v": "5.199",
        },
        timeout=30,
    )
    save_response.raise_for_status()
    save_data = save_response.json()
    if "error" in save_data:
        raise Exception(f"VK API error (photos.saveWallPhoto): {save_data['error']}")

    photo = save_data["response"][0]
    return f"photo{photo['owner_id']}_{photo['id']}"


def publish_vk(text, image_path=None):
    token = os.getenv("VK_ACCESS_TOKEN")
    group_id = os.getenv("VK_GROUP_ID")
    if not token or not group_id:
        raise ValueError("VK_ACCESS_TOKEN или VK_GROUP_ID не заданы в .env")

    attachments = None
    if image_path and os.path.exists(image_path):
        attachments = upload_vk_photo(image_path, group_id, token)

    url = "https://api.vk.com/method/wall.post"
    payload = {
        "owner_id": f"-{group_id}",
        "from_group": 1,
        "message": text,
        "access_token": token,
        "v": "5.199",
    }
    if attachments:
        payload["attachments"] = attachments

    response = requests.post(url, data=payload, timeout=30)
    response.raise_for_status()
    data = response.json()
    if "error" in data:
        raise Exception(f"VK API error: {data['error']}")
    return data


def mark_published(path):
    post = load_post(path)
    post["published_at"] = datetime.now().isoformat()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(post, f, ensure_ascii=False, indent=2)


def publish_post(path):
    """Publish a single post JSON to Telegram and VK."""
    print(f"Найден файл: {path}")
    post = load_post(path)

    if post.get("published_at"):
        print(f"Файл уже опубликован: {post['published_at']}")
        return

    telegram_text = post.get("platforms", {}).get("telegram", {}).get("content")
    vk_text = post.get("platforms", {}).get("vk", {}).get("content")

    if not telegram_text or not vk_text:
        raise ValueError("В JSON отсутствуют platforms.telegram.content или platforms.vk.content")

    # Validate tokens before posting to avoid partial publications
    ok, err = check_telegram_token()
    if not ok:
        raise Exception(err)

    ensure_vk_token_fresh()

    ok, err = check_vk_token()
    if not ok:
        raise Exception(err)

    image_path = post.get("image_path")
    if image_path:
        print(f"Изображение найдено: {image_path}")
    else:
        print("Изображение не найден в JSON, публикуем только текст.")

    print("Публикация в Telegram...")
    publish_telegram(telegram_text, image_path)
    print("Публикация в VK...")
    publish_vk(vk_text, image_path)

    mark_published(path)
    print("Готово. Пост опубликован в Telegram и VK.")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Publish hypno posts to Telegram and VK")
    parser.add_argument("--post", help="Path to a specific post JSON to publish")
    args = parser.parse_args()

    if args.post:
        publish_post(args.post)
    else:
        latest = get_latest_post()
        if not latest:
            print("Нет JSON-файлов в /posts")
            return
        publish_post(latest)


if __name__ == "__main__":
    main()
