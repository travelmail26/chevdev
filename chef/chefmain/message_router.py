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

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MessageRouter:
    def __init__(self, openai_api_key=None):
        """Initialize the MessageRouter with API key"""
        self.openai_api_key = openai_api_key or os.environ.get('OPENAI_API_KEY')
        if not self.openai_api_key:
            # Example before/after: missing key -> OpenAI calls fail; key set -> responses stream
            logging.warning("OPENAI_API_KEY is not set; responses will fail.")

        # Before: instructions pulled from a helper and combined elsewhere.
        # After example: paste paths below and the function will join them in order.
        self.combined_instructions = self.load_instructions()

    def load_instructions(self):
        """Load and join instruction files listed below (edit manually)."""
        base_dir = os.path.dirname(os.path.abspath(__file__))
        instruction_paths = [
            # Before: implicit paths. After example: only this file is loaded; paste more rows to expand.
            os.path.join(base_dir, "utilities", "instructions", "instructions_base.txt"),
        ]

        collected = []
        for path in instruction_paths:
            try:
                with open(path, 'r') as handle:
                    collected.append(handle.read().strip())
            except Exception as exc:
                logging.warning(f"Could not read instruction file '{path}': {exc}")
        return "\n\n".join(collected)
    
    def route_message(self, messages=None, message_object=None):
        """Route a message from a user to OpenAI, persist history, and return the response.

        Tool calling removed:
        - Before: sent `tools` + `tool_choice=auto`, and sometimes did a 2nd OpenAI call.
        - After: single OpenAI call with no tools; response is stored in message history.
        
        Args:
            messages: Optional list of message dictionaries for the conversation history
            message_object: Optional dictionary containing user_message and other data
        """
        user_id = str(message_object.get("user_id", "unknown")) if message_object else "unknown"
        logging.info(f"route_message start: user_id={user_id}, has_message_object={bool(message_object)}")
        logging.debug(f"DEBUG: route_message called with messages={messages}, message_object={message_object}")
        
        if messages is None:
            messages = []
        
        # Ensure system instructions are present at the start of the messages list
        system_instruction = {"role": "system", "content": self.combined_instructions}
    
        
        # Extract user message from message_object if provided
        full_message_object = None

        if message_object and "user_message" in message_object:
            user_message = message_object["user_message"]
            full_message_object = message_history_process(message_object, {"role": "user", "content": user_message})
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
        
        payload = {
            # CRITICAL: keep latest GPT-5 nano model (do not downgrade).
            'model': 'gpt-5-nano-2025-08-07',
            'messages': messages,
            # Fixed: gpt-5-nano expects default temperature (keep 1.0).
            'temperature': 1.0,
        }

        try:
            # Streaming (docs-style) via OpenAI SDK Responses API.
            # Before: manual `requests.post(..., stream=True)` parsing.
            # After example: `for event in stream: ...` (same as docs).
            from openai import OpenAI

            client = OpenAI(api_key=self.openai_api_key)
            stream = client.responses.create(
                model=payload["model"],
                input=payload["messages"],
                stream=True,
            )

            assistant_content = ""
            buffer_text = ""
            buffer_flush_chars = 200  # Send partial output every ~800 chars.

            for event in stream:
                # We only care about text deltas.
                # Example before/after:
                # - Before: parsed `choices[0].delta.content`.
                # - After: capture `response.output_text.delta` events.
                if getattr(event, "type", None) != "response.output_text.delta":
                    continue
                chunk = getattr(event, "delta", None)
                if not chunk:
                    continue

                assistant_content += chunk
                buffer_text += chunk

                if message_object and len(buffer_text) >= buffer_flush_chars:
                    partial = message_object.copy()
                    partial["user_message"] = buffer_text
                    process_message_object(partial)
                    buffer_text = ""

                if message_object and buffer_text.strip():
                    partial = message_object.copy()
                    partial["user_message"] = buffer_text
                    process_message_object(partial)

            # --- Append assistant response to user history ---
            if message_object:
                message_history_process(message_object, {"role": "assistant", "content": assistant_content})

            # Example before/after: empty response -> troubleshoot logs; non-empty -> user sees reply
            logging.info(f"route_message end: user_id={user_id}, response_chars={len(assistant_content)}")
            return assistant_content
        except requests.HTTPError as http_err:
            status = getattr(getattr(http_err, "response", None), "status_code", "unknown")
            body = getattr(getattr(http_err, "response", None), "text", str(http_err))
            logging.error(f"HTTP Error {status}: {body}")
            logging.error(f"Request payload: {payload}")
            return f"HTTP Error {status}: {body}"
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
