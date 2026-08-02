from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import os
import asyncio

TOKEN = "8642125258:AAFYNTNEP2MGkYvDuFVyl_SzaBqPfFX0chE"
PORT = int(os.environ.get("PORT", 8443))

app = Flask(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام")

@app.route('/')
def home():
    return "OK"

async def main():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    await application.initialize()
    await application.start()
    # اجرای Flask در thread جدا
    import threading
    flask_thread = threading.Thread(target=app.run, kwargs={"host": "0.0.0.0", "port": PORT})
    flask_thread.start()
    # اجرای Polling
    await application.updater.start_polling()
    await application.updater.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())
