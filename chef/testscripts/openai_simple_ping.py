import os
import time
import requests


def call_openai_hi():
    """Simple OpenAI call using /v1/responses with a single 'hi' message."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"ok": False, "error": "OPENAI_API_KEY missing"}

    payload = {
        "model": "gpt-5-nano-2025-08-07",
        "input": [{"role": "user", "content": "hi"}],
        "max_output_tokens": 64,
    }

    start = time.monotonic()
    try:
        response = requests.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=20,
        )
        duration_ms = int((time.monotonic() - start) * 1000)
        if response.status_code != 200:
            return {
                "ok": False,
                "status": response.status_code,
                "error": response.text[:300],
                "duration_ms": duration_ms,
            }

        data = response.json()
        # Example before/after: empty output -> "", success -> short text response.
        text = data.get("output_text", "") or ""
        return {"ok": True, "text": text, "duration_ms": duration_ms}
    except Exception as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        return {"ok": False, "error": str(exc), "duration_ms": duration_ms}


if __name__ == "__main__":
    result = call_openai_hi()
    print(result)
