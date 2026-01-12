#!/usr/bin/env python3
"""Scan recent Mongo chat sessions for hollandaise/butter experiments."""

import argparse
import logging
import os
import sys
from typing import Iterable

from pymongo import MongoClient

DEFAULT_DB_NAME = "chef_chatbot"
DEFAULT_COLLECTION_NAME = "chat_sessions"
DEFAULT_KEYWORDS = ["hollandaise", "butter", "sous vide"]


def _mask_uri(uri: str) -> str:
    if not uri:
        return ""
    # Before: full URI echoed to logs; After: only last 6 chars for safety.
    return f"...{uri[-6:]}"


def _get_collection():
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        # Before: missing env -> crash later; After: clear error + exit.
        raise SystemExit("MONGODB_URI is not set.")
    db_name = os.environ.get("MONGODB_DB_NAME", DEFAULT_DB_NAME)
    collection_name = os.environ.get("MONGODB_COLLECTION_NAME", DEFAULT_COLLECTION_NAME)
    logging.info(
        "mongo_config uri_suffix=%s db=%s collection=%s",
        _mask_uri(uri),
        db_name,
        collection_name,
    )
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    return client[db_name][collection_name]


def _normalize_keywords(raw_keywords: Iterable[str]) -> list[str]:
    keywords = [k.strip().lower() for k in raw_keywords if k.strip()]
    # Before: empty list -> no matches; After: default keywords fill in.
    return keywords or DEFAULT_KEYWORDS


def _message_text(message: dict) -> str:
    content = message.get("content") or ""
    tool_calls = message.get("tool_calls") or []
    tool_text = []
    for tool in tool_calls:
        args = tool.get("function", {}).get("arguments")
        if args:
            tool_text.append(str(args))
    combined = "\n".join([content] + tool_text).strip()
    # Before: tool args ignored; After: tool args included in search text.
    return combined


def _matches_keywords(text: str, keywords: list[str]) -> bool:
    lower = text.lower()
    return any(keyword in lower for keyword in keywords)


def _snippet(text: str, max_len: int = 220) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= max_len:
        return collapsed
    return f"{collapsed[:max_len].rstrip()}..."


def _scan_session(doc: dict, keywords: list[str]) -> list[dict]:
    hits = []
    for msg in doc.get("messages", []):
        if not isinstance(msg, dict):
            continue
        text = _message_text(msg)
        if not text:
            continue
        if _matches_keywords(text, keywords):
            hits.append(
                {
                    "role": msg.get("role") or "unknown",
                    "snippet": _snippet(text),
                    "full_text": text,
                }
            )
    return hits


def _print_session(doc: dict, hits: list[dict], show_full: bool) -> None:
    print("")
    print(f"session_id: {doc.get('chat_session_id')}")
    print(f"user_id: {doc.get('user_id')}")
    print(f"session_created_at: {doc.get('chat_session_created_at')}")
    print(f"last_updated_at: {doc.get('last_updated_at')}")
    if not hits:
        print("matches: none")
        return
    print(f"matches: {len(hits)}")
    for hit in hits:
        print(f"- role: {hit['role']}")
        print(f"  snippet: {hit['snippet']}")
        if show_full:
            print("  full_text:")
            print(hit["full_text"])


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scan Mongo chat sessions for hollandaise/butter experiments."
    )
    parser.add_argument("--user-id", help="Filter to a specific user_id.")
    parser.add_argument("--limit", type=int, default=2, help="Number of recent sessions to scan.")
    parser.add_argument(
        "--keywords",
        nargs="*",
        default=DEFAULT_KEYWORDS,
        help="Keywords to match (case-insensitive).",
    )
    parser.add_argument(
        "--scan-all",
        action="store_true",
        help="Scan all sessions for the user (ignores --limit).",
    )
    parser.add_argument(
        "--show-full",
        action="store_true",
        help="Print full matching message text.",
    )
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = _parse_args()
    keywords = _normalize_keywords(args.keywords)
    collection = _get_collection()

    query = {}
    if args.user_id:
        # Before: no user filter -> scans all; After: user_id filter narrows scope.
        query["user_id"] = str(args.user_id)

    cursor = collection.find(query).sort("last_updated_at", -1)
    if not args.scan_all:
        cursor = cursor.limit(args.limit)

    scanned = 0
    for doc in cursor:
        scanned += 1
        hits = _scan_session(doc, keywords)
        _print_session(doc, hits, args.show_full)

    if scanned == 0:
        print("No sessions matched the query. Check user_id and collection settings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
