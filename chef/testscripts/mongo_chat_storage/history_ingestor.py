"""CLI utility to migrate existing chat history JSON files into MongoDB."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Iterable

from .repository import MongoChatRepository

logger = logging.getLogger(__name__)


def iter_history_files(log_dir: Path) -> Iterable[Path]:
    for path in sorted(log_dir.glob("*_history.json")):
        if path.is_file():
            yield path


def load_history(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def ingest_directory(
    log_dir: Path,
    repo: MongoChatRepository,
    dry_run: bool = False,
    limit: int | None = None,
    verbose: bool = False,
) -> int:
    processed = 0
    for idx, file_path in enumerate(iter_history_files(log_dir), start=1):
        if limit is not None and processed >= limit:
            break
        try:
            history = load_history(file_path)
        except json.JSONDecodeError as exc:
            logger.error("Skipping %s due to JSON error: %s", file_path, exc)
            continue
        if verbose:
            print(f"[ingestor] Loaded {file_path.name} with {len(history.get('messages', []))} messages")
        if not dry_run:
            repo.upsert_session(history)
        processed += 1
        if verbose:
            print(f"[ingestor] {'Dry-run ' if dry_run else ''}stored session for user {history.get('user_id')}")
    return processed


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--log-dir",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "utilities" / "chat_history_logs",
        help="Directory containing *_history.json files.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Load files without writing to MongoDB")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of files to process")
    parser.add_argument("--verbose", action="store_true", help="Print per-file progress")
    return parser


def main(args: list[str] | None = None) -> int:
    parser = build_arg_parser()
    parsed = parser.parse_args(args=args)
    repo = MongoChatRepository()
    count = ingest_directory(
        log_dir=parsed.log_dir,
        repo=repo,
        dry_run=parsed.dry_run,
        limit=parsed.limit,
        verbose=parsed.verbose,
    )
    print(f"Processed {count} chat history files from {parsed.log_dir}")
    if not parsed.dry_run:
        print(f"MongoDB now stores approximately {repo.count_sessions()} sessions (estimated)")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry guard
    raise SystemExit(main())
