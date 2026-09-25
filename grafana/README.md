# Grafana Cloud monitoring

A dashboard and alert on the Aiven Postgres `articles` table that
`fetch_news.py` writes to (see `db.py`). Its job is to catch **one topic ×
source going silent** — the failure this repo has actually had (see
CLAUDE.md, "Verification lesson"), which a page-wide total hides.

Nothing here runs in CI or touches the fetch pipeline. It's read-only
config you apply by hand in Grafana Cloud.

| File | What it is |
|---|---|
| `create_readonly_role.sql` | One-time: creates a `grafana_ro` Postgres login that can only `SELECT` from `articles` |
| `setup_readonly_role.py` | Runs that SQL, sets the password, and verifies the login, from a GitHub Actions runner (no local `psql` needed) |
| `dashboard.json` | Import into Grafana: "News pipeline health" |

## 1. Create the read-only database user (once)

Grafana Cloud stores whatever credentials you give it, so don't give it the
admin login from `DATABASE_URL`.

**Without a local `psql` (how it was actually done):** add a repository
secret `GRAFANA_RO_PASSWORD` (16+ ASCII characters, also saved in your
password manager), then run the one-off
`.github/workflows/grafana-role-setup.yml`. It uses the existing
`DATABASE_URL` secret, sends the password only as a SCRAM hash, and
verifies the new login: it can read per-topic/origin counts and has no
write privileges. Delete the workflow once it has succeeded.

**With `psql`:** use the **Service URI** from the Aiven console (service
overview page):

```sh
psql "<Aiven service URI>" -f grafana/create_readonly_role.sql
psql "<Aiven service URI>" -c '\password grafana_ro'   # prompts; pick a new password
```

The second command prompts for the password, so it never ends up in a
file or your shell history. Afterward, `grafana_ro` can't insert, update,
or create anything. That's enforced by permissions (tested), not just by
the role's read-only session default.

## 2. Add the Postgres data source in Grafana Cloud

Connections → Data sources → Add → **PostgreSQL**:

- **Host URL**: `<aiven-host>:<port>` (from the Aiven service overview)
- **Database name**: the database in your Service URI (usually `defaultdb`)
- **Username / Password**: `grafana_ro` / the password from step 1
- **TLS/SSL Mode**: `verify-full`. **TLS/SSL Method**: certificate content.
  Paste the **CA certificate** from the Aiven service overview into
  "TLS/SSL Root Certificate". `require` also works, but it doesn't check
  the server's identity.
- Save & test.

If the test times out, check Aiven's **IP allow-list** (service → Network).
It must allow Grafana Cloud's outbound IPs. GitHub Actions already connects
from arbitrary IPs, so it's likely open already.

## 3. Import the dashboard

Dashboards → New → Import → upload `dashboard.json` → pick the data source
from step 2.

Panels:
1. **Hours since last new article** per topic / source. Turns red above
   36h. The daily run fires anywhere from 14:17 to about 22:30 UTC, so 36h
   means a whole day's run added nothing for that segment.
2. **New articles per day** per topic / source, with zeros filled in, so a
   gap shows as 0 instead of a missing bar.
3. **New in the last 24h**. Red cell = 0.
4. **RSS feed health**. Feeds with nothing in 3 days sort to the top, so
   you'll see a dying feed or a changed feed URL here.
5. **Latest 50 articles**.

Rows are inserted only for **newly saved** articles (duplicates hit
`ON CONFLICT DO NOTHING`), so "0 new" means a run saved nothing for that
segment, not just that it found nothing new to add.

The expected segments are hard-coded at the top of each query:
`el-salvador/perplexity`, `finance-insurance/perplexity`,
`finance-insurance/rss`. That's what lets a silent segment show as 0 or
stale instead of disappearing from the panel. Any other segment seen in the
last 7 days is added automatically. **If you add or retire a topic or
source in `fetch_news.py`, update that list** (it's in each panel's query;
edit it in Grafana, then re-export, or regenerate the JSON).

## 4. The alert (this is the part that matters)

A dashboard only helps if you look at it. The alert emails you when a
segment goes stale.

Alerting → Alert rules → New alert rule:

- **Query** (data source from step 2, Code mode, Format: **Table**):

  ```sql
  WITH segs(topic, origin) AS (
    VALUES ('el-salvador', 'perplexity'),
           ('finance-insurance', 'perplexity'),
           ('finance-insurance', 'rss')
  )
  SELECT s.topic || ' / ' || s.origin AS segment,
         COALESCE(EXTRACT(EPOCH FROM now() - max(a.fetched_at)) / 3600, 9999)::float AS hours_since_last
  FROM segs s
  LEFT JOIN articles a ON a.topic = s.topic AND a.origin = s.origin
  GROUP BY 1
  ```

  Grafana makes one alert instance per row, labeled by `segment`, so the
  email names the silent topic / source.
  Only the fixed list is used here, with no auto-discovery, so a retired
  segment can never page you.
- **Condition**: Threshold **IS ABOVE 36**. If the editor adds a Reduce step,
  leave it on Last; each row is already a single number.
- **Evaluation**: every 1h. Pending period 0s.
- **Configure no data and error handling**: set *Alert state if execution
  error or timeout* to **Alerting**. That also pages you if Aiven is down,
  the service was powered off, or the `grafana_ro` password stops working.
- **Contact point**: your email.

To test it, temporarily change the threshold to `IS ABOVE 1`, confirm the
email arrives, then set it back to 36.
