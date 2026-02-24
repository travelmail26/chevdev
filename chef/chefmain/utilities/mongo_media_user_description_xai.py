#!/usr/bin/env python3
"""Fill media_metadata.user_description using nearby user turns + xAI selection.

Video URLs store Gemini summaries in media_metadata.ai_description.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional
from urllib.parse import urlparse

import requests
from pymongo import MongoClient

MEDIA_PREFIXES = ("[photo_url:", "[video_url:", "[audio_url:")
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
VIDEO_EXTENSIONS = (".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v")
XAI_URL = "https://api.x.ai/v1/chat/completions"
DEFAULT_XAI_MODEL = "grok-4-1-fast-non-reasoning-latest"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"

SYSTEM_PROMPT = (
    "You select which user message best describes the media at the given URL. "
    "Return JSON only: {\"choice_id\": \"after_1\"} or {\"choice_id\": \"NONE\"}. "
    "Never rewrite or summarize the user text."
)


def _get_gemini_api_key() -> Optional[str]:
    # Before example: only XAI_API_KEY supported; After example: GEMINI_API_KEY/GOOGLE_API_KEY used for fallback.
    return (
        os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
        or os.environ.get("GEMINI_KEY_PH")
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Attach verbatim user_description to media_metadata via xAI selection."
    )
    parser.add_argument("--limit", type=int, default=int(os.getenv("MEDIA_LIMIT", "5")))
    parser.add_argument(
        "--scan-latest",
        type=int,
        default=int(os.getenv("MEDIA_SCAN_LATEST", "0")),
    )
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--timing", action="store_true")
    parser.add_argument("--after-turns", type=int, default=int(os.getenv("MEDIA_AFTER_TURNS", "3")))
    parser.add_argument("--include-all-media", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()





def is_media_stub(content: str) -> bool:
    """Return True when the content is a media URL stub."""
    return any(content.startswith(prefix) for prefix in MEDIA_PREFIXES)


def is_image_url(url: str) -> bool:
    """Best-effort check for common image URL extensions."""
    parsed = urlparse(url)
    path = (parsed.path or "").lower()
    return path.endswith(IMAGE_EXTENSIONS)


def is_video_url(url: str) -> bool:
    """Best-effort check for common video URL extensions."""
    parsed = urlparse(url)
    path = (parsed.path or "").lower()
    return path.endswith(VIDEO_EXTENSIONS)


def get_mongo_client() -> MongoClient:
    uri = os.environ.get("MONGODB_URI")
    if not uri:
        raise SystemExit("Set MONGODB_URI before running this script.")
    return MongoClient(uri)


def get_media_collection(client: MongoClient):
    # Before example: media metadata hard-coded to chef_chatbot.
    # After example:  media metadata can use MONGODB_MEDIA_DB_NAME when present.
    db_name = os.environ.get("MONGODB_MEDIA_DB_NAME") or os.environ.get("MONGODB_DB_NAME", "chef_chatbot")
    collection_name = os.environ.get("MONGODB_MEDIA_COLLECTION", "media_metadata")
    return client[db_name][collection_name]


def _get_bot_config_module():
    # Before example: backfill only read MONGODB_DB_NAME.
    # After example:  backfill can load bot_config.py to include dietlog collections.
    chef_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    config_path = os.path.join(chef_root, "utilities", "bot_config.py")
    if not os.path.exists(config_path):
        return None
    try:
        spec = importlib.util.spec_from_file_location("bot_config", config_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
    except Exception:
        return None
    return None


def _collect_chat_configs() -> List[Dict[str, str]]:
    # Before example: only chef_chatbot.chat_sessions searched.
    # After example:  include cheflog + dietlog chat collections when configured.
    configs: List[Dict[str, str]] = []
    module = _get_bot_config_module()
    if module and hasattr(module, "BOT_CONFIG"):
        for mode, config in module.BOT_CONFIG.items():
            db_name = config.get("mongo_db", "")
            collection_name = config.get("mongo_collection", "")
            if db_name and collection_name:
                configs.append(
                    {
                        "label": mode,
                        "db_name": db_name,
                        "collection_name": collection_name,
                    }
                )
        return configs
    configs.append(
        {
            "label": "default",
            "db_name": os.environ.get("MONGODB_DB_NAME", "chef_chatbot"),
            "collection_name": os.environ.get("MONGODB_COLLECTION_NAME", "chat_sessions"),
        }
    )
    configs.append(
        {
            "label": "dietlog",
            "db_name": os.environ.get("MONGODB_DB_NAME_DIETLOG", "chef_dietlog"),
            "collection_name": os.environ.get(
                "MONGODB_COLLECTION_NAME_DIETLOG",
                "chat_dietlog_sessions",
            ),
        }
    )
    return configs


def get_chat_collections(client: MongoClient) -> List[Dict[str, object]]:
    # Before example: single chat collection -> missed dietlog sessions.
    # After example:  iterate all configured chat collections with labels.
    seen = set()
    entries: List[Dict[str, object]] = []
    for config in _collect_chat_configs():
        db_name = config["db_name"]
        collection_name = config["collection_name"]
        key = (db_name, collection_name)
        if key in seen:
            continue
        seen.add(key)
        entries.append(
            {
                "label": f"{config['label']}:{db_name}.{collection_name}",
                "collection": client[db_name][collection_name],
            }
        )
    return entries


def pending_media_query() -> dict:
    """Return the query used to locate docs missing user_description."""
    return {
        "$and": [
            {"url": {"$exists": True, "$ne": ""}},
            {
                "$or": [
                    {"user_description": {"$exists": False}},
                    {"user_description": None},
                    {"user_description": ""},
                ]
            },
        ]
    }


def iter_pending_media(collection, limit: int) -> Iterable[dict]:
    """Yield up to ``limit`` metadata docs missing user_description."""
    yield from collection.find(pending_media_query()).sort("_id", -1).limit(limit)


def iter_latest_media(collection, limit: int) -> Iterable[dict]:
    """Yield the latest ``limit`` metadata docs regardless of user_description."""
    query = {"url": {"$exists": True, "$ne": ""}}
    yield from collection.find(query).sort("_id", -1).limit(limit)


def has_user_description(doc: dict) -> bool:
    """Return True when a user_description already exists on the doc."""
    value = doc.get("user_description")
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def has_ai_description(doc: dict) -> bool:
    """Return True when an ai_description already exists on the doc."""
    value = doc.get("ai_description")
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def count_pending_media(collection) -> int:
    """Return the total count of docs missing user_description."""
    return collection.count_documents(pending_media_query())


def count_media_with_url(collection) -> int:
    """Return the count of docs that have a URL."""
    return collection.count_documents({"url": {"$exists": True, "$ne": ""}})


def count_missing_in_latest(collection, limit: int, include_all_media: bool) -> int:
    """Count missing user_description in the latest ``limit`` docs."""
    missing = 0
    for doc in iter_latest_media(collection, limit):
        url = doc.get("url")
        if not isinstance(url, str) or not url:
            continue
        if not include_all_media and not (is_image_url(url) or is_video_url(url)):
            continue
        if not has_user_description(doc):
            missing += 1
    return missing


def find_media_stub_index(messages: List[dict], url: str) -> Optional[int]:
    """Return the index of the user stub that contains the url."""
    for index, message in enumerate(messages):
        if message.get("role") != "user":
            continue
        content = message.get("content")
        if not isinstance(content, str):
            continue
        if url not in content:
            continue
        if not is_media_stub(content.strip()):
            continue
        return index
    return None


def _previous_user_text(messages: List[dict], start_index: int) -> Optional[str]:
    """Return the nearest previous user text or None if it is another stub."""
    # Before example: previous stub -> accidentally used older context.
    # After example:  previous stub -> return None to avoid bleed.
    for index in range(start_index - 1, -1, -1):
        message = messages[index]
        if message.get("role") != "user":
            continue
        content = message.get("content")
        if not isinstance(content, str):
            return None
        trimmed = content.strip()
        if not trimmed:
            continue
        if is_media_stub(trimmed):
            return None
        return content
    return None


def _after_user_texts(messages: List[dict], start_index: int, limit: int) -> List[str]:
    """Return up to ``limit`` user texts after the media stub."""
    texts: List[str] = []
    for message in messages[start_index + 1:]:
        if message.get("role") != "user":
            continue
        content = message.get("content")
        if not isinstance(content, str):
            continue
        trimmed = content.strip()
        if not trimmed:
            continue
        if is_media_stub(trimmed):
            # Before example: media -> media -> description from wrong photo.
            # After example:  stop when a new media stub appears.
            break
        texts.append(content)
        if len(texts) >= limit:
            break
    return texts


def collect_candidates(messages: List[dict], index: int, after_turns: int) -> List[Dict[str, str]]:
    """Collect candidate user descriptions around the media stub."""
    candidates: List[Dict[str, str]] = []
    # Before example: only the next user turn considered.
    # After example:  up to N user turns after the media stub are candidates.
    after_texts = _after_user_texts(messages, index, after_turns)
    for position, text in enumerate(after_texts, start=1):
        candidates.append({"id": f"after_{position}", "text": text})

    # Before example: user context one turn earlier ignored.
    # After example:  nearest previous user text is added as before_1.
    before_text = _previous_user_text(messages, index)
    if before_text is not None:
        candidates.append({"id": "before_1", "text": before_text})
    return candidates


def build_user_prompt(url: str, candidates: List[Dict[str, str]]) -> str:
    """Build the user prompt for xAI selection."""
    lines = [
        f"Media URL: {url}",
        "Candidates (verbatim user text):",
    ]
    for candidate in candidates:
        escaped = json.dumps(candidate["text"], ensure_ascii=True)
        lines.append(f"- {candidate['id']}: {escaped}")
    lines.append("Return JSON only: {\"choice_id\": \"after_1\"} or {\"choice_id\": \"NONE\"}.")
    return "\n".join(lines)


def call_gemini_select(
    api_key: str,
    model: str,
    url: str,
    candidates: List[Dict[str, str]],
    timing: bool = False,
) -> Optional[str]:
    """Call Gemini and return the chosen candidate id."""
    start = time.monotonic() if timing else None
    prompt = build_user_prompt(url, candidates)
    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": {
            "temperature": 0,
            "maxOutputTokens": 120,
        },
    }
    response = requests.post(
        GEMINI_URL.format(model=model),
        params={"key": api_key},
        json=payload,
        timeout=60,
    )
    if response.status_code != 200:
        logging.warning(
            "gemini_select http_error status=%s body=%s",
            response.status_code,
            response.text[:300],
        )
        return None

    data = response.json()
    content = ""
    try:
        candidates_payload = data.get("candidates", [])
        if candidates_payload:
            parts = candidates_payload[0].get("content", {}).get("parts", [])
            if parts:
                content = parts[0].get("text", "")
    except Exception:
        logging.warning("gemini_select missing content")
        return None

    choice_id = parse_choice_id(content)
    if timing and start is not None:
        duration_ms = int((time.monotonic() - start) * 1000)
        logging.info(
            "gemini_select_timing url=%s candidates=%s duration_ms=%s",
            url,
            len(candidates),
            duration_ms,
        )
    if not choice_id or choice_id == "NONE":
        return None
    return choice_id


def _call_gemini_fallback(
    url: str,
    candidates: List[Dict[str, str]],
    timing: bool,
    reason: str,
) -> Optional[str]:
    # Before example: xAI 503 -> hard stop; After example: Gemini fallback attempts selection.
    api_key = _get_gemini_api_key()
    if not api_key:
        logging.info(
            "gemini_fallback_skip reason=%s missing_env=GEMINI_API_KEY/GOOGLE_API_KEY/GEMINI_KEY_PH",
            reason,
        )
        return None
    model = os.environ.get("GEMINI_FALLBACK_MODEL", DEFAULT_GEMINI_MODEL)
    logging.info("gemini_fallback_start reason=%s model=%s", reason, model)
    return call_gemini_select(api_key, model, url, candidates, timing=timing)


def call_xai_select(
    api_key: str,
    model: str,
    url: str,
    candidates: List[Dict[str, str]],
    timing: bool = False,
) -> Optional[str]:
    """Call xAI and return the chosen candidate id."""
    start = time.monotonic() if timing else None
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(url, candidates)},
        ],
        "max_tokens": 120,
        "temperature": 0,
    }
    response = requests.post(
        XAI_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=60,
    )
    if response.status_code != 200:
        logging.warning("xai_select http_error status=%s body=%s", response.status_code, response.text[:300])
        return _call_gemini_fallback(url, candidates, timing, reason="xai_http_error")

    data = response.json()
    content = ""
    try:
        content = data["choices"][0]["message"]["content"]
    except Exception:
        logging.warning("xai_select missing content")
        return _call_gemini_fallback(url, candidates, timing, reason="xai_missing_content")

    choice_id = parse_choice_id(content)
    if timing and start is not None:
        duration_ms = int((time.monotonic() - start) * 1000)
        logging.info(
            "xai_select_timing url=%s candidates=%s duration_ms=%s",
            url,
            len(candidates),
            duration_ms,
        )
    if not choice_id:
        logging.warning("xai_select_parse_failed url=%s", url)
        return _call_gemini_fallback(url, candidates, timing, reason="xai_parse_failed")
    if choice_id == "NONE":
        return None
    return choice_id


def parse_choice_id(text: str) -> Optional[str]:
    """Parse {"choice_id": "..."} from the model output."""
    if not text:
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            return None
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    choice_id = payload.get("choice_id") if isinstance(payload, dict) else None
    if isinstance(choice_id, str):
        return choice_id.strip()
    return None


def update_user_description(collection, doc_id, description: str, dry_run: bool) -> bool:
    """Persist user_description on the media doc."""
    if dry_run:
        logging.info("dry_run update _id=%s user_description=%s", doc_id, description)
        return False
    # Before example: media_metadata doc missing user_description.
    # After example:  media_metadata doc has user_description set verbatim.
    collection.update_one(
        {"_id": doc_id},
        {"$set": {"user_description": description}},
    )
    return True


def update_ai_description(
    collection,
    doc_id,
    description: str,
    provider: str,
    model: str,
    dry_run: bool,
) -> bool:
    """Persist ai_description on the media doc."""
    if dry_run:
        logging.info("dry_run update _id=%s ai_description=%s", doc_id, description)
        return False
    # Before example: Gemini video text stored as user_description only.
    # After example:  Gemini video text stored as ai_description + provider/model/timestamp.
    collection.update_one(
        {"_id": doc_id},
        {
            "$set": {
                "ai_description": description,
                "ai_provider": provider,
                "ai_model": model,
                "ai_summary_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )
    return True


def process_media_doc(
    media_collection,
    chat_collections,
    doc: dict,
    after_turns: int,
    include_all_media: bool,
    api_key: str,
    model: str,
    dry_run: bool,
    timing: bool,
) -> bool:
    doc_start = time.monotonic() if timing else None
    url = doc.get("url")
    if not isinstance(url, str) or not url:
        logging.info("skip_media_doc missing_url _id=%s", doc.get("_id"))
        return False
    is_video = is_video_url(url)
    if not include_all_media and not is_image_url(url) and not is_video:
        logging.info("skip_media_doc non_image_url _id=%s url=%s", doc.get("_id"), url)
        return False

    if is_video:
        if has_ai_description(doc):
            logging.info("skip_media_doc existing_ai_description _id=%s", doc.get("_id"))
            return False
        # Before example: video URL sent to xAI (unsupported).
        # After example:  video URL routed to Gemini summary and stored as ai_description.
        try:
            from mongo_gemini_video_summary import summarize_video_url
        except Exception as exc:
            logging.warning("video_summary_import_failed url=%s error=%s", url, exc)
            return False
        video_model = os.environ.get("GEMINI_VIDEO_MODEL", "gemini-2.5-flash")
        video_prompt = os.environ.get(
            "GEMINI_VIDEO_PROMPT",
            "Summarize this video in 2-4 sentences. Focus on food, cooking steps, ingredients, "
            "tools, textures, and doneness if visible.",
        )
        summary = summarize_video_url(url, model=video_model, prompt=video_prompt)
        if not summary:
            logging.info("video_summary_empty url=%s", url)
            return False
        saved = update_ai_description(
            media_collection,
            doc.get("_id"),
            summary,
            provider="gemini",
            model=video_model,
            dry_run=dry_run,
        )
        logging.info("ai_description_saved url=%s provider=gemini model=%s", url, video_model)
        if timing and doc_start is not None:
            total_ms = int((time.monotonic() - doc_start) * 1000)
            logging.info("media_backfill_total url=%s duration_ms=%s", url, total_ms)
        return saved

    escaped = re.escape(url)
    query = {"messages": {"$elemMatch": {"content": {"$regex": escaped}}}}
    search_start = time.monotonic() if timing else None
    if not chat_collections:
        logging.info("no_chat_collections url=%s", url)
        return False
    # Before example: only chef_chatbot.chat_sessions scanned.
    # After example:  scan all configured chat collections for the media stub.
    found_stub = False
    for entry in chat_collections:
        chat_collection = entry["collection"]
        label = entry["label"]
        session_cursor = chat_collection.find(query, {"messages": 1})
        for session in session_cursor:
            messages = session.get("messages", [])
            if not isinstance(messages, list):
                continue
            stub_index = find_media_stub_index(messages, url)
            if stub_index is None:
                continue
            found_stub = True

            candidates = collect_candidates(messages, stub_index, after_turns)
            if not candidates:
                logging.info("no_candidates url=%s session_id=%s", url, session.get("_id"))
                continue

            if timing and search_start is not None:
                search_ms = int((time.monotonic() - search_start) * 1000)
                logging.info("media_backfill_search url=%s duration_ms=%s", url, search_ms)

            choice_id = call_xai_select(api_key, model, url, candidates, timing=timing)
            if not choice_id:
                logging.info("no_choice url=%s session_id=%s", url, session.get("_id"))
                continue

            selected = next((item for item in candidates if item["id"] == choice_id), None)
            if not selected:
                logging.info("choice_missing url=%s choice_id=%s", url, choice_id)
                continue

            saved = update_user_description(media_collection, doc.get("_id"), selected["text"], dry_run)
            logging.info(
                "user_description_saved url=%s choice_id=%s session_id=%s chat_collection=%s",
                url,
                choice_id,
                session.get("_id"),
                label,
            )
            if timing and doc_start is not None:
                total_ms = int((time.monotonic() - doc_start) * 1000)
                logging.info("media_backfill_total url=%s duration_ms=%s", url, total_ms)
            return saved

    if found_stub:
        return False

    logging.info("no_session_match url=%s", url)
    if timing and doc_start is not None:
        total_ms = int((time.monotonic() - doc_start) * 1000)
        logging.info("media_backfill_total url=%s duration_ms=%s", url, total_ms)
    return False


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    args = parse_args()
    api_key = os.environ.get("XAI_API_KEY")
    if not api_key:
        raise SystemExit("Set XAI_API_KEY before running this script.")
    model = os.environ.get("XAI_MODEL", DEFAULT_XAI_MODEL)

    client = get_mongo_client()
    media_collection = get_media_collection(client)
    chat_collections = get_chat_collections(client)
    chat_labels = ", ".join(entry["label"] for entry in chat_collections)
    # Before example: backfill logs omitted which chat collections were searched.
    # After example:  logs show all chat collections used for matching.
    logging.info("media_enricher_chat_collections %s", chat_labels)

    logging.info(
        "media_enricher start limit=%s scan_latest=%s after_turns=%s include_all_media=%s model=%s dry_run=%s timing=%s",
        args.limit,
        args.scan_latest,
        args.after_turns,
        args.include_all_media,
        model,
        args.dry_run,
        args.timing,
    )

    total_with_url = count_media_with_url(media_collection)
    pending_total = count_pending_media(media_collection)
    latest_missing = None
    if args.scan_latest > 0:
        latest_missing = count_missing_in_latest(
            media_collection,
            args.scan_latest,
            args.include_all_media,
        )
    # Before example: no visibility into backlog size.
    # After example:  counts show how many docs are pending before processing.
    logging.info(
        "media_enricher_stats total_with_url=%s pending_missing=%s scan_latest=%s scan_latest_missing=%s",
        total_with_url,
        pending_total,
        args.scan_latest,
        latest_missing if latest_missing is not None else "n/a",
    )
    if args.report:
        return

    processed = 0
    filled = 0
    if args.scan_latest > 0:
        # Before example: only missing-description docs were queried.
        # After example:  the newest N docs are scanned, and missing ones are filled.
        docs_to_process = iter_latest_media(media_collection, args.scan_latest)
    else:
        docs_to_process = iter_pending_media(media_collection, args.limit)

    for doc in docs_to_process:
        url = doc.get("url")
        is_video = isinstance(url, str) and is_video_url(url)
        if not is_video and has_user_description(doc):
            logging.info("skip_media_doc existing_user_description _id=%s", doc.get("_id"))
            continue
        # Before example: no visibility into successful fills per run.
        # After example:  track fills so "done" logging shows what changed.
        saved = process_media_doc(
            media_collection,
            chat_collections,
            doc,
            args.after_turns,
            args.include_all_media,
            api_key,
            model,
            args.dry_run,
            args.timing,
        )
        if saved:
            filled += 1
        processed += 1

    if processed == 0:
        logging.info("media_backfill_noop reason=no_docs")
    elif filled == 0:
        logging.info("media_backfill_noop reason=no_updates processed=%s", processed)
    logging.info("media_backfill_done processed=%s filled=%s", processed, filled)


if __name__ == "__main__":
    main()
