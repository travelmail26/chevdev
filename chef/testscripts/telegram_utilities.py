# def send_telegram_message('user_id', text, application):
#     application.bot.send_message(chat_id='1275063227', text='test from send telegram', )


from telegram import Bot
import asyncio

# Your bot token
BOT_TOKEN = "7912564126:AAHpf0J1Ci1_jkIKuTfyuO6GyJ57v44_m00"

# The user ID to send the message to
USER_ID = 1275063227

# The message to send
MESSAGE = "Hello from your Telegram bot using python-telegram-bot!"

async def send_message():
    bot = Bot(token=BOT_TOKEN)
    await bot.send_message(chat_id=USER_ID, text=MESSAGE)

# Run the async function
asyncio.run(send_message())
