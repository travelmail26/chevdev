#!/usr/bin/env python3
"""API-level validation for the session switch lab."""

from __future__ import annotations

import json
import os
import sys
from urllib import request


WEB_BASE = os.getenv("LAB_WEB_BASE_URL", "http://127.0.0.1:5179")
BACKEND_BASE = os.getenv("LAB_SHARED_BACKEND_URL", "http://127.0.0.1:9001")
CANONICAL_USER_ID = os.getenv("LAB_CANONICAL_USER_ID", "demo_user_1")


def _post_json(base: str, path: str, payload: dict, headers: dict | None = None) -> tuple[int, str]:
    url = f"{base.rstrip('/')}{path}"
    body = json.dumps(payload).encode("utf-8")
    merged_headers = {"Content-Type": "application/json"}
    if headers:
        merged_headers.update(headers)
    req = request.Request(url, data=body, headers=merged_headers, method="POST")
    with request.urlopen(req, timeout=30) as resp:
        return resp.status, resp.read().decode("utf-8")


def _get_json(base: str, path: str) -> dict:
    url = f"{base.rstrip('/')}{path}"
    req = request.Request(url, method="GET")
    with request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _extract_last_content_event(sse_payload: str) -> str:
    blocks = [b for b in sse_payload.split("\n\n") if b.strip()]
    content = ""
    for block in blocks:
        event_name = ""
        data = ""
        for line in block.splitlines():
            if line.startswith("event: "):
                event_name = line[len("event: ") :].strip()
            if line.startswith("data: "):
                data = line[len("data: ") :]
        if event_name == "content" and data:
            parsed = json.loads(data)
            content = str(parsed.get("text", ""))
    return content


def main() -> int:
    # Reset session for deterministic test run.
    status, _ = _post_json(
        BACKEND_BASE,
        "/api/session/new",
        {"canonical_user_id": CANONICAL_USER_ID},
    )
    if status != 200:
        print("FAIL: could not reset session")
        return 1

    status, sse_web_1 = _post_json(
        WEB_BASE,
        "/api/chat",
        {
            "message": "brainstorm about follow restaurants new hashbrown",
            "model": "sonar",
        },
        headers={"x-canonical-user-id": CANONICAL_USER_ID},
    )
    if status != 200:
        print("FAIL: web /api/chat returned non-200 on first turn")
        return 1

    web_1_content = _extract_last_content_event(sse_web_1)
    if "Research brief" not in web_1_content:
        print("FAIL: first web response missing expected research marker")
        print(web_1_content)
        return 1

    status, telegram_raw = _post_json(
        BACKEND_BASE,
        "/api/chat",
        {
            "canonical_user_id": CANONICAL_USER_ID,
            "source": "telegram",
            "message": "Give me a quick recap in one line",
        },
    )
    if status != 200:
        print("FAIL: backend telegram turn returned non-200")
        return 1

    telegram_json = json.loads(telegram_raw)
    telegram_text = str(telegram_json.get("assistant_text", ""))
    if "Quick recap" not in telegram_text:
        print("FAIL: telegram response did not reference shared web context")
        print(telegram_text)
        return 1

    status, sse_web_2 = _post_json(
        WEB_BASE,
        "/api/chat",
        {
            "message": "continue from telegram context",
            "model": "sonar",
        },
        headers={"x-canonical-user-id": CANONICAL_USER_ID},
    )
    if status != 200:
        print("FAIL: web /api/chat returned non-200 on second turn")
        return 1

    web_2_content = _extract_last_content_event(sse_web_2)
    if "Continuity note from Telegram context" not in web_2_content:
        print("FAIL: second web response missing telegram continuity note")
        print(web_2_content)
        return 1

    snapshot = _get_json(BACKEND_BASE, f"/api/session/{CANONICAL_USER_ID}")
    if int(snapshot.get("message_count", 0)) < 6:
        print("FAIL: expected at least 6 messages in shared session history")
        print(snapshot)
        return 1

    print("PASS: shared-session web<->telegram continuity validated")
    print(f"PASS: final message_count={snapshot.get('message_count')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
