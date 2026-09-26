#!/usr/bin/env python3
"""
setup_readonly_role.py -- one-off: create the grafana_ro Postgres login
(grafana/create_readonly_role.sql) and set its password, from a GitHub
Actions runner instead of a local psql install.

Reads DATABASE_URL (the existing admin DSN secret) and
GRAFANA_RO_PASSWORD (a new secret the user picks). Then it verifies, by
logging in *as grafana_ro*, that the password works, that per-topic x
origin counts are readable, and that writes are refused.

This repo is public, so its Actions logs are too: nothing here prints the
DSN, host, or password, and failures print only the exception type (the
same redaction rule as db.py / query_summary.py).

The password never reaches the server in plaintext: it is sent as a
SCRAM-SHA-256 verifier computed here, so it can't show up in Postgres
server logs either.
"""

import base64
import hashlib
import hmac
import os
import sys
from pathlib import Path

ROLE = "grafana_ro"
SQL_FILE = Path(__file__).with_name("create_readonly_role.sql")


def scram_verifier(password: str, iterations: int = 4096) -> str:
    """Postgres-format SCRAM-SHA-256 verifier (what CREATE/ALTER ROLE ... PASSWORD accepts pre-hashed)."""
    salt = os.urandom(16)
    salted = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    client_key = hmac.new(salted, b"Client Key", hashlib.sha256).digest()
    stored_key = hashlib.sha256(client_key).digest()
    server_key = hmac.new(salted, b"Server Key", hashlib.sha256).digest()
    b64 = lambda b: base64.b64encode(b).decode()  # noqa: E731
    return f"SCRAM-SHA-256${iterations}:{b64(salt)}${b64(stored_key)}:{b64(server_key)}"


def fail(msg: str, exc: Exception | None = None) -> None:
    print(f"FAILED: {msg}" + (f": {type(exc).__name__}" if exc else ""), file=sys.stderr)
    sys.exit(1)


def main() -> None:
    dsn = os.environ.get("DATABASE_URL", "")
    password = os.environ.get("GRAFANA_RO_PASSWORD", "")
    if not dsn:
        fail("DATABASE_URL secret is not set")
    if not password:
        fail("GRAFANA_RO_PASSWORD secret is not set -- add it under Settings > Secrets and variables > Actions")
    if len(password) < 16 or not password.isascii():
        fail("GRAFANA_RO_PASSWORD must be at least 16 characters, ASCII only")
    # A stray space/newline from copy-paste becomes part of the password
    # here but usually not when it's pasted into Grafana -- a silent
    # mismatch ("password authentication failed") that can't be diagnosed
    # later because secrets are write-only.
    if password != password.strip():
        fail("GRAFANA_RO_PASSWORD has leading/trailing whitespace -- re-paste it without spaces or line breaks")

    import psycopg
    from psycopg import sql
    from psycopg.conninfo import conninfo_to_dict, make_conninfo

    # 1. As admin: create/grant (idempotent), then set the password.
    try:
        with psycopg.connect(dsn, connect_timeout=10, autocommit=True) as conn:
            # Diagnostic only (counts and states, nothing sensitive): how
            # many connections grafana_ro holds right now, e.g. from
            # Grafana's pool, and how many the whole server allows.
            held = conn.execute(
                "SELECT coalesce(state, '?'), count(*) FROM pg_stat_activity "
                "WHERE usename = %s GROUP BY 1 ORDER BY 1", (ROLE,)
            ).fetchall()
            total, limit = conn.execute(
                "SELECT (SELECT count(*) FROM pg_stat_activity), "
                "current_setting('max_connections')::int"
            ).fetchone()
            print(f"INFO: {ROLE} connections open now: "
                  + (", ".join(f"{n} {state}" for state, n in held) or "none"))
            print(f"INFO: server connections in use: {total} of max_connections {limit}")
            conn.execute(SQL_FILE.read_text())
            conn.execute(
                sql.SQL("ALTER ROLE {} PASSWORD {}").format(
                    sql.Identifier(ROLE), sql.Literal(scram_verifier(password))
                )
            )
    except Exception as exc:  # noqa: BLE001
        fail("admin setup", exc)
    print(f"OK: role {ROLE} created/updated and password set")

    # 2. As grafana_ro: same host/db/SSL settings, different user.
    params = conninfo_to_dict(dsn)
    params.update(user=ROLE, password=password)
    try:
        with psycopg.connect(make_conninfo(**params), connect_timeout=10) as ro:
            rows = ro.execute(
                "SELECT topic, origin, count(*) FROM articles GROUP BY 1, 2 ORDER BY 1, 2"
            ).fetchall()
            print(f"OK: logged in as {ROLE}; articles readable per topic x origin:")
            for topic, origin, n in rows:
                print(f"    {topic:<20}{origin:<12}{n:>7}")

            # Ask Postgres which write privileges this login actually holds,
            # rather than attempting a write: a test INSERT can be refused
            # for an unrelated reason (e.g. no USAGE on the id sequence, or
            # the read-only session default) and pass vacuously even when
            # the table grants are wrong -- confirmed in local testing.
            can_write, can_create = ro.execute(
                "SELECT has_table_privilege(current_user, 'articles',"
                "                           'INSERT, UPDATE, DELETE, TRUNCATE'),"
                "       has_schema_privilege(current_user, 'public', 'CREATE')"
            ).fetchone()
            if can_write:
                fail(f"{ROLE} can modify articles -- grants are wrong, do not use this login")
            print(f"OK: {ROLE} has no INSERT/UPDATE/DELETE/TRUNCATE on articles")
            if can_create:
                # Postgres < 15 lets PUBLIC create tables in schema public.
                # Not fixed here (revoking from PUBLIC could affect other
                # roles); the role's read-only default still blocks it.
                print(f"NOTE: {ROLE} inherits CREATE on schema public from PUBLIC "
                      "(Postgres < 15 default); blocked by its read-only default")
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        fail(f"verification as {ROLE}", exc)

    print("\nAll checks passed. Use these in Grafana: user grafana_ro + the password you stored in the secret.")


if __name__ == "__main__":
    main()
