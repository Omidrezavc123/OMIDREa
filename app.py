import os
import asyncio
from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes

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
    asyncio.run(application.process_update(update))
    return "OK"

@flask_app.route("/")
def home():
    return "OK"

async def main():
    await application.initialize()
    await application.start()
    await bot.initialize()
    # پاک کردن webhook قبلی
    await bot.delete_webhook()
    # تنظیم webhook جدید
    await bot.set_webhook(url=f"{RENDER_URL}/{BOT_TOKEN}")
    print("✅ Webhook set!")

if __name__ == "__main__":
    asyncio.run(main())
    print("🤖 ربات راه اندازی شد!")
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)
