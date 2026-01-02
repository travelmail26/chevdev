#!/usr/bin/env python3
"""Find two clips in video A and one clip in video B, then merge them into one video."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass
from shutil import which
from typing import List, Optional, Tuple
from urllib.parse import urlparse

import requests

try:  # pragma: no cover - optional dependency
    from google import genai
except Exception as exc:  # pragma: no cover
    genai = None  # type: ignore
    _GENAI_IMPORT_ERROR = exc
else:
    _GENAI_IMPORT_ERROR = None


VIDEO_A_URL = (
    "https://firebasestorage.googleapis.com/v0/b/cheftest-f174c/o/"
    "telegram_videos%2FBAACAgEAAxkBAAIMcGlW-BELQGDbbjIGYe-Re6c2SJsKAAKCBgAC"
    "iwW4RjeDShiZDv33OAQ.mp4?alt=media&token=f7686120-35e0-4b73-b414-03012d6e394e"
)
VIDEO_B_URL = (
    "https://firebasestorage.googleapis.com/v0/b/cheftest-f174c/o/"
    "telegram_videos%2FBAACAgEAAxkBAAIMcmlW-dKH0wMzxRP8gJGDFmBDzLmGAAKDBgAC"
    "iwW4RhsRXo0wGwumOAQ.mp4?alt=media&token=91926a2a-19e1-4772-b739-043147c86883"
)

VIDEO_A_PROMPT = (
    "Find the beginning and end points timestamp when the user is forking the food into the jar "
    "and when they start cracking the egg and put it into the"
)
VIDEO_B_PROMPT = "Find the beginning and end timestamps when the user is putting the jar in the pot."

DEFAULT_OUTPUT_PATH = "chef/testscripts/output/combined_three_clips.mp4"


@dataclass
class Segment:
    start_time: str
    end_time: str
    description: str


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


def download_video(url: str, target_dir: str, name: str) -> str:
    """Download video content to target_dir and return the local path."""
    parsed = urlparse(url)
    extension = os.path.splitext(parsed.path)[1] or ".mp4"
    local_path = os.path.join(target_dir, f"{name}{extension}")

    # Before example: fetch video in one blob -> big files stall.
    # After example:  streamed download writes in chunks.
    with requests.get(url, stream=True, timeout=120) as response:
        response.raise_for_status()
        with open(local_path, "wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)
    return local_path


def build_prompt(base_prompt: str, segment_count: int) -> str:
    """Return the prompt requesting timestamped segments."""
    # Before example: base prompt only -> timestamps not always parseable.
    # After example:  base prompt + strict JSON schema -> easy to parse downstream.
    return (
        f"{base_prompt}\n\n"
        f"Identify {segment_count} distinct, non-overlapping clip(s). "
        "Return ONLY valid JSON with this exact schema:\n"
        "{\n"
        '  "segments": [\n'
        '    {"start_time": "MM:SS", "end_time": "MM:SS", "description": "..."}\n'
        "  ]\n"
        "}\n"
        "Rules:\n"
        "- Use timestamps in MM:SS format (per Gemini video timestamp guidance).\n"
        "- Ensure start_time < end_time and both are within the video.\n"
        "- If unsure about exact times, give your best estimate.\n"
    )


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


def extract_json_text(text: str) -> str:
    """Strip fences or extra text and return JSON payload."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        first_newline = cleaned.find("\n")
        if first_newline != -1:
            cleaned = cleaned[first_newline + 1 :]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
    else:
        left = cleaned.find("{")
        right = cleaned.rfind("}")
        if left != -1 and right != -1 and right > left:
            cleaned = cleaned[left : right + 1]
    return cleaned


def parse_segments(text: str, expected_count: int) -> List[Segment]:
    """Parse the JSON response into a list of segments."""
    if not text:
        raise ValueError("Gemini returned empty text.")

    # Before example: JSON parse failure -> no actionable data.
    # After example:  strip fences, then parse clean JSON.
    cleaned = extract_json_text(text)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Could not parse JSON response: {exc}\nRaw text:\n{text}") from exc

    segments_data = data.get("segments")
    if segments_data is None and "segment" in data:
        segments_data = [data["segment"]]
    if not isinstance(segments_data, list):
        raise ValueError(f"Response missing segments list: {data}")

    segments = []
    for entry in segments_data:
        start_time = str(entry.get("start_time", "")).strip()
        end_time = str(entry.get("end_time", "")).strip()
        description = str(entry.get("description", "")).strip()
        if not start_time or not end_time:
            raise ValueError(f"Missing start_time/end_time in response: {entry}")
        segments.append(Segment(start_time=start_time, end_time=end_time, description=description))

    if len(segments) != expected_count:
        raise ValueError(f"Expected {expected_count} segment(s), got {len(segments)}: {segments_data}")

    return segments


def _parse_timecode_to_seconds(value: str) -> float:
    """Convert MM:SS (or HH:MM:SS) to seconds."""
    parts = [p.strip() for p in value.split(":")]
    if len(parts) == 2:
        minutes, seconds = parts
        hours = 0
    elif len(parts) == 3:
        hours, minutes, seconds = parts
    else:
        raise ValueError(f"Unsupported time format: {value}")
    return float(hours) * 3600 + float(minutes) * 60 + float(seconds)


