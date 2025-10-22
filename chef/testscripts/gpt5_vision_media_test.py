#!/usr/bin/env python3
"""Minimal GPT-5 vision probe using raw HTTP call (mirrors message_router style)."""
import os
import requests

API_KEY = os.environ.get("OPENAI_API_KEY")
if not API_KEY:
    raise SystemExit("OPENAI_API_KEY is not set; export the chefmain key before running.")

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

payload = {
    "model": "gpt-5-2025-08-07",
    "input": [
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": "what's in this image?"},
                {
                    "type": "input_image",
                    "image_url": "https://firebasestorage.googleapis.com/v0/b/cheftest-f174c/o/telegram_photos%2FAgACAgEAAxkBAAIKC2jrtcylXOfWngrHcngIAAFxdhlgDgACNwtrGwoKYEcBMaJVOyc4iQEAAwIAA3kAAzYE.jpg?alt=media&token=2594b1c7-8b5b-435a-a8c4-50cd65652a2d",
                },
            ],
        }
    ],
}

response = requests.post(
    "https://api.openai.com/v1/responses",
    headers=headers,
    json=payload,
    timeout=120,
)
response.raise_for_status()
response_data = response.json()

# The Responses API returns output -> list -> message -> content -> text.
output_items = response_data.get("output", [])
if output_items:
    first_message = output_items[0]
    content = first_message.get("content", [])
    if content and "text" in content[0]:
        print(content[0]["text"].strip())
    else:
        print(response_data)
else:
    print(response_data)
