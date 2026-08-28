#!/usr/bin/env python3
"""
run_all.py — Run fetch_news.py for every known topic in sequence.

This is the entry point for the scheduled daily task. The workflow that
calls this fires hourly across a morning window (rather than once) because
GitHub's `schedule` trigger isn't reliable enough on its own -- it can be
delayed by hours or dropped for a day outright under load, with no
catch-up. already_fetched_today() makes repeat firings a cheap no-op once
one of them succeeds, so a single missed or delayed trigger doesn't cost
the whole day.
"""

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent
LAST_FETCH_FILE = ROOT / "obsidian" / "Obsedian_R" / ".last_fetch"

TOPICS = [
    "el-salvador",
    "finance-insurance",
]


def already_fetched_today() -> bool:
    if not LAST_FETCH_FILE.exists():
        return False
    try:
        last_fetch = datetime.strptime(
            LAST_FETCH_FILE.read_text(encoding="utf-8").strip(), "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=timezone.utc)
    except (OSError, ValueError):
        return False
    return last_fetch.date() == datetime.now(timezone.utc).date()


def main() -> None:
    if already_fetched_today():
        print(f"{LAST_FETCH_FILE} already shows a successful fetch for today (UTC) -- skipping.")
        return

    python = sys.executable
    fetch_script = ROOT / "fetch_news.py"

    overall_ok = True

    for topic in TOPICS:
        print(f"{'=' * 60}")
        print(f"Running topic: {topic}")
        print(f"{'=' * 60}")

        result = subprocess.run(
            [python, str(fetch_script), topic],
            cwd=ROOT,
        )

        if result.returncode != 0:
            print(f"[ERROR] fetch_news.py exited with code {result.returncode} for topic '{topic}'")
            overall_ok = False

        print()

    if not overall_ok:
        sys.exit(1)

    # Written only on a successful daily fetch, so build_index.py can show
    # when articles were actually last fetched -- not just the last time
    # index.html happened to be regenerated (e.g. an unrelated template edit).
    # Written to a temp file and renamed into place atomically so a run
    # interrupted mid-write can never leave a partial/corrupt marker.
    LAST_FETCH_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = LAST_FETCH_FILE.parent / (LAST_FETCH_FILE.name + ".tmp")
    tmp_path.write_text(
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") + "\n", encoding="utf-8"
    )
    tmp_path.replace(LAST_FETCH_FILE)

    print("All topics completed successfully.")


if __name__ == "__main__":
    main()