def _seconds_to_ffmpeg_ts(seconds: float) -> str:
    """Return an ffmpeg-friendly timestamp string."""
    total = max(seconds, 0)
    hours = int(total // 3600)
    minutes = int((total % 3600) // 60)
    secs = total % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


def segment_to_ffmpeg_range(segment: Segment) -> Tuple[str, str]:
    """Return ffmpeg start ts and duration ts."""
    start_seconds = _parse_timecode_to_seconds(segment.start_time)
    end_seconds = _parse_timecode_to_seconds(segment.end_time)
    if end_seconds <= start_seconds:
        raise ValueError(
            f"end_time must be after start_time; got {segment.start_time} -> {segment.end_time}"
        )
    duration = end_seconds - start_seconds
    return _seconds_to_ffmpeg_ts(start_seconds), _seconds_to_ffmpeg_ts(duration)


def ensure_output_dir(path: str) -> None:
    """Create the output directory if missing."""
    output_dir = os.path.dirname(path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)


def cut_clip(input_path: str, output_path: str, segment: Segment, reencode: bool) -> None:
    """Cut the clip using ffmpeg."""
    if which("ffmpeg") is None:
        raise SystemExit("ffmpeg is required on PATH to cut clips. Install ffmpeg and retry.")

    start_ts, duration_ts = segment_to_ffmpeg_range(segment)

    # Before example: concat failed when codecs differ across sources.
    # After example:  re-encode to a common format (disable with GEMINI_REENCODE=0).
    if reencode:
        command = [
            "ffmpeg",
            "-y",
            "-ss",
            start_ts,
            "-t",
            duration_ts,
            "-i",
            input_path,
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            output_path,
        ]
    else:
        command = [
            "ffmpeg",
            "-y",
            "-ss",
            start_ts,
            "-t",
            duration_ts,
            "-i",
            input_path,
            "-c",
            "copy",
            output_path,
        ]
    logging.info("ffmpeg clip start=%s duration=%s output=%s", start_ts, duration_ts, output_path)
    subprocess.run(command, check=True)


def concat_clips(clip_paths: List[str], output_path: str, reencode: bool) -> None:
    """Concat clip files into a single output mp4."""
    if which("ffmpeg") is None:
        raise SystemExit("ffmpeg is required on PATH to concatenate clips. Install ffmpeg and retry.")

    ensure_output_dir(output_path)
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as handle:
        list_path = handle.name
        for clip in clip_paths:
            handle.write(f"file '{clip}'\n")

    # Before example: concat failed on mixed codecs without re-encode.
    # After example:  re-encode to a single stream (disable with GEMINI_REENCODE=0).
    if reencode:
        command = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            list_path,
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            output_path,
        ]
    else:
        command = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            list_path,
            "-c",
            "copy",
            output_path,
        ]
    logging.info("ffmpeg concat output=%s", output_path)
    subprocess.run(command, check=True)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    model = os.environ.get("GEMINI_VIDEO_MODEL", "gemini-2.5-flash")
    video_a_url = os.environ.get("GEMINI_VIDEO_URL_A", VIDEO_A_URL)
    video_b_url = os.environ.get("GEMINI_VIDEO_URL_B", VIDEO_B_URL)
    prompt_a = os.environ.get("GEMINI_VIDEO_PROMPT_A", VIDEO_A_PROMPT)
    prompt_b = os.environ.get("GEMINI_VIDEO_PROMPT_B", VIDEO_B_PROMPT)
    output_path = os.environ.get("GEMINI_OUTPUT_PATH", DEFAULT_OUTPUT_PATH)
    reencode = os.environ.get("GEMINI_REENCODE", "1") == "1"

    logging.info("gemini_video_merge start model=%s reencode=%s", model, reencode)
    client = _require_gemini_client()

    with tempfile.TemporaryDirectory() as tmpdir:
        video_a_path = download_video(video_a_url, tmpdir, "video_a")
        video_b_path = download_video(video_b_url, tmpdir, "video_b")

        response_a = request_segments(client, video_a_path, model, build_prompt(prompt_a, segment_count=2))
        segments_a = parse_segments(response_a, expected_count=2)
        response_b = request_segments(client, video_b_path, model, build_prompt(prompt_b, segment_count=1))
        segments_b = parse_segments(response_b, expected_count=1)

        clip_paths: List[str] = []
        for idx, segment in enumerate(segments_a, start=1):
            clip_path = os.path.join(tmpdir, f"clip_a_{idx}.mp4")
            logging.info(
                "segment A%s start=%s end=%s description=%s",
                idx,
                segment.start_time,
                segment.end_time,
                segment.description,
            )
            cut_clip(video_a_path, clip_path, segment, reencode)
            clip_paths.append(clip_path)

        segment_b = segments_b[0]
        clip_b_path = os.path.join(tmpdir, "clip_b_1.mp4")
        logging.info(
            "segment B1 start=%s end=%s description=%s",
            segment_b.start_time,
            segment_b.end_time,
            segment_b.description,
        )
        cut_clip(video_b_path, clip_b_path, segment_b, reencode)
        clip_paths.append(clip_b_path)

        concat_clips(clip_paths, output_path, reencode)

    print(
        json.dumps(
            {
                "output_path": output_path,
                "segments": [
                    {"source": "A", **segments_a[0].__dict__},
                    {"source": "A", **segments_a[1].__dict__},
                    {"source": "B", **segment_b.__dict__},
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
