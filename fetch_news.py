#!/usr/bin/env python3
"""
fetch_news.py — RSS news aggregator with Obsidian markdown output.

Usage:
    python fetch_news.py <topic>

The <topic> must match a file in topics/<topic>.md that lists RSS feed URLs.
Output is saved to obsidian/<topic>/ as Obsidian-ready markdown files.
"""

import argparse
import os
import re
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path

import feedparser
import requests
from slugify import slugify

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent
TOPICS_DIR = ROOT / "topics"
OBSIDIAN_DIR = ROOT / "obsidian"

# ---------------------------------------------------------------------------
# HTTP headers — some feeds block bare feedparser user-agents
# ---------------------------------------------------------------------------
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; NewsAggregator/1.0; "
        "+https://github.com/vic/news)"
    )
}

# Maximum articles to save per feed (avoids flooding vault on first run)
MAX_ARTICLES_PER_FEED = 5

# ---------------------------------------------------------------------------
# Built-in feed definitions (used as fallback when no topics/<topic>.md exists)
# ---------------------------------------------------------------------------
BUILT_IN_FEEDS: dict[str, list[str]] = {
    "el-salvador": [
        "https://feeds.reuters.com/reuters/worldNews",
        "https://feeds.bbci.co.uk/news/world/latin_america/rss.xml",
        "https://rss.app/feeds/9KZ8wO6K1X5QcGvM.xml",
        "https://www.france24.com/en/americas/rss",
        "https://apnews.com/rss",
    ],
    "finance-insurance": [
        "https://feeds.reuters.com/reuters/businessNews",
        "https://feeds.bloomberg.com/markets/news.rss",
        "https://feeds.content.dowjones.io/public/rss/mw_topstories",
        "https://www.insurancejournal.com/feeds/news.xml",
        "https://www.insurancebusinessmag.com/rss/news",
        "https://riskandinsurance.com/feed/",
    ],
}


# ---------------------------------------------------------------------------
# Topic loader
# ---------------------------------------------------------------------------

def load_topic(topic: str) -> list[str]:
    """
    Read topics/<topic>.md and return a list of RSS feed URLs.

    The file is expected to have an '## RSS Feeds' section with one URL per line.
    Lines that are blank or start with '#' are ignored.
    """
    topic_file = TOPICS_DIR / f"{topic}.md"
    if not topic_file.exists():
        if topic in BUILT_IN_FEEDS:
            print(f"[INFO] No topic file found for '{topic}'; using built-in feed list.")
            return BUILT_IN_FEEDS[topic]
        print(f"[ERROR] Topic file not found: {topic_file}", file=sys.stderr)
        print(
            f"  Create {topic_file} with an '## RSS Feeds' section listing feed URLs.",
            file=sys.stderr,
        )
        sys.exit(1)

    content = topic_file.read_text(encoding="utf-8")

    # Find the RSS Feeds section and extract URLs
    in_feeds_section = False
    urls: list[str] = []

    for line in content.splitlines():
        stripped = line.strip()
        if re.match(r"^#+\s*RSS Feeds", stripped, re.IGNORECASE):
            in_feeds_section = True
            continue
        if in_feeds_section:
            # Stop at next heading
            if stripped.startswith("#"):
                break
            if stripped and not stripped.startswith("#"):
                urls.append(stripped)

    if not urls:
        print(
            f"[ERROR] No RSS feed URLs found in {topic_file}. "
            "Add them under an '## RSS Feeds' heading.",
            file=sys.stderr,
        )
        sys.exit(1)

    return urls


# ---------------------------------------------------------------------------
# Feed fetching
# ---------------------------------------------------------------------------

def fetch_feed(url: str) -> feedparser.FeedParserDict | None:
    """Fetch and parse a single RSS/Atom feed. Returns None on failure."""
    try:
        # feedparser can use a pre-fetched response so we can pass custom headers
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        feed = feedparser.parse(response.content)
        if feed.bozo and not feed.entries:
            print(f"  [WARN] Feed parse issue for {url}: {feed.bozo_exception}")
            return None
        return feed
    except requests.RequestException as exc:
        print(f"  [WARN] Could not fetch {url}: {exc}")
        return None


# ---------------------------------------------------------------------------
# Markdown generation
# ---------------------------------------------------------------------------

