"""Manual entrypoint for sending scripted conversations to Mongo-backed storage."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable, List

from . import schemas
from .repository import MongoChatRepository

_SCENARIOS_DIR = Path(__file__).resolve().parent / "scenarios"


def list_available_scenarios() -> List[str]:
    return sorted(path.stem for path in _SCENARIOS_DIR.glob("*.json"))


def load_scenario(name: str) -> dict:
    path = _SCENARIOS_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Scenario '{name}' not found under {_SCENARIOS_DIR}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def run_conversation(
    user_id: str,
    messages: Iterable[schemas.Message],
    repository: MongoChatRepository,
    dry_run: bool = False,
    metadata: dict | None = None,
) -> str:
    session_document = schemas.build_session_from_conversation(
        user_id=user_id,
        conversation=messages,
        metadata=metadata,
        session_prefix="manual",
    )
    if dry_run:
        print("[manual_runner] Dry run: not writing session to MongoDB")
        return session_document["chat_session_id"]
    session_id = repository.upsert_session(session_document)
    stored = repository.get_session(session_id)
    message_count = len(stored.get("messages", [])) if stored else 0
    print(
        f"[manual_runner] Stored session {session_id} for user {user_id} with {message_count} messages"
    )
    return session_id


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scenario",
        default="make_eggs",
        help="Scenario name under scenarios/. Use 'list' to show options.",
    )
    parser.add_argument("--user-id", default=None, help="Override the scenario user id")
    parser.add_argument("--dry-run", action="store_true", help="Do not write to MongoDB")
    parser.add_argument(
        "--metadata",
        default=None,
        help="Optional JSON object to merge into session metadata",
    )
    return parser


def main(args: List[str] | None = None) -> int:
    parser = build_parser()
    parsed = parser.parse_args(args=args)

    if parsed.scenario == "list":
        print("Available scenarios:")
        for scenario_name in list_available_scenarios():
            print(f" - {scenario_name}")
        return 0

    scenario = load_scenario(parsed.scenario)
    user_id = parsed.user_id or scenario.get("user_id", "manual_user")
    metadata = dict(scenario.get("metadata", {}))
    if parsed.metadata:
        try:
            extra_metadata = json.loads(parsed.metadata)
            if not isinstance(extra_metadata, dict):
                raise ValueError("Metadata JSON must decode to an object")
            metadata.update(extra_metadata)
        except ValueError as exc:
            parser.error(f"Invalid metadata JSON: {exc}")

    repository = MongoChatRepository()
    run_conversation(
        user_id=user_id,
        messages=scenario.get("messages", []),
        repository=repository,
        dry_run=parsed.dry_run,
        metadata=metadata,
    )
    if not parsed.dry_run:
        sessions = repository.get_sessions_for_user(user_id)
        print(
            f"[manual_runner] Verified retrieval: found {len(sessions)} session(s) for user {user_id}"
        )
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI guard
    raise SystemExit(main())
