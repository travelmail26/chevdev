#!/usr/bin/env python3
"""Backfill short general-chat memory into insights_general + preferences."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Iterable, List, Optional

import requests
from pymongo import MongoClient

XAI_URL = "https://api.x.ai/v1/chat/completions"
DEFAULT_XAI_MODEL = "grok-4-1-fast-non-reasoning-latest"
MEDIA_PREFIXES = ("[photo_url:", "[video_url:", "[audio_url:")

SYSTEM_PROMPT = """
You are creating long-term cooking memory from ONE conversation.

Goal:
Write short memory from USER messages only.

Include only:
- user observations
- user preferences
- user-reported outcomes
- user reflections on what should have been tried

Exclude:
- assistant messages
- logistics/status chatter
- debugging notes
- search requests
- tool/function-call details
- media markers like [photo_url], [video_url], [audio_url]

Rules:
- Keep each field very short.
- Max 45 words per field.
- No advice, no steps, no fluff.
- Do not invent facts.
- If no useful cooking signal exists, return empty strings.

Return JSON only:
{"insight":"<short insight or empty string>","preference":"<short preference or empty string>"}
""".strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill general-chat insights/preferences for unsummarized conversations."
    )
    parser.add_argument(
        "--scan-latest",
        type=int,
        default=int(os.getenv("GENERAL_INSIGHT_SCAN_LATEST", "10")),
    )
    return parser.parse_args()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_mongo_client() -> MongoClient:
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        raise SystemExit("Set MONGODB_URI before running this script.")
    return MongoClient(uri)


def get_chat_collection(client: MongoClient):
    db_name = os.environ.get("MONGODB_DB_NAME_GENERAL", "chat_general")
    collection_name = os.environ.get("MONGODB_COLLECTION_NAME_GENERAL", "chat_general")
    return client[db_name][collection_name]


def get_insights_collection(client: MongoClient):
    db_name = os.environ.get(
        "MONGODB_INSIGHTS_DB_NAME",
        os.environ.get("MONGODB_DB_NAME_GENERAL", "chat_general"),
    )
    collection_name = os.environ.get("MONGODB_INSIGHTS_COLLECTION_NAME", "insights_general")
    return client[db_name][collection_name]


def get_preferences_collection(client: MongoClient):
    db_name = os.environ.get(
        "MONGODB_PREFERENCES_DB_NAME",
        os.environ.get("MONGODB_DB_NAME", "chef_chatbot"),
    )
    collection_name = os.environ.get("MONGODB_PREFERENCES_COLLECTION_NAME", "preferences")
    return client[db_name][collection_name]


def iter_unsummarized_conversations(chat_collection, limit: int) -> Iterable[dict]:
    query = {
        "$and": [
            {"messages.0": {"$exists": True}},
            {"$or": [{"bot_mode": "general"}, {"bot_mode": {"$exists": False}}]},
            {
                "$or": [
                    {"insight_general_hash": {"$exists": False}},
                    {"insight_general_hash": None},
                    {"insight_general_hash": ""},
                ]
            },
        ]
    }
    yield from chat_collection.find(query).sort("last_updated_at", -1).limit(limit)


def _normalize_text(value: str) -> str:
    # Before example: smart quote/emoji bytes could produce noisy hashes.
    # After example:  collapse to stable whitespace for deterministic hashing.
    text = str(value or "").replace("\u2014", "-")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def collect_user_texts(conversation: dict) -> List[str]:
    messages = conversation.get("messages") or []
    lines: List[str] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        if message.get("role") != "user":
            continue
        content = _normalize_text(str(message.get("content", "")))
        if not content:
            continue
        if content.lower().startswith(MEDIA_PREFIXES):
            continue
        if content.startswith("/"):
            continue
        lines.append(content)
    return lines


def build_conversation_hash(conversation: dict, user_texts: List[str]) -> str:
    chat_session_id = str(
        conversation.get("chat_session_id") or conversation.get("_id") or "unknown_session"
    )
    last_updated_at = str(conversation.get("last_updated_at") or "")
    material = f"{chat_session_id}\n{last_updated_at}\n" + "\n".join(user_texts)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def build_user_prompt(user_texts: List[str]) -> str:
    lines = ["User conversation excerpts:"]
    for idx, text in enumerate(user_texts, start=1):
        lines.append(f"{idx}. {json.dumps(text, ensure_ascii=True)}")
    return "\n".join(lines)


def _extract_json_object(raw_text: str) -> Optional[dict]:
    text = str(raw_text or "").strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        parsed = json.loads(text[start : end + 1])
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        return None
    return None


def call_xai_summary(api_key: str, model: str, user_texts: List[str]) -> dict:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(user_texts)},
        ],
        "max_tokens": 220,
        "temperature": 0,
    }
    response = requests.post(
        XAI_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=120,
    )
    response.raise_for_status()
    data = response.json()
    choices = data.get("choices") or []
    if not choices:
        return {"insight": "", "preference": ""}
    message = choices[0].get("message") or {}
    content = message.get("content") or ""
    parsed = _extract_json_object(content)
    if not isinstance(parsed, dict):
        return {"insight": "", "preference": ""}
    insight = str(parsed.get("insight", "") or "").strip()
    preference = str(parsed.get("preference", "") or "").strip()
    return {"insight": insight, "preference": preference}


def iso_to_date(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed.date().isoformat()
    except Exception:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def trim_words(text: str, max_words: int = 45) -> str:
    words = str(text or "").strip().split()
    if len(words) <= max_words:
        return " ".join(words)
    return " ".join(words[:max_words]).strip()


def upsert_memory_docs(
    conversation: dict,
    insight_text: str,
    preference_text: str,
    conversation_hash: str,
    insights_collection,
    preferences_collection,
) -> tuple[str | None, str | None]:
    created_on = now_iso()
    source_chat_session_id = str(
        conversation.get("chat_session_id") or conversation.get("_id") or ""
    )
    user_id = str(conversation.get("user_id") or "")
    source_last_updated_at = str(conversation.get("last_updated_at") or "")
    date_value = iso_to_date(source_last_updated_at or conversation.get("chat_session_created_at"))

    insight_doc_id: str | None = None
    preference_doc_id: str | None = None

    clean_insight = trim_words(insight_text)
    if clean_insight:
        insight_doc_id = f"insight_general_{source_chat_session_id}"
        insight_doc = {
            "_id": insight_doc_id,
            "user_id": user_id,
            "created_on": created_on,
            "source_chat_session_id": source_chat_session_id,
            "source_conversation_hash": conversation_hash,
            "source_last_updated_at": source_last_updated_at,
            "date": date_value,
            "insight": clean_insight,
        }
        insights_collection.update_one({"_id": insight_doc_id}, {"$set": insight_doc}, upsert=True)

    clean_preference = trim_words(preference_text)
    if clean_preference:
        preference_doc_id = f"pref_general_{source_chat_session_id}"
        preference_doc = {
            "_id": preference_doc_id,
            "user_id": user_id,
            "schema_version": 1,
            "type": "preference",
            "key": "general.cooking_preference",
            "value": clean_preference,
            "constraints": "",
            "reason": "",
            "example": "",
            "created_on": created_on,
            "created_at": created_on,
            "updated_at": created_on,
            "source_chat_session_id": source_chat_session_id,
            "source_conversation_hash": conversation_hash,
        }
        preferences_collection.update_one({"_id": preference_doc_id}, {"$set": preference_doc}, upsert=True)

    return insight_doc_id, preference_doc_id


def mark_conversation_processed(
    chat_collection,
    conversation_id: str,
    conversation_hash: str,
    insight_doc_id: str | None,
    preference_doc_id: str | None,
) -> None:
    # Before example: restart backfill re-scanned the same chats repeatedly.
    # After example:  each processed chat stores insight_general_hash as a done marker.
    chat_collection.update_one(
        {"_id": conversation_id},
        {
            "$set": {
                "insight_general_hash": conversation_hash,
                "insight_general_backfilled_at": now_iso(),
                "insight_general_doc_id": insight_doc_id,
                "preference_doc_id": preference_doc_id,
            }
        },
    )


def backfill_latest_conversations(limit: int) -> None:
    api_key = os.environ.get("XAI_API_KEY", "").strip()
    if not api_key:
        logging.info("general_insight_backfill_skip missing_env=XAI_API_KEY")
        return

    model = os.environ.get("XAI_MODEL", DEFAULT_XAI_MODEL)
    client = get_mongo_client()
    chat_collection = get_chat_collection(client)
    insights_collection = get_insights_collection(client)
    preferences_collection = get_preferences_collection(client)

    processed = 0
    marked = 0
    insight_writes = 0
    preference_writes = 0

    for conversation in iter_unsummarized_conversations(chat_collection, limit):
        conversation_id = str(conversation.get("_id") or "")
        if not conversation_id:
            continue

        user_texts = collect_user_texts(conversation)
        conversation_hash = build_conversation_hash(conversation, user_texts)

        insight_text = ""
        preference_text = ""

        if user_texts:
            try:
                summary = call_xai_summary(api_key=api_key, model=model, user_texts=user_texts)
                insight_text = str(summary.get("insight", "") or "").strip()
                preference_text = str(summary.get("preference", "") or "").strip()
            except Exception as exc:
                logging.warning(
                    "general_insight_backfill_llm_failed chat_session_id=%s error=%s",
                    conversation.get("chat_session_id") or conversation_id,
                    exc,
                )

        insight_doc_id, preference_doc_id = upsert_memory_docs(
            conversation=conversation,
            insight_text=insight_text,
            preference_text=preference_text,
            conversation_hash=conversation_hash,
            insights_collection=insights_collection,
            preferences_collection=preferences_collection,
        )
        mark_conversation_processed(
            chat_collection=chat_collection,
            conversation_id=conversation_id,
            conversation_hash=conversation_hash,
            insight_doc_id=insight_doc_id,
            preference_doc_id=preference_doc_id,
        )

        processed += 1
        marked += 1
        if insight_doc_id:
            insight_writes += 1
        if preference_doc_id:
            preference_writes += 1

    logging.info(
        "general_insight_backfill_done scanned_limit=%s processed=%s marked=%s insight_docs=%s preference_docs=%s",
        limit,
        processed,
        marked,
        insight_writes,
        preference_writes,
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(message)s")
    args = parse_args()
    backfill_latest_conversations(limit=max(1, int(args.scan_latest)))


if __name__ == "__main__":
    main()
