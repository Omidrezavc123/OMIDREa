from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import os
import asyncio

TOKEN = "8576536563:AAEjIYNC0bjeHoAyum2MCPWvV3hJ8J1UN4s"
RENDER_URL = "https://omidrea-1.onrender.com"

app = Flask(__name__)
bot_app = Application.builder().token(TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! ربات آنلاین است.")

async def hello(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("درود بر تو!")

bot_app.add_handler(CommandHandler("start", start))
bot_app.add_handler(CommandHandler("hello", hello))

@app.route('/')
def home():
    return "OK"

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot_app.bot)
    asyncio.new_event_loop().run_until_complete(bot_app.process_update(update))
    return 'OK'

if __name__ == '__main__':
    asyncio.new_event_loop().run_until_complete(
        bot_app.bot.set_webhook(url=f"{RENDER_URL}/{TOKEN}")
    )
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8443)))
