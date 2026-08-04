import os
from flask import Flask, request
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.request import HTTPXRequest
import asyncio

BOT_TOKEN = "8642125258:AAFYNTNEP2MGkYvDuFVyl_SzaBqPfFX0chE"
RENDER_URL = "https://omidrea-1.onrender.com"

# ==================== پروکسی ====================
# یه پروکسی HTTP رایگان (اگه کار نکرد، عوضش کن)
PROXY_URL = "http://103.129.222.98:8080"  # پروکسی HTTP رایگان

# ساخت request با پروکسی
request = HTTPXRequest(
    proxy_url=PROXY_URL,
    read_timeout=30,
    write_timeout=30,
    connect_timeout=30,
    pool_timeout=30,
)

flask_app = Flask(__name__)
bot = Bot(token=BOT_TOKEN, request=request)
application = Application.builder().token(BOT_TOKEN).request(request).build()

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
    async def init_app():
        await application.initialize()
        await application.start()
        await bot.initialize()
        await bot.set_webhook(url=f"{RENDER_URL}/{BOT_TOKEN}")
        print("✅ Webhook set!")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(init_app())
    loop.close()
    
    print("🤖 ربات راه اندازی شد!")
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)
