#!/usr/bin/env python3
"""
db.py — optional Aiven PostgreSQL logging of fetched articles.

Purely additive: the markdown files under obsidian/Obsedian_R/ remain the
source of truth for the site. This module lets fetch_news.py also record
each saved article as a row (topic, origin, source, url, published_date)
so a dashboard (e.g. Aiven Grafana) can chart volume per topic x origin
over time -- the per-segment breakdown the site itself doesn't show.

Best-effort by design: if DATABASE_URL isn't set, this module skips DB
logging silently (get_connection() returns None -- the normal case
before the secret exists). If psycopg isn't installed or the
connection/insert/close itself fails, it logs a warning and no-ops
instead of raising. A daily fetch must never fail because the database
is down.
"""

from __future__ import annotations

import logging
import os
from datetime import date
from typing import Any

log = logging.getLogger("news.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id SERIAL PRIMARY KEY,
    topic TEXT NOT NULL,
    origin TEXT NOT NULL,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    published_date DATE,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (topic, origin, url)
);
"""

# One-time migration for tables created before the uniqueness constraint
# moved from a bare "url" to "(topic, origin, url)" -- the same article
# URL can legitimately appear under more than one topic or origin, and a
# global UNIQUE(url) silently dropped every such row via ON CONFLICT DO
# NOTHING, undercounting the exact per-topic/origin numbers this table
# exists to report. Split into two statements (not one multi-statement
# string) since libpq/psycopg don't reliably support several statements
# in a single execute(). Both are safe to run every call: DROP ... IF
# EXISTS is a no-op once the old constraint is gone, and the DO block
# swallows the "already exists" error once the new one is in place.
_MIGRATE_DROP_OLD_UNIQUE = "ALTER TABLE articles DROP CONSTRAINT IF EXISTS articles_url_key;"
_MIGRATE_ADD_COMPOSITE_UNIQUE = """
DO $$
BEGIN
    ALTER TABLE articles ADD CONSTRAINT articles_topic_origin_url_key UNIQUE (topic, origin, url);
EXCEPTION WHEN duplicate_object OR duplicate_table THEN
    -- duplicate_object: the constraint itself already exists.
    -- duplicate_table: a UNIQUE constraint backs itself with an index of
    -- the same name, and re-adding it collides on that index/relation
    -- name instead -- observed for real running this migration twice in
    -- one workflow run (fetch_news.py is invoked once per topic, each a
    -- fresh process, each calling get_connection()).
    NULL;
END $$;
"""


def get_connection() -> Any | None:
    """Return a live psycopg connection with the schema ensured, or None.

    None means "skip DB logging for this run" -- callers should treat it
    as a normal, silent no-op rather than an error.
    """
    dsn = os.environ.get("DATABASE_URL", "")
    if not dsn:
        return None

    try:
        import psycopg
    except ImportError:
        log.warning("psycopg not installed; skipping article DB logging")
        return None

    try:
        conn = psycopg.connect(dsn, connect_timeout=10)
    except Exception as exc:  # noqa: BLE001
        # Deliberately log only the exception type, not str(exc): psycopg's
        # connection-failure messages can include the DSN (host/user, and
        # sometimes the password) verbatim, which would otherwise leak into
        # GitHub Actions logs.
        log.warning("Could not connect to DATABASE_URL: %s", type(exc).__name__)
        return None
    log.info("DB: connected to Postgres for article logging")

    try:
        with conn.cursor() as cur:
            cur.execute(_SCHEMA)
            cur.execute(_MIGRATE_DROP_OLD_UNIQUE)
            cur.execute(_MIGRATE_ADD_COMPOSITE_UNIQUE)
        conn.commit()
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not ensure 'articles' table exists: %s", exc)
        close(conn)
        return None

    return conn


def record_article(
    conn: Any | None,
    topic: str,
    origin: str,
    source: str,
    title: str,
    url: str,
    published_date: date | None,
) -> None:
    """Insert one article row. No-op if conn is None; never raises."""
    if conn is None or not url:
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO articles (topic, origin, source, title, url, published_date)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (topic, origin, url) DO NOTHING
                RETURNING id
                """,
                (topic, origin, source, title, url, published_date),
            )
            inserted = cur.fetchone() is not None
        conn.commit()
        if inserted:
            log.info("DB: recorded %s/%s article %s", topic, origin, url)
        else:
            log.info("DB: %s/%s article already recorded, skipped %s", topic, origin, url)
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not record article in DB (%s): %s", url, exc)
        try:
            conn.rollback()
        except Exception:  # noqa: BLE001
            pass


def close(conn: Any | None) -> None:
    if conn is not None:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass
