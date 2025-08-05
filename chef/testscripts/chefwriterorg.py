




# ... (other imports) ...
from testscripts.serpapirecipes import search_serpapi # Make sure this import exists
import logger
import requests

openai_api_key = os.environ['OPENAI_API_KEY']




class AIHandler:

    def _execute_search_serpapi(self, function_args):
        """Executes the serpapi search and returns the result string."""
        print("DEBUG: Executing tool search_serpapi")
        query = function_args.get('query')
        site = function_args.get('site')
        print(f"DEBUG: search_serpapi called with query: {query}, site: {site}")
        try:
            # Assuming search_serpapi returns the data needed
            result_data = search_serpapi(query, site) 
            # Convert result to string if it's not already
            return str(result_data) 
        except Exception as e:
            print(f"ERROR: executing search_serpapi: {e}")
            logger.error(f"ERROR: executing search_serpapi: {e}")
            # Return an error message string to be sent back to the LLM
            return f"Error executing search_serpapi: {e}" 



    def openai_request(self):
        print('DEBUG: openai_request triggered')
        # ... (rest of the setup: headers, tools list) ...

        MAX_TOOL_CALLS = 5 
        tool_calls_count = 0

        while tool_calls_count < MAX_TOOL_CALLS:
            # --- 1. Prepare API Data ---
            data = {
                'model': 'gpt-4o-mini',
                'messages': self.messages,
                'temperature': 0.5,
                'max_tokens': 4096,
                'stream': True, # Keep streaming enabled
                'tools': tools, # Send the full tool list every time
                'parallel_tool_calls': False
            }
            print(f"DEBUG: Making API call #{tool_calls_count + 1}")

            # --- 2. Make API Call ---
            try:
                response = requests.post(
                    'https://api.openai.com/v1/chat/completions',
                    headers=headers,
                    json=data,
                    stream=True)
                response.raise_for_status()
            except requests.RequestException as e:
                # Handle API call errors
                error_message = f"Error in OpenAI API request: {str(e)}"
                if hasattr(e, 'response') and e.response is not None:
                    error_message += f"\nStatus: {e.response.status_code}, Body: {e.response.text}"
                print(error_message)
                yield error_message # Yield error to the caller
                break # Exit the loop on API error

            # --- 3. Process Streaming Response ---
            # Accumulate response chunks to reconstruct the full assistant message
            # (including potential tool calls)
            
            full_response_content = ""
            tool_call_chunks = {} # To reconstruct tool calls {index: {id:.., type:.., function:{name:.., args:..}}}
            current_tool_call_index = None
            
            rull_response_content = ""


            # --- 4. Reconstruct Assistant Message & Append ---
            assistant_message = {"role": "assistant"}
            final_tool_calls = [tool_call_chunks[i] for i in sorted(tool_call_chunks.keys())]

            if final_tool_calls:
                assistant_message["tool_calls"] = final_tool_calls
                assistant_message["content"] = None # Per API spec
                print(f"DEBUG: Reconstructed tool calls: {final_tool_calls}")
            else:
                assistant_message["content"] = full_response_content
                
            # Only append if there's content OR tool calls
            if assistant_message.get('content') or assistant_message.get('tool_calls'):
                 self.messages.append(assistant_message)
                 print(f"DEBUG: Appended assistant message: {assistant_message}")


            # --- 5. Check for Tool Calls & Execute ---
            if final_tool_calls:
                tool_calls_count += 1
                
                # Prepare results to be added to messages
                tool_results_messages = []

                for tool_call in final_tool_calls:
                    function_name = tool_call['function']['name']
                    arguments = tool_call['function']['arguments']
                    tool_call_id = tool_call['id']
                    
                    try:
                        function_args = json.loads(arguments) if arguments else {}
                    except json.JSONDecodeError:
                         print(f"Error decoding arguments for {function_name}: {arguments}")
                         result_data = f"Error: Invalid JSON arguments received for {function_name}"
                         function_args = {} # Prevent further errors

                    # --- Call the dedicated execution function ---
                    result_data = ""
                    if function_name == 'search_serpapi':
                        result_data = self._execute_search_serpapi(function_args)

                    else:
                        print(f"Warning: Unknown function requested: {function_name}")
                        result_data = f"Error: Unknown function {function_name}"
                    # --------------------------------------------

                    # Append the tool result message for the *next* API call
                    tool_results_messages.append({
                        "role": "tool",
                        "content": result_data, # Result must be a string
                        "tool_call_id": tool_call_id
                    })
                
                # Add all tool results to the main message history
                self.messages.extend(tool_results_messages)
                print(f"DEBUG: Appended tool results: {tool_results_messages}")
                
                # Continue the loop to make the next API call
                continue 
            
            # --- 6. No Tool Calls -> Exit Loop ---
            else:
                print("DEBUG: No tool calls requested by assistant. Finishing.")
                # If we yielded content chunks earlier, we don't need to return/yield again
                # unless the final message had no content initially.
                if not full_response_content:
                     print("DEBUG: Assistant finished without content after tool calls.")
                     # Optionally yield a message here if needed
                break # Exit the while loop

        # --- End of While Loop ---
        if tool_calls_count >= MAX_TOOL_CALLS:
            print("Warning: Reached maximum tool call limit.")
            yield "Reached maximum tool call limit." # Or return






tools = [
        
            #serpapi google search
            {
            "type": "function",
            "function": {
                "name": "search_serpapi",
                "description": "Triggered upon one of a few conditions. Any condition will trigger this function \
                One, the user says 'google search' or mentions 'search the google'. \
                Two, will specify a specific website, such as reddit or linkedin. \
                for instance, if the user writes 'google search reddit for cookie recipes', \
                    fill in the site parameter with 'reddit.com' and the query with verbatim 'cookie recipes' ",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "site": {
                                "type": "string",
                                "description": "Specific site to search"
                            },
                            "query": {
                                "type": "string",
                                "description": "verbatim search query, usually specified after 'for'"
                            }
                        },
                        "required": ["query"],
                        "additionalProperties": False
                    },
                    "strict": False
                }
        }
]
