#!/usr/bin/env python3
"""Summarize the latest Mongo media_metadata video using Gemini and store ai_description."""

from __future__ import annotations

import logging
import os
import tempfile
import time
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

import requests
from pymongo import MongoClient

try:  # pragma: no cover - optional dependency
    from google import genai
except Exception as exc:  # pragma: no cover
    genai = None  # type: ignore
    _GENAI_IMPORT_ERROR = exc
else:
    _GENAI_IMPORT_ERROR = None


VIDEO_EXTENSIONS = (".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v")


def get_media_collection():
    """Return the MongoDB collection that stores media metadata."""
    mongo_uri = os.environ.get("MONGODB_URI")
    if not mongo_uri:
        raise SystemExit("Set MONGODB_URI before running this script.")

    # Before example: collection name duplicated in multiple scripts.
    # After example:  collection name read once and reused here.
    db_name = os.environ.get("MONGODB_DB_NAME", "chef_chatbot")
    collection_name = os.environ.get("MONGODB_MEDIA_COLLECTION", "media_metadata")
    client = MongoClient(mongo_uri)
    return client[db_name][collection_name]


def is_video_url(url: str) -> bool:
    """Best-effort check for common video URL extensions."""
    parsed = urlparse(url)
    path = (parsed.path or "").lower()
    return path.endswith(VIDEO_EXTENSIONS)


def fetch_latest_video_doc(collection) -> Optional[dict]:
    """Return the most recent document with a usable URL (prefer video extensions)."""
    fallback_doc = None
    for doc in collection.find().sort("_id", -1).limit(50):
        url = doc.get("url")
        if not url:
            continue
        if is_video_url(url):
            return doc
        if fallback_doc is None:
            fallback_doc = doc
    return fallback_doc


def _require_gemini_client():
    """Return a Gemini client or exit with a helpful error."""
    if genai is None:
        raise SystemExit(f"Install google-genai before running: {_GENAI_IMPORT_ERROR}")

    # Before example: GEMINI_KEY_PH set but ignored -> missing key error.
    # After example:  GEMINI_KEY_PH accepted as fallback for existing env naming.
    api_key = (
        os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
        or os.environ.get("GEMINI_KEY_PH")
    )
    if not api_key:
        # Before example: missing key -> silent crash later.
        # After example:  clear exit message telling which env var to set.
        raise SystemExit("Set GEMINI_API_KEY (or GOOGLE_API_KEY / GEMINI_KEY_PH) before running this script.")

    return genai.Client(api_key=api_key)


def download_video(url: str, target_dir: str) -> str:
    """Download video content to target_dir and return the local path."""
    parsed = urlparse(url)
    extension = os.path.splitext(parsed.path)[1] or ".mp4"
    local_path = os.path.join(target_dir, f"video{extension}")

    # Before example: video URL fetched as a single blob; large files stalled.
    # After example:  streamed download so progress is incremental.
    with requests.get(url, stream=True, timeout=120) as response:
        response.raise_for_status()
        with open(local_path, "wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)
    return local_path


def summarize_video(client, local_path: str, model: str, prompt: str) -> str:
    """Upload the video file and return Gemini's summary text."""
    uploaded = client.files.upload(file=local_path)
    # Before example: upload -> immediate generateContent -> FAILED_PRECONDITION.
    # After example:  upload -> wait for ACTIVE -> generateContent succeeds.
    active_file = wait_for_file_active(client, uploaded)
    response = client.models.generate_content(
        model=model,
        contents=[active_file, prompt],
    )
    text = getattr(response, "text", "") or ""
    return text.strip()


def _get_file_state(file_obj) -> Optional[str]:
    """Return the file state as a string, if present."""
    if hasattr(file_obj, "state"):
        return getattr(file_obj, "state")
    if isinstance(file_obj, dict):
        return file_obj.get("state")
    return None


def wait_for_file_active(client, file_obj, max_wait_seconds: int = 120, poll_seconds: int = 5):
    """Poll Files API until the uploaded file is ACTIVE or timeout."""
    elapsed = 0
    current = file_obj
    while True:
        state = _get_file_state(current)
        if state and state.upper() == "ACTIVE":
            return current
        if state and state.upper() != "PROCESSING":
            # Before example: unknown state caused a silent loop.
            # After example:  unknown state exits early with a clear error.
            raise RuntimeError(f"Gemini file state={state} for name={getattr(current, 'name', 'unknown')}")
        if elapsed >= max_wait_seconds:
            raise TimeoutError("Timed out waiting for Gemini file to become ACTIVE.")
        logging.info("Waiting for Gemini file to be processed; state=%s", state or "unknown")
        time.sleep(poll_seconds)
        elapsed += poll_seconds
        current = client.files.get(name=current.name)


def analyze_latest_video(model: str, prompt: str) -> None:
    """Analyze the latest video URL in MongoDB and write ai_description."""
    collection = get_media_collection()
    client = _require_gemini_client()
    overwrite = os.environ.get("VISION_OVERWRITE", "0") == "1"

    triggered_url = os.environ.get("VISION_TRIGGER_URL")
    if triggered_url:
        # Before example: we always scanned for the newest doc.
        # After example:  use VISION_TRIGGER_URL when provided.
        doc = collection.find_one({"url": triggered_url}, sort=[("_id", -1)])
        if not doc:
            logging.info("No media_metadata doc found for VISION_TRIGGER_URL=%s", triggered_url)
            return
    else:
        doc = fetch_latest_video_doc(collection)
    if not doc:
        logging.info("No media URLs found in media_metadata.")
        return

    url = doc.get("url")
    if not url:
        logging.info("Latest doc has no url field.")
        return

    if doc.get("ai_description") and not overwrite:
        logging.info("ai_description already set for %s; set VISION_OVERWRITE=1 to replace.", url)
        return

    logging.info("gemini_video_summary start url=%s model=%s", url, model)
    with tempfile.TemporaryDirectory() as tmpdir:
        local_path = download_video(url, tmpdir)
        summary = summarize_video(client, local_path, model, prompt)

    if not summary:
        logging.warning("Gemini returned empty text for %s; not updating ai_description.", url)
        return

    # Before example: URL stored without any Gemini summary attached.
    # After example:  ai_description + ai_provider stored on the same document.
    collection.update_one(
        {"_id": doc["_id"]},
        {
            "$set": {
                "ai_description": summary,
                "ai_provider": "gemini",
                "ai_model": model,
                "ai_summary_at": datetime.now(timezone.utc).isoformat(),
            }
        },
    )
    logging.info("Stored ai_description for %s", url)


def summarize_video_url(url: str, model: str, prompt: str) -> str:
    """Return Gemini's summary text for a single video URL."""
    client = _require_gemini_client()
    # Before example: no direct helper for per-URL summaries.
    # After example:  call this helper and get the raw summary text back.
    with tempfile.TemporaryDirectory() as tmpdir:
        local_path = download_video(url, tmpdir)
        return summarize_video(client, local_path, model, prompt)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    model = os.environ.get("GEMINI_VIDEO_MODEL", "gemini-2.5-flash")
    prompt = os.environ.get(
        "GEMINI_VIDEO_PROMPT",
        "Summarize this video in 2-4 sentences. Focus on food, cooking steps, ingredients, "
        "tools, textures, and doneness if visible.",
    )

    analyze_latest_video(model=model, prompt=prompt)


if __name__ == "__main__":
    main()
