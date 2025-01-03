from flask import Flask, request, jsonify  # <-- Not removed, but no longer used for local
import requests
import json
import os
import logging
import sys
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from chefwriter import AIHandler
from threading import Thread
from datetime import datetime
from pathlib import Path
#from testingscripts.accesschat import readchatfile, appendturn
from firebase import firebase_get_media_url
import traceback

# #Disable debug logging
# logging.getLogger('httpx').setLevel(logging.WARNING)
# logging.getLogger('telegram').setLevel(logging.WARNING)

# # Configure logging
# logging.basicConfig(
#     level=logging.INFO,
#     format="%(asctime)s - %(message)s",
#     handlers=[logging.StreamHandler()]  # Ensures output to console
#)

try:
    ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')

    if ENVIRONMENT == 'production':
        TOKEN = os.environ['TELEGRAM_KEY']
        print("Running in PRODUCTION mode")
    else:
        TOKEN = os.environ['TELEGRAM_DEV_KEY']
        print("Running in DEVELOPMENT mode")

    if not TOKEN:
        raise ValueError(f"No Telegram token found for {ENVIRONMENT} environment")

except KeyError as e:
    raise ValueError(f"Missing required token for {ENVIRONMENT} environment")
except Exception as e:
    raise

conversations = {}
handlers_per_user = {}

def get_user_handler(user_id):
    if user_id not in handlers_per_user:
        handlers_per_user[user_id] = AIHandler(user_id)
    return handlers_per_user[user_id]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        await update.message.reply_text('Hello! I am your AI assistant. How can I help you today?')
    except Exception as e:
        await update.message.reply_text("error in telegram start")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        message_info = {
            'chat_id': update.message.chat.id,
            'user_id': update.message.from_user.id,
            'username': update.message.from_user.username,
            'first_name': update.message.from_user.first_name,
            'message_id': update.message.message_id,
            'text': update.message.text
        }
        user_handler = get_user_handler(message_info['user_id'])

        if update.message.photo:
            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)

            photo_dir = 'saved_photos'
            os.makedirs(photo_dir, exist_ok=True)
            local_path = f"{photo_dir}/{photo.file_id}.jpg"

            await file.download_to_drive(local_path)
            firebase_url = firebase_get_media_url(local_path)
            message_info['text'] = f"[Image URL: {firebase_url}]"

            await update.message.reply_text("Photo processed successfully!")

        elif update.message.video:
            video = update.message.video
            file = await context.bot.get_file(video.file_id)

            video_dir = 'saved_videos'
            os.makedirs(video_dir, exist_ok=True)
            local_path = f"{video_dir}/{video.file_id}.mp4"

            await file.download_to_drive(local_path)
            firebase_url = firebase_get_media_url(local_path)
            message_info['text'] = f"[Video URL: {firebase_url}]"

            await update.message.reply_text("Video processed successfully!")

        elif not update.message.text:
            await update.message.reply_text("I received an empty message. Please send some text or a photo!")
            return

        response = user_handler.agentchat(message_info['text'])

        if not response or response.strip() == "":
            await update.message.reply_text("I apologize, but I couldn't generate a proper response. Please try again.")
            return

        await update.message.reply_text(response)
        

    except Exception as e:
        #logging.error(f"Error in handle_message: {e}")
        #logging.error(traceback.format_exc())
        await update.message.reply_text("An error occurred while processing your message. Please try again.")

        print('DEBUG: error in handle_message', e)



async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        #logging.info("Restart command received. Clearing memory and restarting...")
        handlers_per_user.clear()
        conversations.clear()
        await update.message.reply_text("Bot memory cleared and restarting...")
        os.execv(sys.executable, ['python'] + sys.argv)
    except Exception as e:
        #logging.error(f"Error during restart: {e}")
        await update.message.reply_text(f"Error during restart: {str(e)}")


async def setup_bot():
    application = Application.builder().token(TOKEN).build()
    await application.initialize()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_message))
    application.add_handler(MessageHandler(filters.VIDEO,handle_message))
    application.add_handler(CommandHandler("restart", restart))
    return application

async def run_bot():
    application = None
    try:
        application = await setup_bot()
        # Run the bot via polling (no Flask server, no keep_polling)
        await application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    except Exception as e:
        print(f"Error during bot execution: {e}")
        raise
    finally:
        if application:
            try:
                await application.shutdown()
                await application.stop()
            except Exception as e:
                print(f"Error during shutdown: {e}")
