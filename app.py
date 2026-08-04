import os
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

BOT_TOKEN = "8642125258:AAFYNTNEP2MGkYvDuFVyl_SzaBqPfFX0chE"
ADMIN_ID = 7832771827
RENDER_URL = "https://omidrea-1.onrender.com"

flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "OK"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! ربات کار میکنه ✅")

def run_bot():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    print("🤖 ربات راه اندازی شد!")
    app.run_polling()

if __name__ == "__main__":
    Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    print(f"🌐 Flask on port {port}")
    flask_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
