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
        # Pass session_info to AIHandler constructor
        handlers_per_user[user_id] = AIHandler(user_id=user_id, application=application_data, session_info=session_info)
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

        user_input = ""
        if update.message.photo:
            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            photo_dir = "saved_photos"
            os.makedirs(photo_dir, exist_ok=True)
            local_path = f"{photo_dir}/{photo.file_id}.jpg"
            await file.download_to_drive(local_path)

            firebase_url = firebase_get_media_url(local_path)
            user_input = f"[Photo received: {firebase_url}]"
            response = user_handler.agentchat(user_input)

            await update.message.reply_text("Photo processed successfully!")
            if response:
                await update.message.reply_text(response)
            return

        elif update.message.video:
            video = update.message.video
            file = await context.bot.get_file(video.file_id)
            video_dir = "saved_videos"
            os.makedirs(video_dir, exist_ok=True)
            local_path = f"{video_dir}/{video.file_id}.mp4"
            await file.download_to_drive(local_path)

            firebase_url = firebase_get_media_url(local_path)
            user_input = f"[Video received: {firebase_url}]"
            response = user_handler.agentchat(user_input)

            await update.message.reply_text("Video processed successfully!")
            if response:
                await update.message.reply_text(response)
            return

        else:
            user_input = update.message.text or ""

        if not user_input.strip():
            await update.message.reply_text("I received an empty message. Please send text or media!")
            return

        response_generator = user_handler.agentchat(user_input)

        buffer = ""
        async for chunk in response_generator:
            if chunk and isinstance(chunk, str) and chunk.strip():
                buffer += chunk
                while len(buffer) >= 300:
                    message_part = buffer[:300]
                    try:
                        await update.message.reply_text(message_part)
                        buffer = buffer[300:]
                    except Exception as telegram_error:
                        logging.error(f"Telegram API error sending chunk: {telegram_error}")
                        break

        if buffer.strip():
            try:
                await update.message.reply_text(buffer)
            except Exception as telegram_error:
                logging.error(f"Telegram API error sending final buffer: {telegram_error}")

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
            token = os.getenv('TELEGRAM_DEV_KEY')
        else:
            token = os.getenv('TELEGRAM_KEY')
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
