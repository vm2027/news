#!/usr/bin/env python3
"""
query_summary.py — TEMPORARY diagnostic build.

Finds "phantom" rows in the Postgres articles table: rows logged by a
past fetch (topic, origin, url) that no longer have a matching markdown
file in obsidian/Obsedian_R/<topic>/ -- i.e. articles that were fetched,
saved, logged to the DB, and later removed from the file archive by a
duplicate-cleanup PR. db.record_article() logs at save time and is never
updated or deleted when a file is later removed, so the DB total only
ever grows, while the file-based count reflects only what currently
exists -- this script quantifies exactly how much of that gap is
explained by known cleanups vs. something else.

This is a one-off investigation, not permanent tooling; the original
read-only summary script will be restored after this runs.
"""

import os
import sys
from datetime import timezone
from pathlib import Path

TOPICS = ["el-salvador", "finance-insurance"]


def _utc(dt) -> str:
    if dt is None:
        return ""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def load_local_urls() -> dict[str, set[str]]:
    """topic -> set of article URLs currently present in the file archive."""
    urls: dict[str, set[str]] = {}
    for topic in TOPICS:
        s = set()
        base = Path("obsidian/Obsedian_R") / topic
        for f in base.glob("*.md"):
            text = f.read_text(encoding="utf-8")
            for line in text.splitlines():
                if line.startswith("url:"):
                    s.add(line.split(":", 1)[1].strip())
                    break
        urls[topic] = s
    return urls


def main() -> None:
    dsn = os.environ.get("DATABASE_URL", "")
    if not dsn:
        print("DATABASE_URL is not set -- nothing to report.", file=sys.stderr)
        sys.exit(1)

    import psycopg

    try:
        conn = psycopg.connect(dsn, connect_timeout=10)
    except Exception as exc:  # noqa: BLE001
        print(f"Could not connect: {type(exc).__name__}", file=sys.stderr)
        sys.exit(1)

    try:
        local_urls = load_local_urls()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT topic, origin, title, url, published_date, fetched_at
                FROM articles
                WHERE fetched_at >= '2026-09-02'
                ORDER BY topic, origin, fetched_at
                """
            )
            rows = cur.fetchall()

        print(f"Total DB rows since 2026-09-02: {len(rows)}")

        phantom = [r for r in rows if r[3] not in local_urls.get(r[0], set())]
        print(f"Phantom rows (in DB, no matching file): {len(phantom)}\n")
        for topic, origin, title, url, pub, fetched in phantom:
            print(f"  [{topic}/{origin}] published={pub} fetched={_utc(fetched)}")
            print(f"    title: {title}")
            print(f"    url:   {url}")
    except Exception as exc:  # noqa: BLE001
        print(f"Query failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
