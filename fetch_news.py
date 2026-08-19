#!/usr/bin/env python3
"""
fetch_news.py — RSS news aggregator with Obsidian markdown output.

Usage:
    python fetch_news.py <topic>

The <topic> must match a file in topics/<topic>.md that lists RSS feed URLs.
Output is saved to obsidian/<topic>/ as Obsidian-ready markdown files.
"""

# Runtime Python version guard — must be before any PEP 585/604 annotations are parsed
import sys
if sys.version_info < (3, 10):
    sys.exit(
        "This project requires Python 3.10 or newer. Please run with Python 3.10+ or update the code to remove newer type annotations."
    )

import argparse
import hashlib
import logging
import re
import textwrap
import time
from datetime import datetime, timezone
from pathlib import Path

import feedparser
import requests
from slugify import slugify

# ---------------------------------------------------------------------------
# Basic logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("news")

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
        "Mozilla/5.0 (compatible; NewsAggregator/1.0; +https://github.com/vm2027/news)"
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
            log.info("No topic file found for '%s'; using built-in feed list.", topic)
            return BUILT_IN_FEEDS[topic]
        log.error("Topic file not found: %s", topic_file)
        log.error(
            "  Create %s with an '## RSS Feeds' section listing feed URLs.", topic_file
        )
        raise SystemExit(1)

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
        log.error(
            "No RSS feed URLs found in %s. Add them under an '## RSS Feeds' heading.",
            topic_file,
        )
        raise SystemExit(1)

    return urls


# ---------------------------------------------------------------------------
# Feed fetching with retries
# ---------------------------------------------------------------------------

def fetch_feed(url: str, retries: int = 3, backoff: float = 1.0) -> feedparser.FeedParserDict | None:
    """Fetch and parse a single RSS/Atom feed. Returns None on failure."""
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, headers=HEADERS, timeout=15)
            response.raise_for_status()
            feed = feedparser.parse(response.content)
            if feed.bozo and not feed.entries:
                log.warning("Feed parse issue for %s: %s", url, getattr(feed, "bozo_exception", ""))
                return None
            return feed
        except requests.RequestException as exc:
            last_exc = exc
            log.warning("Attempt %d: Could not fetch %s: %s", attempt, url, exc)
            if attempt < retries:
                time.sleep(backoff * (2 ** (attempt - 1)))
    log.error("All attempts failed fetching %s: %s", url, last_exc)
    return None


# ---------------------------------------------------------------------------
# Markdown generation
# ---------------------------------------------------------------------------

def entry_to_markdown(entry: feedparser.FeedParserDict, topic: str, source_name: str) -> tuple[str, str, str]:
    """
    Convert a feed entry to (filename, markdown_content, url).

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

    # --- Filename: include short URL hash to avoid collisions ---
    slug = slugify(title, max_length=60, separator="-")
    if url:
        short = hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]
        filename = f"{date_str}_{slug}_{short}.md"
    else:
        filename = f"{date_str}_{slug}.md"

    return filename, content, url


# ---------------------------------------------------------------------------
# Output writer with duplicate check
# ---------------------------------------------------------------------------

def article_exists(topic: str, url: str) -> bool:
    """Return True if an article with the same URL already exists in obsidian/<topic>/."""
    out_dir = OBSIDIAN_DIR / topic
    if not out_dir.exists():
        return False
    for p in out_dir.glob("*.md"):
        try:
            txt = p.read_text(encoding="utf-8")
            if f"url: {url}" in txt:
                return True
        except Exception:
            continue
    return False


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

    log.info("Topic : %s", topic)
    log.info("Feeds : %d", len(feed_urls))
    log.info("Max   : %d articles per feed", args.max)
    log.info("")

    total_saved = 0
    total_skipped = 0

    for url in feed_urls:
        log.info("Fetching: %s", url)
        feed = fetch_feed(url)
        if feed is None:
            log.info("  → Skipped (fetch failed)\n")
            continue

        source_name = feed.feed.get("title", url)
        entries = feed.entries[: args.max]
        log.info("  Source : %s", source_name)
        log.info("  Found  : %d entries, processing %d", len(feed.entries), len(entries))

        for entry in entries:
            try:
                filename, content, article_url = entry_to_markdown(entry, topic, source_name)
                if article_url and article_exists(topic, article_url):
                    log.info("  → Skipped (already saved): %s", article_url)
                    total_skipped += 1
                    continue
                out_path = save_article(topic, filename, content)
                log.info("  ✓ %s", out_path.name)
                total_saved += 1
            except Exception as exc:  # noqa: BLE001
                log.error("  ✗ Error processing entry: %s", exc)
                total_skipped += 1

        log.info("")

    log.info("Done. %d articles saved, %d errors.", total_saved, total_skipped)
    log.info("Output: %s", OBSIDIAN_DIR / topic)


if __name__ == "__main__":
    main()
