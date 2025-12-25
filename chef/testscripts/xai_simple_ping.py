import os
import time
import logging
import requests


def call_xai_hi(model: str | None = None) -> dict:
    """Simple xAI call using chat completions with a single 'hi' message."""
    api_key = os.getenv("XAI_AP_KEY") or os.getenv("XAI_API_KEY")
    if not api_key:
        logging.info("xai_simple: missing XAI_AP_KEY/XAI_API_KEY")
        return {"ok": False, "error": "XAI_AP_KEY missing"}

    chosen_model = model or os.getenv("XAI_MODEL", "grok-3-mini")
    payload = {
        "model": chosen_model,
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 64,
        "temperature": 0.2,
    }

    start = time.monotonic()
    logging.info("xai_simple: request start model=%s", chosen_model)
    try:
        response = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        duration_ms = int((time.monotonic() - start) * 1000)

        response_body = response.text.replace("\n", " ")
        chunk_size = 900
        for i in range(0, len(response_body), chunk_size):
            chunk = response_body[i:i + chunk_size]
            logging.info("xai_simple: response_body_part=%s", chunk)

        if response.status_code != 200:
            logging.info("xai_simple: non-200 status=%s", response.status_code)
            return {
                "ok": False,
                "status": response.status_code,
                "error": response.text[:300],
                "duration_ms": duration_ms,
            }

        data = response.json()
        text = ""
        try:
            text = data["choices"][0]["message"]["content"]
        except Exception:
            text = ""
        logging.info("xai_simple: ok duration_ms=%s chars=%s", duration_ms, len(text))
        return {"ok": True, "text": text, "duration_ms": duration_ms}
    except Exception as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        logging.info("xai_simple: exception duration_ms=%s error=%s", duration_ms, exc)
        return {"ok": False, "error": str(exc), "duration_ms": duration_ms}


if __name__ == "__main__":
    result = call_xai_hi()
    print(result)
