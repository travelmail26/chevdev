#!/usr/bin/env python3
"""Throwaway lab backend for cross-frontend shared sessions.

This service is intentionally isolated under interfacetest/session_switch_lab
so it can be deleted without affecting the main bot runtime.
"""

from __future__ import annotations

import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from flask import Flask, jsonify, request


APP = Flask(__name__)

LAB_ROOT = Path(__file__).resolve().parent
RUNTIME_DIR = LAB_ROOT / "runtime"
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
STORE_PATH = RUNTIME_DIR / "session_store.json"

DEFAULT_MODE = "general"
DEFAULT_PERPLEXITY_MODEL = os.getenv("LAB_PERPLEXITY_MODEL", "sonar")
DEFAULT_XAI_MODEL = os.getenv("LAB_XAI_MODEL", os.getenv("XAI_MODEL", "grok-4-1-fast-non-reasoning-latest"))
SHARED_FRONTEND_INSTRUCTION = (
    "You are one assistant shared across two front ends for the same user session. "
    "Use only the provided conversation history for continuity. "
    "Do not invent prior turns, steps, sources, or facts. "
    "Do not create new numbered steps unless they already exist in conversation history. "
    "If the user sends an ambiguous short message (example: 'code 11') and it is not in history, ask what they mean. "
    "If context is missing, say that clearly and ask a short clarifying question. "
    "Be concise and practical."
)


