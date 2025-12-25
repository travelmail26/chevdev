import os
import sys
import logging
import traceback

# Add parent directory to path to import utilities
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv, dotenv_values
from utilities.history_messages import create_session_log_file # Adjust path if necessary

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
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)
import requests
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

def get_webhook_url():
    # Example before/after: TELEGRAM_WEBHOOK_URL unset -> error later; set -> https://service.run.app
    return os.getenv("TELEGRAM_WEBHOOK_URL")

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


        # Gather session information
        session_info = {
            'user_id': user_id,
            'chat_id': update.message.chat_id,
            'message_id': update.message.message_id,
            'timestamp': update.message.date.timestamp(),
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
            file = await context.bot.get_file(audio.file_id)
            audio_dir = "saved_audio"
            os.makedirs(audio_dir, exist_ok=True)
            local_path = f"{audio_dir}/{audio.file_id}.ogg"
            print(f"DEBUG: Downloading audio file to {local_path}")
            await file.download_to_drive(local_path)

            firebase_url = None
            try:
                firebase_url = firebase_get_media_url(local_path)
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
            file = await context.bot.get_file(photo.file_id)
            photo_dir = "saved_photos"
            os.makedirs(photo_dir, exist_ok=True)
            local_path = f"{photo_dir}/{photo.file_id}.jpg"
            await file.download_to_drive(local_path)
            firebase_url = None
            try:
                firebase_url = firebase_get_media_url(local_path)
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
            file = await context.bot.get_file(video.file_id)
            video_dir = "saved_videos"
            os.makedirs(video_dir, exist_ok=True)
            local_path = f"{video_dir}/{video.file_id}.mp4"
            await file.download_to_drive(local_path)
            firebase_url = None
            try:
                firebase_url = firebase_get_media_url(local_path)
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
    user_id = update.effective_user.id

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id # Get chat_id

    # Construct session_info from the update object
    session_info_for_restart = {
        'user_id': user_id,
        'chat_id': chat_id,
        'message_id': update.effective_message.message_id, # ID of the /restart message
        'timestamp': update.effective_message.date.timestamp(), # Timestamp of the /restart message
        'username': update.effective_user.username,
        'first_name': update.effective_user.first_name,
        'last_name': update.effective_user.last_name,
        'trigger_command': '/restart' # You can add custom info like this
    }
    logging.info(f"Restart command received. Session info for restart: {session_info_for_restart}")

    create_session_log_file(user_id)
    try:
        if user_id in handlers_per_user:
            handlers_per_user.pop(user_id)
            await update.message.reply_text(
                "Bot memory cleared for you. Restarting our conversation."
            )
            print(f"DEBUG: Cleared handler for user {user_id}")
        else:
            await update.message.reply_text(
                "No conversation history found for you to clear."
            )
        conversations.pop(user_id, None)
    except Exception as e:
        await update.message.reply_text(f"Error during restart: {str(e)}")

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
    application = Application.builder().token(token).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("restart", restart))
    application.add_handler(CommandHandler("openai_ping", openai_ping))
    application.add_handler(CommandHandler("openai_version", openai_version))
    application.add_handler(CommandHandler("build_version", build_version))
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
            webhook_url = get_webhook_url()
            if not webhook_url:
                raise ValueError("TELEGRAM_WEBHOOK_URL not set!")

            # Example before/after: TELEGRAM_WEBHOOK_URL unset -> "None"; set -> "https://service.run.app"
            logging.info(f"Using TELEGRAM_WEBHOOK_URL: {webhook_url}")
            app.run_webhook(
                listen="0.0.0.0",
                port=get_port(),
                url_path="webhook",
                webhook_url=f"{webhook_url}/webhook"
            )
        elif runtime == "codespaces":
            app.run_polling()
        elif environment == 'production':
            webhook_url = get_webhook_url()
            if not webhook_url:
                raise ValueError("TELEGRAM_WEBHOOK_URL not set!")

            # Example before/after: TELEGRAM_WEBHOOK_URL unset -> "None"; set -> "https://service.run.app"
            logging.info(f"Using TELEGRAM_WEBHOOK_URL: {webhook_url}")
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
