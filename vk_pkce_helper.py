"""
Helper to generate PKCE params and VK ID authorization URL.

Run this script, open the printed URL in a browser, authorize,
then copy `code` and `device_id` from the redirect URL.
Finally run vk_exchange_code.py with those values.
"""

import secrets
import hashlib
import base64
import urllib.parse


def generate_pkce():
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("utf-8")
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode("utf-8")
    return verifier, challenge


def build_auth_url(client_id, code_challenge, redirect_uri="https://oauth.vk.com/blank.html", state="hypno-bot-state"):
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "wall,photos,groups",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"https://id.vk.com/authorize?{urllib.parse.urlencode(params)}"


if __name__ == "__main__":
    client_id = input("Введите VK_CLIENT_ID: ").strip()
    verifier, challenge = generate_pkce()
    auth_url = build_auth_url(client_id, challenge)

    print("\nСохраните code_verifier:")
    print(verifier)
    print("\nОткройте эту ссылку в браузере:")
    print(auth_url)
    print("\nПосле авторизации скопируйте code и device_id из адресной строки.")