def _truthy(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _build_frontend_instruction(source: str) -> str:
    frontend = (source or "").strip().lower()
    if frontend == "web":
        mode_note = (
            "Current frontend: web research. "
            "Provide research-style answers and use available web evidence."
        )
    else:
        mode_note = (
            "Current frontend: telegram chat. "
            "No web lookup in this step. Answer from shared conversation turns only."
        )

    return (
        f"{SHARED_FRONTEND_INSTRUCTION}\n"
        f"{mode_note}\n"
        "When asked 'what did I just ask' or similar, quote the latest user turn from history."
    )


class SessionStore:
    """Very small JSON file store for the lab.

    Before example: each frontend had independent storage.
    After example: both frontends read/write one canonical user record.
    """

    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        if not self.path.exists():
            self.path.write_text(json.dumps({"users": {}}, indent=2), encoding="utf-8")

    def _read(self) -> dict[str, Any]:
        raw = self.path.read_text(encoding="utf-8").strip()
        if not raw:
            return {"users": {}}
        return json.loads(raw)

    def _write(self, data: dict[str, Any]) -> None:
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @staticmethod
    def _new_session_id(user_id: str) -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        return f"{user_id}_{stamp}"

    def ensure_user(self, user_id: str) -> dict[str, Any]:
        with self._lock:
            data = self._read()
            users = data.setdefault("users", {})
            doc = users.get(user_id)
            if not isinstance(doc, dict):
                doc = {
                    "canonical_user_id": user_id,
                    "bot_mode": DEFAULT_MODE,
                    "active_session_id": self._new_session_id(user_id),
                    "messages": [],
                    "last_updated_at": datetime.now(timezone.utc).isoformat(),
                }
                users[user_id] = doc
                self._write(data)
            return doc

    def get_user(self, user_id: str) -> dict[str, Any]:
        with self._lock:
            data = self._read()
            users = data.setdefault("users", {})
            doc = users.get(user_id)
            if not isinstance(doc, dict):
                doc = {
                    "canonical_user_id": user_id,
                    "bot_mode": DEFAULT_MODE,
                    "active_session_id": self._new_session_id(user_id),
                    "messages": [],
                    "last_updated_at": datetime.now(timezone.utc).isoformat(),
                }
                users[user_id] = doc
                self._write(data)
            return doc

    def set_mode(self, user_id: str, bot_mode: str) -> dict[str, Any]:
        mode = (bot_mode or "").strip().lower() or DEFAULT_MODE
        with self._lock:
            data = self._read()
            users = data.setdefault("users", {})
            doc = users.get(user_id)
            if not isinstance(doc, dict):
                doc = {
                    "canonical_user_id": user_id,
                    "bot_mode": mode,
                    "active_session_id": self._new_session_id(user_id),
                    "messages": [],
                    "last_updated_at": datetime.now(timezone.utc).isoformat(),
                }
            else:
                doc["bot_mode"] = mode
                doc["last_updated_at"] = datetime.now(timezone.utc).isoformat()
            users[user_id] = doc
            self._write(data)
            return doc

    def append_turn(
        self,
        user_id: str,
        source: str,
        user_message: str,
        assistant_message: str,
        thinking: str,
        sources: list[dict[str, str]],
    ) -> dict[str, Any]:
        with self._lock:
            data = self._read()
            users = data.setdefault("users", {})
            doc = users.get(user_id)
            if not isinstance(doc, dict):
                doc = {
                    "canonical_user_id": user_id,
                    "bot_mode": DEFAULT_MODE,
                    "active_session_id": self._new_session_id(user_id),
                    "messages": [],
                }

            now = datetime.now(timezone.utc).isoformat()
            messages = doc.setdefault("messages", [])
            messages.append(
                {
                    "role": "user",
                    "source": source,
                    "content": user_message,
                    "created_at": now,
                }
            )
            messages.append(
                {
                    "role": "assistant",
                    "source": source,
                    "content": assistant_message,
                    "thinking": thinking,
                    "sources": sources,
                    "created_at": now,
                }
            )

            # Keep this compact for a throwaway lab run.
            if len(messages) > 120:
                doc["messages"] = messages[-120:]

            doc["last_updated_at"] = now
            users[user_id] = doc
            self._write(data)
            return doc

    def reset_session(self, user_id: str) -> dict[str, Any]:
        with self._lock:
            data = self._read()
            users = data.setdefault("users", {})
            doc = users.get(user_id)
            if not isinstance(doc, dict):
                doc = {
                    "canonical_user_id": user_id,
                    "bot_mode": DEFAULT_MODE,
                    "messages": [],
                }
            doc["active_session_id"] = self._new_session_id(user_id)
            doc["messages"] = []
            doc["last_updated_at"] = datetime.now(timezone.utc).isoformat()
            users[user_id] = doc
            self._write(data)
            return doc


STORE = SessionStore(STORE_PATH)


def _contains_any(text: str, patterns: list[str]) -> bool:
    lowered = text.lower()
    return any(p in lowered for p in patterns)


def _last_user_message(messages: list[dict[str, Any]], source: str | None = None) -> str:
    for message in reversed(messages):
        if message.get("role") != "user":
            continue
        if source and message.get("source") != source:
            continue
        content = str(message.get("content", "")).strip()
        if content:
            return content
    return ""


def _last_assistant_message(messages: list[dict[str, Any]], source: str | None = None) -> str:
    for message in reversed(messages):
        if message.get("role") != "assistant":
            continue
        if source and message.get("source") != source:
            continue
        content = str(message.get("content", "")).strip()
        if content:
            return content
    return ""


def _compact_recap(text: str, limit: int = 260) -> str:
    content = str(text or "").strip()
    if not content:
        return ""
    normalized = content.replace("\n", " ").strip()
    if normalized.lower().startswith("research brief:"):
        normalized = normalized[len("research brief:") :].strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."


def _first_list_item(text: str) -> str:
    content = str(text or "")
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("- "):
            return line[2:].strip()
        if re.match(r"^\d+[.)]\s+", line):
            return re.sub(r"^\d+[.)]\s+", "", line).strip()
    return ""


def _mock_research_sources(query: str) -> list[dict[str, str]]:
    # These are deterministic placeholders so e2e tests work offline.
    return [
        {
            "title": "How to Build a Restaurant Trend Board",
            "url": "https://lab.local/source/trend-board",
            "snippet": f"Framework for evaluating ideas like: {query[:90]}",
        },
        {
            "title": "Hash Brown Menu Innovation Patterns",
            "url": "https://lab.local/source/hashbrown-patterns",
            "snippet": "Common variations: loaded hash browns, crisp texture upgrades, brunch pairings.",
        },
        {
            "title": "Neighborhood Restaurant Follow Strategy",
            "url": "https://lab.local/source/local-follow",
            "snippet": "Use neighborhood segmentation, timing tests, and repeatable social hooks.",
        },
    ]


def _build_alternating_messages(
    history: list[dict[str, Any]],
    latest_user_message: str,
    max_messages: int = 10,
) -> list[dict[str, str]]:
    cleaned: list[dict[str, str]] = []

    for message in history:
        role = str(message.get("role", "")).strip()
        if role not in {"user", "assistant"}:
            continue
        content = str(message.get("content", "")).strip()
        if not content:
            continue

        if not cleaned:
            if role != "user":
                continue
            cleaned.append({"role": "user", "content": content})
            continue

        if cleaned[-1]["role"] == role:
            # Before example: same-role runs can break strict chat APIs.
            # After example: merge adjacent runs so roles alternate.
            cleaned[-1]["content"] = f"{cleaned[-1]['content']}\n\n{content}"
            continue

        cleaned.append({"role": role, "content": content})

    recent = cleaned[-max_messages:]
    if recent and recent[0]["role"] == "assistant":
        recent = recent[1:]

    latest = latest_user_message.strip()
    if not recent and latest:
        recent = [{"role": "user", "content": latest}]
    elif latest and recent[-1]["role"] != "user":
        recent.append({"role": "user", "content": latest})

    return recent


def _normalize_perplexity_sources(payload: dict[str, Any]) -> list[dict[str, str]]:
    sources: list[dict[str, str]] = []
    search_results = payload.get("search_results")
    citations = payload.get("citations")

    if isinstance(search_results, list):
        for idx, item in enumerate(search_results, start=1):
            if not isinstance(item, dict):
                continue
            sources.append(
                {
                    "title": str(item.get("title") or f"Source {idx}"),
                    "url": str(item.get("url") or ""),
                    "snippet": str(item.get("snippet") or ""),
                }
            )
    elif isinstance(citations, list):
        for idx, url in enumerate(citations, start=1):
            sources.append(
                {
                    "title": f"Source {idx}",
                    "url": str(url or ""),
                    "snippet": "",
                }
            )

    return sources


def _call_real_perplexity_research(query: str, history: list[dict[str, Any]]) -> tuple[str, str, list[dict[str, str]]]:
    key = os.getenv("PERPLEXITY_KEY") or os.getenv("PERPLEXITY_API_KEY")
    if not key:
        raise RuntimeError("PERPLEXITY_KEY/PERPLEXITY_API_KEY is missing")

    messages = _build_alternating_messages(history, latest_user_message=query, max_messages=10)
    request_messages = [
        {
            "role": "system",
            "content": _build_frontend_instruction("web"),
        },
        *messages,
    ]
    response = requests.post(
        "https://api.perplexity.ai/chat/completions",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        json={
            "model": DEFAULT_PERPLEXITY_MODEL,
            "messages": request_messages,
            "stream": False,
        },
        timeout=45,
    )
    response.raise_for_status()
    payload = response.json()
    raw_content = str((payload.get("choices") or [{}])[0].get("message", {}).get("content") or "").strip()
    sources = _normalize_perplexity_sources(payload)
    final = f"Research brief:\n\n{raw_content or '(no answer text returned)'}"
    thinking = f"Live web search via Perplexity model={DEFAULT_PERPLEXITY_MODEL}"
    return final, thinking, sources


def _build_web_research_reply(query: str, history: list[dict[str, Any]]) -> tuple[str, str, list[dict[str, str]]]:
    sources = _mock_research_sources(query)
    thinking = "Scanning local research index, clustering restaurant + hash brown opportunities, then drafting concise actions."

    plan = [
        "Target brunch-forward and late-night comfort-food spots first.",
        "Pilot 2 SKUs: classic crispy stack + loaded signature version.",
        "Test a weekly 'new hashbrown' drop and track repeat orders.",
    ]

    answer = (
        "Research brief: follow restaurants + new hashbrown brainstorming.\n\n"
        + "\n".join(f"- {item}" for item in plan)
    )
    return answer, thinking, sources


def _call_real_xai_generic(query: str, history: list[dict[str, Any]]) -> tuple[str, str, list[dict[str, str]]]:
    key = os.getenv("XAI_API_KEY")
    if not key:
        raise RuntimeError("XAI_API_KEY is missing")

    context_messages = _build_alternating_messages(history, latest_user_message=query, max_messages=10)
    request_messages = [
        {
            "role": "system",
            "content": _build_frontend_instruction("telegram"),
        },
        *context_messages,
    ]
    response = requests.post(
        "https://api.x.ai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        json={
            "model": DEFAULT_XAI_MODEL,
            "messages": request_messages,
            "stream": False,
        },
        timeout=45,
    )
    response.raise_for_status()
    payload = response.json()
    text = str((payload.get("choices") or [{}])[0].get("message", {}).get("content") or "").strip()
    return text or "No response text returned.", "", []


