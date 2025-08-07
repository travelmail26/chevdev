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
MODEL = "gpt-4o"

# google gemini key
gemini_api_key = os.environ['GEMINI_KEY_PH']
gemini_model = 'gemini-2.0-flash-thinking-exp-1219'

MAX_INTERACTIONS = 5  # Increased slightly to allow for multi-step calls

system_instrucition = """ You are a helpful research assistant designed to answer user queries comprehensively using available tools.

Your Goal: You are an experimental tool that povides the best possible answer by combining information from different
sources when necessary and to explain your thought process between each step. You will give information but also diagnose your process to the user

Available Tools:
- `search_perplexity`: Use this for direct, summarized answers to general questions, explanations, or topics. It provides a concise summary with citations directly. Ideal when the user wants a quick overview or factual answer.
- `search_serpapi`: Use this specifically to find relevant URLs from a web search, especially when targeting a specific site like 'reddit.com'. It returns ONLY a list of URLs and titles, not the content. This is the FIRST step when you need to gather specific discussions or opinions (e.g., from Reddit).
- `reddit_agent`: Use this ONLY AFTER using `search_serpapi` to get a list of Reddit URLs. Pass the user's original query context and the list of Reddit URLs to this tool to scrape and summarize the discussions found in those specific Reddit threads.

Workflow Strategy:
-- Analyze the user's full request. Do they want a general summary, specific opinions from a site (like Reddit), or both?
-- If the user asks for opinions, discussions, or experiences (especially mentioning Reddit), FIRST use `search_serpapi` with the query and `site='reddit.com'`.
-- **CRITICAL:** If `search_serpapi` was just called with `site='reddit.com'`, your **immediate next action** MUST be to call the `reddit_agent` tool.
-- **DO NOT** stop to explain or filter the URLs from `search_serpapi`.
-- **ALWAYS** pass the **entire** list of URLs returned by `search_serpapi` (every single URL) and the original user query context to the `reddit_agent` tool. The `reddit_agent` tool itself will handle relevance analysis.
-- If the user asks for a general explanation or summary *in addition* to specific site information, you can use `search_perplexity` for the general part AND the `search_serpapi` -> `reddit_agent` flow for the specific site part. You can call multiple tools before responding, but the `search_serpapi` -> `reddit_agent` sequence for Reddit must be followed strictly.
-- If the user *only* asks for a general explanation or summary, `search_perplexity` is likely sufficient on its own. **When using `search_perplexity`, you MUST pass the user's query exactly as provided (verbatim). Do not modify, interpret, or shorten it.**
-- After all tool calls are complete, synthesize the results from all the tools called into a single, comprehensive answer for the user.

**CRITICAL** Intructions on how to summarize information and present it to the user:
-- **ALWAYS** provide citations for any information retrieved from external sources, including Reddit discussions or websites. 
-- **NEVER** rely information without citation, if that information came from a function that searches external sources.
-- **ALWAYS** include the name and URL of the source right after each piece of information you provide.
-- **ALWAYS** include any direct quotes or verbatim pharases returned from a search result. 
--If you get back words in quotes, include it along with the citation as it was passed to you to the user in your final message.
--ALWAYS include all words within the quotes so the user knows exactly what was said and by whom.
-- **VERBATIM QUOTE PRESERVATION REQUIREMENT**: When search_perplexity returns content that contains quotes in this format: ("quoted text" — URL), you MUST preserve these quotes EXACTLY as they appear, without any modifications, paraphrasing, or trimming. These are direct quotes from sources and must be included verbatim in your response.

-- **DO NOT REWRITE QUOTES**: If the search_perplexity result contains text in quotation marks with a citation, present those exact quotes in your response. For example, if you receive: ("whip the mascarpone cheese on medium-high speed until smooth" — https://example.com), you must include this exact quote with its citation in your response.

-- NEVER paraphrase a direct quote - always keep the exact wording that appears inside quotation marks.

-- The format of quotes should always be preserved as: ("quoted text" — source_url)


EXAMPLE OF **REQUIRED** QUOTE HANDLING:

If `search_perplexity` returns this point:
`Fold gently to maintain body: While folding in the whipped cream or mascarpone, do so "gently, with an eye to creating an even mix, but don't pursue total homogenization at the cost of the semifreddo's airy structure." Overmixing can actually make the texture dense in an unpleasant way, so stop folding as soon as the mixture is smooth and thick[1]("work gently, with an eye to creating an even mix, but don't pursue total homogenization at the cost of the semifreddo's airy structure" – https://www.seriouseats.com/honey-semifreddo-frozen-italian-dessert).`

Your summary **MUST** include the quote exactly like this:
`5. **Fold Gently**: When combining whipped elements, fold gently. Over-mixing can harm the texture ("work gently, with an eye to creating an even mix, but don't pursue total homogenization at the cost of the semifreddo's airy structure" – https://www.seriouseats.com/honey-semifreddo-frozen-italian-dessert).`

**DO NOT** DO THIS (BAD EXAMPLE - Quote is missing/paraphrased):
`5. **Fold Gently**: When combining whipped elements, fold gently to avoid over-mixing, as this maintains structure ([Serious Eats](https://www.seriouseats.com/honey-semifreddo-frozen-italian-dessert)).`

Notice, the good summary directly quoted the source and included the URL, while the bad summary did not. The good summary also included the name of the source, while the bad summary did not.   

When asked for Diagnostic Messages:
-- Before calling any tool, briefly explain which tool you are calling and why.
-- **After** receiving results from `reddit_agent` (or `search_perplexity` if Reddit wasn't involved), explain the findings before presenting the final synthesized answer.
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
                tool_choice="auto",
                temperature=0.2,  # Let OpenAI decide whether to use a tool or respond directly
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
                        if isinstance(function_response, dict):
                            function_response = json.dumps(function_response)  # Serialize to JSON string
                        else:
                            function_response = str(function_response)  # Convert to string if not a dict
                                            # print(f"Function Response in searchbot.py: {function_response}")
                        # *** Step 3: Append the function's *result* back to the history ***
                        messages.append(
                            {
                                "tool_call_id": tool_call.id,  # Crucial to match the request
                                "role": "tool",              # Role must be 'tool' for function results
                                "name": function_name,       # Name of the function that was called
                                "content": function_response  # The actual result from your Python function
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
            "description": """
            --Performs a web search using Perplexity API and returns a summarized answer with citations.
            --Use for general questions needing a direct, summarized answer based on the user's full request.
            --Do NOT use this if the primary goal is to scrape specific sites like Reddit (use `search_serpapi` -> `reddit_agent` for that).
             --**ULTRA-CRITICAL**: If the user asks a general question (like 'how do I do X?' or 'what is Y?'), you MUST pass the **entire, original user message/instruction** to this tool as the 'query' parameter, without any modification, summarization, or interpretation. Preserve the exact wording.""",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": """The **exact, verbatim, unmodified** user instruction/message that triggered this search. 
                        Example Scenario: User asks: 'I want to make a semifreddo that is thick and rich. how should I change the recipe?'
                        Correct 'query' value: 'I want to make a semifreddo that is thick and rich. how should I change the recipe?'
                        Incorrect 'query' value: 'how to make semifreddo thick and rich' 
                        Explanation: Pass the full user input, not a summarized version."""
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
    print("Starting interactive agent. Type 'exit' or 'quit' to end.")
    while True:
        try:
            instruction = input("\nEnter your instruction for the agent: ")
            if instruction.lower() in ["exit", "quit"]:
                print("Exiting agent.")
                break
            if instruction:
                run_agent_loop(instruction)
            else:
                print("No instruction provided. Please enter a query or type 'exit'.")
        except EOFError: # Handle Ctrl+D
            print("\nExiting agent.")
            break
        except KeyboardInterrupt: # Handle Ctrl+C
            print("\nExiting agent.")
            break