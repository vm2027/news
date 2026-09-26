-- create_readonly_role.sql -- one-time setup of a read-only Postgres login
-- for Grafana Cloud, so the dashboard never holds the admin credentials
-- that DATABASE_URL (and so fetch_news.py) uses.
--
-- Run once as the Aiven admin user, from psql:
--   psql "<Aiven service URI>" -f grafana/create_readonly_role.sql
--   psql "<Aiven service URI>" -c '\password grafana_ro'
-- The second command prompts for the password interactively, so it never
-- lands in this file, a shell history, or a CI log.
--
-- Safe to re-run: every statement below is idempotent.

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'grafana_ro') THEN
        CREATE ROLE grafana_ro LOGIN;
    END IF;
    -- CONNECT and schema USAGE are granted to PUBLIC by default, so these
    -- two are belt and braces -- and the Aiven admin user may not own the
    -- database/schema, so a missing grant option must not abort the setup.
    -- current_database() rather than a hard-coded name, since the
    -- database name is whatever the Aiven service URI points at.
    BEGIN
        EXECUTE format('GRANT CONNECT ON DATABASE %I TO grafana_ro', current_database());
        GRANT USAGE ON SCHEMA public TO grafana_ro;
    EXCEPTION WHEN insufficient_privilege THEN
        RAISE NOTICE 'skipped CONNECT/USAGE grants (PUBLIC defaults apply)';
    END;
END $$;

GRANT SELECT ON articles TO grafana_ro;

-- Belt and braces: even a query Grafana sends can't write, can't run away,
-- and can't hog the (small) Aiven connection pool. The limit was first 3,
-- which Grafana's own connection pool exhausted (one held connection per
-- dashboard panel, plus the alert editor's preview -> "too many
-- connections for role"). But the Aiven service allows only 20
-- connections in total (17 in use when measured on 2026-09-26, including
-- Grafana's 3), so a generous limit could starve fetch_news.py of the one
-- connection it needs for DB logging -- which is best-effort, so articles
-- would still publish but their rows would go missing, and the dashboard
-- and alert would then report a false "stale". 5 is the hard ceiling;
-- Grafana's data source "Max open" = 2 keeps real use below it.
ALTER ROLE grafana_ro SET default_transaction_read_only = on;
ALTER ROLE grafana_ro SET statement_timeout = '15s';
ALTER ROLE grafana_ro CONNECTION LIMIT 5;
