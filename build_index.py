"""
build_index.py
Reads all markdown files in obsidian/<topic>/ and rebuilds index.html.
Run automatically by GitHub Actions after fetch_news.py.
"""

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
    """Extract YAML frontmatter fields from a markdown file."""
    meta = {}
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        return meta, text
    fm = match.group(1)
    body = text[match.end():]
    for line in fm.splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            meta[key.strip()] = val.strip().strip('"')
    return meta, body.strip()


def load_articles(topic):
    """Load all markdown articles for a topic, newest first."""
    folder = OBSIDIAN_DIR / topic
    if not folder.exists():
        return []
    articles = []
    for md_file in sorted(folder.glob("*.md"), reverse=True):
        text = md_file.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(text)
        summary_match = re.search(r"## Summary\n\n(.*?)(?:\n\n## |\Z)", body, re.DOTALL)
        excerpt = summary_match.group(1).strip() if summary_match else body.split("## Read More")[0].strip()
        articles.append({
            "title": meta.get("title", md_file.stem),
            "date": meta.get("date", ""),
            "source": meta.get("source", ""),
            "url": meta.get("url", "#"),
            "body": excerpt[:500] + ("…" if len(excerpt) > 500 else ""),
        })
    return articles[:10]  # Show latest 10 per topic


def render_story(article, color):
    return f"""
  <div class="story" style="border-left-color:{color}">
    <h3><a href="{article['url']}" target="_blank">{article['title']}</a></h3>
    <p class="meta">{article['date']} — {article['source']}</p>
    <p>{article['body']}</p>
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
