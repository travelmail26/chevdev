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

def search_perplexity(query):
    """
    Performs a search using the Perplexity API and returns the summarized result with citations.
    Use this tool for general web searches, finding explanations, or getting summaries on topics.
    Args:
        query: Either a string for simple queries or a list of message dicts for conversation context
    """
    print(f'**DEBUG: search_perplexity triggered with query type: {type(query)}**')
    print(f'**DEBUG: query content: {query}**')

    # If query is a string, treat as single message. If list, use as conversation history
    if isinstance(query, str):
        query_messages = [{"role": "user", "content": query}]
    else:
        query_messages = query

    messages = [
        {
            "role": "system",
            "content": """
            **CRITICAL INSTRUCTION:** For each source you cite, you **MUST** include: --At least one direct quote (a few words minimum) from that source that directly supports the information you are providing. Integrate this quote naturally into your response.
            --NEVER say you do not have access to search or browse a specific website. 
            --**ALWAYS** paste the full URL link in every citation. 
            --**CRITICAL**-- Provide at least one direct quote when citing a source. ALWAYS quote at least a few words from each citation,  \
                directly relevant to your summary of why you chose this citation."""
        }
    ] + query_messages

    headers = {
        "Authorization": f"Bearer {YOUR_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "sonar-reasoning-pro",  # Using model that returns reasoning tokens
        "messages": messages,
        "stream": True,  # Enable streaming for reasoning tokens
        "reasoning_effort": "high"  # Get detailed reasoning tokens
    }

    try:
        print("\n=== Streaming reasoning tokens: ===\n")
        response = requests.post(
            "https://api.perplexity.ai/chat/completions",
            headers=headers,
            json=data,
            stream=True,
            timeout=120
        )
        response.raise_for_status()
        
        # Collect the complete response while streaming reasoning tokens
        full_content = ""
        seen_citations = set()  # Use a set to track unique citations
        citations = []
        
        for line in response.iter_lines():
            if line:
                try:
                    # Remove 'data: ' prefix and parse JSON
                    decoded_line = json.loads(line.decode('utf-8').removeprefix('data: '))
                    
                    # Extract the delta content (new tokens) if present
                    if 'choices' in decoded_line and len(decoded_line['choices']) > 0:
                        delta = decoded_line['choices'][0].get('delta', {})
                        if 'content' in delta:
                            # Print just the new content tokens
                            print(delta['content'], end='', flush=True)
                            full_content += delta['content']
                        # Handle citations - only add new ones
                        if 'citations' in decoded_line:
                            for citation in decoded_line['citations']:
                                if citation not in seen_citations:
                                    seen_citations.add(citation)
                                    citations.append(citation)
                except json.JSONDecodeError:
                    # Skip lines that aren't JSON
                    continue
                except Exception as e:
                    print(f"Error processing stream line: {e}")
                    continue
        
        print("\n=== End of reasoning tokens ===\n")
        
        # Create response_data structure matching the non-streaming format
        response_data = {
            'choices': [{
                'message': {
                    'content': full_content
                }
            }],
            'citations': citations
        }

        # Extract content and citations
        content = ""
        citations = []

        if 'choices' in response_data and len(response_data['choices']) > 0:
            message = response_data['choices'][0].get('message', {})
            content = message.get('content', '')
            citations = response_data.get('citations', [])
            structured_citations = [{"index": i + 1, "url": url} for i, url in enumerate(citations)]
            
            # Format the result with content and citations in a single string
            formatted_result = content
            
            # Add citations at the end if there are any
            if structured_citations:
                formatted_result += "\n\nCitations:\n"
                for citation in structured_citations:
                    formatted_result += f"[{citation['index']}] {citation['url']}\n"
            
            return formatted_result

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
    test_query = "I want to make a semifreddo that is thick and rich. how should I change the recipe?"
    print(f"Testing Perplexity with query: '{test_query}'")
    result = search_perplexity(test_query)
    print("\n--- Perplexity Result ---")
    print(result)
    print("------------------------")


