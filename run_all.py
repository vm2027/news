#!/usr/bin/env python3
"""
run_all.py — Run fetch_news.py for every known topic in sequence.

This is the entry point for the scheduled daily task.
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


def main() -> None:
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
    LAST_FETCH_FILE.parent.mkdir(parents=True, exist_ok=True)
    LAST_FETCH_FILE.write_text(
        datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") + "\n", encoding="utf-8"
    )

    print("All topics completed successfully.")


if __name__ == "__main__":
    main()
