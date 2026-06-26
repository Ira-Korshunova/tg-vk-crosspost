"""
Exchange authorization code for access_token and refresh_token.

Usage:
    python3 vk_exchange_code.py --code КОД --device_id УСТРОЙСТВО --verifier VERIFIER --client_id CLIENT_ID

Then copy the printed tokens into .env.
"""

import argparse
import requests

TOKEN_URL = "https://id.vk.com/oauth2/auth"


def exchange_code(code, device_id, code_verifier, client_id, redirect_uri="https://oauth.vk.com/blank.html"):
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "device_id": device_id,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "code_verifier": code_verifier,
        "state": "hypno-bot-state",
    }

    response = requests.post(
        TOKEN_URL,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--code", required=True)
    parser.add_argument("--device_id", required=True)
    parser.add_argument("--verifier", required=True)
    parser.add_argument("--client_id", required=True)
    args = parser.parse_args()

    data = exchange_code(args.code, args.device_id, args.verifier, args.client_id)
    print("\nОтвет VK ID:")
    print(data)

    if "access_token" in data:
        print("\nДобавьте в .env:")
        print(f"VK_ACCESS_TOKEN={data['access_token']}")
        print(f"VK_REFRESH_TOKEN={data.get('refresh_token', '')}")
        print(f"VK_DEVICE_ID={args.device_id}")
        print(f"VK_CLIENT_ID={args.client_id}")
    else:
        print("\naccess_token не получен. Проверьте ошибку выше.")


if __name__ == "__main__":
    main()
