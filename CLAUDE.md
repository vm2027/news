# news

A personal news aggregator. `fetch_news.py` pulls articles from RSS feeds
(`topics/<topic>.md` lists feed URLs) and, for topics in
`PERPLEXITY_TOPICS`, from the Perplexity API, saving each as a markdown
file with YAML frontmatter under `obsidian/Obsedian_R/<topic>/`.
`build_index.py` reads those files and regenerates `index.html`, the
GitHub Pages site. `.github/workflows/fetch-news.yml` runs both scripts
and commits the results, targeting once daily around 7am Pacific.

Because GitHub's `schedule` trigger isn't reliable on its own (runs get
delayed under load, and a missed slot is dropped rather than retried —
two scheduled runs were silently skipped in a row on 2026-08-27/28), the
workflow's cron fires hourly across a 14:00-20:00 UTC window instead of
once. `run_all.py`'s `already_fetched_today()` checks the
`.last_fetch` marker and no-ops immediately once one firing in the
window has already succeeded, so the retries cost almost nothing.

Topics currently configured: `el-salvador`, `finance-insurance`.
`finance-insurance` uses both RSS and Perplexity together (Perplexity
supplements RSS rather than replacing it — see `PERPLEXITY_SUPPLEMENTS_RSS`
in `fetch_news.py`).

## Verification lesson (don't repeat this)

While adding the RSS/Perplexity source badges to `index.html`, a bug was
introduced and missed: RSS publishes far more Finance & Insurance articles
per day than Perplexity does, so `load_articles()`'s "top 10 by filename"
selection silently pushed every Perplexity article out of the display for
that topic — while `el-salvador` (which has more Perplexity than RSS
volume) looked fine. The badge feature was verified by checking the
page-wide total (9 Perplexity + 11 RSS, which looked plausible) instead of
the per-topic breakdown, so the zero-Perplexity-articles-shown bug on
Finance & Insurance wasn't caught until the user asked about it directly.

When this repo has more than one topic/source/category feeding the same
page (currently: 2 topics × 2 sources each):
- **Verify per-segment, not just in aggregate.** A page-wide or
  all-topics total can look correct while one topic or one source is
  silently at zero. Check each topic × source combination that matters,
  not just the sum.
- **Verify against the outcome the user described, not just that the
  code runs.** Rendering a badge correctly is not the same as the
  specific article actually being displayed. If the user's question was
  "why don't I see X", the check is "is X now visible", not "does the
  code that would show X run without error."
- Before calling a fix on this project done, actually count what's
  showing per topic (e.g. `grep`/parse `index.html` broken out by topic
  section), not just the whole-page total — the same way the fix for
  this exact bug was confirmed in PR #11.

## Copilot review is a required check, not optional feedback

On PR #9, GitHub Copilot's automated review caught an HTML-escaping /
tabnabbing issue that was missed during self-review — after the PR had
already been merged, requiring a separate follow-up PR (#10) to fix.
To make Copilot review an actual check-and-balance instead of feedback
that arrives too late to matter:

- After opening a PR, call `request_copilot_review` and wait for its
  review comment before merging. Do not merge solely because
  `mergeable_state` is `"clean"` — that only reflects merge conflicts,
  not whether Copilot has reviewed the diff.
- If Copilot flags something, fix it (or explain in this repo why not)
  before merging, the same way a human reviewer's comment would be
  handled.
- A ruleset on `master` requires a pull request before merging and a
  required status check named `"verify"` that no workflow in this repo
  reports — so it can never be satisfied, and it blocks *any* direct
  push to `master`, including the daily fetch workflow's own commit.
  Only the "Repository admin" role is on the bypass list (checked
  2026-08-28); `github-actions[bot]` (the identity behind the default
  `GITHUB_TOKEN`) is not, and isn't selectable as a bypass actor on this
  repo at all. See "Daily fetch push authentication" below for how
  `fetch-news.yml` works around this.

## Daily fetch push authentication

`fetch-news.yml`'s checkout step passes `token: ${{ secrets.GH_PUSH_TOKEN }}`
instead of relying on the default `GITHUB_TOKEN`. This is required, not
optional: the default token pushes as `github-actions[bot]`, which the
`master` ruleset blocks outright (see above) — every run fails at the
commit/push step otherwise, exactly as runs #33-35 did on 2026-08-28.
`GH_PUSH_TOKEN` is a fine-grained PAT scoped to just this repo
(Contents: read/write), attributed to the repo owner's account, which
the ruleset's "Repository admin" bypass does cover. It has an expiration
and will need to be regenerated and the secret updated when it lapses —
if the workflow starts failing at "Commit and push new articles" with a
403/protected-branch error, check that first.

## Analytics

`build_index.py` embeds a Plausible Analytics script tag
(`data-domain="vm2027.github.io"`) in `<head>`. Plausible only collects
data once the domain is registered in the site owner's Plausible
dashboard (plausible.io or self-hosted) — that's an account/billing
decision, not something a Claude Code session can do on its own, so it's
the user's responsibility to complete. Since this is a project page
(`vm2027.github.io/news/`, not a custom domain), stats are grouped under
the whole `vm2027.github.io` domain — any other GitHub Pages project
under the same username would appear in the same Plausible site unless
filtered by page path in the dashboard.

## Workflow notes

- Verification of live behavior (RSS feed reachability, Perplexity API
  responses) can't be done from this sandbox — outbound network access is
  restricted here. Use `workflow_dispatch` to run `fetch-news.yml` on the
  actual GitHub Actions runner (real network + the real
  `PERPLEXITY_API_KEY` secret), then read the job logs, instead of trying
  to hit feeds or the Perplexity API directly from this environment.
- After any change to `build_index.py` or the markdown under
  `obsidian/Obsedian_R/`, regenerate and commit `index.html` in the same
  change — the live site is the committed file, not something built at
  deploy time.
