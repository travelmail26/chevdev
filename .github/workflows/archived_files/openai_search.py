import os
from openai import OpenAI

# Access the OpenAI API key from environment variables
openai_api_key = os.environ.get('OPENAI_API_KEY')
if not openai_api_key:
    raise ValueError("OPENAI_API_KEY environment variable not set.")

# Initialize the client with the API key




client = OpenAI(api_key=openai_api_key)

response = client.responses.create(
    model="gpt-4o",
    tools=[
    {
      "type": "web_search_preview",
      "user_location": {
        "type": "approximate"
      },
      "search_context_size": "high"
    }],
    input="What was a positive news story from today?",
)

print(response)
