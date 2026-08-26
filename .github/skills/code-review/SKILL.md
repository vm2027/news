---
name: code-review
description: Repo-specific context for reviewing changes to the news aggregator (fetch_news.py, build_index.py, index.html, obsidian article data).
---

# Reviewing changes to this repository

This repo pulls news from RSS feeds and the Perplexity API
(`fetch_news.py`), saves articles as markdown under
`obsidian/Obsedian_R/<topic>/`, and regenerates the GitHub Pages site
(`index.html`) from that data via `build_index.py`. Apply the following
when reviewing changes here.

## Checks specific to this repo

- **`index.html` must be regenerated and committed alongside any change
  to `build_index.py` or the article data under `obsidian/Obsedian_R/`.**
  The live site is the committed `index.html` file, not something built
  at deploy time — a PR that changes `build_index.py` without a
  regenerated `index.html` in the same diff is incomplete.
- **User-supplied content (RSS/Perplexity output) rendered into HTML must
  be escaped.** Article title, source, date, body, and url all originate
  from external feeds or an LLM and are interpolated into `index.html` —
  flag any interpolation that isn't passed through `html.escape()` (or
  equivalent) as an injection risk. Outbound article links should carry
  `rel="noopener noreferrer"` alongside `target="_blank"`.
- **Selection/filtering logic that treats multiple sources or topics
  unevenly is a common bug class here.** RSS publishes far more articles
  per day than Perplexity does. Any "top N" or "latest N" selection over
  combined RSS + Perplexity data should be checked for whether higher-
  volume RSS could silently crowd out lower-volume Perplexity articles
  (or vice versa) — this has happened twice in this repo's history (a
  fixed-count reservation still dropped articles once daily volume
  exceeded the count; an unscoped "reserve everything" fix then crowded
  out RSS by reserving weeks of historical Perplexity articles instead of
  just the current day's). Prefer solutions that scale with actual daily
  volume over hardcoded slot counts.
- **Perplexity fetch changes should preserve the article-URL quality
  filter** (`looks_like_article_url()` in `fetch_news.py`) — Perplexity
  has previously substituted section/landing pages (e.g.
  `bloomberg.com/markets`) for real article URLs when it couldn't find a
  direct link, and this filter is the backstop against that recurring
  issue, even after prompt tightening.
- **Don't assume network calls can be tested from CI or a sandboxed
  agent.** RSS feed reachability and Perplexity API responses can only be
  verified against the real GitHub Actions workflow run
  (`.github/workflows/fetch-news.yml`, which has the real
  `PERPLEXITY_API_KEY` secret and real network access), not from a
  restricted sandbox. Don't flag a lack of local network-call testing as
  a gap if the PR instead references a `workflow_dispatch` run's logs.

## Verifying selection/display logic

When a change affects which articles get shown (`load_articles()`,
badges, topic sections), the right check is the **per-topic / per-source
breakdown** in the regenerated `index.html`, not just a page-wide total.
A correct-looking aggregate (e.g. "20 articles total") can hide one topic
or source being silently at zero — this has previously caused a real bug
that shipped and went unnoticed for a full review cycle.
