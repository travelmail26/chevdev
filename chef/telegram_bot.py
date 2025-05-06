import os
import sys
import logging
import traceback
from dotenv import load_dotenv, dotenv_values

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)

# Import AIHandler again
from chefwriter import AIHandler
from firebase import firebase_get_media_url # Add this import back

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


def get_user_handler(user_id, application_data, session_info):
    if user_id not in handlers_per_user:
        # Remove the 'session_info' argument from the AIHandler initialization
        handlers_per_user[user_id] = AIHandler(user_id=user_id, application=application_data)
        print(f"DEBUG: Created new AIHandler for user {user_id}")
    return handlers_per_user[user_id]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello! I'm your AI assistant. How can I help you today?")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.message.from_user.id
        application_data = context.application
        
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

        # Pass session_info to get_user_handler
        user_handler = get_user_handler(user_id, application_data, session_info)

        user_input = "" # Initialize user_input

        if update.message.audio or update.message.voice:
            # Handle audio or voice messages
            audio = update.message.audio or update.message.voice
            file = await context.bot.get_file(audio.file_id)
            audio_dir = "saved_audio"
            os.makedirs(audio_dir, exist_ok=True)
            local_path = f"{audio_dir}/{audio.file_id}.ogg"
            print(f"DEBUG: Downloading audio file to {local_path}")
            await file.download_to_drive(local_path)
            # Set input for agentchat, transcription/analysis happens there
            user_input = f"[Audio received: {local_path}]"
            # Optional: Acknowledge receipt immediately if processing might take time
            # await update.message.reply_text("Processing audio...")

        elif update.message.photo:
            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            photo_dir = "saved_photos"
            os.makedirs(photo_dir, exist_ok=True)
            local_path = f"{photo_dir}/{photo.file_id}.jpg"
            await file.download_to_drive(local_path)
            firebase_url = firebase_get_media_url(local_path)
            user_input = f"[Photo received: {firebase_url}]"
            # Optional: Acknowledge receipt
            # await update.message.reply_text("Processing photo...")

        elif update.message.video:
            video = update.message.video
            file = await context.bot.get_file(video.file_id)
            video_dir = "saved_videos"
            os.makedirs(video_dir, exist_ok=True)
            local_path = f"{video_dir}/{video.file_id}.mp4"
            await file.download_to_drive(local_path)
            firebase_url = firebase_get_media_url(local_path)
            user_input = f"[Video received: {firebase_url}]"
            # Optional: Acknowledge receipt
            # await update.message.reply_text("Processing video...")

        else: # Text messages
            user_input = update.message.text or ""
            # Check for empty text *only* in this block
            if not user_input.strip():
                await update.message.reply_text("I received an empty message. Please send text!")
                return # Return only if text is empty

        # If user_input is still empty here, it means no handler matched or an issue occurred.
        if not user_input:
             logging.warning("handle_message reached agentchat call with no user_input set.")
             # Avoid sending a message if the initial message was empty text (already handled)
             if not (update.message.text is not None and not update.message.text.strip()):
                 await update.message.reply_text("Could not process the message type.")
             return

        # Centralized call to agentchat and response handling for all types
        #status user handler class agent chat rather than passing the message
        response = user_handler.agentchat(user_input)


        print (f"DEBUG telegram_bot: User {user_id} input: {user_input}")
        print (f"DEBUG telegram_bot: User {user_id} response: {response}")

        return response
        
        ##buffer and send message

        # buffer = ""
        # # Process the response generator (synchronous logic)
        # for chunk in response:
        #     if chunk and isinstance(chunk, str) and chunk.strip():
        #         buffer += chunk
        #         # Send message parts when buffer reaches a certain size
        #         while len(buffer) >= 300: # Example threshold
        #             message_part = buffer[:300]
        #             try:
        #                 await update.message.reply_text(message_part)
        #                 buffer = buffer[300:]
        #             except Exception as telegram_error:
        #                 logging.error(f"Telegram API error sending chunk: {telegram_error}")
        #                 break # Exit the inner while loop on error

        # # Send any remaining part in the buffer
        # if buffer.strip():
        #     try:
        #         await update.message.reply_text(buffer)
        #     except Exception as telegram_error:
        #         logging.error(f"Telegram API error sending final buffer: {telegram_error}")

    except Exception as e:
        error_message = f"Error in handle_message: {e}\n{traceback.format_exc()}"
        logging.error(error_message)
        await update.message.reply_text("An error occurred while processing your message.")

async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
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

#setup bot loads message handler commands into application
def setup_bot() -> Application:
    environment = os.getenv("ENVIRONMENT", "development")
    print('DEBUG: setup bot triggered', environment)

    try: 
        if environment == 'development':
            print ('DEBUG: Production environment detected')
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
    
    global application
    application = Application.builder().token(token).build()
    print('DEBUG: telegram application', application)
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("restart", restart))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_message))
    application.add_handler(MessageHandler(filters.VIDEO, handle_message))
    application.add_handler(MessageHandler(filters.AUDIO | filters.VOICE, handle_message))  # Add this line


    return application

def run_bot_webhook_set():
    try:
        app = setup_bot()
        webhook_url = 'https://fuzzy-happiness-7jgw66wxqqhg77-8080.app.github.dev'
        if not webhook_url:
            raise ValueError("TELEGRAM_WEBHOOK_URL not set!")
        
        app.run_webhook(
            listen="0.0.0.0",
            port=8080,
            url_path="webhook",
            webhook_url=f"{webhook_url}/webhook"
        )
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
