import os
import json
import time
import argparse
import requests
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DEFAULT_POSTS_DIR = str(BASE_DIR / "posts")


def generate_image(prompt, api_key, base_url, model, size="1280*1280", n=1):
    """Generate image via DashScope Wan 2.6 multimodal-generation API and return bytes."""
    if not api_key:
        raise ValueError("QWEN_API_KEY не задан в .env")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable",
    }

    payload = {
        "model": model,
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"text": prompt}
                    ],
                }
            ]
        },
        "parameters": {
            "size": size,
            "n": n,
            "watermark": False,
        },
    }

    url = f"{base_url}/api/v1/services/aigc/image-generation/generation"
    response = requests.post(url, headers=headers, json=payload, timeout=60)
    response.raise_for_status()
    data = response.json()

    if "output" not in data or "task_id" not in data["output"]:
        raise Exception(f"Unexpected response: {data}")

    task_id = data["output"]["task_id"]
    return wait_for_result(task_id, api_key, base_url)


def wait_for_result(task_id, api_key, base_url, max_attempts=60, delay=5):
    """Poll async task until image is ready."""
    status_url = f"{base_url}/api/v1/tasks/{task_id}"
    headers = {"Authorization": f"Bearer {api_key}"}

    for attempt in range(max_attempts):
        response = requests.get(status_url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        status = data.get("output", {}).get("task_status", "UNKNOWN")
        if status == "SUCCEEDED":
            img_url = extract_image_url(data)
            if not img_url:
                raise Exception(f"No image url in succeeded task: {data}")
            img_response = requests.get(img_url, timeout=60)
            img_response.raise_for_status()
            return img_response.content
        elif status in ("FAILED", "ERROR"):
            raise Exception(f"Task failed: {data}")

        print(f"Ожидание генерации... попытка {attempt + 1}/{max_attempts}, статус: {status}")
        time.sleep(delay)

    raise Exception(f"Timeout waiting for image generation task {task_id}")


def save_image_for_post(json_path, posts_dir=DEFAULT_POSTS_DIR):
    """Read a post JSON, generate image from its prompt, save as PNG next to it."""
    json_path = Path(json_path)
    with open(json_path, "r", encoding="utf-8") as f:
        post = json.load(f)

    prompt = post.get("image_prompt")
    if not prompt:
        raise ValueError(f"image_prompt не найден в {json_path}")

    api_key = os.getenv("QWEN_API_KEY")
    base_url = os.getenv("BASE_URL", "https://dashscope-intl.aliyuncs.com")
    model = os.getenv("IMAGE_MODEL", "wan2.6-t2i")

    image_bytes = generate_image(prompt, api_key, base_url, model)

    image_path = json_path.with_suffix(".png")
    with open(image_path, "wb") as f:
        f.write(image_bytes)

    # Update JSON with image_path
    post["image_path"] = str(image_path)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(post, f, ensure_ascii=False, indent=2)

    return image_path


def extract_image_url(data):
    """Extract image URL from various DashScope response shapes."""
    output = data.get("output", {})

    # Legacy shape
    for key in ("results", "image_results"):
        results = output.get(key, [])
        if results and results[0].get("url"):
            return results[0]["url"]

    # Wan 2.6 chat-style shape: output.choices[*].message.content[*].image
    for choice in output.get("choices", []):
        message = choice.get("message", {})
        for item in message.get("content", []):
            if item.get("type") == "image" and item.get("image"):
                return item["image"]
            if item.get("url"):
                return item["url"]

    return None


def main():
    parser = argparse.ArgumentParser(description="Generate image for a post JSON via Qwen/DashScope API")
    parser.add_argument("json_path", nargs="?", help="Path to post JSON file")
    args = parser.parse_args()

    if args.json_path:
        json_path = args.json_path
    else:
        files = sorted(
            Path(DEFAULT_POSTS_DIR).glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not files:
            raise FileNotFoundError(f"Нет JSON-файлов в {DEFAULT_POSTS_DIR}")
        json_path = files[0]

    image_path = save_image_for_post(json_path)
    print(f"Изображение сохранено: {image_path}")


if __name__ == "__main__":
    main()
