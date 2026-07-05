from telegram.ext import Application, CommandHandler
import os

TOKEN = "8576536563:AAEjIYNC0bjeHoAyum2MCPWvV3hJ8J1UN4s"
RENDER_URL = "https://omidre-bot.onrender.com"

async def start(update, context):
    await update.message.reply_text("سلام! من آنلاینم.")

app = Application.builder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))

app.run_webhook(
    listen="0.0.0.0",
    port=int(os.environ.get("PORT", 8443)),
    url_path=TOKEN,
    webhook_url=f"{RENDER_URL}/{TOKEN}"
)
