import os
from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes
import asyncio

BOT_TOKEN = "8642125258:AAFYNTNEP2MGkYvDuFVyl_SzaBqPfFX0chE"
RENDER_URL = "https://omidrea-1.onrender.com"

flask_app = Flask(__name__)
bot = Bot(token=BOT_TOKEN)
application = Application.builder().token(BOT_TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! ربات کار میکنه ✅")

application.add_handler(CommandHandler("start", start))

@flask_app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    data = request.get_json()
    update = Update.de_json(data, bot)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(application.process_update(update))
    loop.close()
    return "OK"

@flask_app.route("/")
def home():
    return "OK"

if __name__ == "__main__":
    # Webhook رو دستی تنظیم نکن - بذار با لینک دستی ست بشه
    port = int(os.environ.get("PORT", 10000))
    print("🤖 ربات راه اندازی شد!")
    flask_app.run(host="0.0.0.0", port=port)
