#!/usr/bin/env python3
"""
query_summary.py — read-only summary of the Aiven Postgres articles
table (see db.py): article counts per topic x origin, for on-demand
checks without needing Grafana or any other persistent dashboard.

Connects directly with psycopg rather than going through
db.get_connection() -- that helper also runs the CREATE TABLE/ALTER
TABLE schema-ensure and migration statements, which would make this
"read-only" script perform writes (and fail outright against a
read-only DB role).

DATABASE_URL only exists as a GitHub Actions secret, so this is meant
to run via the "DB Summary" workflow (workflow_dispatch only, never
scheduled) rather than from a local shell.
"""

import os
import sys
from datetime import timezone


def _utc(dt) -> str:
    """Format a timestamptz value as an explicit UTC string.

    psycopg returns timestamptz columns as timezone-aware datetimes in
    the session's timezone, not necessarily UTC -- astimezone() forces
    the conversion so the "(UTC)" header is actually accurate.
    """
    if dt is None:
        return ""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def main() -> None:
    dsn = os.environ.get("DATABASE_URL", "")
    if not dsn:
        print("DATABASE_URL is not set -- nothing to report.", file=sys.stderr)
        sys.exit(1)

    import psycopg

    try:
        conn = psycopg.connect(dsn, connect_timeout=10)
    except Exception as exc:  # noqa: BLE001
        # Only the exception type, not str(exc): psycopg connection-failure
        # messages can include the DSN (host/user, sometimes the password)
        # verbatim, which would otherwise leak into the Actions log.
        print(f"Could not connect: {type(exc).__name__}", file=sys.stderr)
        sys.exit(1)

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT topic, origin, count(*) AS n,
                       min(fetched_at) AS first_seen, max(fetched_at) AS last_seen
                FROM articles
                GROUP BY topic, origin
                ORDER BY topic, origin
                """
            )
            rows = cur.fetchall()

            print(f"{'topic':<20}{'origin':<12}{'count':>7}  {'first_fetched (UTC)':<24}{'last_fetched (UTC)'}")
            for topic, origin, n, first_seen, last_seen in rows:
                print(f"{topic:<20}{origin:<12}{n:>7}  {_utc(first_seen):<24}{_utc(last_seen)}")

            cur.execute("SELECT count(*) FROM articles")
            total = cur.fetchone()[0]
            print(f"\nTotal rows: {total}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
