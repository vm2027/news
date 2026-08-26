"""
build_index.py
Reads all markdown files in obsidian/<topic>/ and rebuilds index.html.
Run automatically by GitHub Actions after fetch_news.py.
"""

import html
import os
import re
from datetime import datetime
from pathlib import Path

OBSIDIAN_DIR = Path("obsidian") / "Obsedian_R"
OUTPUT_FILE = Path("index.html")

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


def load_articles(topic):
    """Load markdown articles for a topic, newest first.

    RSS feeds publish far more articles per day than Perplexity does, so
    simply taking the newest ARTICLES_PER_TOPIC would let RSS crowd
    Perplexity-sourced articles out entirely on busy days. Reserve a slot
    for every Perplexity article from the most recent date represented in
    this topic's data (its volume is naturally small and bounded, unlike
    RSS) so none get silently dropped, then fill the rest with the
    freshest remaining articles. Only Perplexity articles from that most
    recent date are reserved -- older ones are still eligible to fill
    remaining slots on their own recency, same as RSS, so they don't pin
    stale Perplexity content ahead of fresh RSS.
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

    most_recent_date = all_articles[0]["date"] if all_articles else None
    latest_day_perplexity_indices = [
        i for i, a in enumerate(all_articles)
        if a["via_perplexity"] and a["date"] == most_recent_date
    ]
    selected = set(latest_day_perplexity_indices[:ARTICLES_PER_TOPIC])
    for i in range(len(all_articles)):
        if len(selected) >= ARTICLES_PER_TOPIC:
            break
        selected.add(i)
    return [all_articles[i] for i in sorted(selected)][:ARTICLES_PER_TOPIC]


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


def build_html(topics_data):
    from datetime import timezone, timedelta
    pacific = timezone(timedelta(hours=-7))  # PDT (UTC-7); change to -8 in winter for PST
    now = datetime.now(tz=pacific)
    today = now.strftime("%B %d, %Y at %I:%M %p PT")
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

    html = build_html(topics_data)
    OUTPUT_FILE.write_text(html, encoding="utf-8")
    print(f"Built {OUTPUT_FILE} with {sum(len(v) for v in topics_data.values())} articles.")


if __name__ == "__main__":
    main()
