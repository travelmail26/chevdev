#!/usr/bin/env python3
"""
nano_entity_worker.py

Small NLP worker using gpt-5-nano-2025-08-07.
- Reads JSON from stdin.
- Extracts cooking entities from provided sessions.
- Outputs JSON to stdout.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any, Dict, List

from openai import OpenAI


MODEL = "gpt-5-nano-2025-08-07"
MAX_MESSAGE_CHARS = 1200


def render_sessions(sessions: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for session in sessions:
        session_id = session.get("session_id") or session.get("_id") or "unknown_session"
        session_date = session.get("last_updated_at") or session.get("chat_session_created_at")
        for message in session.get("messages", []) or []:
            content = str(message.get("content") or "")
            if len(content) > MAX_MESSAGE_CHARS:
                # Before: 5000 chars -> After: 1200 chars + "...".
                content = content[:MAX_MESSAGE_CHARS].rstrip() + "..."
            lines.append(
                f"[{session_id}|{session_date}|{message.get('index')}|{message.get('role')}]: {content}"
            )
    return "\n".join(lines)


def parse_json(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise RuntimeError("Model returned non-JSON output.")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")

    raw = sys.stdin.read().strip()
    if not raw:
        raise RuntimeError("Expected JSON on stdin.")
    payload = json.loads(raw)

    instruction = (payload.get("instruction") or "").strip()
    sessions = payload.get("sessions") or []

    if not instruction:
        raise RuntimeError("instruction is required.")

    text_block = render_sessions(sessions)

    prompt = f"""
You are a small NLP extraction bot.
Your job: extract cooking entities from the provided messages.
You must follow the instruction exactly and return JSON only.

Output format:
- A JSON list of objects.
- Each object should include only fields asked for by the instruction.
- Always include evidence keys if possible: session_id, message_index, excerpt.

Example:
Instruction: "Extract temperature and outcome mentions for onions"
Output:
[
  {{"temperature":"180 F","outcome":"browned", "session_id":"abc", "message_index":12, "excerpt":"..."}}
]

Instruction:
{instruction}

Messages:
{text_block}
"""

    client = OpenAI()
    resp = client.responses.create(
        model=MODEL,
        input=[{"role": "user", "content": prompt}],
    )

    output_text = (resp.output_text or "").strip()
    data = parse_json(output_text)
    sys.stdout.write(json.dumps(data, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("Missing OPENAI_API_KEY.")
    main()
