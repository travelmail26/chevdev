import os
import time
import logging
import json
from typing import Any, Dict, List

import httpx
import requests

OPENAI_URL = "https://api.openai.com/v1/responses"
PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"


def _extract_openai_text(response_data: Dict[str, Any]) -> str:
    """Return text from a Responses API payload with simple fallbacks."""
    output_text = response_data.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    parts: List[str] = []
    for item in response_data.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                parts.append(str(content["text"]))

    return "\n".join(parts).strip()


def _is_reasoning_only_response(response_data: Dict[str, Any], text: str) -> bool:
    if text.strip():
        return False
    output_items = response_data.get("output") or []
    if not output_items:
        return False
    # Before example: output was reasoning-only and parsed as empty text.
    # After example: detect reasoning-only payload and trigger a single retry.
    return all(isinstance(item, dict) and item.get("type") == "reasoning" for item in output_items)


async def quick_openai_message_stream(prompt: str, model: str | None = None):
    """Yield real-time text deltas from OpenAI Responses API SSE stream."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY missing")

    chosen_model = model or os.getenv("INTERFACETEST_OPENAI_MODEL", "gpt-5-2025-08-07")
    max_output_tokens = int(os.getenv("INTERFACETEST_OPENAI_MAX_OUTPUT_TOKENS", "1200"))
    payload = {
        "model": chosen_model,
        "input": [{"role": "user", "content": prompt}],
        "max_output_tokens": max_output_tokens,
        "reasoning": {"effort": "minimal"},
        "text": {"verbosity": "medium"},
        "stream": True,
    }

    timeout = httpx.Timeout(connect=20.0, read=300.0, write=30.0, pool=30.0)
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    full_text = ""

    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", OPENAI_URL, headers=headers, json=payload) as response:
            if response.status_code != 200:
                body = await response.aread()
                raise RuntimeError(f"OpenAI stream error {response.status_code}: {body[:500].decode('utf-8', errors='ignore')}")

            async for raw_line in response.aiter_lines():
                if not raw_line:
                    continue
                if raw_line.startswith("data:"):
                    raw_line = raw_line[5:].strip()
                if not raw_line:
                    continue
                if raw_line == "[DONE]":
                    break

                try:
                    event = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue

                event_type = str(event.get("type") or "")
                if event_type == "response.output_text.delta":
                    delta = str(event.get("delta") or "")
                    if delta:
                        full_text += delta
                        yield {"type": "delta", "delta": delta, "full_text": full_text}
                    continue

                # Compatibility fallback for chat-completions-like deltas
                choices = event.get("choices")
                if isinstance(choices, list) and choices:
                    delta = str(((choices[0] or {}).get("delta") or {}).get("content") or "")
                    if delta:
                        full_text += delta
                        yield {"type": "delta", "delta": delta, "full_text": full_text}
                        continue

                if event_type in ("response.error", "error"):
                    err = event.get("error") or {}
                    message = err.get("message") if isinstance(err, dict) else str(err)
                    raise RuntimeError(f"OpenAI stream event error: {message}")

                if event_type == "response.completed":
                    break

    yield {"type": "done", "full_text": full_text}


async def quick_perplexity_stream_existing_app(query: str):
    """Yield Perplexity streaming deltas using the existing app pattern and sonar model."""
    api_key = os.getenv("PERPLEXITY_KEY")
    if not api_key:
        raise RuntimeError("PERPLEXITY_KEY missing")

    # Keep this pinned to sonar per request.
    model = "sonar"
    payload = {
        # Before example: model could drift by environment config.
        # After example: force sonar for this UI stream path.
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Answer clearly with concise facts and include citations when available."
                ),
            },
            {"role": "user", "content": query},
        ],
        "stream": True,
        "reasoning_effort": "high",
        "web_search_options": {
            "search_type": "pro",
            "search_domain_filter": ["reddit.com"],
        },
    }

    timeout = httpx.Timeout(connect=20.0, read=300.0, write=30.0, pool=30.0)
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    full_text = ""
    seen_citations = set()
    citations: List[str] = []

    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", PERPLEXITY_URL, headers=headers, json=payload) as response:
            if response.status_code != 200:
                body = await response.aread()
                raise RuntimeError(
                    f"Perplexity stream error {response.status_code}: "
                    f"{body[:500].decode('utf-8', errors='ignore')}"
                )

            async for raw_line in response.aiter_lines():
                if not raw_line:
                    continue
                if raw_line.startswith("data:"):
                    raw_line = raw_line[5:].strip()
                if not raw_line:
                    continue
                if raw_line == "[DONE]":
                    break

                try:
                    event = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue

                if isinstance(event.get("citations"), list):
                    for url in event["citations"]:
                        if isinstance(url, str) and url and url not in seen_citations:
                            seen_citations.add(url)
                            citations.append(url)

                delta = ""
                choices = event.get("choices")
                if isinstance(choices, list) and choices:
                    delta = str(((choices[0] or {}).get("delta") or {}).get("content") or "")

                if delta:
                    full_text += delta
                    yield {
                        "type": "delta",
                        "delta": delta,
                        "full_text": full_text,
                        "citations": citations,
                        "model": model,
                    }

                if (choices and isinstance(choices, list) and
                        str((choices[0] or {}).get("finish_reason") or "") == "stop"):
                    break

    yield {"type": "done", "full_text": full_text, "citations": citations, "model": model}


def quick_openai_message(prompt: str, model: str | None = None) -> Dict[str, Any]:
    """Fast one-shot text response for quick message UX demos."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"ok": False, "error": "OPENAI_API_KEY missing"}

    chosen_model = model or os.getenv("INTERFACETEST_OPENAI_MODEL", "gpt-5-2025-08-07")
    max_output_tokens = int(os.getenv("INTERFACETEST_OPENAI_MAX_OUTPUT_TOKENS", "1200"))
    payload = {
        # Before example: no explicit model and unpredictable behavior.
        # After example: explicit gpt-5-2025-08-07 default for stable demo behavior.
        "model": chosen_model,
        "input": [{"role": "user", "content": prompt}],
        "max_output_tokens": max_output_tokens,
        "reasoning": {"effort": "minimal"},
        "text": {"verbosity": "medium"},
    }

    start = time.monotonic()
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        response = requests.post(OPENAI_URL, headers=headers, json=payload, timeout=180)
        duration_ms = int((time.monotonic() - start) * 1000)
        if response.status_code != 200:
            return {
                "ok": False,
                "status": response.status_code,
                "error": response.text[:600],
                "duration_ms": duration_ms,
            }

        data = response.json()
        text = _extract_openai_text(data)
        status_value = str(data.get("status") or "")
        incomplete_reason = ""
        incomplete_details = data.get("incomplete_details")
        if isinstance(incomplete_details, dict):
            incomplete_reason = str(incomplete_details.get("reason") or "")

        if _is_reasoning_only_response(data, text) and (
            incomplete_reason == "max_output_tokens" or status_value == "incomplete"
        ):
            retry_payload = dict(payload)
            retry_payload["max_output_tokens"] = int(
                os.getenv("INTERFACETEST_OPENAI_RETRY_MAX_OUTPUT_TOKENS", "2400")
            )
            retry_payload["reasoning"] = {"effort": "minimal"}

            retry_response = requests.post(OPENAI_URL, headers=headers, json=retry_payload, timeout=180)
            duration_ms = int((time.monotonic() - start) * 1000)
            if retry_response.status_code == 200:
                retry_data = retry_response.json()
                retry_text = _extract_openai_text(retry_data)
                if retry_text.strip():
                    text = retry_text
                    data = retry_data

        return {
            "ok": True,
            "text": text,
            "duration_ms": duration_ms,
            "model": chosen_model,
            "status": data.get("status"),
        }
    except Exception as exc:
        logging.warning("quick_openai_message failed: %s", exc)
        duration_ms = int((time.monotonic() - start) * 1000)
        return {"ok": False, "error": str(exc), "duration_ms": duration_ms}


