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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

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
OBSIDIAN_DIR = ROOT / "obsidian" / "Obsedian_R"

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
# Perplexity API config
# Set PERPLEXITY_TOPICS to route those topics through Perplexity in addition
# to (or instead of) RSS. Topics listed in PERPLEXITY_SUPPLEMENTS_RSS run
# Perplexity *and then* still fetch their RSS feeds; topics in
# PERPLEXITY_TOPICS but not in PERPLEXITY_SUPPLEMENTS_RSS use Perplexity only.
# The API key is read from the PERPLEXITY_API_KEY environment variable.
# ---------------------------------------------------------------------------
import os
import json

PERPLEXITY_TOPICS: list[str] = ["el-salvador", "finance-insurance"]
PERPLEXITY_SUPPLEMENTS_RSS: list[str] = ["finance-insurance"]
PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"
PERPLEXITY_MODEL = "sonar"
MAX_PERPLEXITY_ARTICLES = 10

# Perplexity is asked for stories from "the past 48 hours" but the sonar model
# sometimes returns older stories it turned up during search. Allow a little
# slack for timezone/model imprecision, but discard anything clearly stale.
PERPLEXITY_MAX_ARTICLE_AGE_DAYS = 4

PERPLEXITY_QUERIES: dict[str, str] = {
    "el-salvador": "El Salvador news politics economy security Bukele",
    "finance-insurance": "finance insurance industry news markets",
}


class PerplexityFetchError(Exception):
    """Raised when the Perplexity API call itself fails (auth, network, bad JSON)."""


def looks_like_article_url(url: str) -> bool:
    """
    Heuristic check that a URL points to a specific article rather than a
    section/category/homepage. Perplexity sometimes returns pages like
    bloomberg.com/markets or reuters.com/legal/insurance/ as if they were
    dated articles, regardless of prompt instructions - this is a
    code-level backstop rather than relying on the model alone.

    A URL counts as an article if its path contains a year (a dated
    article), or its final path segment is a long, specific slug rather
    than a short generic category name.
    """
    try:
        path = urlparse(url).path.strip("/")
    except ValueError:
        return False
    if not path:
        return False
    segments = [s for s in path.split("/") if s]
    if any(re.fullmatch(r"(19|20)\d{2}", seg) for seg in segments):
        return True
    if len(path) > 40:
        return True
    last_segment_words = re.split(r"[-_]", segments[-1])
    return len([w for w in last_segment_words if w]) >= 4


