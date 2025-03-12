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

#webhook_url = os.getenv("TELEGRAM_WEBHOOK_URL")

from chefwriter import AIHandler
from firebase import firebase_get_media_url

# Set up logging
logging.basicConfig(level=logging.DEBUG)

logging.debug("telegram_bot.py module loaded.")

conversations = {}
handlers_per_user = {}

def get_user_handler(user_id):
    if user_id not in handlers_per_user:
        handlers_per_user[user_id] = AIHandler(user_id)
    return handlers_per_user[user_id]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello! I'm your AI assistant. How can I help you today?")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.message.from_user.id
        user_handler = get_user_handler(user_id)

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

        if update.message.video:
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

        text_input = update.message.text or ""
        if not text_input.strip():
            await update.message.reply_text("I received an empty message. Please send text or media!")
            return

        response = user_handler.agentchat(text_input)
        buffer = ""
        for chunk in response:
            # Filter out invalid chunks at Telegram level
            if chunk and isinstance(chunk, str) and chunk.strip():
                logging.debug(f"Sending chunk to Telegram: '{chunk}'")
                buffer += chunk
                # Send buffer when it exceeds 30 characters
                while len(buffer) >= 300:
                    message = buffer[:300]  # Take first 30 characters
                    logging.debug(f"Sending buffered message: '{message}'")
                    await update.message.reply_text(message)
                    buffer = buffer[300:]  # Remove sent portion
                #await update.message.reply_text(chunk)
            else:
                logging.warning(f"Filtered out invalid chunk: '{chunk}'")
        if buffer:
            logging.debug(f"Sending remaining buffered message: '{buffer}'")
            await update.message.reply_text(buffer)

    except Exception as e:
        error_message = f"Error in handle_message: {e}\n{traceback.format_exc()}"
        logging.error(error_message)
        await update.message.reply_text("An error occurred while processing your message.")

        # text_input = update.message.text or ""
        # if not text_input.strip():
        #     await update.message.reply_text("I received an empty message. Please send text or media!")
        #     return


        # response = user_handler.agentchat(text_input)
        # if response:
        #     await update.message.reply_text(response)
        # else:
        #     await update.message.reply_text("I couldn't generate a response. Please try again.")

    except Exception as e:
        error_message = f"Error in handle_message: {e}\n{traceback.format_exc()}"
        logging.error(error_message)
        await update.message.reply_text("An error occurred while processing your message.")

async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        handlers_per_user.pop(user_id, None)
        conversations.pop(user_id, None)
        await update.message.reply_text(
            "Bot memory cleared for you. Restarting our conversation. Please try again."
        )
    except Exception as e:
        await update.message.reply_text(f"Error during restart: {str(e)}")

def setup_bot() -> Application:
    """
    Build and return the Application *synchronously*.
    We'll let python-telegram-bot handle all async details internally.
    """
    environment = os.getenv("ENVIRONMENT", "development")
    #token = os.getenv("TELEGRAM_KEY")


    # Check if the .env.production file exists
    try: 
        
        env_production_path = os.path.join(os.path.dirname(__file__), ".env.production")
        print ('DEBUG: testing env.production variables', env_production_path)
        if os.path.exists(env_production_path):
        # Load the environment variables from the .env.production file
            env_production_path_variables = dotenv_values(env_production_path)
            print ('DEBUG: testing env.production variables', env_production_path_variables)
        
        # Get the ENVIRONMENT variable
        environment = env_production_path_variables.get('ENVIRONMENT', 'development')        
        # Check the value of ENVIRONMENT and get the appropriate TELEGRAM_KEY


        if environment == 'development':
            print ('DEBUG: testing env.production variables loaded', environment)
            token = os.getenv('TELEGRAM_DEV_KEY')
        else:
            token = os.getenv('TELEGRAM_KEY')
    except Exception as e:
        print(f"Error loading env.production variables: {e}")
        logging.error(f"Error loading env.production variables: {e}")
    if not token:
        raise ValueError("No Telegram token found; check environment variables.")
    

    application = Application.builder().token(token).build()

    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("restart", restart))

    # Register message handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_message))
    application.add_handler(MessageHandler(filters.VIDEO, handle_message))

    return application


def run_bot():
    try:
        app = setup_bot()

        # Instead of checking environment == 'development', 
        # assume we always do webhooks:
        #webhook_url = 'https://chef-bot-209538059512.us-central1.run.app'
        webhook_url = 'https://fuzzy-happiness-7jgw66wxqqhg77-8080.app.github.dev'
        #webhook_url = os.getenv("TELEGRAM_WEBHOOK_URL")
        if not webhook_url:
            raise ValueError("TELEGRAM_WEBHOOK_URL not set!")
        
        # This listens on port 8080 inside the container
        # and sets up the public webhook with the domain above
        app.run_webhook(
            listen="0.0.0.0",
            port=8080,
            url_path="webhook",
            webhook_url=f"{webhook_url}/webhook"
        )
    except Exception as e:
        logging.error(f"Error in run_bot: {e}\n{traceback.format_exc()}")
        raise

# def run_bot():
#     """
#     Synchronous function that sets up the bot & calls run_polling().
#     Blocks until the bot is shut down, returning control to main.py afterward.
#     """
#     try:
#         app = setup_bot()
#         # run_polling() is a synchronous call that manages the event loop internally.
#         app.run_polling(allowed_updates=Update.ALL_TYPES)
#     except Exception as e:
#         logging.error(f"Error in run_bot: {e}\n{traceback.format_exc()}")
#         raise
