#!/usr/bin/env python3
"""Telegram-style CLI adapter for the session switch lab."""

from __future__ import annotations

import argparse
import json
import os
import sys
from urllib import request


DEFAULT_BACKEND = os.getenv("LAB_SHARED_BACKEND_URL", "http://127.0.0.1:9001")
DEFAULT_USER = os.getenv("LAB_CANONICAL_USER_ID", "demo_user_1")


def _post_json(path: str, payload: dict) -> dict:
    url = f"{DEFAULT_BACKEND.rstrip('/')}{path}"
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get_json(path: str) -> dict:
    url = f"{DEFAULT_BACKEND.rstrip('/')}{path}"
    req = request.Request(url, method="GET")
    with request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Telegram simulator for shared-session lab")
    parser.add_argument("--user", default=DEFAULT_USER, help="Canonical user id shared across interfaces")
    parser.add_argument("--message", default="", help="Message to send as telegram source")
    parser.add_argument("--set-mode", default="", help="Optional mode set (e.g. general)")
    parser.add_argument("--new-session", action="store_true", help="Start a fresh session")
    parser.add_argument("--show-session", action="store_true", help="Print full current session payload")
    args = parser.parse_args()

    if args.new_session:
        result = _post_json("/api/session/new", {"canonical_user_id": args.user})
        print("NEW SESSION:", json.dumps(result, indent=2))

    if args.set_mode:
        result = _post_json(
            "/api/mode",
            {"canonical_user_id": args.user, "bot_mode": args.set_mode},
        )
        print("MODE UPDATED:", json.dumps(result, indent=2))

    if args.message:
        result = _post_json(
            "/api/chat",
            {
                "canonical_user_id": args.user,
                "source": "telegram",
                "message": args.message,
            },
        )
        print("TELEGRAM RESPONSE:")
        print(result.get("assistant_text", ""))

    if args.show_session:
        result = _get_json(f"/api/session/{args.user}")
        print("SESSION SNAPSHOT:")
        print(json.dumps(result, indent=2))

    if not (args.new_session or args.set_mode or args.message or args.show_session):
        parser.print_help(sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
