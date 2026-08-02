from telegram.ext import Application, CommandHandler
from telegram import Update
from telegram.ext import ContextTypes
import os

TOKEN = "8642125258:AAFYNTNEP2MGkYvDuFVyl_SzaBqPfFX0chE"
RENDER_URL = "https://omidrea-bot.onrender.com"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام")

if __name__ == "__main__":
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    print(f"ربات شروع به کار کرد... آدرس: {RENDER_URL}")
    app.run_polling()
