import os
import json
import google.generativeai as genai # Use Gemini library
import traceback # Import traceback for detailed error printing

# --- Assume these imports work ---
try:
    from redditapi import search_reddit_with_url
    from serpapirecipes import search_serpapi
    print("Successfully imported 'search_reddit_with_url' and 'search_serpapi'.")
except ImportError as e:
    print(f"ERROR: Could not import local functions: {e}")
    print("Please ensure 'redditapi.py' and 'serpapirecipes.py' are in the Python path.")
    exit(1) # Exit if functions aren't available

# --- Configuration ---

# --- Use Gemini API Key ---
YOUR_GEMINI_API_KEY = os.environ['GEMINI_KEY_PH'] # <<< PUT YOUR KEY HERE

# --- Choose a Gemini Model ---
# *** IMPORTANT: Strongly recommend switching to a stable model first! ***
# GEMINI_MODEL = "gemini-1.5-pro-latest"  # <<< TRY THIS
# GEMINI_MODEL = "gemini-1.5-flash-latest" # <<< OR TRY THIS
GEMINI_MODEL = 'gemini-1.5-pro-latest' # <<< Your experimental model (Try stable if errors occur)


MAX_INTERACTIONS = 5

system_instruction = """You are a helpful research assistant.
You can search the web for information.
You will use function calls to retrieve information.
Sometimes you will call multiple functions and can choose to collect more information before messaging the user.
"""

