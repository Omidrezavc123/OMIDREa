from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import os
import asyncio

TOKEN = "8642125258:AAFYNTNEP2MGkYvDuFVyl_SzaBqPfFX0chE"
RENDER_URL = "https://omidrea-1.onrender.com"

app = Flask(__name__)

# ساخت Application بدون await
application = Application.builder().token(TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ربات با موفقیت روشن شد!")

application.add_handler(CommandHandler("start", start))

@app.route('/')
def home():
    return "OK"

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    # پردازش async update با اجرای مستقیم
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(application.process_update(update))
    loop.close()
    return 'OK'

if __name__ == '__main__':
    # تنظیم Webhook
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(application.bot.set_webhook(url=f"{RENDER_URL}/{TOKEN}"))
    loop.close()
    
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8443)))
