import os
import sys
import asyncio
import logging
import subprocess
import traceback
import time
import threading

# Add current + parent directories to path so local utilities resolve first.
base_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(base_dir)
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from dotenv import load_dotenv, dotenv_values
from utilities.history_messages import (
    create_session_log_file,
    get_user_bot_mode,
    set_user_bot_mode,
    set_user_active_session,
) # Adjust path if necessary

# Load environment variables early so downstream imports (e.g., perplexity) see keys
try:
    # Load default .env
    load_dotenv()
    # Optionally load a local override file that is gitignored
    if os.path.exists(os.path.join(os.getcwd(), ".env.local")):
        load_dotenv(dotenv_path=os.path.join(os.getcwd(), ".env.local"), override=False)
except Exception:
    pass


from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)
import requests
from testscripts.openai_simple_ping import call_openai_hi
from testscripts.xai_simple_ping import call_xai_hi
from message_router import MessageRouter # Import MessageRouter
from utilities.firebase import firebase_get_media_url

# Set up logging
logging.basicConfig(level=logging.INFO)

# Set the logging level to WARNING or higher

# Get the httpx logger
# Silence all debug logs from external libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.WARNING)

# Global variables
application = None
conversations = {}
handlers_per_user = {}
message_router = None # Add global variable for the router

# Global dictionary to store user contexts
user_contexts = {}

# === INTERFACETEST-STYLE STREAMING BLOCK START (easy to undo) ===
_general_stream_state_lock = threading.Lock()
_general_stream_state_by_user = {}


def _is_general_edit_streaming_enabled() -> bool:
    # Toggle off quickly by setting GENERAL_EDIT_STREAMING=0.
    return os.getenv("GENERAL_EDIT_STREAMING", "1").strip().lower() not in {"0", "false", "no", "off"}


def _stream_start_run(user_id: int) -> int:
    with _general_stream_state_lock:
        state = _general_stream_state_by_user.get(user_id) or {"run_id": 0, "active": False, "stop_requested": False}
        run_id = int(state.get("run_id", 0)) + 1
        _general_stream_state_by_user[user_id] = {
            "run_id": run_id,
            "active": True,
            "stop_requested": False,
        }
        return run_id


def _stream_request_stop(user_id: int) -> bool:
    with _general_stream_state_lock:
        state = _general_stream_state_by_user.get(user_id)
        if not state or not state.get("active"):
            return False
        state["stop_requested"] = True
        _general_stream_state_by_user[user_id] = state
        return True


def _stream_should_stop(user_id: int, run_id: int) -> bool:
    with _general_stream_state_lock:
        state = _general_stream_state_by_user.get(user_id)
        if not state:
            return True
        # Stop if a newer run started or user requested stop.
        return int(state.get("run_id", 0)) != int(run_id) or bool(state.get("stop_requested"))


def _stream_finish_run(user_id: int, run_id: int) -> None:
    with _general_stream_state_lock:
        state = _general_stream_state_by_user.get(user_id)
        if not state:
            return
        if int(state.get("run_id", 0)) == int(run_id):
            state["active"] = False
            _general_stream_state_by_user[user_id] = state


def _clip_telegram_text(text: str, limit: int = 3900) -> str:
    content = str(text or "")
    if len(content) <= limit:
        return content
    # Before example: long streams failed edit with Telegram 4096-char cap.
    # After example:  long streams are clipped safely with an explicit suffix.
    return content[: limit - 26] + "\n\n[truncated for Telegram]"


async def _safe_edit_stream_message(bot, chat_id: int, message_id: int, text: str) -> None:
    try:
        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=_clip_telegram_text(text))
    except Exception as exc:
        # Ignore "message is not modified" edit races while streaming.
        if "message is not modified" not in str(exc).lower():
            logging.warning("stream_edit_failed chat_id=%s message_id=%s error=%s", chat_id, message_id, exc)