# --- Gemini Tool Definition (Removing top-level "type": "object" based on specific traceback) ---
gemini_tools = [
    {
        "name": "search_serpapi",
        "description": """Performs a Google search with optional site-specific filtering.
        If a user specifies a site, fill in the appropriate parameters to search only that site. \
            For instance, if the user says reddit, fill the parameter with reddit.com""",
        "parameters": {
            # "type": "object",  # <<< REMOVED based on explicit ValueError traceback
            "properties": {
                "query": {
                    "type": "string", # Type definitions *within* properties are standard
                    "description": "The search query to look for",
                },
                "site": {
                    "type": "string",
                    "description": "Optional: Specific website to search (e.g., 'allrecipes.com', 'foodnetwork.com'). Leave empty for general web search."
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "search_reddit_with_url",
        "description": """Scrapes a Reddit URLs. It necessary to get comments and posts from Google search or URL \
            The function returns a list of dictionaries, each containing the post and its comments.""",
        "parameters": {
            # "type": "object",  # <<< REMOVED based on explicit ValueError traceback
            "properties": {
                "urls": {
                    "type": "string",
                    "description": "The full Reddit post URL and must only be a URL string",
                }
            },
            "required": ["urls"]
        }
    }
]


# --- Map Function Names to Actual Python Functions (Keep As Is) ---
AVAILABLE_FUNCTIONS = {
    "search_serpapi": search_serpapi,
    "search_reddit_with_url": search_reddit_with_url
}

# --- Helper Functions for History Translation (Keep As Is) ---

def convert_openai_to_gemini_history(openai_messages):
    gemini_history = []
    for msg in openai_messages:
        role = msg['role']
        content = msg.get('content')
        if role == 'system': continue
        elif role == 'user':
            gemini_history.append({'role': 'user', 'parts': [{'text': content or ""}]})
        elif role == 'assistant':
            tool_calls = msg.get('tool_calls')
            if tool_calls:
                gemini_parts = []
                for tc in tool_calls:
                    func = tc.get('function', {})
                    func_name = func.get('name')
                    func_args_str = func.get('arguments', '{}')
                    try: func_args = json.loads(func_args_str)
                    except json.JSONDecodeError: func_args = {}
                    if func_name: gemini_parts.append({'function_call': {'name': func_name, 'args': func_args}})
                if gemini_parts: gemini_history.append({'role': 'model', 'parts': gemini_parts})
            elif content: gemini_history.append({'role': 'model', 'parts': [{'text': content}]})
        elif role == 'tool':
            func_name = msg.get('name')
            if func_name: gemini_history.append({'role': 'function', 'parts': [{'function_response': {'name': func_name, 'response': {'content': content or ""}}}]})
    return gemini_history

def convert_gemini_to_openai_message(gemini_content_obj):
    openai_message = {'role': 'assistant', 'content': None, 'tool_calls': None}
    parts = gemini_content_obj.parts
    text_content = []
    tool_calls_list = []
    for i, part in enumerate(parts):
        if hasattr(part, 'function_call'):
            fc = part.function_call
            tool_call_id = f"call_{fc.name}_{i}_{os.urandom(4).hex()}"
            tool_calls_list.append({"id": tool_call_id, "type": "function", "function": {"name": fc.name, "arguments": json.dumps(dict(fc.args))}})
        elif hasattr(part, 'text'): text_content.append(part.text)
    if tool_calls_list: openai_message['tool_calls'] = tool_calls_list
    elif text_content: openai_message['content'] = "".join(text_content)
    return openai_message

# --- Main Agent Loop (Modified for Gemini API Calls - Keep As Is Structure) ---

def run_agent_loop(user_instruction: str):

    if YOUR_GEMINI_API_KEY == "PASTE_YOUR_GEMINI_API_KEY_HERE":
        print("\nERROR: Please replace 'PASTE_YOUR_GEMINI_API_KEY_HERE' with your actual Gemini API key.\n")
        return

    # --- Initialize Gemini ---
    try:
        print(f"--- Configuring Gemini (Key ending: ...{YOUR_GEMINI_API_KEY[-4:]}) ---")
        genai.configure(api_key=YOUR_GEMINI_API_KEY)

        print(f"--- Preparing to Initialize Gemini Model: {GEMINI_MODEL} ---")
        # Check if using experimental model and advise switching if errors occur
        if 'exp' in GEMINI_MODEL or 'thinking' in GEMINI_MODEL:
             print("--- NOTE: Using an experimental model. If initialization fails, try a stable model like 'gemini-1.5-pro-latest' or 'gemini-1.5-flash-latest'. ---")

        # Print the tools structure just before passing it
        print("--- Tool Schema Being Passed to Model ---")
        try:
            print(json.dumps(gemini_tools, indent=2))
        except Exception as json_e:
            print(f"Could not pretty-print tools schema: {json_e}")
            print(gemini_tools)
        print("----------------------------------------")

        # Initialize the model, passing the corrected tools schema
        model = genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            system_instruction=system_instruction,
            tools=gemini_tools
        )
        print(f"--- Gemini Model Initialized Successfully ---")

    except Exception as e:
        print("\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print(f"!!! Error during Gemini Initialization: {e} !!!")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n")
        print("--- Full Traceback ---")
        traceback.print_exc()
        print("----------------------\n")
        print("--- Debugging Suggestions ---")
        print("1. **TRY SWITCHING TO A STABLE MODEL:** Edit the script and change `GEMINI_MODEL` to `\"gemini-1.5-pro-latest\"` or `\"gemini-1.5-flash-latest\"`.")
        print("2. Ensure your 'google-generativeai' library is up-to-date: `pip install --upgrade google-generativeai`")
        print("3. Verify the 'gemini_tools' schema printed above matches documentation EXACTLY for the *specific model* and library version you are using.")
        print("---------------------------\n")
        return # Stop execution

    # --- Maintain Conversation History in OpenAI Format ---
    messages = [
        {"role": "user", "content": user_instruction}
    ]

    print(f"\nStarting agent loop with instruction: '{user_instruction}'")
    print(f"Max interactions set to: {MAX_INTERACTIONS}")

    for i in range(MAX_INTERACTIONS):
        print(f"\n--- Interaction {i + 1} ---")

        try:
            # --- Translate history and Send to Gemini ---
            gemini_request_history = convert_openai_to_gemini_history(messages)

            print("Sending request to Gemini...")
            response = model.generate_content(
                gemini_request_history,
                tool_config={'function_calling_config': 'AUTO'}
            )

            # --- Process Gemini Response ---
            if not response.candidates:
                 print("Error: Gemini response did not contain any candidates.")
                 if hasattr(response, 'prompt_feedback'): print(f"Prompt Feedback: {response.prompt_feedback}")
                 else: print("No prompt feedback available.")
                 break

            gemini_response_content = response.candidates[0].content

            # --- Translate Gemini response back to OpenAI message format ---
            openai_style_response_message = convert_gemini_to_openai_message(gemini_response_content)

            # Append the translated assistant response
            messages.append(openai_style_response_message)

            # Check if Gemini requested function calls
            tool_calls = openai_style_response_message.get('tool_calls')

            if tool_calls:
                print(f"Gemini requests calling functions: {[tc['function']['name'] for tc in tool_calls]}")

                # Call the requested functions and gather results
                for tool_call in tool_calls:
                    function_name = tool_call['function']['name']
                    tool_call_id = tool_call['id']
                    function_to_call = AVAILABLE_FUNCTIONS.get(function_name)

                    if not function_to_call:
                        print(f"  Error: Function '{function_name}' not found locally.")
                        messages.append({"tool_call_id": tool_call_id, "role": "tool", "name": function_name, "content": f"Error: Function '{function_name}' not found."})
                        continue

                    try:
                        function_args_str = tool_call['function']['arguments']
                        function_args = json.loads(function_args_str)
                        print(f"  Calling locally: {function_name} with args: {function_args}")
                        function_response = function_to_call(**function_args)
                        print(f"  Local function '{function_name}' executed.")
                        messages.append({"tool_call_id": tool_call_id, "role": "tool", "name": function_name, "content": str(function_response)})
                    except Exception as e:
                        print(f"  Error calling function {function_name} or processing its result: {e}")
                        messages.append({"tool_call_id": tool_call_id, "role": "tool", "name": function_name, "content": f"Error executing function {function_name}: {str(e)}"})

            else:
                # Gemini provided a direct text response
                final_response_text = openai_style_response_message.get('content')
                print(f"\n--- Final Response from Gemini ---")
                print(final_response_text if final_response_text else "(No text content received)")
                break # Exit the loop

        except Exception as e:
            print(f"\nAn error occurred during API call {i+1} or processing: {e}")
            print("--- Full Traceback ---")
            traceback.print_exc() # Print the detailed traceback
            print("----------------------\n")
            try:
                if 'response' in locals() and hasattr(response, 'prompt_feedback'):
                     print(f"Gemini Prompt Feedback: {response.prompt_feedback}")
            except Exception as inner_e:
                 print(f"Error accessing response details: {inner_e}")
            break # Exit loop on error

    else:
        # Max interactions reached
        print("\n--- Agent loop finished: Maximum interaction limit reached. ---")
        last_message = messages[-1] if messages else None
        if last_message:
             if last_message['role'] == 'assistant': print("Last message from assistant:", last_message.get('content', '(No text content)'))
             elif last_message['role'] == 'tool': print("Loop ended after processing tool result:", last_message.get('name'))
             else: print("Loop ended with last message role:", last_message.get('role'))
        else: print("Loop ended.")


# --- Script Entry Point (Keep As Is) ---
if __name__ == "__main__":

    instruction = input("Enter your instruction for the agent: ")
    if instruction: run_agent_loop(instruction)
    else: print("No instruction provided.")