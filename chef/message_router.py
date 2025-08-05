import json
import os
import sys
import logging
import requests

# Import necessary modules for tool functions
sys.path.append('/workspaces/chevdev')
from perplexity import search_perplexity
from chef.testscripts.serpapirecipes import search_serpapi
from chef.utilities.sheetscall import sheets_call, task_create, fetch_preferences, fetch_recipes, update_task
from chef.firestore_chef import firestore_get_docs_by_date_range
from chef.message_user import process_message_object
from chef.utilities.history_messages import message_history_process, get_full_history_message_object
from testscripts.openai_agent_no_tool import call_openai_no_tool

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MessageRouter:
    def __init__(self, openai_api_key=None):
        """Initialize the MessageRouter with API key"""
        self.openai_api_key = openai_api_key or os.environ.get('OPENAI_API_KEY')
        self.handlers = {}  # Store AIHandler instances by user_id
        self.tool_map = {
            "search_perplexity": search_perplexity,
            "search_serpapi": search_serpapi,
            "firestore_get_docs_by_date_range": firestore_get_docs_by_date_range,
            "sheets_call": sheets_call,
            "task_create": task_create,
            "update_task": update_task,
            "fetch_preferences": fetch_preferences,
            "fetch_recipes": fetch_recipes,
            "call_openai_no_tool": lambda query="", openai_api_key=None: call_openai_no_tool(
                {"messages": [

                    {"role": "user", "content": query}
                ]},
                openai_api_key=openai_api_key
            )
        }
        
        if not self.openai_api_key:
            logging.error("OpenAI API key is missing!")
    

    
    def execute_tool(self, tool_call, user_id=None):
        """Execute a tool call and return the result as a string"""
        if not tool_call:
            return "Error: No tool call provided"
        
        function_name = tool_call['function']['name']
        arguments_str = tool_call['function']['arguments']
        print(f"DIAGNOSIS: TOOL CALL OBJECT: {tool_call}")

        logging.info(f"Executing tool: {function_name}")
        
        if function_name in self.tool_map:
            try:
                # Parse arguments
                logging.debug(f"Attempting to parse arguments: {arguments_str}")
                function_args = json.loads(arguments_str) if arguments_str else {}
                logging.debug(f"Parsed arguments: {function_args}")
                
                # Get the function from the map
                tool_function = self.tool_map[function_name]
                logging.debug(f"Found tool function: {tool_function.__name__}")
                
                # Special handling for Perplexity - include last 5 messages as context
                if function_name == "search_perplexity" and user_id:
                    history_obj = get_full_history_message_object(str(user_id))
                    all_messages = history_obj.get("messages", [])
                    
                    # Filter messages to only include those with valid content for Perplexity
                    valid_messages = []
                    for msg in all_messages:
                        # Only include messages that have non-empty content
                        if (msg.get("content") is not None and 
                            msg.get("content") != "" and 
                            msg.get("role") in ["user", "assistant"]):
                            valid_messages.append({"role": msg["role"], "content": msg["content"]})
                    
                    # Get last 5 valid messages for context
                    context_messages = valid_messages[-5:] if len(valid_messages) >= 5 else valid_messages
                    
                    if context_messages:
                        # Keep the user's query but inject it with conversation context as a JSON string
                        user_query = function_args.get("query", "")
                        
                        # Convert context to JSON string and combine with current query
                        context_json = json.dumps(context_messages, indent=2)
                        combined_query = f"Current query: {user_query}\n\nConversation context (JSON):\n{context_json}"
                        
                        function_args["query"] = combined_query
                        print(f"**DEBUG: Perplexity will receive context as JSON string with {len(context_messages)} messages**")
                    else:
                        # If no valid context, just send the current query
                        print(f"**DEBUG: No valid context found, sending current query only**")
                
                # === DIAGNOSIS START ===
                #print(f"**DIAGNOSIS: About to call {function_name} with args: {function_args}**")
                # === DIAGNOSIS END ===

                # === SIMPLER DIAGNOSIS: Show function and args START ===
                #print(f"**DIAGNOSIS: Attempting call: {tool_function.__name__} with args: {function_args}**")
                # === SIMPLER DIAGNOSIS: Show function and args END ===
                
                # Call the function generically
                result = tool_function(**function_args) # Use generic unpacking for all tools
                
                # === DIAGNOSIS START ===
                print(f"**DIAGNOSIS: Call to {function_name} completed. Result type: {type(result)}**")
                # === DIAGNOSIS END ===

                # Special handling for generators (like perplexitycall)
                if hasattr(result, '__iter__') and hasattr(result, '__next__'):
                    result = list(result)  # Convert generator to list
                
                logging.info(f"Tool {function_name} executed successfully")
                # Convert result to string if it's not already
                if not isinstance(result, str):
                    if isinstance(result, dict) and 'content' in result:
                        # Extract just the content text from dictionaries
                        result = result['content']
                    else:
                        # Use JSON serialization for other objects, not str()
                        result = json.dumps(result)
                return result
            except json.JSONDecodeError:
                error = f"Failed to parse arguments: {arguments_str}"
                logging.error(error)
                return error
            except Exception as e:
                error = f"Error executing {function_name}: {str(e)}"
                logging.error(f"{error}", exc_info=True)
                return error
        else:
            error = f"Unknown tool: {function_name}"
            logging.warning(error)
            return error
    
    def route_message(self, messages=None, message_object=None):
        """Route a message from a user to their AIHandler, execute tools if needed, and return the response
        
        Args:
            messages: Optional list of message dictionaries for the conversation history
            message_object: Optional dictionary containing user_message and other data
        """
        if messages is None:
            messages = []
        
        # Ensure system instructions are present at the start of the messages list
        system_instruction = {"role": "system", "content": """You are an assistant that MUST ALWAYS call a tool for EVERY user message.
                              For general conversation, greetings, or simple questions, use the call_openai_no_tool tool.
                              When calling search_perplexity, pass only the user's current search query as a string - do NOT construct message arrays.
                              NEVER pass your own response as the query."""}
        if not messages or messages[0].get("role") != "system":
            messages.insert(0, system_instruction)

        # Extract user message from message_object if provided
        if message_object and "user_message" in message_object:
            user_message = message_object["user_message"]
            full_message_object = message_history_process(message_object, {"role": "user", "content": user_message})  # Process the message object
            # Use the full message history from the updated object
            messages = full_message_object.get("messages", [])
            logging.debug(f"Added user message from message_object: {user_message}")
        
        # Clean messages before sending to OpenAI: remove any with content None, but preserve those with tool_calls
        messages = [m for m in messages if m.get('content') is not None or m.get('tool_calls') is not None]
        
        # Make the OpenAI API call
        headers = {
            'Authorization': f'Bearer {self.openai_api_key}',
            'Content-Type': 'application/json'
        }
        
        # This is a simplified version of the tool definitions
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "search_perplexity",
                    "description": "Search the web for information with conversation context. This tool automatically includes the last 5 messages from the conversation history to provide contextual search results. Use this when the user's question relates to previous conversation topics or when follow-up questions need context.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The current user's question or search query - conversation context will be automatically added"
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_serpapi",
                    "description": "Search for information using SerpAPI",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query"
                            },
                            "site": {
                                "type": "string",
                                "description": "Specific site to search"
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "call_openai_no_tool",
                    "description": "DEFAULT TOOL for all general conversation, greetings, questions, and anything that doesn't specifically require other specialized tools. \
                        This tool MUST be used whenever no other specialized tool is needed. \
                            If you're at all uncertain which tool to use, use this one. \
                                The object will always been a string from the user. It is the user's message",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The message from the user"
                            }
                        },
                        "required": ["query"]
                    }
                }
            }
        ]
        #print(f"**DEBUG: message passed to openai message_router: {messages}**")
        
        payload = {
            'model': 'gpt-4o-mini-2024-07-18',
            'messages': messages,
            'temperature': 0.5,
            'tools': tools,
            'tool_choice': 'required'  # Force the model to always use a tool
        }
        
        print(f"**DEBUG: Payload sent to OpenAI: {payload}**")

        try:
            # Make the API call
            response = requests.post(
                'https://api.openai.com/v1/chat/completions',
                headers=headers,
                json=payload,
                timeout=120
            )
            response.raise_for_status()
            response_data = response.json()
            print(f"**DEBUG: OpenAI response: {response_data}**")
            
            # Get the assistant's response
            assistant_message = response_data['choices'][0]['message']
            
            # Check if the assistant wants to use a tool
            if 'tool_calls' in assistant_message and assistant_message['tool_calls']:
                tool_call = assistant_message['tool_calls'][0] # Assuming one tool call

                # Prepare the assistant's message (that includes the tool_call) for history and the next API call
                assistant_response_with_tool_call = {"role": "assistant"}
                raw_content = assistant_message.get("content")
                if raw_content is not None: # Include content if it's present (even if empty string)
                    assistant_response_with_tool_call["content"] = raw_content
                assistant_response_with_tool_call["tool_calls"] = assistant_message["tool_calls"]

                if message_object:
                    message_history_process(message_object, assistant_response_with_tool_call)
                
                # Execute the tool
                user_id = message_object.get('user_id') if message_object else None
                result = self.execute_tool(tool_call, user_id)
                
                tool_response_message = {
                    "role": "tool",
                    "content": str(result), # Ensure result is a string
                    "tool_call_id": tool_call['id']
                }
                
                if message_object:
                    message_history_process(message_object, tool_response_message)

                # Construct messages for the second API call
                messages_for_second_call = []
                if message_object:
                    # Reload the complete history, which now includes the assistant's tool call and the tool response
                    current_full_object = message_history_process(message_object) # Re-reads from file
                    messages_for_second_call = current_full_object.get("messages", [])
                else:
                    # 'messages' is the history used for the FIRST API call.
                    # Append the assistant's response (with tool_calls) and the tool message.
                    messages_for_second_call = messages + [assistant_response_with_tool_call, tool_response_message]
                
                payload2 = {
                    'model': 'gpt-4o-mini-2024-07-18',
                    'messages': messages_for_second_call,
                    'temperature': 0.5,
                    # No 'tools' or 'tool_choice' for the second call
                }
                
                print(f"**DEBUG: Second payload to OpenAI: {payload2}**")
                response2 = requests.post(
                    'https://api.openai.com/v1/chat/completions',
                    
                    headers=headers,
                    json=payload2,
                    timeout=120
                )
                response2.raise_for_status()
                response_data2 = response2.json()
                print(f"**DEBUG: OpenAI second response: {response_data2}**")
                final_assistant_message = response_data2['choices'][0]['message']
                if message_object:
                    message_history_process(message_object, {"role": "assistant", "content": final_assistant_message.get('content', '')})
                
                # Send response to user
                if message_object:
                    response_message_object = message_object.copy()
                    response_message_object['user_message'] = final_assistant_message.get('content', '')
                    process_message_object(response_message_object)
                
                return final_assistant_message.get('content', '')
            else:
                # --- Append assistant response to user history ---
                if message_object:
                    message_history_process(message_object, {"role": "assistant", "content": assistant_message.get('content', '')})
                
                # Send response to user
                if message_object:
                    response_message_object = message_object.copy()
                    response_message_object['user_message'] = assistant_message.get('content', '')
                    process_message_object(response_message_object)
                
                # --- End append ---
                return assistant_message.get('content', '')
        except requests.HTTPError as http_err:
            logging.error(f"HTTP Error {response.status_code}: {response.text}")
            logging.error(f"Request payload: {payload}")
            return f"HTTP Error {response.status_code}: {response.text}"
        except Exception as e:
            logging.error(f"Error in openai API call in message_router.py: {str(e)}", exc_info=True)
            return f"Error processing your message: {str(e)}"
    
# Simple command-line interface for testing
if __name__ == "__main__":
    router = MessageRouter()
    messages_history = [] # Maintain conversation history
    
    print("Message Router Initialized. Enter messages (or 'quit'):")
    while True:
        user_input = input("You: ")
        if user_input.lower() == 'quit':
            break
        
        # Add user message to history
        messages_history.append({"role": "user", "content": user_input})
        
        # Pass the entire history to route_message
        response = router.route_message(messages_history) 
        
        # Note: The route_message function modifies the messages_history list in place
        # by appending assistant responses and tool results.
        
        print(f"AI: {response}")