def _build_telegram_generic_reply(query: str, history: list[dict[str, Any]]) -> tuple[str, str, list[dict[str, str]]]:
    _ = query
    _ = history
    return ("I don't have enough context for that yet. Ask in web first, then I can continue here.", "", [])


def _generate_reply(source: str, query: str, user_doc: dict[str, Any]) -> tuple[str, str, list[dict[str, str]]]:
    history = user_doc.get("messages", []) if isinstance(user_doc, dict) else []
    if source == "web":
        if _truthy(os.getenv("LAB_ENABLE_REAL_WEB_RESEARCH"), default=True):
            try:
                return _call_real_perplexity_research(query, history)
            except Exception as exc:
                print(f"LAB_WARN real_web_research_failed: {exc}")
        return _build_web_research_reply(query, history)
    if _truthy(os.getenv("LAB_ENABLE_REAL_TELEGRAM_GENERIC"), default=True):
        try:
            return _call_real_xai_generic(query, history)
        except Exception as exc:
            print(f"LAB_WARN real_telegram_generic_failed: {exc}")
    return _build_telegram_generic_reply(query, history)


@APP.get("/health")
def health():
    return jsonify({"ok": True, "store": str(STORE_PATH)})


@APP.get("/")
def index():
    # Before example: opening backend root returned 404 and looked broken.
    # After example: backend root returns a clear status payload with next-step hints.
    return jsonify(
        {
            "ok": True,
            "service": "session_switch_lab_backend",
            "hint": "This is the backend API. Open the web UI port from main.py output.",
            "health_path": "/health",
            "chat_path": "/api/chat",
            "session_path_example": "/api/session/<canonical_user_id>",
        }
    )


