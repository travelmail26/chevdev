import os
import time
import requests
import logging


def call_openai_hi():
    """Simple OpenAI call using /v1/responses with a single 'hi' message."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logging.info("openai_simple: missing OPENAI_API_KEY")
        return {"ok": False, "error": "OPENAI_API_KEY missing"}

    payload = {
        "model": "gpt-5-mini-2025-08-07",
        "input": [{"role": "user", "content": "hi"}],
        "max_output_tokens": 64,
    }

    start = time.monotonic()
    logging.info("openai_simple: request start")
    try:
        response = requests.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=180,
        )
        duration_ms = int((time.monotonic() - start) * 1000)
        logging.info("openai_simple: response_body=%s", response.text)
        if response.status_code != 200:
            logging.info("openai_simple: non-200 status=%s", response.status_code)
            return {
                "ok": False,
                "status": response.status_code,
                "error": response.text[:300],
                "duration_ms": duration_ms,
            }

        data = response.json()
        # Example before/after: empty output -> "", success -> short text response.
        text = data.get("output_text", "") or ""
        logging.info("openai_simple: ok duration_ms=%s chars=%s", duration_ms, len(text))
        return {"ok": True, "text": text, "duration_ms": duration_ms}
    except Exception as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        logging.info("openai_simple: exception duration_ms=%s error=%s", duration_ms, exc)
        return {"ok": False, "error": str(exc), "duration_ms": duration_ms}


if __name__ == "__main__":
    result = call_openai_hi()
    print(result)
