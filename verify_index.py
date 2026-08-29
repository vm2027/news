"""
verify_index.py
Sanity-checks that index.html actually reflects the source article data --
specifically, that recent-enough Perplexity articles in a topic's data
made it into the rendered page, up to the same PERPLEXITY_RESERVED_SLOTS
cap build_index.py itself applies (this does not claim every recent
Perplexity article is shown -- once a topic has more of them than the
cap, some are expected to be left out in favor of RSS, by design).

This exists because a code review (human, Claude, or Copilot) of
build_index.py's selection logic can look correct and still ship a bug
that only shows up in the actual output -- that's exactly what happened
in PR #11 (a fixed slot count silently dropped a 4th same-day Perplexity
article), again while fixing it (an unscoped reservation crowded out
all of RSS), a third time when this script's own "most recent day"
computation mirrored build_index.py's topic-wide-date bug closely enough
that both sides were wrong in the same way and still agreed -- so it
passed while finance-insurance silently rendered zero Perplexity badges
-- and a fourth time when both sides scoped the reservation to a single
most-recent day, which broke again once PERPLEXITY_SEARCH_RECENCY_FILTER
started returning genuinely fresh results spanning several distinct
days: only the single day matching the fetch date kept its reservation,
so finance-insurance's rendered Perplexity count silently dropped from 4
to 1 even though 7 fresh articles had just been saved. All four were
only caught by manually counting badges in the rendered page after the
fact. This script makes that count automatic and independent: it
recomputes the expected count straight from the markdown files, not by
calling build_index.py's own selection function -- and, since the
fourth bug, scopes "recent enough" to the same
PERPLEXITY_MAX_ARTICLE_AGE_DAYS window fetch_news.py itself uses to
accept a result, not a single most-recent day, so it can't silently
share build_index.py's date-scoping bugs again.

Widening that window (fixing bug #4) immediately over-corrected into
the mirror-image bug locally, before it shipped: enough Perplexity
articles had accumulated within 4 days that the reservation claimed
all ARTICLES_PER_TOPIC slots, rendering 0 RSS articles for
finance-insurance. build_index.py now caps the reservation at
PERPLEXITY_RESERVED_SLOTS (half of ARTICLES_PER_TOPIC) rather than the
full slot count -- this script's expected count is capped the same
way, for the same never-recompute-the-same-bug-independently reason.

Run after build_index.py. Exits non-zero (and prints what's wrong) on
failure, so it can gate CI and the daily fetch workflow.
"""

import re
import sys
from datetime import datetime, timedelta, timezone

from build_index import PERPLEXITY_RESERVED_SLOTS, OBSIDIAN_DIR, OUTPUT_FILE, TOPIC_LABELS, parse_frontmatter
from constants import PERPLEXITY_MAX_ARTICLE_AGE_DAYS


def source_recent_perplexity_count(topic):
    """Independently recompute, from the raw markdown files, how many
    Perplexity articles should be reserved a slot for this topic --
    without going through build_index.py's own selection logic.

    Scoped to the same PERPLEXITY_MAX_ARTICLE_AGE_DAYS window
    fetch_news.py uses to accept a Perplexity result in the first place,
    not a single most-recent date -- a fetch can legitimately return
    articles spanning several distinct days (Perplexity's date is the
    article's true publish date, routinely a day or more behind the
    fetch day), and reserving only the single newest day let the other
    fresh days get crowded out by same-day RSS.
    """
    folder = OBSIDIAN_DIR / topic
    if not folder.exists():
        return 0
    cutoff = (datetime.now(timezone.utc).date() - timedelta(days=PERPLEXITY_MAX_ARTICLE_AGE_DAYS)).isoformat()
    count = 0
    for md_file in folder.glob("*.md"):
        meta, _ = parse_frontmatter(md_file.read_text(encoding="utf-8"))
        if "perplexity" in meta.get("tags", []) and meta.get("date", "") >= cutoff:
            count += 1
    return count


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
        source_count = source_recent_perplexity_count(topic)
        expected = min(source_count, PERPLEXITY_RESERVED_SLOTS)
        rendered_perplexity, _ = rendered_badge_counts(html_text, topic)
        if rendered_perplexity < expected:
            cap_note = f" (capped at {PERPLEXITY_RESERVED_SLOTS})" if source_count > PERPLEXITY_RESERVED_SLOTS else ""
            failures.append(
                f"{topic}: source data has {source_count} Perplexity article(s) within "
                f"the last {PERPLEXITY_MAX_ARTICLE_AGE_DAYS} days{cap_note}, but only "
                f"{rendered_perplexity} appear in the rendered page (expected at least {expected})."
            )

    if failures:
        print("index.html verification FAILED:")
        for failure in failures:
            print(f"  - {failure}")
        sys.exit(1)

    print(
        "index.html verification passed: every topic's recent (within "
        f"{PERPLEXITY_MAX_ARTICLE_AGE_DAYS} days) Perplexity articles are represented "
        f"in the rendered page, up to the {PERPLEXITY_RESERVED_SLOTS}-slot reservation cap."
    )


if __name__ == "__main__":
    main()
