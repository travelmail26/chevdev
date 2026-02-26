import json
import os
import sys
import logging
import requests
import time
import importlib.util
import threading
import re
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
# After example: sys.path uses local repo dirs so Cloud Run/Codespaces both work.
base_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(base_dir)
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)
from message_user import process_message_object
from utilities.history_messages import message_history_process, archive_message_history
from utilities.insight_memory import load_user_insights, add_user_principle_insight

_bot_config_module = None
_principles_memory_lock = threading.Lock()
_principles_memory_enabled_by_user = {}


def _is_load_principles_trigger(text: str | None) -> bool:
    return " ".join(str(text or "").strip().lower().split()) == "load principles into memory"


def _extract_add_principle_text(text: str | None) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    # Supports: "add a cooking principle into memory: <text>"
    # Also supports typo "priniciple".
    pattern = re.compile(
        r"^\s*add\s+a\s+cooking\s+prini?ciple\s+into\s+memory\s*:\s*(.+?)\s*$",
        re.IGNORECASE,
    )
    match = pattern.match(raw)
    if not match:
        return ""
    return " ".join(match.group(1).strip().split())


def _set_principles_memory_enabled(user_id: str, enabled: bool) -> None:
    with _principles_memory_lock:
        _principles_memory_enabled_by_user[str(user_id)] = bool(enabled)


def _is_principles_memory_enabled(user_id: str) -> bool:
    with _principles_memory_lock:
        return bool(_principles_memory_enabled_by_user.get(str(user_id), False))


