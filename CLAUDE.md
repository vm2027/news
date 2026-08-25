# news

A personal news aggregator. `fetch_news.py` pulls articles from RSS feeds
(`topics/<topic>.md` lists feed URLs) and, for topics in
`PERPLEXITY_TOPICS`, from the Perplexity API, saving each as a markdown
file with YAML frontmatter under `obsidian/Obsedian_R/<topic>/`.
`build_index.py` reads those files and regenerates `index.html`, the
GitHub Pages site. `.github/workflows/fetch-news.yml` runs both scripts
daily at 7am Pacific and commits the results.

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
- Branch protection on `master` (Settings → Branches → require a pull
  request + at least one approval before merging) is a stronger,
  GitHub-enforced version of this and should be enabled if not already —
  it doesn't depend on remembering to do the above.

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
