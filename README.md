# News Aggregator

Fetches the latest news from RSS feeds and saves results as Obsidian-compatible markdown files with YAML frontmatter.

No API key required — uses public RSS feeds from Reuters, AP, BBC, and others.

---

## Project Structure

```
news/
├── fetch_news.py          # Main script
├── requirements.txt       # Python dependencies
├── topics/                # RSS feed lists per topic
│   └── el-salvador.md
└── obsidian/              # Output folder (auto-created)
    └── el-salvador/       # One subfolder per topic
        └── YYYY-MM-DD_article-title.md
```

---

## Setup

### 1. Clone / navigate to the project

```bash
cd C:\Users\vhmag\OneDrive\GitHub\news
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

---

## Usage

```bash
python fetch_news.py <topic>
```

The `<topic>` argument must match a file name (without `.md`) inside the `topics/` folder.

### Examples

```bash
# Fetch El Salvador news
python fetch_news.py el-salvador

# Fetch technology news (if topics/technology.md exists)
python fetch_news.py technology
```

Output files are saved to `obsidian/<topic>/`.

---

## Adding a New Topic

1. Create `topics/<your-topic>.md`
2. List RSS feed URLs under an `## RSS Feeds` heading, one per line:

```markdown
## RSS Feeds

https://feeds.reuters.com/reuters/technologyNews
https://rss.cnn.com/rss/cnn_tech.rss
```

3. Run `python fetch_news.py <your-topic>`

---

## Obsidian Integration

Point an Obsidian vault (or a folder within one) at the `obsidian/` directory. Each article is saved as a note with YAML frontmatter:

```yaml
---
title: "Article Title"
date: 2026-08-18
source: Reuters
url: https://...
tags:
  - el-salvador
  - news
---
```

---

## Dependencies

| Package      | Purpose                        |
|-------------|-------------------------------|
| feedparser  | Parse RSS/Atom feeds           |
| requests    | HTTP requests with user-agent  |
| python-slugify | Clean filenames from titles |

See `requirements.txt` for pinned versions.
