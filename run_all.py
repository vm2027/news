#!/usr/bin/env python3
"""
run_all.py — Run fetch_news.py for every known topic in sequence.

This is the entry point for the scheduled daily task.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent

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

    print("All topics completed successfully.")


if __name__ == "__main__":
    main()
