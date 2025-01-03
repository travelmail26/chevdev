import json
import os
from sheetscall import add_chatlog_entry

from openai import OpenAI

YOUR_API_KEY = openai_api_key = os.environ['PERPLEXITY_KEY']

try:
    with open('tools.txt', 'r') as file:
        tools = json.load(file)
except Exception:
    None

messages = [{
    "role":
    "system",
    "content":
    ("""You are an artificial intelligence assistant. Just say hi back to me."""
     ),
}]


def perplexitychat():
    print('**DEBUG: persplexitychat triggered**')

    first_input = True
    user_input = ""

    while True:
        user_input = input("User: ")
        if first_input:
            user_input = user_input
            first_input = False

        # Add user input to messages
        messages.append({"role": "user", "content": user_input})

        # Get response from OpenAI
        response = perplexitycall(messages)

        # Add AI response to messages
        messages.append({"role": "assistant", "content": response})
        print('**DEBUG: message after response**', messages)

        # Print AI response
        print("\nAI: ", response)


def perplexitycall(messages):
    logging.info('Perplexity API call triggered')
    print('**DEBUG: perplexitycall triggered**')

    client = OpenAI(api_key=YOUR_API_KEY, base_url="https://api.perplexity.ai")

    print ('**DEBUG: messages sent perplexity api**', messages)

    # chat completion with streaming
    stream = client.chat.completions.create(
        model="llama-3.1-sonar-large-128k-online", 
        messages=messages,
        stream=True
    )

    buffer = ""
    content = ""
    for chunk in stream:
        if chunk.choices[0].delta.content is not None:
            buffer += chunk.choices[0].delta.content
            content += chunk.choices[0].delta.content
            if len(buffer) >= 300:
                print(buffer, end='', flush=True)
                buffer = ""

    if buffer:  # Print any remaining content
        print(buffer, end='', flush=True)

    add_chatlog_entry(content)
    return content  # Return the complete content


if __name__ == "__main__":
    test_messages = [
        {"role": "user", "content": "recipe for short meatballs"}
    ]
    result = perplexitycall(test_messages)
    print(result)
