"""
constants.py
Shared constants with no third-party dependencies, so scripts that only
need a constant's value (e.g. build_index.py, verify_index.py) don't have
to import fetch_news.py and pull in its feedparser/requests/slugify
dependencies just to read one number.
"""

# Perplexity is asked for stories from "the past 48 hours" but the sonar model
# sometimes returns older stories it turned up during search. Allow a little
# slack for timezone/model imprecision, but discard anything clearly stale.
# Also used by build_index.py/verify_index.py to scope how far back a
# Perplexity article can be and still reserve a display slot.
PERPLEXITY_MAX_ARTICLE_AGE_DAYS = 4
