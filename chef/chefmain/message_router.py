import json
import os
import sys
import logging
import requests
try:
    from dotenv import load_dotenv
    # Load default .env
    load_dotenv()
    # Optionally load .env.local for per-developer overrides (gitignored)
    if os.path.exists(os.path.join(os.getcwd(), ".env.local")):
        load_dotenv(dotenv_path=os.path.join(os.getcwd(), ".env.local"), override=False)
except Exception:
    pass

# Import necessary modules for tool functions
sys.path.append('/workspaces/chevdev')
from message_user import process_message_object
from utilities.history_messages import message_history_process, archive_message_history
from utilities.openai_agent_no_tool import call_openai_no_tool

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MessageRouter:
    def __init__(self, openai_api_key=None):
        """Initialize the MessageRouter with API key"""
        self.openai_api_key = openai_api_key or os.environ.get('OPENAI_API_KEY')
        self.handlers = {}  # Store AIHandler instances by user_id
        self.tool_map = {}  # Tools optional; keep empty until one is added

        # Before: instructions pulled from a helper and combined elsewhere.
        # After example: paste paths below and the function will join them in order.
        self.combined_instructions = self.load_instructions()

    def load_instructions(self):
        """Load and join instruction files listed below (edit manually)."""
        instruction_paths = [
            # Before: implicit paths. After example: only this file is loaded; paste more rows to expand.
            "/workspaces/chevdev/chef/chefmain/utilities/instructions/instructions_base.txt",
        ]

        collected = []
        for path in instruction_paths:
            try:
                with open(path, 'r') as handle:
                    collected.append(handle.read().strip())
            except Exception as exc:
                logging.warning(f"Could not read instruction file '{path}': {exc}")
        return "\n\n".join(collected)


    
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

                # Special handling for generator-style tool outputs
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
        logging.debug(f"DEBUG: route_message called with messages={messages}, message_object={message_object}")
        
        if messages is None:
            messages = []
        
        # Ensure system instructions are present at the start of the messages list
        system_instruction = {"role": "system", "content": self.combined_instructions}
    
        
        # Extract user message from message_object if provided
        full_message_object = None

        if message_object and "user_message" in message_object:
            user_message = message_object["user_message"]
            full_message_object = message_history_process(message_object, {"role": "user", "content": user_message})  # Process the message object
            # Use the full message history from the updated object
            messages = full_message_object.get("messages", [])
            if messages:
                logging.debug(f"First message: {messages[0]}")
                logging.debug(f"Last message: {messages[-1]}")
            else:
                logging.debug("Messages list is empty!")
                
        # Ensure messages is a proper list
        if not isinstance(messages, list):
            logging.debug(f"DEBUG: Converting messages from {type(messages)} to list")
            messages = []
        
        # Ensure system instruction is present at the start AFTER loading conversation history
        instructions_applied = False

        if not messages or len(messages) == 0 or not isinstance(messages[0], dict) or messages[0].get("role") != "system":
            # Before: an empty history after /restart stayed empty. After example: we re-seed with the base prompt.
            messages.insert(0, system_instruction)
            instructions_applied = True
        elif messages[0].get("content") in (None, ""):
            # Before: the stored system stub remained blank. After example: we refill it with the combined prompt.
            messages[0]["content"] = self.combined_instructions
            instructions_applied = True

        if instructions_applied and full_message_object and message_object:
            full_message_object["messages"] = messages
            user_identifier = str(message_object.get("user_id", "unknown"))
            archive_message_history(full_message_object, user_identifier)

        # Clean messages before sending to OpenAI: remove any with content None, but preserve those with tool_calls
        messages = [m for m in messages if m.get('content') is not None or m.get('tool_calls') is not None]
        
        # Make the OpenAI API call
        headers = {
            'Authorization': f'Bearer {self.openai_api_key}',
            'Content-Type': 'application/json'
        }
        
        # Tool definitions trimmed to the single conversational response helper
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "answer_general_question",
                    "description": "Generate a short, conversational answer to the user's question.",
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
            'model': 'gpt-5-2025-08-07',
            'messages': messages,
            'temperature': 1.0,  # Fixed: gpt-5-nano only supports default temperature of 1.0
            'tools': tools,
            'tool_choice': 'auto',  # Tools remain optional; base instruction is loaded before any tool calls
            'parallel_tool_calls': False
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


            #IF TOOL CALLS
            
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
                
                # With only the general question tool available, keep the follow-up concise.
                function_name = tool_call['function']['name']
                system_content = "Present the tool's response exactly as given. Keep it brief and natural." if function_name == "answer_general_question" else "Present the tool's response exactly as given."
                
                if not messages_for_second_call or messages_for_second_call[0].get("role") != "system":
                    messages_for_second_call.insert(0, {"role": "system", "content": system_content})
                elif messages_for_second_call[0].get("content") == "":
                    # Replace empty system message with our instruction
                    messages_for_second_call[0] = {"role": "system", "content": system_content}

                payload2 = {
                    'model': 'gpt-5-nano-2025-08-07',
                    'messages': messages_for_second_call,
                    'temperature': 1,
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