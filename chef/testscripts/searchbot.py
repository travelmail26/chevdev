import os
import json
from openai import OpenAI
from redditapi import search_reddit_with_url
from serpapirecipes import search_serpapi

# --- Configuration ---

openai_api_key = os.environ['OPENAI_API_KEY']
MODEL = "gpt-4o-mini" 
MAX_INTERACTIONS = 5 




system_instrucition = """ You are a helpful research assistant \
    You can search the web for information, 
    You will use function calls to retrieve information 
    Sometimes you will call multiple functions and can choose to collect more information before messaging the user.
 """

def run_agent_loop(user_instruction: str):

    try:
        client = OpenAI(api_key=openai_api_key) # Initializes the client with API key
    except Exception as e:
        print(f"Error initializing OpenAI client: {e}")
        print("Please ensure your OPENAI_API_KEY environment variable is set correctly.")
        return

    # Start the conversation history. You can add a system message for context.
    messages = [
        {"role": "system", "content": system_instrucition},
        {"role": "user", "content": user_instruction}
    ]

    print(f"\nStarting agent loop with instruction: '{user_instruction}'")
    print(f"Max interactions set to: {MAX_INTERACTIONS}")

    for i in range(MAX_INTERACTIONS):
        print(f"\n--- Interaction {i + 1} ---")
        #print(f"Messages sent to OpenAI: {messages}")

        try:
            # Send the current conversation history and function descriptions to OpenAI
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=tools,
                tool_choice="auto",  # Let OpenAI decide whether to use a tool or respond directly
            )

            response_message = response.choices[0].message
            # print(f"OpenAI Raw Response: {response_message}") # Optional: for debugging

            # Check if OpenAI wants to call one or more tools (functions)
            tool_calls = response_message.tool_calls

            if tool_calls:
                # *** Step 1: Append the assistant's request to call functions to the history ***
                messages.append(response_message) # Important: Add the response containing the tool_calls

                # *** Step 2: Call the requested functions and gather results ***
                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    function_to_call = AVAILABLE_FUNCTIONS.get(function_name)

                    if not function_to_call:
                        print(f"Error: OpenAI requested unknown function '{function_name}'")
                        # Optionally, send an error message back to OpenAI
                        messages.append(
                             {
                                "tool_call_id": tool_call.id,
                                "role": "tool",
                                "name": function_name,
                                "content": f"Error: Function '{function_name}' not found.",
                            }
                        )
                        continue # Skip to next tool call if any, or next loop iteration

                    try:
                        # Arguments are provided as a JSON string by OpenAI
                        function_args = json.loads(tool_call.function.arguments)
                        print(f"OpenAI requests calling: {function_name} with args: {function_args}")

                        # Call the actual Python function with the arguments
                        function_response = function_to_call(**function_args)

                         # *** Step 3: Append the function's *result* back to the history ***
                        messages.append(
                            {
                                "tool_call_id": tool_call.id, # Crucial to match the request
                                "role": "tool",              # Role must be 'tool' for function results
                                "name": function_name,       # Name of the function that was called
                                "content": str(function_response)# The actual result from your Python function
                            }
                        )
                    except Exception as e:
                        print(f"Error calling function {function_name} or processing its result: {e}")
                        # Append an error message for this specific tool call
                        messages.append(
                             {
                                "tool_call_id": tool_call.id,
                                "role": "tool",
                                "name": function_name,
                                "content": f"Error executing function {function_name}: {str(e)}",
                            }
                        )
                # After processing all tool calls in this turn, loop back to OpenAI

            else:
                # *** OpenAI provided a direct text response (no function call needed) ***
                final_response = response_message.content
                print(f"\n--- Final Response from OpenAI ---")
                print(final_response)
                messages.append(response_message) # Add the final response to history
                break # Exit the loop as we have a final answer

        except Exception as e:
            print(f"An error occurred during the API call or processing: {e}")
            break # Exit loop on error

    else:
        # This executes if the loop completes without hitting the 'break' statement
        print("\n--- Agent loop finished: Maximum interaction limit reached. ---")
        # Display the last message from the assistant if available, otherwise show history
        last_message = messages[-1]
        if last_message['role'] == 'assistant':
             print("Last message from assistant:", last_message.get('content', 'No content'))
        else:
             print("Loop ended, review message history for context.")
             # print(messages) # Optional: print full history if needed


tools = [
    {
        "type": "function",
        "function": {
            "name": "search_serpapi",
            "description": """Performs a Google search with optional site-specific filtering. 
            If a user specifies a site, fill in the appropriate parameters to search only that site. \
                For instance, if the user says reddit, fill the parameter with reddit.com""",   
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to look for",
                    },
                    "site": {
                        "type": "string",
                        "description": "Optional: Specific website to search (e.g., 'allrecipes.com', 'foodnetwork.com'). Leave empty for general web search."
                    }
                },
                "required": ["query"]  # Only query is required, site is optional
            },
            "strict": False
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_reddit_with_url",
            "description": """Scrapes a Reddit URLs. It necessary to get comments and posts from Google search or URL \
                The function returns a list of dictionaries, each containing the post and its comments.""",
            "parameters": {
                "type": "object",
                "properties": {
                    "urls": {
                        "type": "string",
                        "description": "The full Reddit post URL and must only be a URL string",
                    }
                },
                "required": ["urls"]
            },
            "strict": False
        }
    }
]

# Update the AVAILABLE_FUNCTIONS to match:
AVAILABLE_FUNCTIONS = {
    "search_serpapi": search_serpapi,
    "search_reddit_with_url": search_reddit_with_url
}


if __name__ == "__main__":
    # Check if API key is likely set (basic check)
    if not os.getenv("OPENAI_API_KEY"):
        print("Warning: OPENAI_API_KEY environment variable not found.")
        print("Please set it before running the script.")
        # You could exit here or attempt to proceed if the key is set some other way
        # exit(1) # Uncomment to force exit if key is missing

    # Get the initial instruction from the user
    instruction = input("Enter your instruction for the agent: ")

    if instruction:
        run_agent_loop(instruction)
    else:
        print("No instruction provided.")