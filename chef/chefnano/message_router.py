import argparse
import json
import os
import sys
import logging
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
from openai import OpenAI
from analysisfolder import answer_with_nano
from message_user import process_message_object
from utilities.history_messages import message_history_process, archive_message_history

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _build_nano_args() -> argparse.Namespace:
    # Before example: manual overrides changed behavior; After: use answer_with_nano defaults.
    db_name = answer_with_nano.DEFAULT_DB_NAME
    collection_name = answer_with_nano.DEFAULT_COLLECTION_NAME
    return argparse.Namespace(
        db_name=db_name,
        collection_name=collection_name,
        index_name=answer_with_nano.DEFAULT_INDEX_NAME,
        analysis_model=answer_with_nano.DEFAULT_ANALYSIS_MODEL,
        tool_model=answer_with_nano.DEFAULT_ANALYSIS_MODEL,
        embedding_model=answer_with_nano.DEFAULT_EMBEDDING_MODEL,
        dimensions=None,
        limit=answer_with_nano.DEFAULT_LIMIT,
        embedding_path=answer_with_nano.DEFAULT_EMBEDDING_PATH,
        text_field=answer_with_nano.DEFAULT_TEXT_FIELD,
        session_id_field=answer_with_nano.DEFAULT_SESSION_ID_FIELD,
        message_start_field=answer_with_nano.DEFAULT_MESSAGE_START_FIELD,
        message_end_field=answer_with_nano.DEFAULT_MESSAGE_END_FIELD,
        max_chunk_chars=answer_with_nano.DEFAULT_MAX_CHUNK_CHARS,
        max_message_chars=answer_with_nano.DEFAULT_MAX_MESSAGE_CHARS,
        max_messages_per_session=answer_with_nano.DEFAULT_MAX_MESSAGES_PER_SESSION,
    )


def _get_nano_collection(args: argparse.Namespace):
    mongo_uri = os.environ.get("MONGODB_URI")
    if not mongo_uri:
        return None
    return answer_with_nano.get_collection(mongo_uri, args.db_name, args.collection_name)


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
        # Before example: no nano client -> answer_with_nano fails; After: OpenAI client cached on init.
        self.nano_client = OpenAI(api_key=self.openai_api_key) if self.openai_api_key else None
        if self.nano_client and not hasattr(self.nano_client, "responses"):
            logging.warning("OpenAI SDK missing Responses API; upgrade openai package.")
        self.nano_args = _build_nano_args()
        self.nano_collection = _get_nano_collection(self.nano_args)
        if self.nano_collection is None:
            # Example before/after: missing MONGODB_URI -> nano queries skip; env set -> Mongo ready.
            logging.warning("MONGODB_URI not set; nano queries will fail.")
        logging.info("router_init: bot_mode=%s", os.getenv("BOT_MODE"))

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
                    content = handle.read().strip()
                collected.append(content)
                # Before example: instruction source unclear; after example: log path + size.
                logging.info("instructions_loaded path=%s chars=%s", path, len(content))
            except Exception as exc:
                logging.warning(f"Could not read instruction file '{path}': {exc}")
        return "\n\n".join(collected)
    
    def route_message(self, messages=None, message_object=None):
        """Route a message to answer_with_nano, persist history, and return the response.

        Tool calling details:
        - Before: router used direct model chat calls.
        - After: answer_with_nano drives vector search + tool calling for recipe answers.

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

        try:
            if self.nano_client is None or self.nano_collection is None:
                raise RuntimeError("Nano is not configured. Set OPENAI_API_KEY and MONGODB_URI.")
            question = ""
            if message_object and "user_message" in message_object:
                question = str(message_object["user_message"]).strip()
            elif messages:
                # Before example: CLI passes history only -> question empty; After: last user message used.
                for entry in reversed(messages):
                    if entry.get("role") == "user":
                        question = str(entry.get("content") or "").strip()
                        break
            if not question:
                raise RuntimeError("Nano needs a question to answer.")

            # Before example: no timing logs -> unclear latency; After: duration_ms logged per query.
            nano_start = time.monotonic()
            logging.info("nano_call start: user_id=%s question_preview='%s'", user_id, question[:200])
            assistant_content = answer_with_nano.answer_question(
                question,
                self.nano_client,
                self.nano_collection,
                self.nano_args,
            )
            nano_duration_ms = int((time.monotonic() - nano_start) * 1000)
            logging.info(
                "nano_call end: user_id=%s duration_ms=%s response_chars=%s",
                user_id,
                nano_duration_ms,
                len(assistant_content or ""),
            )

            if message_object and assistant_content:
                partial = message_object.copy()
                partial["user_message"] = assistant_content
                process_message_object(partial)

            # --- Append assistant response to user history ---
            if message_object:
                message_history_process(message_object, {"role": "assistant", "content": assistant_content})

            logging.info(f"route_message end: user_id={user_id}, response_chars={len(assistant_content)}")
            if not assistant_content:
                # Example before/after: empty reply -> silent; now emits explicit stdout marker.
                print(f"NANO_CALL_EMPTY_RESPONSE user_id={user_id}")
            return assistant_content
        except Exception as e:
            logging.error(f"Error in nano call in message_router.py: {str(e)}", exc_info=True)
            if message_object:
                # Example before/after: exception -> silent; now a short error reply is sent.
                error_message = "Sorry, I ran into an error while answering from Nano. Please try again."
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