async def _handle_general_single_message_stream(update: Update, context: ContextTypes.DEFAULT_TYPE, message_object: dict) -> None:
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    run_id = _stream_start_run(user_id)
    status_msg = await update.message.reply_text(
        "Thinking... streaming in one message. Send /stop to stop."
    )

    stream_state = {
        "latest_text": "",
        "final_text": "",
        "done": False,
        "error": None,
    }
    state_lock = threading.Lock()

    def stream_callback(partial_text: str) -> None:
        with state_lock:
            stream_state["latest_text"] = str(partial_text or "")

    def should_stop() -> bool:
        return _stream_should_stop(user_id, run_id)

    router_instance = MessageRouter()

    def worker() -> None:
        try:
            final = router_instance.route_message(
                message_object=message_object,
                stream=True,
                stream_callback=stream_callback,
                should_stop=should_stop,
            )
            with state_lock:
                stream_state["final_text"] = str(final or "")
        except Exception as exc:
            with state_lock:
                stream_state["error"] = str(exc)
        finally:
            with state_lock:
                stream_state["done"] = True

    worker_task = asyncio.create_task(asyncio.to_thread(worker))

    last_sent = ""
    last_typing_at = 0.0
    while True:
        await asyncio.sleep(0.35)
        now = time.monotonic()
        with state_lock:
            latest_text = stream_state["latest_text"]
            done = bool(stream_state["done"])
            error = stream_state["error"]
            final_text = stream_state["final_text"]

        if latest_text and latest_text != last_sent:
            await _safe_edit_stream_message(
                context.bot,
                chat_id,
                status_msg.message_id,
                latest_text + (" ▌" if not done else ""),
            )
            last_sent = latest_text

        if now - last_typing_at >= 4.0 and not done:
            try:
                await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            except Exception:
                pass
            last_typing_at = now

        if done:
            await worker_task
            if error:
                await _safe_edit_stream_message(
                    context.bot,
                    chat_id,
                    status_msg.message_id,
                    f"Streaming failed: {error}",
                )
            else:
                final_display = final_text or latest_text or "No output was generated."
                await _safe_edit_stream_message(
                    context.bot,
                    chat_id,
                    status_msg.message_id,
                    final_display,
                )
            break

    _stream_finish_run(user_id, run_id)