@APP.post("/api/mode")
def set_mode():
    payload = request.get_json(silent=True) or {}
    user_id = str(payload.get("canonical_user_id", "")).strip()
    bot_mode = str(payload.get("bot_mode", DEFAULT_MODE)).strip().lower() or DEFAULT_MODE
    if not user_id:
        return jsonify({"message": "canonical_user_id is required"}), 400

    doc = STORE.set_mode(user_id, bot_mode)
    return jsonify(
        {
            "canonical_user_id": user_id,
            "bot_mode": doc.get("bot_mode", DEFAULT_MODE),
            "active_session_id": doc.get("active_session_id"),
        }
    )


@APP.post("/api/session/new")
def new_session():
    payload = request.get_json(silent=True) or {}
    user_id = str(payload.get("canonical_user_id", "")).strip()
    if not user_id:
        return jsonify({"message": "canonical_user_id is required"}), 400

    doc = STORE.reset_session(user_id)
    return jsonify(
        {
            "canonical_user_id": user_id,
            "active_session_id": doc.get("active_session_id"),
            "message_count": len(doc.get("messages", [])),
        }
    )


@APP.get("/api/session/<canonical_user_id>")
def get_session(canonical_user_id: str):
    user_id = str(canonical_user_id).strip()
    if not user_id:
        return jsonify({"message": "canonical_user_id is required"}), 400

    doc = STORE.get_user(user_id)
    return jsonify(
        {
            "canonical_user_id": user_id,
            "bot_mode": doc.get("bot_mode", DEFAULT_MODE),
            "active_session_id": doc.get("active_session_id"),
            "message_count": len(doc.get("messages", [])),
            "messages": doc.get("messages", []),
        }
    )


@APP.post("/api/chat")
def chat():
    payload = request.get_json(silent=True) or {}
    user_id = str(payload.get("canonical_user_id", "")).strip()
    source = str(payload.get("source", "web")).strip().lower() or "web"
    message = str(payload.get("message", "")).strip()

    if not user_id:
        return jsonify({"message": "canonical_user_id is required"}), 400
    if source not in {"web", "telegram"}:
        return jsonify({"message": "source must be one of: web, telegram"}), 400
    if not message:
        return jsonify({"message": "message is required"}), 400

    mode_override = str(payload.get("bot_mode", "")).strip().lower()
    if mode_override:
        STORE.set_mode(user_id, mode_override)

    user_doc = STORE.get_user(user_id)
    assistant_text, thinking, sources = _generate_reply(source, message, user_doc)
    updated = STORE.append_turn(
        user_id=user_id,
        source=source,
        user_message=message,
        assistant_message=assistant_text,
        thinking=thinking,
        sources=sources,
    )

    return jsonify(
        {
            "canonical_user_id": user_id,
            "bot_mode": updated.get("bot_mode", DEFAULT_MODE),
            "active_session_id": updated.get("active_session_id"),
            "assistant_text": assistant_text,
            "thinking": thinking,
            "sources": sources,
            "message_count": len(updated.get("messages", [])),
        }
    )


def _resolve_port() -> int:
    raw = os.getenv("LAB_BACKEND_PORT", "9001")
    cleaned = re.sub(r"[^0-9]", "", raw)
    return int(cleaned or "9001")


if __name__ == "__main__":
    port = _resolve_port()
    APP.run(host="0.0.0.0", port=port, debug=False)
