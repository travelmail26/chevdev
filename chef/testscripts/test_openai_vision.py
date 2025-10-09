"""Simple one-off script that mirrors our messenger flow to test image analysis."""

import os
import requests


def main() -> None:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("Set OPENAI_API_KEY before running this script.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "gpt-5-mini",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "what's in this image?"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": (
                                "https://firebasestorage.googleapis.com/v0/b/cheftest-f174c/o/"
                                "telegram_photos%2FAgACAgEAAxkBAAIJgmjliOqJZHnJkkVwePhPF4rwobhBAAIMC2sbH1cxR3eZv-"
                                "FxCWqhAQADAgADeQADNgQ.jpg?alt=media&token=bc7240bb-eddc-48dc-9053-1ad23721feec"
                            )
                        },
                    },
                ],
            }
        ],
    }

    # Before: we only sent plain text and the model replied it couldn't view the media.
    # After: the same messenger-style payload includes the image URL so the model can choose to analyze it.
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=60,
    )
    response.raise_for_status()

    data = response.json()
    print(data["choices"][0]["message"].get("content"))


if __name__ == "__main__":
    main()
