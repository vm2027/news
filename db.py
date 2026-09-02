#!/usr/bin/env python3
"""
db.py — optional Aiven PostgreSQL logging of fetched articles.

Purely additive: the markdown files under obsidian/Obsedian_R/ remain the
source of truth for the site. This module lets fetch_news.py also record
each saved article as a row (topic, origin, source, url, published_date)
so a dashboard (e.g. Aiven Grafana) can chart volume per topic x origin
over time -- the per-segment breakdown the site itself doesn't show.

Best-effort by design: if DATABASE_URL isn't set, psycopg isn't
installed, or the connection/insert fails, every function here logs a
warning and returns quietly. A daily fetch must never fail because the
database is down.
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
    url TEXT NOT NULL UNIQUE,
    published_date DATE,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
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
        log.warning("Could not connect to DATABASE_URL: %s", exc)
        return None

    try:
        with conn.cursor() as cur:
            cur.execute(_SCHEMA)
        conn.commit()
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not ensure 'articles' table exists: %s", exc)
        conn.close()
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
                ON CONFLICT (url) DO NOTHING
                """,
                (topic, origin, source, title, url, published_date),
            )
        conn.commit()
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not record article in DB (%s): %s", url, exc)
        conn.rollback()


def close(conn: Any | None) -> None:
    if conn is not None:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass
