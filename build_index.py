"""
build_index.py
Reads all markdown files in obsidian/<topic>/ and rebuilds index.html.
Run automatically by GitHub Actions after fetch_news.py.
"""

import html
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fetch_news import PERPLEXITY_MAX_ARTICLE_AGE_DAYS

OBSIDIAN_DIR = Path("obsidian") / "Obsedian_R"
OUTPUT_FILE = Path("index.html")
LAST_FETCH_FILE = OBSIDIAN_DIR / ".last_fetch"

TOPIC_LABELS = {
    "el-salvador": "🇸🇻 El Salvador",
    "finance-insurance": "💼 Finance & Insurance",
}

TOPIC_COLORS = {
    "el-salvador": "#003366",
    "finance-insurance": "#006633",
}


def parse_frontmatter(text):
    """Extract YAML frontmatter fields from a markdown file. List values
    (e.g. tags) are collected into a list under their key."""
    meta = {}
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        return meta, text
    fm = match.group(1)
    body = text[match.end():]
    current_list_key = None
    for line in fm.splitlines():
        stripped = line.strip()
        if stripped.startswith("- ") and current_list_key:
            meta.setdefault(current_list_key, []).append(stripped[2:].strip())
            continue
        if ":" in line:
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip().strip('"')
            if val:
                meta[key] = val
                current_list_key = None
            else:
                current_list_key = key
    return meta, body.strip()


ARTICLES_PER_TOPIC = 10

# Cap on how many of ARTICLES_PER_TOPIC's slots a Perplexity reservation can
# claim. Without a sub-cap, a topic that has accumulated more recent-enough
# Perplexity articles than ARTICLES_PER_TOPIC (routine now that a single
# fetch can save 7+ of them, see load_articles()) would reserve every slot
# and crowd RSS out entirely -- the mirror image of the original bug this
# reservation exists to prevent. Half keeps both sources represented.
PERPLEXITY_RESERVED_SLOTS = ARTICLES_PER_TOPIC // 2


def load_articles(topic):
    """Load markdown articles for a topic, newest first.

    RSS feeds publish far more articles per day than Perplexity does, so
    simply taking the newest ARTICLES_PER_TOPIC would let RSS crowd
    Perplexity-sourced articles out entirely on busy days. Reserve a slot
    for each Perplexity article dated within the last
    PERPLEXITY_MAX_ARTICLE_AGE_DAYS days (its volume is naturally small
    and bounded, unlike RSS), up to PERPLEXITY_RESERVED_SLOTS, so they
    aren't silently dropped, then fill the rest with the freshest
    remaining articles. Older or overflow Perplexity articles are still
    eligible to fill remaining slots on their own recency, same as RSS,
    so they don't pin stale Perplexity content ahead of fresh RSS, and
    the reservation itself is capped well below ARTICLES_PER_TOPIC so a
    busy Perplexity day can't crowd RSS out entirely either.

    Deliberately scoped to the same freshness window fetch_news.py
    itself uses to accept a Perplexity result (PERPLEXITY_MAX_ARTICLE_AGE_DAYS),
    not a single "most recent date": an RSS article's date comes from
    the feed entry's own published/updated timestamp
    (entry_to_markdown() in fetch_news.py), which for fast-moving feeds
    is usually the fetch day but isn't guaranteed to be. Perplexity's
    date is the article's true publish date, which is routinely a day
    (or more) behind the fetch day even for genuinely fresh results, and
    with PERPLEXITY_SEARCH_RECENCY_FILTER="week" a single fetch can
    legitimately return articles spanning several distinct days. A
    single-most-recent-day reservation only protected whichever one of
    those days matched the fetch day, so the other fresh-but-not-newest
    days lost their reservation and got crowded out by same-day RSS --
    exactly what happened to finance-insurance on 2026-08-29, when only
    1 of 7 freshly-fetched Perplexity articles was dated that day.
    Widening the window to fix that (before PERPLEXITY_RESERVED_SLOTS
    existed) over-corrected into the opposite bug the same day: enough
    Perplexity articles had accumulated within the window that the
    reservation claimed all ARTICLES_PER_TOPIC slots, rendering 0 RSS
    articles for finance-insurance.
    """
    folder = OBSIDIAN_DIR / topic
    if not folder.exists():
        return []
    all_articles = []
    for md_file in sorted(folder.glob("*.md"), reverse=True):
        text = md_file.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(text)
        summary_match = re.search(r"## Summary\n\n(.*?)(?:\n\n## |\Z)", body, re.DOTALL)
        excerpt = summary_match.group(1).strip() if summary_match else body.split("## Read More")[0].strip()
        all_articles.append({
            "title": meta.get("title", md_file.stem),
            "date": meta.get("date", ""),
            "source": meta.get("source", ""),
            "url": meta.get("url", "#"),
            "body": excerpt[:500] + ("…" if len(excerpt) > 500 else ""),
            "via_perplexity": "perplexity" in meta.get("tags", []),
        })

    cutoff = (datetime.now(timezone.utc).date() - timedelta(days=PERPLEXITY_MAX_ARTICLE_AGE_DAYS)).isoformat()
    recent_perplexity_indices = [
        i for i, a in enumerate(all_articles)
        if a["via_perplexity"] and a["date"] >= cutoff
    ]
    selected = set(recent_perplexity_indices[:PERPLEXITY_RESERVED_SLOTS])
    for i in range(len(all_articles)):
        if len(selected) >= ARTICLES_PER_TOPIC:
            break
        selected.add(i)
    return [all_articles[i] for i in sorted(selected)][:ARTICLES_PER_TOPIC]


def load_last_fetch():
    """Read the UTC timestamp run_all.py wrote after its last successful
    fetch. Returns None if it's missing or unparseable, so callers don't
    fabricate a time that didn't come from an actual fetch."""
    if not LAST_FETCH_FILE.exists():
        return None
    try:
        text = LAST_FETCH_FILE.read_text(encoding="utf-8").strip()
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (ValueError, OSError):
        return None


def render_story(article, color):
    if article.get("via_perplexity"):
        badge = '<span class="badge badge-perplexity">Perplexity</span>'
    else:
        badge = '<span class="badge badge-rss">RSS</span>'
    url = html.escape(article["url"])
    title = html.escape(article["title"])
    date = html.escape(article["date"])
    source = html.escape(article["source"])
    body = html.escape(article["body"])
    return f"""
  <div class="story" style="border-left-color:{color}">
    <h3><a href="{url}" target="_blank" rel="noopener noreferrer">{title}</a> {badge}</h3>
    <p class="meta">{date} — {source}</p>
    <p>{body}</p>
  </div>"""


def build_html(topics_data, last_fetch_utc):
    try:
        pacific, tz_label = ZoneInfo("America/Los_Angeles"), "PT"
    except ZoneInfoNotFoundError:
        # No IANA tzdata available on this system (e.g. bare Windows) --
        # fall back to UTC rather than crashing the whole build.
        pacific, tz_label = timezone.utc, "UTC"
    if last_fetch_utc:
        today = last_fetch_utc.astimezone(pacific).strftime(f"%B %d, %Y at %I:%M %p {tz_label}")
    else:
        today = "unknown (no valid fetch marker found)"
    nav = "\n    ".join(
        f'<a href="#{slug}">{label}</a>'
        for slug, label in TOPIC_LABELS.items()
        if slug in topics_data
    )

    sections = ""
    for slug, label in TOPIC_LABELS.items():
        articles = topics_data.get(slug, [])
        color = TOPIC_COLORS.get(slug, "#003366")
        stories = "".join(render_story(a, color) for a in articles) if articles else \
            "<p>No articles fetched yet. Run <code>python fetch_news.py " + slug + "</code>.</p>"
        sections += f"""
  <h2 id="{slug}">{label}</h2>
{stories}"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>News Aggregator</title>
  <!-- Privacy-friendly analytics by Plausible -->
  <script async src="https://plausible.io/js/pa-o4hLL702isUW-J6J0-m95.js"></script>
  <script>
    window.plausible=window.plausible||function(){{(plausible.q=plausible.q||[]).push(arguments)}},plausible.init=plausible.init||function(i){{plausible.o=i||{{}}}};
    plausible.init()
  </script>
  <style>
    body {{ font-family: Arial, sans-serif; max-width: 860px; margin: 40px auto; padding: 0 20px; color: #222; overflow-x: hidden; }}
    h1 {{ color: #003366; border-bottom: 3px solid #003366; padding-bottom: 10px; }}
    h2 {{ color: #003366; margin-top: 40px; border-bottom: 1px solid #ccc; padding-bottom: 6px; }}
    h3 {{ margin-bottom: 2px; overflow-wrap: break-word; }}
    h3 a {{ color: #005599; text-decoration: none; }}
    h3 a:hover {{ text-decoration: underline; }}
    .badge {{ display: inline-block; font-size: 0.65em; font-weight: bold; padding: 2px 8px; border-radius: 10px; vertical-align: middle; text-transform: uppercase; letter-spacing: 0.03em; white-space: nowrap; }}
    .badge-rss {{ background: #e0e0e0; color: #555; }}
    .badge-perplexity {{ background: #6b46c1; color: #fff; }}
    .meta {{ color: #777; font-size: 0.85em; margin: 2px 0 8px; }}
    .date {{ color: #777; font-size: 0.9em; margin-bottom: 30px; }}
    .story {{ background: #f9f9f9; border-left: 4px solid #003366; padding: 14px 18px; margin-bottom: 16px; border-radius: 4px; overflow-wrap: break-word; word-break: break-word; }}
    nav {{ display: flex; gap: 16px; margin-bottom: 30px; flex-wrap: wrap; }}
    nav a {{ font-weight: bold; text-decoration: none; color: #003366; padding: 6px 14px; border: 2px solid #003366; border-radius: 4px; }}
    nav a:hover {{ background: #003366; color: #fff; }}
  </style>
</head>
<body>
  <h1>📰 News Aggregator</h1>
  <p class="date">Updated: {today} — Auto-refreshed daily at 7am Pacific</p>
  <nav>
    {nav}
  </nav>
{sections}
</body>
</html>"""


def main():
    topics_data = {}
    for slug in TOPIC_LABELS:
        articles = load_articles(slug)
        if articles:
            topics_data[slug] = articles

    html = build_html(topics_data, load_last_fetch())
    OUTPUT_FILE.write_text(html, encoding="utf-8")
    print(f"Built {OUTPUT_FILE} with {sum(len(v) for v in topics_data.values())} articles.")


if __name__ == "__main__":
    main()
