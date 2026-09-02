#!/usr/bin/env python3
"""
query_summary.py — read-only summary of the Aiven Postgres articles
table (see db.py): article counts per topic x origin, for on-demand
checks without needing Grafana or any other persistent dashboard.

DATABASE_URL only exists as a GitHub Actions secret, so this is meant
to run via the "DB Summary" workflow (workflow_dispatch only, never
scheduled) rather than from a local shell.
"""

import os
import sys

import db


def main() -> None:
    if not os.environ.get("DATABASE_URL", ""):
        print("DATABASE_URL is not set -- nothing to report.", file=sys.stderr)
        sys.exit(1)

    conn = db.get_connection()
    if conn is None:
        # get_connection() already logged a warning with the specific
        # reason (psycopg missing, connect failed, schema setup failed).
        print("Could not connect (see warning above) -- nothing to report.", file=sys.stderr)
        sys.exit(1)

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

        print(f"{'topic':<20}{'origin':<12}{'count':>7}  {'first_fetched (UTC)':<22}{'last_fetched (UTC)'}")
        for topic, origin, n, first_seen, last_seen in rows:
            print(f"{topic:<20}{origin:<12}{n:>7}  {str(first_seen):<22}{last_seen}")

        cur.execute("SELECT count(*) FROM articles")
        total = cur.fetchone()[0]
        print(f"\nTotal rows: {total}")

    db.close(conn)


if __name__ == "__main__":
    main()
