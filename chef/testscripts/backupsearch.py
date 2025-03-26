import os
import requests

search_key = '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'

import os
from openai import OpenAI

def main():
    # Retrieve the OpenAI API key from the environment variable
    if not search_key:
        print("Error: OPENAI_API_KEY environment variable is not set.")
        return

    # Initialize OpenAI client with the API key
    client = OpenAI(api_key=search_key)

    # Define the prompt for the API
    prompt = "search reddit and only reddit urls for cookie recipes"

    try:
        # Call the OpenAI API with the new model and web search options
        completion = client.chat.completions.create(
            model="gpt-4o-mini-search-preview",
            #web_search_options={},  # Add any specific options if needed
            messages=[
                {
                    "role": "user",
                    "content": 'search reddit.com cookie mistakes and what commenters have suggested as fixes',
                }
            ],
        )

        # Print the response from the API
        print("Response from OpenAI:")
        print(completion.choices[0].message.content)

    except Exception as e:
        print(f"Error while calling OpenAI API: {e}")

if __name__ == "__main__":
    main()