"""
verify_index.py
Sanity-checks that index.html actually reflects the source article data --
specifically, that every Perplexity article from the most recent day in a
topic's data made it into the rendered page.

This exists because a code review (human, Claude, or Copilot) of
build_index.py's selection logic can look correct and still ship a bug
that only shows up in the actual output -- that's exactly what happened
in PR #11 (a fixed slot count silently dropped a 4th same-day Perplexity
article) and again while fixing it (an unscoped reservation crowded out
all of RSS). Both were only caught by manually counting badges in the
rendered page after the fact. This script makes that count automatic
and independent: it recomputes the expected count straight from the
markdown files, not by calling build_index.py's own selection function.

Run after build_index.py. Exits non-zero (and prints what's wrong) on
failure, so it can gate CI and the daily fetch workflow.
"""

import re
import sys

from build_index import ARTICLES_PER_TOPIC, OBSIDIAN_DIR, OUTPUT_FILE, TOPIC_LABELS, parse_frontmatter


def source_perplexity_count_for_latest_day(topic):
    """Independently recompute, from the raw markdown files, how many
    Perplexity articles should be reserved a slot for this topic --
    without going through build_index.py's own selection logic."""
    folder = OBSIDIAN_DIR / topic
    if not folder.exists():
        return 0
    dated = []
    for md_file in folder.glob("*.md"):
        meta, _ = parse_frontmatter(md_file.read_text(encoding="utf-8"))
        dated.append((meta.get("date", ""), "perplexity" in meta.get("tags", [])))
    if not dated:
        return 0
    most_recent_date = max(date for date, _ in dated)
    return sum(1 for date, is_perplexity in dated if date == most_recent_date and is_perplexity)


def rendered_badge_counts(html_text, topic):
    """Count RSS/Perplexity badges within one topic's <h2 id="topic"> section."""
    match = re.search(
        rf'<h2 id="{re.escape(topic)}">.*?(?=<h2 id="|\Z)', html_text, re.DOTALL
    )
    section = match.group(0) if match else ""
    perplexity = len(re.findall(r'badge-perplexity">', section))
    rss = len(re.findall(r'badge-rss">', section))
    return perplexity, rss


def main():
    if not OUTPUT_FILE.exists():
        print(f"FAIL: {OUTPUT_FILE} does not exist -- run build_index.py first.")
        sys.exit(1)

    html_text = OUTPUT_FILE.read_text(encoding="utf-8")
    failures = []

    for topic in TOPIC_LABELS:
        expected = min(source_perplexity_count_for_latest_day(topic), ARTICLES_PER_TOPIC)
        rendered_perplexity, _ = rendered_badge_counts(html_text, topic)
        if rendered_perplexity < expected:
            failures.append(
                f"{topic}: source data has {expected} Perplexity article(s) from its "
                f"most recent day, but only {rendered_perplexity} appear in the "
                f"rendered page."
            )

    if failures:
        print("index.html verification FAILED:")
        for failure in failures:
            print(f"  - {failure}")
        sys.exit(1)

    print(
        "index.html verification passed: every topic's most-recent-day "
        "Perplexity articles are all represented in the rendered page."
    )


if __name__ == "__main__":
    main()