def _get_bot_config_module():
    # Before example: instruction paths hard-coded; After: load central bot_config.py once.
    global _bot_config_module
    if _bot_config_module is not None:
        return _bot_config_module
    config_path = os.path.join(parent_dir, "utilities", "bot_config.py")
    if not os.path.exists(config_path):
        return None
    try:
        spec = importlib.util.spec_from_file_location("bot_config", config_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            _bot_config_module = module
    except Exception:
        _bot_config_module = None
    return _bot_config_module


def _get_bot_instructions_path(bot_mode: str | None) -> str:
    # Before example: paths scattered; After: use bot_config when available.
    module = _get_bot_config_module()
    if module and hasattr(module, "get_bot_instructions_path"):
        return module.get_bot_instructions_path(bot_mode)
    return os.path.join(base_dir, "utilities", "instructions", "instructions_base.txt")

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _resolve_output_log_limit(default: int = 4000) -> int:
    raw = str(os.getenv("BOT_OUTPUT_LOG_MAX_CHARS", default)).strip()
    try:
        value = int(raw)
        if value > 0:
            return value
    except Exception:
        pass
    return default


def _clip_output_for_log(text: str, limit: int) -> str:
    content = str(text or "")
    if len(content) <= limit:
        return content
    extra = len(content) - limit
    return f"{content[:limit]}\n...[truncated {extra} chars]"


def _log_bot_user_output(
    user_id: str,
    assistant_text: str,
    *,
    source_interface: str = "unknown",
    bot_mode: str = "unknown",
    stream: bool = False,
) -> None:
    content = str(assistant_text or "")
    if not content:
        return
    limit = _resolve_output_log_limit()
    clipped = _clip_output_for_log(content, limit)
    logging.info(
        "bot_user_output user_id=%s source=%s bot_mode=%s stream=%s chars=%s text=%s",
        user_id,
        source_interface,
        bot_mode,
        bool(stream),
        len(content),
        clipped,
    )
    print(
        "BOT_USER_OUTPUT "
        f"user_id={user_id} source={source_interface} bot_mode={bot_mode} "
        f"stream={bool(stream)} chars={len(content)} text={clipped}"
    )


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
        # Before example: model/provider unclear; after example: log BOT_MODE + XAI model per init.
        logging.info(
            "router_init: bot_mode=%s xai_model=%s",
            os.getenv("BOT_MODE"),
            os.getenv("XAI_MODEL", "grok-4-1-fast-non-reasoning-latest"),
        )

        # Before: instructions pulled from a helper and combined elsewhere.
        # After example: paste paths below and the function will join them in order.
        self.combined_instructions = self.load_instructions()

    def load_instructions(self, bot_mode: str | None = None):
        """Load and join instruction files listed below (edit manually)."""
        mode = (bot_mode or "").lower()
        # Before: per-mode path logic here; After: bot_config.py owns the mapping.
        instruction_path = _get_bot_instructions_path(mode)
        instruction_paths = [instruction_path] if instruction_path else []

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

    def _build_search_tool_schema(self):
        # Before example: web search routing was hard-coded by command prefix.
        # After example: model can call a standard function tool when policy allows.
        # LLM instruction:
        # - Keep search policy in instruction files + tool description text.
        # - Do NOT add keyword/regex gating logic in Python here unless explicitly requested by user.
        return [
            {
                "type": "function",
                "function": {
                    "name": "search_perplexity",
                    "description": (
                        "Use the existing Perplexity web search utility to fetch live internet results. "
                        "REQUIRED CONDITION: call this tool ONLY if the CURRENT user message explicitly asks "
                        "to search internet/web/online/perplexity, or explicitly asks for latest/current/news. "
                        "If those explicit words/intent are not present in the current user message, do not call. "
                        "Do NOT call for normal chat, brainstorming, meal ideas, preference discussions, "
                        "or follow-up explanation questions that can be answered from existing conversation context. "
                        "If user asks a follow-up like 'why does thickness matter?' after a hashbrown discussion, "
                        "answer from context without calling this tool unless user explicitly asks to search again."
                    ),
                    "strict": True,
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Exact internet search query to send to Perplexity.",
                            }
                        },
                        "required": ["query"],
                        "additionalProperties": False,
                    },
                },
            }
        ]

    def _parse_tool_arguments(self, raw_arguments):
        # Before example: malformed tool args could crash JSON decode.
        # After example: invalid args safely degrade to an empty dict.
        if isinstance(raw_arguments, dict):
            return raw_arguments
        if not raw_arguments:
            return {}
        try:
            return json.loads(raw_arguments)
        except Exception:
            return {}

    def _build_perplexity_context_messages(
        self,
        conversation_messages: list | None,
        current_user_query: str,
        max_turns: int = 8,
    ):
        """Build ordered user/assistant context for Perplexity (turn-by-turn)."""
        context_messages = []
        for entry in conversation_messages or []:
            if not isinstance(entry, dict):
                continue
            role = entry.get("role")
            content = entry.get("content")
            if role in {"user", "assistant"} and isinstance(content, str) and content.strip():
                context_messages.append({"role": role, "content": content.strip()})

        # Merge adjacent same-role messages so role sequence alternates.
        cleaned_messages = []
        for message in context_messages:
            if not cleaned_messages:
                if message.get("role") != "user":
                    continue
                cleaned_messages.append(message)
                continue
            if cleaned_messages[-1].get("role") == message.get("role"):
                cleaned_messages[-1]["content"] = (
                    f"{cleaned_messages[-1]['content']}\n\n{message.get('content', '')}".strip()
                )
            else:
                cleaned_messages.append(message)

        max_messages = max_turns * 2
        cleaned_messages = cleaned_messages[-max_messages:]
        while cleaned_messages and cleaned_messages[0].get("role") != "user":
            cleaned_messages.pop(0)

        query_text = str(current_user_query or "").strip()
        if not cleaned_messages and query_text:
            cleaned_messages = [{"role": "user", "content": query_text}]
        elif query_text and cleaned_messages[-1].get("role") != "user":
            cleaned_messages.append({"role": "user", "content": query_text})

        return [
            {"role": message["role"], "content": message["content"]}
            for message in cleaned_messages
            if isinstance(message, dict) and message.get("role") in {"user", "assistant"} and message.get("content")
        ]

    def _should_emit_chat_output(self, message_object: dict | None) -> bool:
        # For web-origin turns, persist history but avoid Telegram send side-effects.
        if not isinstance(message_object, dict):
            return False
        source = str(message_object.get("source_interface") or "").strip().lower()
        if source == "web":
            return False
        return True

    def _execute_tool_call(
        self,
        tool_call,
        verbatim_user_query: str | None = None,
        conversation_messages: list | None = None,
        stream_callback=None,
        should_stop=None,
    ):
        # Before example: command-prefix routing called Perplexity directly in route_message.
        # After example: tool execution is centralized and tied to tool_call payload.
        function_payload = tool_call.get("function") or {}
        function_name = function_payload.get("name")
        function_args = self._parse_tool_arguments(function_payload.get("arguments"))

        if function_name != "search_perplexity":
            return f"Tool error: unsupported function '{function_name}'."

        model_query = str(function_args.get("query", "")).strip()
        query = str(verbatim_user_query or "").strip() or model_query
        if not query:
            return "Tool error: missing required argument 'query'."

        # Before example: user says "search the internet for ... keep your answer very short"
        # and model tool args become shortened "ways of making ...".
        # After example:  Perplexity receives the full original user message verbatim.
        logging.info(
            "tool_query_resolution: function=%s using_verbatim=%s model_query_preview='%s' final_query_preview='%s'",
            function_name,
            bool(str(verbatim_user_query or "").strip()),
            model_query[:160],
            query[:160],
        )

        perplexity_query_payload = self._build_perplexity_context_messages(
            conversation_messages=conversation_messages,
            current_user_query=query,
        )
        logging.info(
            "tool_context_messages: function=%s count=%s first_role=%s last_role=%s",
            function_name,
            len(perplexity_query_payload),
            perplexity_query_payload[0].get("role") if perplexity_query_payload else "none",
            perplexity_query_payload[-1].get("role") if perplexity_query_payload else "none",
        )

        from utilities.perplexity import search_perplexity
        return search_perplexity(
            perplexity_query_payload,
            stream_callback=stream_callback,
            should_stop=should_stop,
        )

    # === INTERFACETEST-STYLE STREAMING BLOCK START (easy to undo) ===
    def _emit_text_stream(self, text, stream_callback=None, should_stop=None):
        """
        Emit progressive text updates for a single-message edit UI.
        Returns (final_text_to_keep, stopped_early).
        """
        full_text = str(text or "")
        if not full_text:
            return "", False

        if not callable(stream_callback):
            return full_text, False

        words = full_text.split()
        if not words:
            stream_callback(full_text)
            return full_text, False

        built_words = []
        last_emitted_chars = 0
        for index, word in enumerate(words):
            if callable(should_stop) and should_stop():
                partial = " ".join(built_words).strip()
                if partial:
                    stream_callback(partial)
                return partial, True

            built_words.append(word)
            preview = " ".join(built_words)
            is_last = index == len(words) - 1
            punctuated = word.endswith((".", "!", "?", ",", ";", ":"))
            grew_enough = (len(preview) - last_emitted_chars) >= 80
            if is_last or punctuated or grew_enough:
                stream_callback(preview)
                last_emitted_chars = len(preview)
                # Before example: all chunks arrived instantly.
                # After example:  tiny pause creates visible progressive edits.
                time.sleep(0.03)

        return " ".join(built_words).strip(), False
    # === INTERFACETEST-STYLE STREAMING BLOCK END ===

    def _call_model(self, model, messages, tools=None):
        # Before example: request/response parsing was duplicated in multiple places.
        # After example: one helper sends the call and returns the assistant message object.
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": 256,
            "temperature": 0.7,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        response = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.xai_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=180,
        )
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            return {}
        return choices[0].get("message") or {}

    def _call_model_stream(self, model, messages, tools=None, stream_callback=None, should_stop=None):
        """Call xAI with server-side streaming and assemble assistant message."""
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": 256,
            "temperature": 0.7,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        response = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.xai_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            stream=True,
            timeout=180,
        )
        response.raise_for_status()

        content_parts = []
        tool_calls_by_index = {}

        for raw_line in response.iter_lines(decode_unicode=True):
            if callable(should_stop) and should_stop():
                break
            if not raw_line:
                continue

            line = str(raw_line).strip()
            if line.startswith("data:"):
                line = line[5:].strip()
            if not line or line == "[DONE]":
                continue

            try:
                chunk = json.loads(line)
            except Exception:
                continue

            choices = chunk.get("choices") or []
            if not choices:
                continue
            delta = (choices[0] or {}).get("delta") or {}

            token = delta.get("content")
            if token:
                content_parts.append(str(token))
                if callable(stream_callback):
                    # Before example: general replies were emitted only after full completion.
                    # After example:  each new token updates the in-flight Telegram/web stream.
                    stream_callback("".join(content_parts))

            tool_deltas = delta.get("tool_calls") or []
            for item in tool_deltas:
                idx = int(item.get("index", 0))
                assembled = tool_calls_by_index.setdefault(
                    idx,
                    {"id": "", "type": "function", "function": {"name": "", "arguments": ""}},
                )
                if item.get("id"):
                    assembled["id"] = str(item["id"])
                if item.get("type"):
                    assembled["type"] = str(item["type"])
                fn = item.get("function") or {}
                if fn.get("name"):
                    assembled["function"]["name"] += str(fn["name"])
                if fn.get("arguments"):
                    assembled["function"]["arguments"] += str(fn["arguments"])

        assistant_message = {
            "role": "assistant",
            "content": "".join(content_parts),
        }
        if tool_calls_by_index:
            assistant_message["tool_calls"] = [
                tool_calls_by_index[index] for index in sorted(tool_calls_by_index.keys())
            ]
        return assistant_message

    def _build_frontend_context_note(self, message_object: dict | None) -> str:
        """Add tiny context so the model knows which frontend produced this turn."""
        if not isinstance(message_object, dict):
            return ""
        source = str(
            message_object.get("source_interface")
            or message_object.get("source")
            or ""
        ).strip().lower()
        if source not in {"telegram", "web"}:
            return ""
        if source == "telegram":
            source_note = "Current frontend: Telegram chat."
        else:
            source_note = "Current frontend: Web UI chat."
        return (
            "\n\nFrontend context:\n"
            f"- {source_note}\n"
            "- Same user may switch frontends in one shared session.\n"
            "- Continue only from stored conversation history."
        )

    def _build_principles_context_note(self, user_id: str, source_mode: str | None = None) -> str:
        """Load explicit user-defined principles and format a compact system note."""
        if not user_id or user_id == "unknown":
            return ""
        filter_by_mode = os.environ.get("INSIGHT_PRINCIPLES_FILTER_BY_MODE", "0").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        mode_filter = (source_mode or None) if filter_by_mode else None
        try:
            principles = load_user_insights(
                user_id=str(user_id),
                principle_only=True,
                source_mode=mode_filter,
                limit=int(os.environ.get("INSIGHT_PRINCIPLES_LIMIT", "5")),
            )
        except Exception as exc:
            logging.warning("insight_principles_load_failed user_id=%s error=%s", user_id, exc)
            return ""
        if not principles:
            return ""

        lines = [
            "",
            "User-defined principles context:",
            "- These principles are explicit user-defined rules from prior conversations.",
            "- Treat them as anchor reasoning for future suggestions unless user overrides them now.",
        ]
        for item in principles:
            text = str(item.get("insight") or "").strip()
            if not text:
                continue
            # Keep the appended system note short to avoid token bloat.
            text = " ".join(text.split())
            if len(text) > 220:
                text = text[:220].rstrip() + "..."
            mode = str(item.get("source_bot_mode") or "").strip().lower() or "unknown"
            lines.append(f"- ({mode}) {text}")
        if len(lines) <= 4:
            return ""
        return "\n".join(lines)

    def route_message(self, messages=None, message_object=None, stream=False, stream_callback=None, should_stop=None):
        """Route a message from a user to OpenAI, persist history, and return the response.

        Tool calling behavior:
        - Uses standard function-calling flow (assistant tool call -> tool result -> assistant follow-up).
        - Internet search tool is available only in general mode.
        - Policy on when to call tools must stay instruction-driven (not code-gated heuristics).
        
        Args:
            messages: Optional list of message dictionaries for the conversation history
            message_object: Optional dictionary containing user_message and other data
            stream: If True, emit progressive updates through stream_callback
            stream_callback: Callable that receives full partial text for single-message edits
            should_stop: Callable that returns True when generation should stop safely
        """
        user_id = str(message_object.get("user_id", "unknown")) if message_object else "unknown"
        source_interface = (
            str(message_object.get("source_interface", "unknown")).strip().lower()
            if isinstance(message_object, dict)
            else "unknown"
        )
        logging.info(f"route_message start: user_id={user_id}, has_message_object={bool(message_object)}")
        logging.debug(f"DEBUG: route_message called with messages={messages}, message_object={message_object}")
        
        if messages is None:
            messages = []
        
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
                
        # Before: instructions chosen before we knew the user's mode; after: mode drives instructions.
        effective_bot_mode = None
        if isinstance(full_message_object, dict):
            effective_bot_mode = full_message_object.get("bot_mode")
        if not effective_bot_mode and isinstance(message_object, dict):
            effective_bot_mode = message_object.get("bot_mode")
        if not effective_bot_mode:
            effective_bot_mode = os.getenv("BOT_MODE") or "chefmain"

        current_user_message = (
            str(message_object.get("user_message", "")).strip()
            if isinstance(message_object, dict)
            else ""
        )
        add_principle_text = _extract_add_principle_text(current_user_message)
        add_principles_triggered = (
            str(effective_bot_mode).strip().lower() == "general"
            and bool(add_principle_text)
        )
        load_principles_triggered = (
            str(effective_bot_mode).strip().lower() == "general"
            and _is_load_principles_trigger(current_user_message)
        )
        if add_principles_triggered:
            created_doc = add_user_principle_insight(
                user_id=str(user_id),
                insight_text=add_principle_text,
                source_mode=str(effective_bot_mode or "general"),
                source_chat_session_id=(
                    str(full_message_object.get("chat_session_id"))
                    if isinstance(full_message_object, dict) and full_message_object.get("chat_session_id")
                    else None
                ),
            )
            _set_principles_memory_enabled(user_id, True)
            loaded_after = load_user_insights(
                user_id=str(user_id),
                principle_only=True,
                limit=int(os.environ.get("INSIGHT_PRINCIPLES_LIMIT", "5")),
            )
            if created_doc is not None:
                assistant_content = (
                    f'Principle added to memory ({len(loaded_after)} total): "{add_principle_text}".'
                )
            else:
                assistant_content = "Could not add principle to memory."
            _log_bot_user_output(
                user_id,
                assistant_content,
                source_interface=source_interface,
                bot_mode=str(effective_bot_mode or "unknown"),
                stream=stream,
            )
            if message_object:
                message_history_process(message_object, {"role": "assistant", "content": assistant_content})
            if (
                message_object
                and (not stream or not callable(stream_callback))
                and self._should_emit_chat_output(message_object)
            ):
                partial = message_object.copy()
                partial["user_message"] = assistant_content
                process_message_object(partial)
            return assistant_content

        if load_principles_triggered:
            _set_principles_memory_enabled(user_id, True)
            loaded = load_user_insights(
                user_id=str(user_id),
                principle_only=True,
                limit=int(os.environ.get("INSIGHT_PRINCIPLES_LIMIT", "5")),
            )
            assistant_content = (
                f"Loaded {len(loaded)} principle insights into memory."
                if loaded
                else "No principle insights found to load yet."
            )
            _log_bot_user_output(
                user_id,
                assistant_content,
                source_interface=source_interface,
                bot_mode=str(effective_bot_mode or "unknown"),
                stream=stream,
            )
            if message_object:
                message_history_process(message_object, {"role": "assistant", "content": assistant_content})
            if (
                message_object
                and (not stream or not callable(stream_callback))
                and self._should_emit_chat_output(message_object)
            ):
                partial = message_object.copy()
                partial["user_message"] = assistant_content
                process_message_object(partial)
            return assistant_content

        self.combined_instructions = self.load_instructions(bot_mode=effective_bot_mode)
        principles_note = ""
        if (
            str(effective_bot_mode).strip().lower() == "general"
            and _is_principles_memory_enabled(user_id)
        ):
            principles_note = self._build_principles_context_note(
                user_id=user_id,
                source_mode=effective_bot_mode,
            )
        system_prompt = (
            self.combined_instructions
            + self._build_frontend_context_note(message_object)
            + principles_note
        )
        system_instruction = {"role": "system", "content": system_prompt}

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
        elif messages[0].get("content") != system_prompt:
            # Before: first-turn system prompt could linger and miss updated mode/frontend context.
            # After example: system prompt is refreshed each turn while keeping a single system entry.
            messages[0]["content"] = system_prompt
            instructions_applied = True

        if instructions_applied and full_message_object and message_object:
            full_message_object["messages"] = messages
            user_identifier = str(message_object.get("user_id", "unknown"))
            archive_message_history(full_message_object, user_identifier)

        # Clean messages before sending to OpenAI: remove any with content None, but preserve those with tool_calls
        messages = [m for m in messages if m.get('content') is not None or m.get('tool_calls') is not None]

        last_user_content = None
        for entry in reversed(messages):
            if entry.get("role") == "user":
                last_user_content = entry.get("content")
                break

        xai_model = os.getenv("XAI_MODEL", "grok-4-1-fast-non-reasoning-latest")
        # Keep search decision instruction-driven for general mode.
        search_tools = self._build_search_tool_schema() if effective_bot_mode == "general" else []

        try:
            if callable(should_stop) and should_stop():
                assistant_content = "Stopped by user before generation started."
                _log_bot_user_output(
                    user_id,
                    assistant_content,
                    source_interface=source_interface,
                    bot_mode=str(effective_bot_mode or "unknown"),
                    stream=stream,
                )
                if message_object:
                    message_history_process(message_object, {"role": "assistant", "content": assistant_content})
                if message_object and (not stream or not callable(stream_callback)):
                    partial = message_object.copy()
                    partial["user_message"] = assistant_content
                    process_message_object(partial)
                return assistant_content

            # Before: OpenAI call timing was opaque; after example: log start/end with model + duration.
            openai_start = time.monotonic()
            message_count = len(messages)
            logging.info(
                "xai_call start: user_id=%s, model=%s, message_count=%s, tools_enabled=%s",
                user_id,
                xai_model,
                message_count,
                bool(search_tools),
            )
            # Example before/after: no stdout log -> missing in Cloud Run UI; now prints to stdout too.
            print(
                f"XAI_CALL_START user_id={user_id} model={xai_model} "
                f"message_count={message_count} tools_enabled={bool(search_tools)}"
            )
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

            used_native_stream = False
            if stream and callable(stream_callback):
                assistant_message = self._call_model_stream(
                    model=xai_model,
                    messages=messages,
                    tools=search_tools,
                    stream_callback=stream_callback,
                    should_stop=should_stop,
                )
                used_native_stream = True
            else:
                assistant_message = self._call_model(
                    model=xai_model,
                    messages=messages,
                    tools=search_tools,
                )
            assistant_content = assistant_message.get("content") or ""
            tool_calls = assistant_message.get("tool_calls") or []

            if tool_calls:
                tool_context_messages = list(messages)
                logging.info(
                    "xai_tool_round start: user_id=%s round=%s tool_calls=%s",
                    user_id,
                    1,
                    len(tool_calls),
                )
                messages.append(
                    {
                        "role": "assistant",
                        "content": assistant_message.get("content"),
                        "tool_calls": tool_calls,
                    }
                )
                if len(tool_calls) > 1:
                    logging.warning(
                        "xai_tool_round multiple_calls: user_id=%s count=%s using_first_call_only",
                        user_id,
                        len(tool_calls),
                    )

                tool_call = tool_calls[0]
                tool_call_id = tool_call.get("id") or "tool_call_1_1"
                function_name = (tool_call.get("function") or {}).get("name")
                try:
                    tool_output = self._execute_tool_call(
                        tool_call,
                        verbatim_user_query=str(last_user_content or ""),
                        conversation_messages=tool_context_messages,
                        stream_callback=stream_callback if stream else None,
                        should_stop=should_stop if stream else None,
                    )
                except Exception as tool_exc:
                    tool_output = f"Tool execution error: {tool_exc}"

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "name": function_name,
                        "content": tool_output,
                    }
                )

                # User preference: return Perplexity output verbatim (no rewrite, no trim).
                assistant_content = tool_output if isinstance(tool_output, str) else str(tool_output)

            # Stream non-tool model text via progressive single-message updates.
            if (
                stream
                and assistant_content
                and effective_bot_mode == "general"
                and not tool_calls
                and not used_native_stream
            ):
                streamed_text, stopped_early = self._emit_text_stream(
                    assistant_content,
                    stream_callback=stream_callback,
                    should_stop=should_stop,
                )
                assistant_content = streamed_text
                if stopped_early:
                    assistant_content = (assistant_content + "\n\n[Stopped by user]").strip()

            if (
                message_object
                and assistant_content
                and (not stream or not callable(stream_callback))
                and self._should_emit_chat_output(message_object)
            ):
                partial = message_object.copy()
                partial["user_message"] = assistant_content
                process_message_object(partial)

            # --- Append assistant response to user history ---
            if message_object:
                message_history_process(message_object, {"role": "assistant", "content": assistant_content})

            # Example before/after: empty response -> troubleshoot logs; non-empty -> user sees reply
            openai_duration_ms = int((time.monotonic() - openai_start) * 1000)
            _log_bot_user_output(
                user_id,
                assistant_content,
                source_interface=source_interface,
                bot_mode=str(effective_bot_mode or "unknown"),
                stream=stream,
            )
            logging.info(f"route_message end: user_id={user_id}, response_chars={len(assistant_content)}")
            logging.info(
                "xai_call end: user_id=%s, model=%s, duration_ms=%s, response_chars=%s",
                user_id,
                xai_model,
                openai_duration_ms,
                len(assistant_content),
            )
            print(
                "XAI_CALL_END "
                f"user_id={user_id} model={xai_model} "
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
            if message_object and self._should_emit_chat_output(message_object):
                # Example before/after: error swallowed -> user sees nothing; now user gets a brief error.
                error_message = f"Sorry, I hit an upstream error ({status}). Please try again."
                _log_bot_user_output(
                    user_id,
                    error_message,
                    source_interface=source_interface,
                    bot_mode=str(effective_bot_mode or "unknown"),
                    stream=stream,
                )
                partial = message_object.copy()
                partial["user_message"] = error_message
                process_message_object(partial)
            return f"HTTP Error {status}: {body}"
        except Exception as e:
            logging.error(f"Error in openai API call in message_router.py: {str(e)}", exc_info=True)
            if message_object and self._should_emit_chat_output(message_object):
                # Example before/after: exception -> silent; now a short error reply is sent.
                error_message = "Sorry, I ran into an error while generating a response. Please try again."
                _log_bot_user_output(
                    user_id,
                    error_message,
                    source_interface=source_interface,
                    bot_mode=str(effective_bot_mode or "unknown"),
                    stream=stream,
                )
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
