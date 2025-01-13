import os
import sys
import asyncio
import logging
from telegram import Update

# Configure logging
logging.getLogger('httpx').setLevel(logging.DEBUG)
logging.getLogger('telegram').setLevel(logging.DEBUG)
logging.getLogger('httpcore').setLevel(logging.DEBUG)
logging.basicConfig(level=logging.DEBUG)


logging.info("telegram_bot.py module imported.")


from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)

# Configure logging
logging.basicConfig(level=logging.DEBUG)

from chefwriter import AIHandler
from firebase import firebase_get_media_url

conversations = {}
handlers_per_user = {}

def get_user_handler(user_id):
    if user_id not in handlers_per_user:
        handlers_per_user[user_id] = AIHandler(user_id)
    return handlers_per_user[user_id]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logging.debug('start triggered in telegram_bot.py')
    await update.message.reply_text("Hello! I'm your AI assistant. How can I help you today?")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        logging.debug('Testing get() method')
        user_id = update.message.from_user.id
        user_handler = get_user_handler(user_id)

        # Photo
        if update.message.photo:
            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            photo_dir = "saved_photos"
            os.makedirs(photo_dir, exist_ok=True)
            local_path = f"{photo_dir}/{photo.file_id}.jpg"
            await file.download_to_drive(local_path)
            firebase_url = firebase_get_media_url(local_path)

            # Pass some string to AI
            user_input = f"[Photo received: {firebase_url}]"
            response = user_handler.agentchat(user_input)

            await update.message.reply_text("Photo processed successfully!")
            if response:
                await update.message.reply_text(response)
            return

        # Video
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

        # Text
        logging.debug('DEBUG: message handler triggered with message ', update.message.text)
        text_input = update.message.text
        if not text_input:
            await update.message.reply_text("I received an empty message. Please send text or media!")
            return

        response = user_handler.agentchat(text_input)
        if response:
            await update.message.reply_text(response)
        else:
            await update.message.reply_text("I couldn't generate a response. Please try again.")

    except Exception as e:
        await update.message.reply_text("An error occurred while processing your message.")
        print(f"Error in handle_message: {e}")


async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        handlers_per_user.clear()
        conversations.clear()
        await update.message.reply_text("Bot memory cleared. Restarting...")

        # Stop the bot gracefully
        await context.application.stop()  # Await this async function

        # Restart the bot process
        os.execv(sys.executable, [sys.executable] + sys.argv)
    except Exception as e:
        await update.message.reply_text(f"Error during restart: {str(e)}")


async def setup_bot():
    environment = os.getenv("ENVIRONMENT", "development")
    if environment == "production":
        token = os.getenv("TELEGRAM_KEY")
    else:
        token = os.getenv("TELEGRAM_DEV_KEY")

    if not token:
        raise ValueError("No Telegram token found; check environment variables.")

    application = Application.builder().token(token).build()

    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("restart", restart))

    # Register message handlers (text, photo, video)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_message))
    application.add_handler(MessageHandler(filters.VIDEO, handle_message))

    return application

async def monitor_polling():
    """Logs polling activity every 5 seconds."""
    while True:
        logging.info("Bot is polling for updates...")
        await asyncio.sleep(5)  # Log every 5 seconds

async def run_bot():
    """
    This is what main.py calls to actually start the bot.
    """
    app = await setup_bot()

    # Create a background task for monitoring polling
    polling_monitor_task = asyncio.create_task(monitor_polling())

    try:
        # Run the bot's polling
        await app.run_polling(allowed_updates=Update.ALL_TYPES)
    finally:
        # Ensure the polling monitor task is cancelled on shutdown
        polling_monitor_task.cancel()
        try:
            await polling_monitor_task
        except asyncio.CancelledError:
            logging.info("Polling monitor task cancelled.")

