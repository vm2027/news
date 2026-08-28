"""
verify_index.py
Sanity-checks that index.html actually reflects the source article data --
specifically, that every Perplexity article from the most recent day in a
topic's data made it into the rendered page.

This exists because a code review (human, Claude, or Copilot) of
build_index.py's selection logic can look correct and still ship a bug
that only shows up in the actual output -- that's exactly what happened
in PR #11 (a fixed slot count silently dropped a 4th same-day Perplexity
article), again while fixing it (an unscoped reservation crowded out
all of RSS), and a third time when this script's own "most recent day"
computation mirrored build_index.py's topic-wide-date bug closely enough
that both sides were wrong in the same way and still agreed -- so it
passed while finance-insurance silently rendered zero Perplexity badges.
All three were only caught by manually counting badges in the rendered
page after the fact. This script makes that count automatic and
independent: it recomputes the expected count straight from the
markdown files, not by calling build_index.py's own selection function
-- and, since the third bug, computes "most recent day" scoped to
Perplexity's own dates, not the topic-wide most recent date, so it
can't silently share build_index.py's date-scoping bugs again.

Run after build_index.py. Exits non-zero (and prints what's wrong) on
failure, so it can gate CI and the daily fetch workflow.
"""

import re
import sys

from build_index import ARTICLES_PER_TOPIC, OBSIDIAN_DIR, OUTPUT_FILE, TOPIC_LABELS, parse_frontmatter


def source_perplexity_count_for_latest_day(topic):
    """Independently recompute, from the raw markdown files, how many
    Perplexity articles should be reserved a slot for this topic --
    without going through build_index.py's own selection logic.

    Scoped to the most recent date *among Perplexity articles*, not the
    most recent date across all sources -- RSS's date is typically the
    fetch day, while Perplexity's is the article's true publish date and
    is routinely a day behind. Computing this the same way build_index.py
    does previously meant this check couldn't catch a regression in that
    exact scoping (it had the identical bug), since both sides would be
    wrong in the same way and still agree.
    """
    folder = OBSIDIAN_DIR / topic
    if not folder.exists():
        return 0
    perplexity_dates = []
    for md_file in folder.glob("*.md"):
        meta, _ = parse_frontmatter(md_file.read_text(encoding="utf-8"))
        if "perplexity" in meta.get("tags", []):
            perplexity_dates.append(meta.get("date", ""))
    if not perplexity_dates:
        return 0
    most_recent_perplexity_date = max(perplexity_dates)
    return sum(1 for date in perplexity_dates if date == most_recent_perplexity_date)


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
        source_count = source_perplexity_count_for_latest_day(topic)
        expected = min(source_count, ARTICLES_PER_TOPIC)
        rendered_perplexity, _ = rendered_badge_counts(html_text, topic)
        if rendered_perplexity < expected:
            cap_note = f" (capped at {ARTICLES_PER_TOPIC})" if source_count > ARTICLES_PER_TOPIC else ""
            failures.append(
                f"{topic}: source data has {source_count} Perplexity article(s) from its "
                f"most recent day{cap_note}, but only {rendered_perplexity} appear in the "
                f"rendered page (expected at least {expected})."
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