async def stop_stream(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    stopped = _stream_request_stop(user_id)
    if stopped:
        await update.message.reply_text("Stop requested. I will stop at the next safe checkpoint.")
    else:
        await update.message.reply_text("No active stream to stop.")
# === INTERFACETEST-STYLE STREAMING BLOCK END ===

def detect_runtime():
    # Example before/after: K_SERVICE set -> "cloud_run"; CODESPACES=true -> "codespaces"
    if os.getenv("K_SERVICE"):
        return "cloud_run"
    if os.getenv("CODESPACES") == "true":
        return "codespaces"
    return "default"

def get_port():
    # Example before/after: PORT unset -> 8080; PORT=9090 -> 9090
    return int(os.getenv("PORT", "8080"))

def get_webhook_url(runtime: str | None = None):
    # Example before/after: runtime=codespaces uses TELEGRAM_WEBHOOK_CODESPACE -> codespaces URL; runtime=cloud_run uses TELEGRAM_WEBHOOK_URL -> Cloud Run URL
    runtime = runtime or detect_runtime()
    if runtime == "codespaces":
        return os.getenv("TELEGRAM_WEBHOOK_CODESPACE")
    return os.getenv("TELEGRAM_WEBHOOK_URL")

def get_webhook_env_var_name(runtime: str | None = None) -> str:
    # Example before/after: runtime=codespaces -> TELEGRAM_WEBHOOK_CODESPACE; runtime=cloud_run -> TELEGRAM_WEBHOOK_URL
    runtime = runtime or detect_runtime()
    if runtime == "codespaces":
        return "TELEGRAM_WEBHOOK_CODESPACE"
    return "TELEGRAM_WEBHOOK_URL"


def _spawn_media_description_backfill(limit: int = 20) -> None:
    """Kick off background backfill for media_metadata.user_description."""
    # Before example: /restart only cleared sessions; media metadata stayed untouched.
    # After example:  /restart spawns a background job to fill user_description.
    if not os.environ.get("MONGODB_URI"):
        logging.info("media_backfill_skip missing_env=MONGODB_URI")
        return
    if not os.environ.get("XAI_API_KEY"):
        logging.info("media_backfill_skip missing_env=XAI_API_KEY")
        return

    script_path = os.path.join(parent_dir, "chefmain", "utilities", "mongo_media_user_description_xai.py")
    if not os.path.exists(script_path):
        logging.warning("media_backfill_skip missing_script path=%s", script_path)
        return

    try:
        env = {
            **os.environ,
            # Before example: model drifted per process.
            # After example:  xAI model is pinned for the backfill job.
            "XAI_MODEL": os.environ.get("XAI_MODEL", "grok-4-1-fast-non-reasoning-latest"),
        }
        subprocess.Popen(
            [sys.executable, script_path, "--scan-latest", str(limit)],
            env=env,
        )
        logging.info("media_backfill_spawned limit=%s script=%s", limit, script_path)
    except Exception as exc:
        logging.warning("media_backfill_failed error=%s", exc)

def get_user_handler(user_id, session_info, user_message, application_data=None):
    """
    Creates or retrieves a user context dictionary.
    
    curl -s "https://api.telegram.org/bot7912564126:AAHpf0J1Ci1_jkIKuTfyuO6GyJ57v44_m00/setWebhook?url=https://chefdev-209538059512.us-west2.run.app/webhook"
    

    Args:
        user_id: The user's ID.
        application_data: The Telegram application object.
        session_info: A dictionary containing session information.
        user_message: The user's message.

    Returns:
        A dictionary containing the user's context.
    """
    if user_id not in user_contexts:
        # Create a new user context
        user_context = {
            'user_id': user_id,
            #'application': application_data,
            'session_info': session_info,
            'user_message': user_message,  # Add the user's message to the context
            # Before: stale bot_mode stuck in memory; After: bot_mode is read fresh each message.
            'bot_mode': get_user_bot_mode(user_id),
            # Add other relevant data here as needed
        }
        user_contexts[user_id] = user_context
    else:
        # Retrieve existing user context
        user_context = user_contexts[user_id]
        # Update session info
        user_context['session_info'] = session_info
        # Update user message
        user_context['user_message'] = user_message
        # Before: /1 switch updated Mongo but not in-memory context; After: syncs from Mongo every turn.
        user_context['bot_mode'] = get_user_bot_mode(user_id)
    return user_context

# def get_user_handler(user_id, application_data, session_info):
#     if user_id not in handlers_per_user:
#         # Remove the 'session_info' argument from the AIHandler initialization
#         handlers_per_user[user_id] = AIHandler(user_id=user_id, application=application_data)
#         print(f"DEBUG: Created new AIHandler for user {user_id}")
#     return handlers_per_user[user_id]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello! I'm your AI assistant. How can I help you today?")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.message.from_user.id
        application_data = context.application
        user_input = update.message.text
        logging.info(f"handle_message start: user_id={user_id}, has_text={bool(update.message.text)}")


        message_timestamp = update.message.date
        # Before example: timestamp=1767225871.0 only; After example: timestamp_iso="2026-01-01T19:55:13+00:00".
        message_timestamp_iso = message_timestamp.isoformat() if message_timestamp else None
        # Gather session information
        session_info = {
            'user_id': user_id,
            'chat_id': update.message.chat_id,
            'message_id': update.message.message_id,
            'timestamp': message_timestamp.timestamp() if message_timestamp else None,
            'timestamp_iso': message_timestamp_iso,
            'username': update.message.from_user.username,
            'first_name': update.message.from_user.first_name,
            'last_name': update.message.from_user.last_name
        }

        #store application token
        with open(f"application_data_for_{session_info['user_id']}.txt", "w") as f:
            f.write(str(application_data))
        
        # Pass session_info to get_user_handler

        message_object = get_user_handler(user_id, session_info, user_input)


        user_input = "" # Initialize user_input


        if update.message.audio or update.message.voice:
            # Handle audio or voice messages
            audio = update.message.audio or update.message.voice
            # Example before/after: no audio -> skip; audio present -> download + upload flow
            logging.info("handle_message: received audio/voice message")
            get_file_start = time.time()
            file = await context.bot.get_file(audio.file_id)
            # Example before/after: no timing logs -> "media_timing audio_get_file_ms=42 file_id=abc size=12345"
            logging.info(
                "media_timing audio_get_file_ms=%d file_id=%s size=%s",
                int((time.time() - get_file_start) * 1000),
                audio.file_id,
                getattr(audio, "file_size", None),
            )
            audio_dir = "saved_audio"
            os.makedirs(audio_dir, exist_ok=True)
            local_path = f"{audio_dir}/{audio.file_id}.ogg"
            print(f"DEBUG: Downloading audio file to {local_path}")
            download_start = time.time()
            await file.download_to_drive(local_path)
            # Example before/after: no timing logs -> "media_timing audio_download_ms=3500 path=saved_audio/... size=23456"
            logging.info(
                "media_timing audio_download_ms=%d path=%s size=%s",
                int((time.time() - download_start) * 1000),
                local_path,
                os.path.getsize(local_path) if os.path.exists(local_path) else None,
            )

            firebase_url = None
            try:
                # Before example: audio saved to telegram_photos folder.
                # After example:  media_type=audio routes to telegram_audio folder.
                firebase_url = firebase_get_media_url(local_path, media_type="audio")
            except Exception as firebase_error:
                logging.error(f"Firebase upload failed for audio: {firebase_error}")

            if firebase_url:
                # Example before/after: [audio_gridfs_id: 123] -> [audio_url: https://...]
                user_input = f"[audio_url: {firebase_url}]"
            else:
                user_input = f"[Audio saved locally: {local_path}]"

        elif update.message.photo:
            photo = update.message.photo[-1]
            # Example before/after: no photo -> skip; photo present -> download + upload flow
            logging.info("handle_message: received photo message")
            get_file_start = time.time()
            file = await context.bot.get_file(photo.file_id)
            # Example before/after: no timing logs -> "media_timing photo_get_file_ms=35 file_id=abc size=12345"
            logging.info(
                "media_timing photo_get_file_ms=%d file_id=%s size=%s",
                int((time.time() - get_file_start) * 1000),
                photo.file_id,
                getattr(photo, "file_size", None),
            )
            photo_dir = "saved_photos"
            os.makedirs(photo_dir, exist_ok=True)
            local_path = f"{photo_dir}/{photo.file_id}.jpg"
            download_start = time.time()
            await file.download_to_drive(local_path)
            # Example before/after: no timing logs -> "media_timing photo_download_ms=4200 path=saved_photos/... size=45678"
            logging.info(
                "media_timing photo_download_ms=%d path=%s size=%s",
                int((time.time() - download_start) * 1000),
                local_path,
                os.path.getsize(local_path) if os.path.exists(local_path) else None,
            )
            firebase_url = None
            try:
                # Before example: photos already go to telegram_photos by default.
                # After example:  media_type=photo keeps that explicit.
                firebase_url = firebase_get_media_url(local_path, media_type="photo")
            except Exception as firebase_error:
                logging.error(f"Firebase upload failed for photo: {firebase_error}")

            if firebase_url:
                # Example before/after: [photo_gridfs_id: 456] -> [photo_url: https://...]
                user_input = f"[photo_url: {firebase_url}]"
            else:
                user_input = f"[Photo saved locally: {local_path}]"

        elif update.message.video:
            video = update.message.video
            # Example before/after: no video -> skip; video present -> download + upload flow
            logging.info("handle_message: received video message")
            get_file_start = time.time()
            file = await context.bot.get_file(video.file_id)
            # Example before/after: no timing logs -> "media_timing video_get_file_ms=55 file_id=abc size=12345"
            logging.info(
                "media_timing video_get_file_ms=%d file_id=%s size=%s",
                int((time.time() - get_file_start) * 1000),
                video.file_id,
                getattr(video, "file_size", None),
            )
            video_dir = "saved_videos"
            os.makedirs(video_dir, exist_ok=True)
            local_path = f"{video_dir}/{video.file_id}.mp4"
            download_start = time.time()
            await file.download_to_drive(local_path)
            # Example before/after: no timing logs -> "media_timing video_download_ms=7800 path=saved_videos/... size=789012"
            logging.info(
                "media_timing video_download_ms=%d path=%s size=%s",
                int((time.time() - download_start) * 1000),
                local_path,
                os.path.getsize(local_path) if os.path.exists(local_path) else None,
            )
            firebase_url = None
            try:
                # Before example: video stored under telegram_photos; hard to segment.
                # After example:  media_type=video routes to telegram_videos folder.
                firebase_url = firebase_get_media_url(local_path, media_type="video")
            except Exception as firebase_error:
                logging.error(f"Firebase upload failed for video: {firebase_error}")

            if firebase_url:
                # Example before/after: [video_gridfs_id: 789] -> [video_url: https://...]
                user_input = f"[video_url: {firebase_url}]"
            else:
                user_input = f"[Video saved locally: {local_path}]"

        elif update.message.text:  # Text messages
            user_input = update.message.text
            # Example before/after: empty text -> skip; text present -> route_message
            logging.info("handle_message: received text message")
        else:
            # Unknown message type
            await update.message.reply_text("Could not process the message type.")
            return

        # Centralized call to agentchat and response handling for all types
        #status user handler class agent chat rather than passing the message
        
        message_object =  get_user_handler(user_id, session_info, user_input)
        # Example before/after: no user preview -> unclear payload; now logs first 200 chars.
        logging.info(f"handle_message: user_message_preview='{str(user_input)[:200]}'")


        #thhe message object dictionary example
        """
        DEBUG: User handler object: {'user_id': 1275******, 
        'application': Application[bot=ExtBot[token=<token>]], 
        'session_info': {'user_id': 1275******, 'chat_id': 1275******, 'message_id': 1***, 
        'timestamp': 1746130241.0, 'username': 'ferenstein', 
        'first_name': '<name>', 'last_name': '<name>'}, 'user_message': 'hi'}
        """


        print(f"DEBUG: User handler object: {message_object}")
        
        # Get or create user conversation history
        if user_id not in conversations:
            print(f"DEBUG: Creating new conversation history for user {user_id}")
            conversations[user_id] = []
        else:
            print(f"DEBUG: Using existing conversation history for user {user_id}")
        
        # Trigger the message router with the conversation history and message object
         

        router_instance_for_this_call = MessageRouter()
        # Example before/after: no routing -> no response; routing -> OpenAI + Telegram output
        logging.info(f"handle_message: routing message for user_id={user_id}")
        # Before example: general mode sent a single final message only.
        # After example:  general mode can stream by editing one Telegram message.
        if (
            _is_general_edit_streaming_enabled()
            and str(message_object.get("bot_mode", "")).strip().lower() == "general"
        ):
            await _handle_general_single_message_stream(update, context, message_object)
        else:
            router_instance_for_this_call.route_message(message_object=message_object)
        logging.info(f"Message object for user {user_id} passed to message router.")
        
            
        pass




        # Now, pass the user_context to the agentchat function

        pass
        
        ##buffer and send message

        # buffer = ""
        # # Process the response generator (synchronous logic)
        # for chunk in response:
        #     if chunk and isinstance(chunk, str) and chunk.strip():
        #                 buffer += chunk
        #                 # Send message parts when buffer reaches a certain size
        #             while len(buffer) >= 300: # Example threshold
        #                 message_part = buffer[:300]
        #                 try:
        #                     await update.message.reply_text(message_part)
        #                     buffer = buffer[300:]
        #                 except Exception as telegram_error:
        #                     logging.error(f"Telegram API error sending chunk: {telegram_error}")
        #                     break # Exit the inner while loop on error

        # # Send any remaining part in the buffer
        # if buffer.strip():
        #     try:
        #                 await update.message.reply_text(buffer)
        #             except Exception as telegram_error:
        #                 logging.error(f"Telegram API error sending final buffer: {telegram_error}")

    except Exception as e:
        error_message = f"Error in handle_message: {e}\n{traceback.format_exc()}"
        logging.error(error_message)
        await update.message.reply_text("An error occurred while processing your message.")

async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await _apply_restart_flow(update, trigger_command="/restart", send_restart_reply=True)
    except Exception as e:
        await update.message.reply_text(f"Error during restart: {str(e)}")


def _build_session_info_from_update(update: Update, trigger_command: str) -> dict:
    command_timestamp = update.effective_message.date
    # Before example: command session had only epoch timestamps.
    # After example:  command session stores both epoch and ISO timestamp.
    command_timestamp_iso = command_timestamp.isoformat() if command_timestamp else None
    return {
        "user_id": update.effective_user.id,
        "chat_id": update.effective_chat.id,
        "message_id": update.effective_message.message_id,
        "timestamp": command_timestamp.timestamp() if command_timestamp else None,
        "timestamp_iso": command_timestamp_iso,
        "username": update.effective_user.username,
        "first_name": update.effective_user.first_name,
        "last_name": update.effective_user.last_name,
        "trigger_command": trigger_command,
    }


async def _apply_restart_flow(
    update: Update,
    trigger_command: str,
    send_restart_reply: bool = False,
) -> dict:
    user_id = update.effective_user.id
    session_info = _build_session_info_from_update(update, trigger_command)
    logging.info("%s command received. Session info: %s", trigger_command, session_info)

    create_session_log_file(user_id)
    # Before example: mode switches did not create a new active chat session.
    # After example:  mode switches and /restart both seed a fresh chat_session_id.
    new_session = set_user_active_session(str(user_id), session_info=session_info)
    logging.info(
        "reset_new_session: user_id=%s trigger=%s chat_session_id=%s",
        user_id,
        trigger_command,
        new_session.get("chat_session_id"),
    )

    # Before example: mode switch only dropped in-memory conversation list.
    # After example:  mode switch runs the same full reset path as /restart.
    user_contexts.pop(user_id, None)
    had_handler = user_id in handlers_per_user
    handlers_per_user.pop(user_id, None)
    conversations.pop(user_id, None)
    _spawn_media_description_backfill(limit=20)

    if send_restart_reply:
        if had_handler:
            await update.message.reply_text(
                "Bot memory cleared for you. Restarting our conversation."
            )
            print(f"DEBUG: Cleared handler for user {user_id}")
        else:
            await update.message.reply_text(
                "No conversation history found for you to clear."
            )

    return session_info

def _reset_history_file(logs_dir: str, user_id: str) -> None:
    # Before example: missing logs_dir -> FileNotFoundError. After: logs_dir exists with an empty JSON file.
    os.makedirs(logs_dir, exist_ok=True)
    filepath = os.path.join(logs_dir, f"{user_id}_history.json")
    with open(filepath, "w") as handle:
        pass

async def bot_mode_switch_cook(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Before example: /1 toggled modes; After example: /cook forces cheflog every time.
    user_id = update.effective_user.id
    current_mode = get_user_bot_mode(str(user_id))
    next_mode = "cheflog"
    try:
        session_info = await _apply_restart_flow(
            update,
            trigger_command="/cook",
            send_restart_reply=False,
        )
        set_user_bot_mode(str(user_id), next_mode, session_info=session_info)
        await update.message.reply_text("Switched to cook mode.")
        logging.info("mode_switch: user_id=%s from=%s to=%s", user_id, current_mode, next_mode)
    except Exception as e:
        await update.message.reply_text(f"Error during mode switch: {str(e)}")


async def bot_mode_switch_log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Before example: /1 toggled modes; After example: /log forces dietlog every time.
    user_id = update.effective_user.id
    current_mode = get_user_bot_mode(str(user_id))
    next_mode = "dietlog"
    try:
        session_info = await _apply_restart_flow(
            update,
            trigger_command="/log",
            send_restart_reply=False,
        )
        set_user_bot_mode(str(user_id), next_mode, session_info=session_info)
        await update.message.reply_text("Switched to dietlog mode.")
        logging.info("mode_switch: user_id=%s from=%s to=%s", user_id, current_mode, next_mode)
    except Exception as e:
        await update.message.reply_text(f"Error during mode switch: {str(e)}")


async def bot_mode_switch_general(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Before example: /general fell through to normal chat mode.
    # After example:  /general forces general mode every time.
    user_id = update.effective_user.id
    current_mode = get_user_bot_mode(str(user_id))
    next_mode = "general"
    try:
        session_info = await _apply_restart_flow(
            update,
            trigger_command="/general",
            send_restart_reply=False,
        )
        set_user_bot_mode(str(user_id), next_mode, session_info=session_info)
        await update.message.reply_text("Switched to general mode.")
        logging.info("mode_switch: user_id=%s from=%s to=%s", user_id, current_mode, next_mode)
    except Exception as e:
        await update.message.reply_text(f"Error during mode switch: {str(e)}")


async def openai_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        await update.message.reply_text("openai ping: missing OPENAI_API_KEY")
        return
    try:
        response = requests.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {key}"},
            timeout=10,
        )
        await update.message.reply_text(f"openai ping: {response.status_code}")
    except Exception as exc:
        await update.message.reply_text(f"openai ping error: {exc}")

async def openai_version(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        import openai
        await update.message.reply_text(f"openai version: {getattr(openai, '__version__', 'unknown')}")
    except Exception as exc:
        await update.message.reply_text(f"openai version error: {exc}")

async def build_version(update: Update, context: ContextTypes.DEFAULT_TYPE):
    build_tag = os.getenv("BUILD_TAG", "unknown")
    await update.message.reply_text(f"build tag: {build_tag}")

async def openai_simple(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info("openai_simple: command received")
    result = call_openai_hi()
    if result.get("ok"):
        text = result.get("text", "")
        duration_ms = result.get("duration_ms", "unknown")
        # Example before/after: empty response -> "(empty)"; text -> first 120 chars.
        preview = text[:120] if text else "(empty)"
        await update.message.reply_text(f"openai_simple ok in {duration_ms}ms: {preview}")
    else:
        await update.message.reply_text(
            f"openai_simple error: {result.get('error', 'unknown')}"
        )

async def xai_simple(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logging.info("xai_simple: command received")
    result = call_xai_hi()
    if result.get("ok"):
        text = result.get("text", "")
        duration_ms = result.get("duration_ms", "unknown")
        preview = text[:120] if text else "(empty)"
        await update.message.reply_text(f"xai_simple ok in {duration_ms}ms: {preview}")
    else:
        await update.message.reply_text(
            f"xai_simple error: {result.get('error', 'unknown')}"
        )

#setup bot loads message handler commands into application
def setup_bot() -> Application:
    environment = os.getenv("ENVIRONMENT", "development")
    runtime = detect_runtime()

    try: 
        if runtime == "cloud_run":
            # Example before/after: runtime=cloud_run -> TELEGRAM_KEY; runtime=codespaces -> TELEGRAM_DEV_KEY
            token = os.getenv('TELEGRAM_KEY')
        elif runtime == "codespaces":
            token = os.getenv('TELEGRAM_DEV_KEY')
        elif environment == 'development':
            token = os.getenv('TELEGRAM_DEV_KEY')
            print(f"DEBUG: Using TELEGRAM_DEV_KEY: {token}")


        else:
            token = os.getenv('TELEGRAM_KEY')
            print(f"DEBUG: Using TELEGRAM_KEY: {token}")
    except Exception as e:
        print(f"Error loading env.production variables: {e}")
        logging.error(f"Error loading env.production variables: {e}")
    if not token:
        raise ValueError("No Telegram token found; check environment variables.")
    
    global application, message_router # Add message_router to global declaration
    builder = Application.builder().token(token)
    if _is_general_edit_streaming_enabled():
        # Before example: updates were handled one-by-one, delaying /stop during streaming.
        # After example:  concurrent updates allow /stop while a stream is in progress.
        builder = builder.concurrent_updates(8)
    application = builder.build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("cook", bot_mode_switch_cook))
    application.add_handler(CommandHandler("log", bot_mode_switch_log))
    application.add_handler(CommandHandler("general", bot_mode_switch_general))
    application.add_handler(CommandHandler("1", bot_mode_switch_log))
    application.add_handler(CommandHandler("restart", restart))
    application.add_handler(CommandHandler("stop", stop_stream))
    # Before example: "/restart@chefbot" or " /restart" skipped; After example: those match too.
    application.add_handler(MessageHandler(filters.Regex(r"^\s*/restart(?:@\w+)?(\s|$)"), restart))
    application.add_handler(MessageHandler(filters.Regex(r"^\s*/cook(?:@\w+)?(\s|$)"), bot_mode_switch_cook))
    application.add_handler(MessageHandler(filters.Regex(r"^\s*/(log|1)(?:@\w+)?(\s|$)"), bot_mode_switch_log))
    application.add_handler(MessageHandler(filters.Regex(r"^\s*/general(?:@\w+)?(\s|$)"), bot_mode_switch_general))
    application.add_handler(MessageHandler(filters.Regex(r"^\s*/stop(?:@\w+)?(\s|$)"), stop_stream))
    application.add_handler(CommandHandler("openai_ping", openai_ping))
    application.add_handler(CommandHandler("openai_version", openai_version))
    application.add_handler(CommandHandler("build_version", build_version))
    application.add_handler(CommandHandler("openai_simple", openai_simple))
    application.add_handler(CommandHandler("xai_simple", xai_simple))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_message))
    application.add_handler(MessageHandler(filters.VIDEO, handle_message))
    application.add_handler(MessageHandler(filters.AUDIO | filters.VOICE, handle_message))  # Add this line


    return application

def run_bot_webhook_set():
    environment = os.getenv("ENVIRONMENT", "development")
    try:
        runtime = detect_runtime()
        app = setup_bot()
        if runtime == "cloud_run":
            webhook_url = get_webhook_url(runtime)
            if not webhook_url:
                raise ValueError(f"{get_webhook_env_var_name(runtime)} not set!")

            # Example before/after: TELEGRAM_WEBHOOK_URL unset -> "None"; set -> "https://service.run.app"
            logging.info(f"Using {get_webhook_env_var_name(runtime)}: {webhook_url}")
            app.run_webhook(
                listen="0.0.0.0",
                port=get_port(),
                url_path="webhook",
                webhook_url=f"{webhook_url}/webhook"
            )
        elif runtime == "codespaces":
            webhook_url = get_webhook_url(runtime)
            if webhook_url:
                # Example before/after: TELEGRAM_WEBHOOK_CODESPACE unset -> polling; set -> webhook in Codespaces.
                logging.info(f"Using {get_webhook_env_var_name(runtime)}: {webhook_url}")
                app.run_webhook(
                    listen="0.0.0.0",
                    port=get_port(),
                    url_path="webhook",
                    webhook_url=f"{webhook_url}/webhook"
                )
            else:
                app.run_polling()
        elif environment == 'production':
            webhook_url = get_webhook_url(runtime)
            if not webhook_url:
                raise ValueError(f"{get_webhook_env_var_name(runtime)} not set!")

            # Example before/after: TELEGRAM_WEBHOOK_URL unset -> "None"; set -> "https://service.run.app"
            logging.info(f"Using {get_webhook_env_var_name(runtime)}: {webhook_url}")
            app.run_webhook(
                listen="0.0.0.0",
                port=get_port(),
                url_path="webhook",
                webhook_url=f"{webhook_url}/webhook"
            )
        else:
            app.run_polling()
    except Exception as e:
        logging.error(f"Error in run_bot: {e}\n{traceback.format_exc()}")
        raise

async def send_message_job(context: ContextTypes.DEFAULT_TYPE):
    job_context = context.job.context
    user_id = job_context['user_id']
    message = job_context['message']
    
    if user_id in handlers_per_user:
        handler = handlers_per_user[user_id]
        await context.bot.send_message(chat_id=user_id, text=message)
    else:
        logging.warning(f"No AIHandler instance found for user_id: {user_id}")

def schedule_message(user_id, message):
    if not application:
        logging.error("Telegram bot application is not initialized.")
        return
    if user_id not in handlers_per_user:
        logging.warning(f"No AIHandler instance exists for user_id: {user_id}")
        return
    application.job_queue.run_once(
        send_message_job,
        when=0,
        context={'user_id': user_id, 'message': message}
    )
