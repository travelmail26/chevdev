import os
import requests

def call_openai_no_tool(query, openai_api_key=None, model="gpt-4.1-nano-2025-04-14"):
    """
    Calls OpenAI's chat/completions endpoint with the given message_object (must have 'messages' key).
    Returns the assistant's response content.
    
    """
    openai_api_key = openai_api_key or os.environ.get("OPENAI_API_KEY")
    if not openai_api_key:
        raise ValueError("OpenAI API key is missing.")

    headers = {
        "Authorization": f"Bearer {openai_api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": query["messages"],
        "temperature": 0.2,
        "max_tokens": 120
    }

    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=60
    )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]

# Example usage:
if __name__ == "__main__":
    import json
    # Example message_object (replace with your actual object)
    message_object = {
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello, who won the world series in 2020?"}
        ]
    }
    result = call_openai_no_tool(message_object)
    print("Assistant:", result)
