from telegram.ext import Application, CommandHandler
from flask import Flask
import os

# ====== تنظیمات ======
TOKEN = "8576536563:AAEjIYNC0bjeHoAyum2MCPWvV3hJ8J1UN4s"
RENDER_URL = "https://omidre-bot.onrender.com"

# ====== Flask (برای Render) ======
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Bot is running!"

# ====== ربات تلگرام ======
async def start(update, context):
    await update.message.reply_text("سلام! من آنلاینم.")

async def hello(update, context):
    await update.message.reply_text("درود بر تو!")

app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("hello", hello))

# ====== اجرای Webhook ======
async def main():
    await app.bot.set_webhook(url=f"{RENDER_URL}/{TOKEN}")

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 8443)),
        url_path=TOKEN,
        webhook_url=f"{RENDER_URL}/{TOKEN}"
    )