def entry_to_markdown(entry: feedparser.FeedParserDict, topic: str, source_name: str) -> tuple[str, str]:
    """
    Convert a feed entry to (filename, markdown_content).

    The markdown uses YAML frontmatter compatible with Obsidian.
    """
    # --- Title ---
    title = entry.get("title", "Untitled").strip()
    # Remove any embedded newlines from titles
    title = " ".join(title.splitlines())

    # --- Date ---
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        pub_dt = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
    elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
        pub_dt = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
    else:
        pub_dt = datetime.now(timezone.utc)

    date_str = pub_dt.strftime("%Y-%m-%d")
    datetime_str = pub_dt.strftime("%Y-%m-%d %H:%M UTC")

    # --- URL ---
    url = entry.get("link", "")

    # --- Summary ---
    summary_raw = entry.get("summary", entry.get("description", ""))
    # Strip HTML tags from summary
    summary = re.sub(r"<[^>]+>", "", summary_raw).strip()
    # Collapse whitespace
    summary = re.sub(r"\s+", " ", summary)
    # Wrap nicely
    summary = textwrap.fill(summary, width=100) if summary else "_No summary available._"

    # --- Author ---
    author = entry.get("author", "").strip()

    # --- Escape title for YAML (use double-quoted string) ---
    yaml_title = title.replace('"', '\\"')

    # --- YAML frontmatter ---
    frontmatter_lines = [
        "---",
        f'title: "{yaml_title}"',
        f"date: {date_str}",
        f"datetime: {datetime_str}",
        f"source: {source_name}",
        f"url: {url}",
        f"tags:",
        f"  - {topic}",
        f"  - news",
    ]
    if author:
        frontmatter_lines.append(f"author: {author}")
    frontmatter_lines.append("---")

    frontmatter = "\n".join(frontmatter_lines)

    # --- Body ---
    body_parts = [
        f"# {title}",
        "",
        f"> **Source:** {source_name}  ",
        f"> **Published:** {datetime_str}  ",
        f"> **URL:** {url}",
        "",
        "## Summary",
        "",
        summary,
        "",
    ]
    if url:
        body_parts += [
            "## Read More",
            "",
            f"[Read the full article →]({url})",
            "",
        ]

    body = "\n".join(body_parts)
    content = frontmatter + "\n\n" + body

    # --- Filename ---
    slug = slugify(title, max_length=60, separator="-")
    filename = f"{date_str}_{slug}.md"

    return filename, content


# ---------------------------------------------------------------------------
# Output writer
# ---------------------------------------------------------------------------

def save_article(topic: str, filename: str, content: str) -> Path:
    """Write article markdown to obsidian/<topic>/<filename>. Returns the path."""
    out_dir = OBSIDIAN_DIR / topic
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / filename
    out_path.write_text(content, encoding="utf-8")
    return out_path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch latest news via RSS and save as Obsidian markdown."
    )
    parser.add_argument(
        "topic",
        help="Topic slug matching a file in topics/<topic>.md (e.g. el-salvador)",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=MAX_ARTICLES_PER_FEED,
        metavar="N",
        help=f"Max articles to save per feed (default: {MAX_ARTICLES_PER_FEED})",
    )
    args = parser.parse_args()

    topic = args.topic.lower()
    feed_urls = load_topic(topic)

    print(f"Topic : {topic}")
    print(f"Feeds : {len(feed_urls)}")
    print(f"Max   : {args.max} articles per feed")
    print()

    total_saved = 0
    total_skipped = 0

    for url in feed_urls:
        print(f"Fetching: {url}")
        feed = fetch_feed(url)
        if feed is None:
            print("  → Skipped (fetch failed)\n")
            continue

        source_name = feed.feed.get("title", url)
        entries = feed.entries[: args.max]
        print(f"  Source : {source_name}")
        print(f"  Found  : {len(feed.entries)} entries, processing {len(entries)}")

        for entry in entries:
            try:
                filename, content = entry_to_markdown(entry, topic, source_name)
                out_path = save_article(topic, filename, content)
                print(f"  ✓ {out_path.name}")
                total_saved += 1
            except Exception as exc:  # noqa: BLE001
                print(f"  ✗ Error processing entry: {exc}")
                total_skipped += 1

        print()

    print(f"Done. {total_saved} articles saved, {total_skipped} errors.")
    print(f"Output: {OBSIDIAN_DIR / topic}/")


if __name__ == "__main__":
    main()
