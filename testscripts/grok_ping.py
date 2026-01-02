import os
import requests

def ping_grok():
    api_key = os.environ.get("XAI_API_KEY")
    if not api_key:
        print("Error: XAI_API_KEY not found in environment variables.")
        return

    url = "https://api.x.ai/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    data = {
        "model": "grok-4-fast-non-reasoning",
        "messages": [
            {"role": "user", "content": "hi"}
        ]
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        print("Grok says back:")
        print(result['choices'][0]['message']['content'])
    except Exception as e:
        print(f"An error occurred: {e}")
        if 'response' in locals():
            print(f"Response status: {response.status_code}")
            print(f"Response text: {response.text}")

if __name__ == "__main__":
    ping_grok()
