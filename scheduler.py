#!/usr/bin/env python3
"""
Queue scheduler for the hypno content factory.

Two modes:
  --mode generate  : checks queue.json and reminds (or tries) to generate pending posts.
  --mode publish   : checks queue.json and auto-publishes generated posts when publish_at arrives.

Recommended schedule:
  22:00 every day  -> python3 scheduler.py --mode generate
  every 10 minutes  -> python3 scheduler.py --mode publish
"""

import os
import json
import time
import argparse
import subprocess
from datetime import datetime
from pathlib import Path

PROJECT_DIR = "/Users/irina/Desktop/claud_mod_3_2"
DEFAULT_QUEUE = os.path.join(PROJECT_DIR, "queue.json")


def load_queue(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_queue(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def send_notification(title, message):
    """Send a macOS desktop notification via osascript."""
    try:
        script = f'display notification "{message}" with title "{title}"'
        subprocess.run(["osascript", "-e", script], timeout=15, check=True)
    except Exception as e:
        print(f"Could not send notification: {e}")


def try_execute_generate():
    """Try to launch Claude Code with /generate-queue. Experimental."""
    try:
        command = [
            "claude",
            "--project", PROJECT_DIR,
            "--message", "/generate-queue",
        ]
        subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception as e:
        print(f"Could not auto-execute generate-queue: {e}")
        return False


def check_generate(queue_path, auto_execute=False):
    data = load_queue(queue_path)
    now = datetime.now()
    pending = [
        item for item in data.get("items", [])
        if item.get("status") == "pending"
        and item.get("generate_at")
        and datetime.fromisoformat(item["generate_at"]) <= now
    ]

    if not pending:
        print("No pending items ready for generation.")
        return

    urls = ", ".join(item["url"] for item in pending)
    print(f"[{now.isoformat()}] {len(pending)} posts ready for generation: {urls}")

    if auto_execute:
        if try_execute_generate():
            print("Launched Claude Code with /generate-queue.")
        else:
            send_notification(
                "Hypno Factory: generate posts",
                "Run /generate-queue to generate tomorrow's posts",
            )
    else:
        send_notification(
            "Hypno Factory: generate posts",
            "Run /generate-queue to generate tomorrow's posts",
        )


def publish_single_post(post_path, queue_item=None, queue_path=None, data=None):
    """Publish one post via publish.py and update queue if provided."""
    print(f"Publishing {post_path}...")
    result = subprocess.run(
        ["python3", os.path.join(PROJECT_DIR, "publish.py"), "--post", post_path],
        capture_output=True,
        text=True,
        timeout=120,
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)

    if result.returncode == 0 and queue_item and data:
        queue_item["status"] = "published"
        queue_item["published_at"] = datetime.now().isoformat()
        save_queue(queue_path, data)
        send_notification(
            "Hypno Factory: published",
            f"Posted {queue_item.get('id')} at {queue_item.get('publish_at')}",
        )
    return result.returncode == 0


def check_publish(queue_path):
    data = load_queue(queue_path)
    now = datetime.now()
    updated = False

    for item in data.get("items", []):
        if item.get("status") != "generated":
            continue

        publish_at = item.get("publish_at")
        post_path = item.get("post_path")
        if not publish_at or not post_path:
            continue

        if datetime.fromisoformat(publish_at) <= now:
            print(f"[{now.isoformat()}] Publishing due item: {item.get('id')}")
            if publish_single_post(post_path, item, queue_path, data):
                updated = True

    if not updated:
        print("No posts due for publishing.")


def main():
    parser = argparse.ArgumentParser(description="Hypno content factory scheduler")
    parser.add_argument("--queue", default=DEFAULT_QUEUE, help="Path to queue.json")
    parser.add_argument("--mode", choices=["generate", "publish"], required=True,
                        help="Mode: generate reminders or publish due posts")
    parser.add_argument("--interval", type=int, default=0,
                        help="Run continuously every N minutes (0 = run once)")
    parser.add_argument("--execute", action="store_true",
                        help="Try to auto-execute /generate-queue (experimental)")
    args = parser.parse_args()

    if args.mode == "generate":
        if args.interval > 0:
            print(f"Generate scheduler running every {args.interval} minutes. Press Ctrl+C to stop.")
            while True:
                check_generate(args.queue, auto_execute=args.execute)
                time.sleep(args.interval * 60)
        else:
            check_generate(args.queue, auto_execute=args.execute)

    elif args.mode == "publish":
        if args.interval > 0:
            print(f"Publish scheduler running every {args.interval} minutes. Press Ctrl+C to stop.")
            while True:
                check_publish(args.queue)
                time.sleep(args.interval * 60)
        else:
            check_publish(args.queue)


if __name__ == "__main__":
    main()
