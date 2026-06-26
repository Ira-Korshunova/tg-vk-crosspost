"""
Refresh VK access token using refresh_token via VK ID OAuth 2.1.

Reads from .env:
    VK_CLIENT_ID
    VK_REFRESH_TOKEN
    VK_DEVICE_ID

Updates in .env:
    VK_ACCESS_TOKEN
    VK_REFRESH_TOKEN (if a new one is returned)
"""

import os
import re
import requests
from dotenv import load_dotenv

load_dotenv()

ENV_PATH = "/Users/irina/Desktop/claud_mod_3_2/.env"
TOKEN_URL = "https://id.vk.com/oauth2/auth"


def refresh_vk_token():
    client_id = os.getenv("VK_CLIENT_ID")
    refresh_token = os.getenv("VK_REFRESH_TOKEN")
    device_id = os.getenv("VK_DEVICE_ID")

    if not client_id or not refresh_token or not device_id:
        print("VK_CLIENT_ID, VK_REFRESH_TOKEN или VK_DEVICE_ID не заданы в .env")
        return False

    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "device_id": device_id,
    }

    response = requests.post(
        TOKEN_URL,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()

    if "access_token" not in data:
        print(f"Не удалось обновить токен: {data}")
        return False

    new_access_token = data["access_token"]
    new_refresh_token = data.get("refresh_token", refresh_token)

    update_env("VK_ACCESS_TOKEN", new_access_token)
    update_env("VK_REFRESH_TOKEN", new_refresh_token)

    print("VK access_token обновлён.")
    return True


def update_env(key, value):
    """Update a single key in .env file."""
    if not os.path.exists(ENV_PATH):
        with open(ENV_PATH, "w", encoding="utf-8") as f:
            f.write(f"{key}={value}\n")
        return

    with open(ENV_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    if pattern.search(content):
        content = pattern.sub(f"{key}={value}", content)
    else:
        content += f"\n{key}={value}\n"

    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write(content)

    # Reload in-memory .env
    os.environ[key] = value


if __name__ == "__main__":
    refresh_vk_token()
