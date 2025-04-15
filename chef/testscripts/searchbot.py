import os
import json
import sys  # Add sys import
from openai import OpenAI
from redditapi import search_reddit_with_url
from serpapirecipes import search_serpapi
from redditbot import reddit_agent
from perplexity_test import search_perplexity  # Import the new function


# --- Configuration ---


# openai key
openai_api_key = os.environ['OPENAI_API_KEY']
MODEL = "gpt-4o-mini"

# google gemini key
gemini_api_key = os.environ['GEMINI_KEY_PH']
gemini_model = 'gemini-2.0-flash-thinking-exp-1219'

MAX_INTERACTIONS = 5  # Increased slightly to allow for multi-step calls

system_instrucition = """ You are a helpful research assistant designed to answer user queries comprehensively using available tools.

Your Goal: Provide the best possible answer by combining information from different sources when necessary.

Available Tools:
- `search_perplexity`: Use this for direct, summarized answers to general questions, explanations, or topics. It provides a concise summary with citations directly. Ideal when the user wants a quick overview or factual answer.
- `search_serpapi`: Use this specifically to find relevant URLs from a web search, especially when targeting a specific site like 'reddit.com'. It returns ONLY a list of URLs and titles, not the content. This is the FIRST step when you need to gather specific discussions or opinions (e.g., from Reddit).
- `reddit_agent`: Use this ONLY AFTER using `search_serpapi` to get a list of Reddit URLs. Pass the user's original query context and the list of Reddit URLs to this tool to scrape and summarize the discussions found in those specific Reddit threads.

Workflow Strategy:
1. Analyze the user's full request. Do they want a general summary, specific opinions from a site (like Reddit), or both?
2. If the user asks for opinions, discussions, or experiences (especially mentioning Reddit), FIRST use `search_serpapi` with the query and `site='reddit.com'`.
3. THEN, take the list of Reddit URLs returned by `search_serpapi` and pass them, along with the original query context, to the `reddit_agent` tool.
4. If the user asks for a general explanation or summary *in addition* to specific site information, you can use `search_perplexity` for the general part AND the `search_serpapi` -> `reddit_agent` flow for the specific site part. You can call multiple tools before responding.
5. If the user *only* asks for a general explanation or summary, `search_perplexity` is likely sufficient on its own.
6. Synthesize the results from all the tools called into a single, comprehensive answer for the user.
"""

def run_agent_loop(user_instruction: str):

    try:
        client = OpenAI(api_key=openai_api_key)  # Initializes the client with API key
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
        # print(f"Messages sent to OpenAI: {messages}")

        try:
            # Send the current conversation history and function descriptions to OpenAI
            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                tools=tools,
                tool_choice="auto",  # Let OpenAI decide whether to use a tool or respond directly
            )

            response_message = response.choices[0].message
            print(f"OpenAI Raw Response: {response_message}")  # Optional: for debugging

            # Check if OpenAI wants to call one or more tools (functions)
            tool_calls = response_message.tool_calls

            if tool_calls:
                # *** Step 1: Append the assistant's request to call functions to the history ***
                messages.append(response_message)  # Important: Add the response containing the tool_calls

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
                        continue  # Skip to next tool call if any, or next loop iteration

                    try:
                        # Arguments are provided as a JSON string by OpenAI
                        function_args = json.loads(tool_call.function.arguments)
                        print("\n=== Debug: Full function arguments ===")
                        print(f"Function: {function_name}")
                        print(f"Arguments: {json.dumps(function_args, indent=2)}")
                        print("=====================================\n")

                        # Call the actual Python function with the arguments
                        function_response = function_to_call(**function_args)
                        # print(f"Function Response in searchbot.py: {function_response}")
                        # *** Step 3: Append the function's *result* back to the history ***
                        messages.append(
                            {
                                "tool_call_id": tool_call.id,  # Crucial to match the request
                                "role": "tool",              # Role must be 'tool' for function results
                                "name": function_name,       # Name of the function that was called
                                "content": str(function_response)  # The actual result from your Python function
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
                messages.append(response_message)  # Add the final response to history
                break  # Exit the loop as we have a final answer

        except Exception as e:
            print(f"An error occurred during the API call or processing: {e}")
            break  # Exit loop on error

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
            "name": "reddit_agent",
            "description": """Scrapes and summarizes content from a list of Reddit URLs. CRITICAL: Only use this tool *after* getting Reddit URLs from `search_serpapi`. Pass the original user query context and the *exact* list of URLs provided by `search_serpapi`.""",
            "parameters": {
                "type": "object",
                "properties": {
                    "user_instruction": {
                        "type": "string",
                        "description": "The original user query or context.",
                    },
                    "urls": {
                        "type": "array",
                        "items": {
                            "type": "string",
                        },
                        "description": "The list of Reddit URLs obtained from `search_serpapi`."
                    }
                },
                "required": ["user_instruction", 'urls']
            },
            "strict": False
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_serpapi",
            "description": """Performs a Google search, optionally filtered by site (e.g., 'reddit.com'). Returns ONLY a list of URLs and titles. Use this as the *first step* to find URLs for specific sites (like Reddit) before using another tool (like `reddit_agent`) to process them.""",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to look for",
                    },
                    "site": {
                        "type": "string",
                        "description": "Optional: Specific website to search (e.g., 'reddit.com'). Use this when the user asks for info from a specific site."
                    }
                },
                "required": ["query"]
            },
            "strict": False
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_perplexity",
            "description": """Performs a web search using Perplexity API and returns a summarized answer with citations. Use for general questions needing a direct, summarized answer. Do NOT use this if the primary goal is to scrape specific sites like Reddit (use `search_serpapi` -> `reddit_agent` for that).""",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query for Perplexity."
                    }
                },
                "required": ["query"]
            },
            "strict": False
        }
    }
]

# Update the AVAILABLE_FUNCTIONS to match:
AVAILABLE_FUNCTIONS = {
    "search_serpapi": search_serpapi,
    "reddit_agent": reddit_agent,
    "search_perplexity": search_perplexity  # Add the new function mapping
}


if __name__ == "__main__":
    if len(sys.argv) > 1:
        instruction = " ".join(sys.argv[1:])  # Join all arguments as the instruction
        print(f"Instruction received from command line: '{instruction}'")
        run_agent_loop(instruction)
    else:
        # Fallback to input if no arguments provided
        instruction = input("Enter your instruction for the agent: ")
        if instruction:
            run_agent_loop(instruction)
        else:
            print("No instruction provided.")