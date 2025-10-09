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
from perplexity import search_perplexity
#from testscripts.serpapirecipes import search_serpapi
from chef.testscripts.advanced_recipe_reasoning import advanced_recipe_reasoning
from utilities.sheetscall import sheets_call, task_create, fetch_preferences, fetch_recipes, update_task
from utilities.firestore_chef import firestore_get_docs_by_date_range
from chef.testscripts.message_user import process_message_object
from utilities.history_messages import message_history_process, get_full_history_message_object
from utilities.openai_agent_no_tool import call_openai_no_tool

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MessageRouter:
    def __init__(self, openai_api_key=None):
        """Initialize the MessageRouter with API key"""
        self.openai_api_key = openai_api_key or os.environ.get('OPENAI_API_KEY')
        self.handlers = {}  # Store AIHandler instances by user_id
        self.base_instructions = self._load_base_instructions()
        
        # Restore tool_map definition
        self.tool_map = {
            "search_perplexity": search_perplexity,
            "search_serpapi": search_perplexity,  # Use perplexity as fallback for serpapi
            "firestore_get_docs_by_date_range": firestore_get_docs_by_date_range,
            "sheets_call": sheets_call,
            "task_create": task_create,
            "update_task": update_task,
            "fetch_preferences": fetch_preferences,
            "fetch_recipes": fetch_recipes,
            "advanced_recipe_reasoning": lambda conversation_history=None, openai_api_key=None: advanced_recipe_reasoning(
                conversation_history=conversation_history,
                openai_api_key=openai_api_key or self.openai_api_key
            ),
            "answer_general_question": lambda query="", openai_api_key=None: call_openai_no_tool(
                {"messages": [
                    {"role": "system", "content": "You are a cooking assistant with specialized capabilities. Be explicit about what you can do:\n\nIf the user mentions recipes AND wants to 'explore', 'experiment', 'make simultaneously', 'at the same time', or optimize workflows, say: 'I can help you with advanced recipe experimentation and optimization. This involves analyzing constraints, identifying overlapping steps, and creating efficient workflows. Would you like me to engage my advanced recipe reasoning to design an optimized experimental approach?'\n\nOtherwise, provide brief helpful responses with ONE sentence and ONE follow-up question."},
                    {"role": "user", "content": query}
                ]},
                openai_api_key=openai_api_key
            )
        }
        if not self.openai_api_key:
            logging.error("OpenAI API key is missing!")
    
    def _load_base_instructions(self):
        """Load the base instructions from the instructions file"""
        try:
            base_path = os.path.dirname(__file__)
            instructions_path = os.path.join(base_path, 'utilities/instructions/instructions_base.txt')
            with open(instructions_path, 'r') as file:
                return "=== BASE DEFAULT INSTRUCTIONS ===\n" + file.read()
        except Exception as e:
            print(f"ERROR loading base instructions: {e}")
            return "You are a helpful culinary assistant."
    

    
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

                # Special handling for Advanced Recipe Reasoning - pass conversation history directly
                if function_name == "advanced_recipe_reasoning" and user_id:
                    print(f"**DEBUG: Advanced Recipe Reasoning will receive conversation history for user_id: {user_id}**")
                    history_obj = get_full_history_message_object(str(user_id))
                    all_messages = history_obj.get("messages", [])
                    
                    # Filter messages to only include those with valid content
                    valid_messages = []
                    for msg in all_messages:
                        if (msg.get("content") is not None and 
                            msg.get("content") != "" and 
                            msg.get("role") in ["user", "assistant"]):
                            valid_messages.append({"role": msg["role"], "content": msg["content"]})
                    
                    print(f"**DEBUG: Conversation history loaded: {len(valid_messages)} messages**")
                    # Pass conversation history directly to the function and remove query parameter
                    function_args.clear()  # Remove all existing args including 'query'
                    function_args["conversation_history"] = valid_messages
                    print(f"**DEBUG: Advanced Recipe Reasoning will receive {len(valid_messages)} messages directly**")
                
                
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
        logging.debug(f"DEBUG: route_message called with messages={messages}, message_object={message_object}")
        
        if messages is None:
            messages = []
        
        # Ensure system instructions are present at the start of the messages list
        system_instruction = {"role": "system", "content": """You MUST ALWAYS select and call EXACTLY ONE tool for EVERY user message (never zero, never more than one). Do not answer directly without a tool.

STRICT TOOL DECISIONS:
1. advanced_recipe_reasoning → Use ONLY when BOTH are true:
   a. User is exploring / experimenting / modifying / optimizing / overlapping / batching / comparing recipes (keywords: explore, experiment, variation, modify, substitute, swap, compare, simultaneous, at the same time, concurrently, parallel, overlap, optimize, workflow, plan, schedule, timing, batch) AND
   b. Recent conversation (last ~10 messages) already contains recipe data, prior search results, ingredients, steps, or constraints.

2. search_perplexity or search_serpapi → Use when the user explicitly wants NEW info or to look up / find / search / pull data not yet in conversation. If the user explicitly mentions "perplexity", use search_perplexity.

3. answer_general_question → Use ONLY for greetings, small talk, acknowledgments, off-topic, or simple clarifying/general cooking questions WITHOUT experimentation intent and WITHOUT sufficient recipe context for (1).

PRIORITY: If (1) and (2) both could apply, prefer advanced_recipe_reasoning unless user explicitly asks to search. Never choose answer_general_question if (1) conditions are satisfied.

CONTINUITY (PROMPT-ONLY): If the last assistant tool output was from advanced_recipe_reasoning and the user reply is short and appears to supply a constraint (time, equipment, quantity, dietary, confirmation) without requesting a search, continue with advanced_recipe_reasoning to gather remaining constraints or produce the plan.

OUTPUT: Provide only the tool call (model-internal). Never fabricate tool names. Exactly one tool per turn.
"""}
        logging.debug(f"DEBUG: messages type: {type(messages)}, length: {len(messages) if hasattr(messages, '__len__') else 'no length'}")
        logging.debug(f"DEBUG: messages content: {messages}")
        
        # Extract user message from message_object if provided
        if message_object and "user_message" in message_object:
            user_message = message_object["user_message"]
            logging.debug(f"Processing message_object: {message_object}")
            full_message_object = message_history_process(message_object, {"role": "user", "content": user_message})  # Process the message object
            logging.debug(f"Returned from message_history_process: {full_message_object}")
            # Use the full message history from the updated object
            messages = full_message_object.get("messages", [])
            logging.debug(f"Added user message from message_object: {user_message}")
            logging.debug(f"Messages structure: {type(messages)}, length: {len(messages)}")
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
        if not messages or len(messages) == 0 or not isinstance(messages[0], dict) or messages[0].get("role") != "system":
            messages.insert(0, system_instruction)
        
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
                    "name": "advanced_recipe_reasoning",
                    "description": "Use ONLY when ALL of these conditions are met: 1) User is asking about recipe experimentation, variations, modifications, or cooking techniques AND 2) Recent conversation (last 5-10 messages) contains recipe data from previous searches or recipe discussions. Keywords: 'explore', 'experiment', 'variation', 'what if', 'try different', 'modify recipe', ingredient substitutions within recipe context. Do NOT use for general cooking questions without existing recipe context.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "User's recipe experimentation question"
                            }
                        },
                        "required": ["query"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "answer_general_question",
                    "description": "DEFAULT TOOL. Use when: 1) No recipe context exists in recent conversation,"
                    " OR 2) User asks general cooking questions without specific recipe experimentation intent, OR "
                    "3) Greetings, acknowledgments, or off-topic questions. DO NOT use if user wants to 'explore't"
                    ", "
                    "'experiment', or 'try different' recipes when recipe data exists in conversation."
                    "NEVER use this tool at the same time as another tool",
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
            'model': 'gpt-5-nano-2025-08-07',
            'messages': messages,
            'temperature': 1.0,  # Fixed: gpt-5-nano only supports default temperature of 1.0
            'tools': tools,
            'tool_choice': 'required',
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
                
                # Add conditional system instruction based on tool type - respect tool's intended behavior
                function_name = tool_call['function']['name']
                if function_name == "answer_general_question":
                    # For general questions, keep responses brief and natural
                    system_content = "Present the tool's response exactly as given. Keep it brief and natural."
                elif function_name == "advanced_recipe_reasoning":
                    # For advanced recipe reasoning, respect the tool's escalation logic
                    system_content = "CRITICAL: You are a transparent message relay. Output ONLY the exact text from the tool response, nothing else. Do not add context, explanations, elaborations, or your own steps. Do not interpret or expand. If the tool asks a question, output only that question. If the tool provides a plan, output only that plan. Be a perfect pass-through."
                else:
                    # For search tools (perplexity, serpapi, etc.), present full detailed responses
                    system_content = "Present the tool's response fully and completely. Include all details, formatting, and citations provided."
                
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

