#!/usr/bin/env python3
"""Probe Gemini video understanding to find two key clip segments."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from typing import Optional
from urllib.parse import urlparse

import requests

try:  # pragma: no cover - optional dependency
    from google import genai
except Exception as exc:  # pragma: no cover
    genai = None  # type: ignore
    _GENAI_IMPORT_ERROR = exc
else:
    _GENAI_IMPORT_ERROR = None


DEFAULT_VIDEO_URL = (
    "https://firebasestorage.googleapis.com/v0/b/cheftest-f174c/o/"
    "telegram_videos%2FBAACAgEAAxkBAAIMcGlW-BELQGDbbjIGYe-Re6c2SJsKAAKCBgAC"
    "iwW4RjeDShiZDv33OAQ.mp4?alt=media&token=f7686120-35e0-4b73-b414-03012d6e394e"
)

DEFAULT_PROMPT = (
    "Find the beginning and end points timestamp when the user is forking the food into the jar "
    "and when they start cracking the egg and put it into the"
)


def _require_gemini_client():
    """Return a Gemini client or exit with a helpful error."""
    if genai is None:
        raise SystemExit(f"Install google-genai before running: {_GENAI_IMPORT_ERROR}")

    # Before example: GEMINI_API_KEY missing -> cryptic auth error later.
    # After example:  fail fast with the exact env var to set.
    api_key = (
        os.environ.get("GEMINI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
        or os.environ.get("GEMINI_KEY_PH")
    )
    if not api_key:
        raise SystemExit("Set GEMINI_API_KEY (or GOOGLE_API_KEY / GEMINI_KEY_PH) before running.")

    return genai.Client(api_key=api_key)


def _get_file_state(file_obj) -> Optional[str]:
    """Return the file state as a string, if present."""
    if hasattr(file_obj, "state"):
        return getattr(file_obj, "state")
    if isinstance(file_obj, dict):
        return file_obj.get("state")
    return None


def wait_for_file_active(client, file_obj, max_wait_seconds: int = 120, poll_seconds: int = 5):
    """Poll Files API until the uploaded file is ACTIVE or timeout."""
    # Before example: upload -> immediate generateContent -> FAILED_PRECONDITION.
    # After example:  upload -> wait for ACTIVE -> generateContent succeeds.
    elapsed = 0
    current = file_obj
    while True:
        state = _get_file_state(current)
        if state and state.upper() == "ACTIVE":
            return current
        if state and state.upper() != "PROCESSING":
            raise RuntimeError(f"Gemini file state={state} for name={getattr(current, 'name', 'unknown')}")
        if elapsed >= max_wait_seconds:
            raise TimeoutError("Timed out waiting for Gemini file to become ACTIVE.")
        logging.info("Waiting for Gemini file to be processed; state=%s", state or "unknown")
        time.sleep(poll_seconds)
        elapsed += poll_seconds
        current = client.files.get(name=current.name)


def download_video(url: str, target_dir: str) -> str:
    """Download video content to target_dir and return the local path."""
    parsed = urlparse(url)
    extension = os.path.splitext(parsed.path)[1] or ".mp4"
    local_path = os.path.join(target_dir, f"video{extension}")

    # Before example: fetch video in one blob -> big files stall.
    # After example:  streamed download writes in chunks.
    with requests.get(url, stream=True, timeout=120) as response:
        response.raise_for_status()
        with open(local_path, "wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)
    return local_path


def build_prompt(base_prompt: str, segment_count: int = 2) -> str:
    """Return the prompt requesting timestamped segments with JSON output."""
    # Before example: base prompt only -> timestamps not always parseable.
    # After example:  base prompt + strict JSON schema -> easy to parse downstream.
    return (
        f"{base_prompt}\n\n"
        "Identify {segment_count} distinct, non-overlapping clips that capture key moments in this video. "
        "Return ONLY valid JSON with this exact schema:\n"
        "{\n"
        '  "segments": [\n'
        '    {"start_time": "MM:SS", "end_time": "MM:SS", "description": "..."},\n'
        '    {"start_time": "MM:SS", "end_time": "MM:SS", "description": "..."}\n'
        "  ]\n"
        "}\n"
        "Rules:\n"
        "- Use timestamps in MM:SS format (per Gemini video timestamp guidance).\n"
        "- Ensure start_time < end_time and both are within the video.\n"
        "- Provide descriptions that mention visible actions and any audio cues.\n"
        "- If unsure about exact times, give your best estimate.\n"
    ).format(segment_count=segment_count)


def request_segments(client, local_path: str, model: str, prompt: str) -> str:
    """Upload the video file and return Gemini's response text."""
    uploaded = client.files.upload(file=local_path)
    active_file = wait_for_file_active(client, uploaded)
    response = client.models.generate_content(
        model=model,
        contents=[active_file, prompt],
    )
    text = getattr(response, "text", "") or ""
    return text.strip()


def print_response(text: str) -> None:
    """Print JSON when possible, otherwise print raw text."""
    if not text:
        logging.warning("Gemini returned empty text.")
        return

    # Before example: JSON parse failure -> no output.
    # After example:  print raw text if JSON parsing fails.
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        print(text)
        return

    print(json.dumps(data, indent=2, sort_keys=True))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    model = os.environ.get("GEMINI_VIDEO_MODEL", "gemini-2.5-flash")
    url = os.environ.get("GEMINI_VIDEO_URL", DEFAULT_VIDEO_URL)
    # Before example: prompt hard-coded in the function call.
    # After example:  edit DEFAULT_PROMPT below or set GEMINI_VIDEO_PROMPT to swap quickly.
    base_prompt = os.environ.get("GEMINI_VIDEO_PROMPT", DEFAULT_PROMPT)
    prompt = (
        build_prompt(base_prompt, segment_count=2)
        if os.environ.get("GEMINI_PROMPT_AS_JSON", "0") == "1"
        else base_prompt
    )

    # Before example: hard-coded URL only.
    # After example:  override with GEMINI_VIDEO_URL for quick swaps.
    logging.info("gemini_video_segments start url=%s model=%s", url, model)
    client = _require_gemini_client()

    with tempfile.TemporaryDirectory() as tmpdir:
        local_path = download_video(url, tmpdir)
        response_text = request_segments(client, local_path, model, prompt)

    print_response(response_text)


if __name__ == "__main__":
    main()
