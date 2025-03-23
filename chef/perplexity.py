
import json
import os
import sys
from sheetscall import add_chatlog_entry
import requests

from openai import OpenAI

try:
    YOUR_API_KEY = os.environ.get('PERPLEXITY_KEY')

except:
    raise ValueError("The 'PERPLEXITY_KEY' environment variable is not set.")

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





def perplexitycall(messages):
    print('**DEBUG: perplexitycall triggered**')

    headers = {
        "Authorization": f"Bearer {YOUR_API_KEY}",
        "Content-Type": "application/json"
    }

    print('**DEBUG: messages sent to perplexity api**', messages)

    messages.insert(
        0, {
            "role": "system",
            "content": """--Return the full citations and bibliography for each result. \
                                --Always paste the full URL link in every citation. \ 
                                 --Provide at last one direct quote when citing a source \
                                    --Do not suggest nutritional advice on your own. 
                                    -- You do not know what is health or if I should consult someone. You will not suggest it independent of a source"""
        }
    )


    data = {
        "model": "sonar-pro",
        "messages": messages,
        "stream": True
    }

    response = requests.post(
        "https://api.perplexity.ai/chat/completions",
        headers=headers,
        json=data,
        stream=True
    )
    response.raise_for_status()

    content = ""
    buffer = ""
    for line in response.iter_lines():
        if line:
            decoded_line = line.decode('utf-8')
            if decoded_line.startswith("data: ") and decoded_line != "data: [DONE]":
                data = json.loads(decoded_line[len("data: "):])

                # Capture citations if present
                if 'citations' in data:
                    citations = data['citations']
                    #print('**DEBUG: Citations found:**', citations)

                #print ('DEBUG: perplexity data', data)
                if 'choices' in data and 'delta' in data['choices'][0]:
                    delta = data['choices'][0]['delta']
                    if 'content' in delta and delta['content'] is not None:
                        buffer += delta['content']
                        content += delta['content']
                        if len(buffer) >= 40:
                            #print(buffer, end='', flush=True)
                            buffer = ""
            elif decoded_line == "data: [DONE]":
                #print("**DEBUG: Stream ended with [DONE]**")
                break

    # if buffer:
    #     print(buffer, end='', flush=True)

    if citations:
        content += "\n\n**Sources:**\n"
        for i, citation in enumerate(citations, 1):
            content += f"[{i}] {citation}\n"

    print('**DEBUG: perplexity.py full content of perplexity call**', content)
    return content


if __name__ == "__main__":
    test_messages = [{
        "role":
        "user",
        "content":
        "i'm having difficulty makgin the carrot syrup similar to chef Michael Solomonov's . \
            I reduce the liquid of about a pound of carrots and i'm maybe left with a tablespoon of liquid. \
                am i doing it wrong or is that what it should yeild? Find solutions"
    }]
    result = perplexitycall(test_messages)
    print(result)




##misc code###

# def perplexitychat():
#     print('**DEBUG: persplexitychat triggered**')

#     first_input = True
#     user_input = ""

#     while True:
#         user_input = input("User: ")
#         if first_input:
#             user_input = user_input
#             first_input = False

#         # Add user input to messages
#         messages.append({"role": "user", "content": user_input})

#         # Get response from OpenAI
#         response = perplexitycall(messages)

#         # Add AI response to messages
#         messages.append({"role": "assistant", "content": response})
#         print('**DEBUG: message after response**', messages)

#         # Print AI response
#         print("\nAI: ", response)