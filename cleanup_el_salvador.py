"""
cleanup_el_salvador.py
Removes articles from obsidian/el-salvador/ that don't mention any
El Salvador keywords in their title or body. Run once to purge pre-filter
articles that snuck in before keyword filtering was added.
"""

import re
from pathlib import Path

OBSIDIAN_DIR = Path(__file__).parent / "obsidian" / "el-salvador"

KEYWORDS = [
    "el salvador",
    "salvadoran",
    "salvadorean",
    "salvadoreño",
    "bukele",
    "cecot",
    "san salvador",
    "nayib",
]

def is_relevant(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in KEYWORDS)

def main():
    if not OBSIDIAN_DIR.exists():
        print("Folder not found:", OBSIDIAN_DIR)
        return

    removed = []
    kept = []

    for md_file in sorted(OBSIDIAN_DIR.glob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        if is_relevant(text):
            kept.append(md_file.name)
        else:
            md_file.unlink()
            removed.append(md_file.name)

    print(f"Removed {len(removed)} irrelevant articles:")
    for name in removed:
        print(f"  ✗ {name}")

    print(f"\nKept {len(kept)} relevant articles:")
    for name in kept:
        print(f"  ✓ {name}")

if __name__ == "__main__":
    main()