def _extract_perplexity_text(response_data: Dict[str, Any]) -> str:
    choices = response_data.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    return str(message.get("content", "")).strip()


def _extract_perplexity_citations(response_data: Dict[str, Any]) -> List[str]:
    citations = response_data.get("citations")
    if isinstance(citations, list):
        return [str(url) for url in citations if isinstance(url, str)]
    return []


def quick_perplexity_search(query: str, model: str | None = None) -> Dict[str, Any]:
    """Fast internet search call for Telegram search UX demos."""
    api_key = os.getenv("PERPLEXITY_KEY")
    if not api_key:
        return {"ok": False, "error": "PERPLEXITY_KEY missing"}

    chosen_model = model or os.getenv("INTERFACETEST_PERPLEXITY_MODEL", "sonar")
    payload = {
        "model": chosen_model,
        "messages": [
            {
                "role": "system",
                # Before example: giant system prompt slows small demos.
                # After example: short format instructions for snappier test responses.
                "content": "Answer briefly first, then add 3-5 bullet facts and include sources.",
            },
            {"role": "user", "content": query},
        ],
        "stream": False,
        "web_search_options": {"search_type": "pro"},
    }

    start = time.monotonic()
    try:
        response = requests.post(
            PERPLEXITY_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=120,
        )
        duration_ms = int((time.monotonic() - start) * 1000)
        if response.status_code != 200:
            return {
                "ok": False,
                "status": response.status_code,
                "error": response.text[:600],
                "duration_ms": duration_ms,
            }

        data = response.json()
        text = _extract_perplexity_text(data)
        citations = _extract_perplexity_citations(data)
        return {
            "ok": True,
            "text": text,
            "citations": citations,
            "duration_ms": duration_ms,
            "model": chosen_model,
        }
    except Exception as exc:
        logging.warning("quick_perplexity_search failed: %s", exc)
        duration_ms = int((time.monotonic() - start) * 1000)
        return {"ok": False, "error": str(exc), "duration_ms": duration_ms}
