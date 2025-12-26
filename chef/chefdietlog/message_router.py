import json
import os
import sys
import logging
import requests
import time
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
# Before example: sys.path hard-coded to /workspaces/chevdev.
# After example: sys.path uses the repo root so Cloud Run/Codespaces both work.
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.append(repo_root)
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
        else:
            # Example before/after: no key visibility -> unclear auth; now logs masked key suffix.
            logging.info(f"OPENAI_API_KEY loaded (suffix=...{self.openai_api_key[-4:]})")
        self.xai_api_key = os.environ.get("XAI_API_KEY")
        if not self.xai_api_key:
            # Example before/after: missing xAI key -> xAI calls fail; key set -> Grok responses.
            logging.warning("XAI_API_KEY is not set; xAI calls will fail.")

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
        
        xai_model = os.getenv("XAI_MODEL", "grok-4-1-fast-non-reasoning-latest")
        payload = {
            # Before: OpenAI GPT-5 nano model. After example: xAI Grok model for router test.
            "model": xai_model,
            "messages": messages,
            "max_tokens": 256,
            "temperature": 0.7,
        }

        try:
            # Before: OpenAI call timing was opaque; after example: log start/end with model + duration.
            openai_start = time.monotonic()
            message_count = len(payload["messages"])
            last_user_content = None
            for entry in reversed(payload["messages"]):
                if entry.get("role") == "user":
                    last_user_content = entry.get("content")
                    break
            logging.info(
                "xai_call start: user_id=%s, model=%s, message_count=%s",
                user_id,
                payload["model"],
                message_count,
            )
            # Example before/after: no stdout log -> missing in Cloud Run UI; now prints to stdout too.
            print(f"XAI_CALL_START user_id={user_id} model={payload['model']} message_count={message_count}")
            # Example before/after: no message visibility -> hard to debug; now logs preview.
            logging.info(
                "xai_call payload_preview: user_id=%s, last_user_preview='%s'",
                user_id,
                str(last_user_content)[:200] if last_user_content is not None else "",
            )
            # Example before/after: token unclear -> now logs masked suffix only.
            logging.info(
                "xai_call auth: user_id=%s, key_suffix=...%s",
                user_id,
                self.xai_api_key[-4:] if self.xai_api_key else "NONE",
            )

            response = requests.post(
                "https://api.x.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.xai_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=180,
            )

            assistant_content = ""
            if response.status_code == 200:
                data = response.json()
                try:
                    assistant_content = data["choices"][0]["message"]["content"]
                except Exception:
                    assistant_content = ""
            else:
                logging.error("xai_call http_error status=%s body=%s", response.status_code, response.text[:300])

            if message_object and assistant_content:
                partial = message_object.copy()
                partial["user_message"] = assistant_content
                process_message_object(partial)

            # --- Append assistant response to user history ---
            if message_object:
                message_history_process(message_object, {"role": "assistant", "content": assistant_content})

            # Example before/after: empty response -> troubleshoot logs; non-empty -> user sees reply
            openai_duration_ms = int((time.monotonic() - openai_start) * 1000)
            logging.info(f"route_message end: user_id={user_id}, response_chars={len(assistant_content)}")
            logging.info(
                "xai_call end: user_id=%s, model=%s, duration_ms=%s, response_chars=%s",
                user_id,
                payload["model"],
                openai_duration_ms,
                len(assistant_content),
            )
            print(
                "XAI_CALL_END "
                f"user_id={user_id} model={payload['model']} "
                f"duration_ms={openai_duration_ms} response_chars={len(assistant_content)}"
            )
            if not assistant_content:
                # Example before/after: empty reply -> silent; now emits explicit stdout marker.
                print(f"XAI_CALL_EMPTY_RESPONSE user_id={user_id}")
            return assistant_content
        except requests.HTTPError as http_err:
            status = getattr(getattr(http_err, "response", None), "status_code", "unknown")
            body = getattr(getattr(http_err, "response", None), "text", str(http_err))
            logging.error(f"HTTP Error {status}: {body}")
            logging.error(f"Request payload: {payload}")
            if message_object:
                # Example before/after: error swallowed -> user sees nothing; now user gets a brief error.
                error_message = f"Sorry, I hit an upstream error ({status}). Please try again."
                partial = message_object.copy()
                partial["user_message"] = error_message
                process_message_object(partial)
            return f"HTTP Error {status}: {body}"
        except Exception as e:
            logging.error(f"Error in openai API call in message_router.py: {str(e)}", exc_info=True)
            if message_object:
                # Example before/after: exception -> silent; now a short error reply is sent.
                error_message = "Sorry, I ran into an error while generating a response. Please try again."
                partial = message_object.copy()
                partial["user_message"] = error_message
                process_message_object(partial)
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
