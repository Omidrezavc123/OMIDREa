import os
import asyncio
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = "8642125258:AAFYNTNEP2MGkYvDuFVyl_SzaBqPfFX0chE"
RENDER_URL = "https://omidrea-1.onrender.com"

app = Flask(__name__)
bot = Bot(token=TOKEN)
application = Application.builder().token(TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام")

application.add_handler(CommandHandler("start", start))

async def setup_webhook():
    await application.initialize()
    await application.start()
    await bot.set_webhook(url=f"{RENDER_URL}/{TOKEN}")

@app.route(f"/{TOKEN}", methods=["POST"])
async def webhook():
    data = request.get_json()
    update = Update.de_json(data, bot)
    await application.process_update(update)
    return "OK"

@app.route("/")
def index():
    return "Bot is running!"

if __name__ == "__main__":
    asyncio.run(setup_webhook())
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8443)))
