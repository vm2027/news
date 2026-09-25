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
    -- current_database() rather than a hard-coded name, since the
    -- database name is whatever the Aiven service URI points at.
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO grafana_ro', current_database());
END $$;

GRANT USAGE ON SCHEMA public TO grafana_ro;
GRANT SELECT ON articles TO grafana_ro;

-- Belt and braces: even a query Grafana sends can't write, can't run away,
-- and can't hog the (small) Aiven connection pool.
ALTER ROLE grafana_ro SET default_transaction_read_only = on;
ALTER ROLE grafana_ro SET statement_timeout = '15s';
ALTER ROLE grafana_ro CONNECTION LIMIT 3;
