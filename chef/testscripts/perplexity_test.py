\
import json
import os
import requests

try:
    YOUR_API_KEY = os.environ.get('PERPLEXITY_KEY')
    if not YOUR_API_KEY:
        raise ValueError("The 'PERPLEXITY_KEY' environment variable is not set or is empty.")
except KeyError:
    raise ValueError("The 'PERPLEXITY_KEY' environment variable is not set.")

def search_perplexity(query: str):
    """
    Performs a search using the Perplexity API and returns the summarized result with citations.
    Use this tool for general web searches, finding explanations, or getting summaries on topics.
    It directly returns the answer content, unlike search_serpapi which only returns URLs.
    """
    print(f'**DEBUG: search_perplexity triggered with query: {query}**')

    messages = [
        {
            "role": "system",
            "content": """NEVER say you do not have access to search or browse a specific website. You will search for what the user asks. Return the full citations and bibliography for each result. Always paste the full URL link in every citation. Provide at least one direct quote when citing a source."""
        },
        {
            "role": "user",
            "content": query
        }
    ]

    headers = {
        "Authorization": f"Bearer {YOUR_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "sonar-pro", # Using the online model for search capabilities
        "messages": messages,
        "stream": False # Set stream to False to get the full response at once
    }

    try:
        response = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers=headers,
            json=data
        )
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)

        response_data = response.json()
        print(f"**DEBUG: Perplexity API Response Data:**\n{json.dumps(response_data, indent=2)}") # Debugging output

        # Extract content and citations
        content = ""
        citations = []

        if 'choices' in response_data and len(response_data['choices']) > 0:
            message = response_data['choices'][0].get('message', {})
            content = message.get('content', '')
            # Perplexity API might include citations differently in non-streamed responses,
            # often embedded within the content or in a separate field. Adjust based on actual API structure.
            # For now, assuming citations might be part of the content or need specific parsing.
            # If the API has a dedicated 'citations' field in the response, use that.
            # Example: citations = response_data.get('citations', [])

        # Basic citation handling (if they are appended manually or need extraction)
        # This part might need refinement based on how the 'sonar-medium-online' model returns citations non-streamed.
        # If citations are embedded like "[1]", "[2]", etc., they are already in 'content'.
        # If there's a separate citation structure, parse it here.

        # For simplicity, returning the main content for now.
        # Add explicit citation formatting if needed based on API response structure.

        return content

    except requests.exceptions.RequestException as e:
        print(f"Error calling Perplexity API: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_details = e.response.json()
                print(f"Error details: {json.dumps(error_details, indent=2)}")
                return f"Error accessing Perplexity: {error_details.get('error', {}).get('message', str(e))}"
            except json.JSONDecodeError:
                print(f"Could not decode JSON error response. Status code: {e.response.status_code}, Response text: {e.response.text}")
                return f"Error accessing Perplexity: Status {e.response.status_code} - {e.response.reason}"
        return f"Error accessing Perplexity: {str(e)}"
    except Exception as e:
        print(f"An unexpected error occurred in search_perplexity: {e}")
        return f"An unexpected error occurred: {str(e)}"


if __name__ == "__main__":
    test_query = "search why semifreddo recipe is too solid and not soft. cite names of sources"
    print(f"Testing Perplexity with query: '{test_query}'")
    result = search_perplexity(test_query)
    print("\n--- Perplexity Result ---")
    print(result)
    print("------------------------")

    test_query_2 = "latest news on AI advancements"
    print(f"\nTesting Perplexity with query: '{test_query_2}'")
    result_2 = search_perplexity(test_query_2)
    print("\n--- Perplexity Result ---")
    print(result_2)
    print("------------------------")

