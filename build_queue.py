#!/usr/bin/env python3
"""
Build queue.json from a simple links.txt file.

links.txt format:
  - one URL per line
  - empty lines and lines starting with # are ignored

The script asks (or uses defaults):
  - generation time (default: today 22:00)
  - first publish time (default: tomorrow 10:00)
  - interval between posts (default: 60 minutes)

Run:
  python3 /Users/irina/Desktop/claud_mod_3_2/build_queue.py
"""

import os
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_DIR = "/Users/irina/Desktop/claud_mod_3_2"
DEFAULT_LINKS = os.path.join(PROJECT_DIR, "links.txt")
DEFAULT_QUEUE = os.path.join(PROJECT_DIR, "queue.json")


def parse_links(path):
    links = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            links.append(line)
    return links


def build_queue(links, generate_at, first_publish_at, interval_minutes):
    items = []
    publish_at = first_publish_at
    for i, url in enumerate(links, 1):
        items.append({
            "id": f"post-{i}",
            "url": url,
            "generate_at": generate_at.isoformat(),
            "publish_at": publish_at.isoformat(),
            "status": "pending",
            "generated_at": None,
            "published_at": None,
            "post_path": None,
        })
        publish_at += timedelta(minutes=interval_minutes)

    return {
        "schema_version": "hypno-queue/v2",
        "items": items,
    }


def main():
    parser = argparse.ArgumentParser(description="Build queue.json from links.txt")
    parser.add_argument("--links", default=DEFAULT_LINKS, help="Path to links.txt")
    parser.add_argument("--queue", default=DEFAULT_QUEUE, help="Path to queue.json")
    parser.add_argument("--generate", help="Generation time ISO (default: today 22:00)")
    parser.add_argument("--first-publish", help="First publish time ISO (default: tomorrow 10:00)")
    parser.add_argument("--interval", type=int, default=60, help="Minutes between posts (default: 60)")
    args = parser.parse_args()

    links = parse_links(args.links)
    if not links:
        print(f"No links found in {args.links}")
        return

    now = datetime.now()
    generate_at = datetime.fromisoformat(args.generate) if args.generate else now.replace(hour=22, minute=0, second=0, microsecond=0)
    if args.first_publish:
        first_publish_at = datetime.fromisoformat(args.first_publish)
    else:
        first_publish_at = (now + timedelta(days=1)).replace(hour=10, minute=0, second=0, microsecond=0)

    data = build_queue(links, generate_at, first_publish_at, args.interval)

    with open(args.queue, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Built {args.queue} with {len(links)} item(s):")
    for item in data["items"]:
        print(f"  {item['id']}: generate {item['generate_at']} -> publish {item['publish_at']} -> {item['url']}")


if __name__ == "__main__":
    main()