def fetch_perplexity_articles(topic: str) -> list[dict]:
    """
    Fetch latest news for a topic via Perplexity's sonar API.
    Returns a list of article dicts with title, url, date, source, summary,
    filtered to articles within PERPLEXITY_MAX_ARTICLE_AGE_DAYS.

    Raises PerplexityFetchError if the API call itself fails (missing key,
    network/HTTP error, or an unparsable response) so callers can treat it
    as a hard failure. An empty result set is not an error - it means no
    fresh articles were found - and returns an empty list instead.
    """
    api_key = os.environ.get("PERPLEXITY_API_KEY", "")
    if not api_key:
        raise PerplexityFetchError("PERPLEXITY_API_KEY not set")

    query = PERPLEXITY_QUERIES.get(topic, f"latest news {topic}")
    prompt = (
        f"Search for the {MAX_PERPLEXITY_ARTICLES} most important individual news "
        f"articles about {query} published in the past 48 hours.\n\n"
        "Each result MUST be a single specific news article with its own headline "
        "and a URL that links directly to that article. Do NOT include section, "
        "category, or markets/homepage pages (e.g. URLs like /markets, /news, "
        "/insurance/, or a site's front page) even if they list relevant "
        "headlines - only individual dated articles count. If you cannot find a "
        "direct article URL for a story, skip it rather than substituting a "
        "homepage or section URL.\n\n"
        "Return ONLY a JSON array (no other text) where each element has these fields:\n"
        "- title: the article's actual headline\n"
        "- url: direct link to that specific article\n"
        "- date: publication date as YYYY-MM-DD\n"
        "- source: publication name\n"
        "- summary: 2-3 sentence summary of that article's content\n\n"
        "Return valid JSON only."
    )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": PERPLEXITY_MODEL,
        "messages": [
            {"role": "system", "content": "You are a news research assistant. Always return valid JSON."},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 3000,
    }

    try:
        resp = requests.post(PERPLEXITY_API_URL, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()
        # Strip markdown code fences if present
        if content.startswith("```"):
            content = re.sub(r"^```[a-z]*\n?", "", content)
            content = re.sub(r"\n?```$", "", content)
        articles = json.loads(content)
    except json.JSONDecodeError as exc:
        raise PerplexityFetchError(f"Could not parse Perplexity JSON response: {exc}") from exc
    except requests.RequestException as exc:
        raise PerplexityFetchError(f"Perplexity API request failed: {exc}") from exc

    if not articles:
        log.warning("Perplexity returned no articles for '%s' (no fresh news, not an error)", topic)
        return []

    log.info("Perplexity returned %d articles for '%s' (pre-filter)", len(articles), topic)

    cutoff = datetime.now(timezone.utc).date() - timedelta(days=PERPLEXITY_MAX_ARTICLE_AGE_DAYS)
    fresh_articles = []
    for article in articles:
        date_str = str(article.get("date", "")).strip()
        try:
            article_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            log.warning("  → Discarding article with unparsable date %r: %s", date_str, article.get("title", "?"))
            continue
        if article_date < cutoff:
            log.warning(
                "  → Discarding stale article dated %s (older than %d days): %s",
                date_str, PERPLEXITY_MAX_ARTICLE_AGE_DAYS, article.get("title", "?"),
            )
            continue
        article_url = str(article.get("url", ""))
        if not looks_like_article_url(article_url):
            log.warning(
                "  → Discarding non-article URL (looks like a section/homepage page): %s (%s)",
                article_url, article.get("title", "?"),
            )
            continue
        fresh_articles.append(article)

    log.info(
        "Perplexity: %d/%d articles within the last %d days for '%s'",
        len(fresh_articles), len(articles), PERPLEXITY_MAX_ARTICLE_AGE_DAYS, topic,
    )
    return fresh_articles


def perplexity_article_to_markdown(article: dict, topic: str) -> tuple[str, str, str]:
    """Convert a Perplexity article dict to (filename, markdown_content, url)."""
    title = str(article.get("title", "Untitled")).strip()
    url = str(article.get("url", ""))
    date_str = str(article.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d")))
    source = str(article.get("source", "Perplexity"))
    summary = str(article.get("summary", "")).strip()

    yaml_title = title.replace('"', '\\"')
    frontmatter = "\n".join([
        "---",
        f'title: "{yaml_title}"',
        f"date: {date_str}",
        f"source: {source}",
        f"url: {url}",
        "tags:",
        f"  - {topic}",
        "  - news",
        "  - perplexity",
        "---",
    ])

    body = "\n".join([
        f"# {title}",
        "",
        f"> **Source:** {source}  ",
        f"> **Published:** {date_str}  ",
        f"> **URL:** {url}",
        "",
        "## Summary",
        "",
        summary,
        "",
        "## Read More",
        "",
        f"[Read the full article →]({url})",
        "",
    ])

    slug = slugify(title, max_length=60, separator="-")
    short = hashlib.sha1(url.encode()).hexdigest()[:8] if url else "000000"
    filename = f"{date_str}_{slug}_{short}.md"
    return filename, frontmatter + "\n\n" + body, url


# ---------------------------------------------------------------------------
# Per-topic keyword filters (case-insensitive).
# When a topic has keywords defined, an article must mention at least one
# keyword in its title or summary to be saved.  Topics without an entry here
# are saved without filtering (e.g. finance-insurance uses targeted feeds).
# ---------------------------------------------------------------------------
TOPIC_KEYWORDS: dict[str, list[str]] = {
    "el-salvador": [
        "el salvador",
        "salvadoran",
        "salvadorean",
        "salvadoreño",
        "bukele",
        "cecot",
        "san salvador",
        "nayib",
        "tps",          # Temporary Protected Status often tied to El Salvador
    ],
}

# ---------------------------------------------------------------------------
# Built-in feed definitions (used as fallback when no topics/<topic>.md exists)
# ---------------------------------------------------------------------------
BUILT_IN_FEEDS: dict[str, list[str]] = {
    "el-salvador": [
        # Targeted Latin America / Central America feeds
        "https://feeds.reuters.com/reuters/worldNews",
        "https://feeds.bbci.co.uk/news/world/latin_america/rss.xml",
        "https://rss.app/feeds/9KZ8wO6K1X5QcGvM.xml",
        "https://www.france24.com/en/americas/rss",
        "https://apnews.com/rss",
        # El Salvador local outlets (English)
        "https://www.elsalvadortimes.com/feed/",
        "https://elfaro.net/en/rss",
    ],
    "finance-insurance": [
        "https://www.cnbc.com/id/19836768/device/rss/rss.html",
        "https://feeds.bloomberg.com/markets/news.rss",
        "https://feeds.content.dowjones.io/public/rss/mw_topstories",
        "https://www.insurancejournal.com/feed/",
        "https://www.insurancebusinessmag.com/us/rss/",
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

    # ---------------------------------------------------------------------------
    # Perplexity path — replaces RSS for configured topics, or supplements it
    # for topics listed in PERPLEXITY_SUPPLEMENTS_RSS (both sources run).
    # ---------------------------------------------------------------------------
    if topic in PERPLEXITY_TOPICS:
        log.info("Using Perplexity API for topic '%s'", topic)
        try:
            articles = fetch_perplexity_articles(topic)
        except PerplexityFetchError as exc:
            log.error("Perplexity fetch failed for '%s': %s", topic, exc)
            sys.exit(1)
        for article in articles:
            try:
                filename, content, article_url = perplexity_article_to_markdown(article, topic)
                if article_url and article_exists(topic, article_url):
                    log.info("  → Skipped (already saved): %s", article_url)
                    total_skipped += 1
                    continue
                out_path = save_article(topic, filename, content)
                log.info("  ✓ %s", out_path.name)
                total_saved += 1
            except Exception as exc:
                log.error("  ✗ Error processing Perplexity article: %s", exc)
                total_skipped += 1
        log.info("Perplexity done. %d articles saved, %d skipped so far.", total_saved, total_skipped)
        if topic not in PERPLEXITY_SUPPLEMENTS_RSS:
            log.info("Done. %d articles saved, %d skipped.", total_saved, total_skipped)
            return
        log.info("Continuing to RSS feeds for '%s'...", topic)
        log.info("")

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

        keywords = [kw.lower() for kw in TOPIC_KEYWORDS.get(topic, [])]

        for entry in entries:
            try:
                filename, content, article_url = entry_to_markdown(entry, topic, source_name)

                # Keyword filter: skip articles that don't mention any topic keyword
                if keywords:
                    title_text = entry.get("title", "").lower()
                    summary_text = re.sub(r"<[^>]+>", "", entry.get("summary", entry.get("description", ""))).lower()
                    if not any(kw in title_text or kw in summary_text for kw in keywords):
                        log.info("  → Skipped (no keyword match): %s", entry.get("title", "?"))
                        total_skipped += 1
                        continue

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
