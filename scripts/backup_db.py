#!/usr/bin/env python3
import argparse
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from game.db import db_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a consistent SQLite backup.")
    parser.add_argument(
        "target",
        nargs="?",
        help="Backup file path. Defaults to /tmp/providnyk-<UTC timestamp>.sqlite3.",
    )
    args = parser.parse_args()

    source = db_path()
    if not source.exists():
        raise SystemExit(f"Database does not exist: {source}")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    target = Path(args.target or f"/tmp/providnyk-{timestamp}.sqlite3")
    target.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(source) as source_conn:
        with sqlite3.connect(target) as target_conn:
            source_conn.backup(target_conn)

    print(target)


if __name__ == "__main__":
    main()
