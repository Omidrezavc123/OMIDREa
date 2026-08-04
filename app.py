import sqlite3
import random
import os
from flask import Flask, request
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
import asyncio

# ==================== CONFIG ====================
BOT_TOKEN = "8642125258:AAFYNTNEP2MGkYvDuFVyl_SzaBqPfFX0chE"
ADMIN_ID = 7832771827
RENDER_URL = "https://omidrea-1.onrender.com"

# ==================== FLASK ====================
flask_app = Flask(__name__)
bot = Bot(token=BOT_TOKEN)
application = Application.builder().token(BOT_TOKEN).build()

# ==================== DATABASE ====================
DB_PATH = "dart_cup.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS players (user_id INTEGER PRIMARY KEY, username TEXT, full_name TEXT, total_wins INTEGER DEFAULT 0, championships INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS tournaments (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, capacity INTEGER, stage TEXT DEFAULT 'waiting', status TEXT DEFAULT 'open', created_by INTEGER, winner_id INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS registrations (id INTEGER PRIMARY KEY AUTOINCREMENT, tournament_id INTEGER, user_id INTEGER, status TEXT DEFAULT 'pending', UNIQUE(tournament_id, user_id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS matches (id INTEGER PRIMARY KEY AUTOINCREMENT, tournament_id INTEGER, stage TEXT, player1_id INTEGER, player2_id INTEGER, player1_score INTEGER DEFAULT 0, player2_score INTEGER DEFAULT 0, winner_id INTEGER, status TEXT DEFAULT 'waiting', match_order INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS throws (id INTEGER PRIMARY KEY AUTOINCREMENT, match_id INTEGER, player_id INTEGER, throw_number INTEGER, score INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS boosters (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, booster_type TEXT, quantity INTEGER DEFAULT 0, UNIQUE(user_id, booster_type))''')
    conn.commit()
    conn.close()

def query(sql, params=(), fetchone=False, fetchall=False):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(sql, params)
    conn.commit()
    result = None
    if fetchone: result = c.fetchone()
    elif fetchall: result = c.fetchall()
    conn.close()
    return result

# ==================== KEYBOARDS ====================
def main_menu_keyboard(is_admin=False):
    keyboard = [
        [InlineKeyboardButton("🏆 جام و مسابقات", callback_data="cup_menu")],
        [InlineKeyboardButton("👤 پروفایل من", callback_data="my_profile")],
        [InlineKeyboardButton("📊 رتبه بندی", callback_data="leaderboard")],
        [InlineKeyboardButton("🎁 تقویتی های من", callback_data="my_boosters")],
        [InlineKeyboardButton("📋 قوانین بازی", callback_data="rules")],
    ]
    if is_admin:
        keyboard.append([InlineKeyboardButton("👑 پنل مدیریت", callback_data="admin_panel")])
    return InlineKeyboardMarkup(keyboard)

def cup_menu_keyboard(tournament_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ ثبت نام در جام", callback_data=f"register_{tournament_id}")],
        [InlineKeyboardButton("📋 جدول مسابقات", callback_data=f"bracket_{tournament_id}")],
        [InlineKeyboardButton("🎯 مسابقه من", callback_data=f"my_match_{tournament_id}")],
        [InlineKeyboardButton("👑 قهرمان جام", callback_data=f"champion_{tournament_id}")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")],
    ])

def admin_panel_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ ساخت جام جدید", callback_data="create_tournament")],
        [InlineKeyboardButton("👥 بازیکنان ثبت نامی", callback_data="pending_players")],
        [InlineKeyboardButton("🎲 قرعه کشی جام", callback_data="draw_tournament")],
        [InlineKeyboardButton("📋 مشاهده مسابقات", callback_data="view_matches")],
        [InlineKeyboardButton("🏆 قهرمان جام", callback_data="view_champion")],
        [InlineKeyboardButton("🎁 مدیریت تقویتی ها", callback_data="manage_boosters")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")],
    ])

# ==================== HELPERS ====================
def get_name(user):
    if user.username: return "@" + user.username
    elif user.full_name: return user.full_name
    return "User " + str(user.id)

def get_name_db(p):
    if not p: return "ناشناس"
    if p["username"]: return "@" + p["username"]
    if p["full_name"]: return p["full_name"]
    return "User " + str(p["user_id"])

def get_stages(n):
    stages = {2: ["فینال"], 4: ["نیمه نهایی", "فینال"], 8: ["یک چهارم نهایی", "نیمه نهایی", "فینال"], 16: ["یک هشتم نهایی", "یک چهارم نهایی", "نیمه نهایی", "فینال"]}
    for s in [16, 8, 4, 2]:
        if n >= s: return stages[s]
    return ["مرحله ۱", "فینال"]

# ==================== HANDLERS ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not query("SELECT * FROM players WHERE user_id = ?", (user.id,), fetchone=True):
        query("INSERT INTO players (user_id, username, full_name) VALUES (?, ?, ?)", (user.id, user.username, user.full_name))
    is_admin = (user.id == ADMIN_ID)
    await update.message.reply_text(f"🎯 سلام! به ربات جام دارت خوش آمدید!\n\n👤 {get_name(user)}", reply_markup=main_menu_keyboard(is_admin))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data
    user = update.effective_user
    is_admin = (user.id == ADMIN_ID)

    if data == "main_menu":
        await q.edit_message_text("📋 منوی اصلی:", reply_markup=main_menu_keyboard(is_admin))

    elif data == "cup_menu":
        t = query("SELECT * FROM tournaments WHERE status IN ('open', 'active') ORDER BY id DESC LIMIT 1", fetchone=True)
        if t:
            cnt = query("SELECT COUNT(*) as c FROM registrations WHERE tournament_id = ? AND status = 'approved'", (t["id"],), fetchone=True)["c"]
            await q.edit_message_text(f"🏆 جام دارت\n\n📋 نام جام: {t['name']}\n📊 مرحله: {t['stage']}\n👥 بازیکنان: {cnt}\n🎯 ظرفیت: {t['capacity']}", reply_markup=cup_menu_keyboard(t["id"]))
        else:
            await q.edit_message_text("❌ جام فعالی نیست.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]]))

    elif data.startswith("register_"):
        tid = int(data.split("_")[1])
        t = query("SELECT * FROM tournaments WHERE id = ?", (tid,), fetchone=True)
        if not t or t["status"] != "open":
            await q.answer("❌ در دسترس نیست!", show_alert=True); return
        if query("SELECT COUNT(*) as c FROM registrations WHERE tournament_id = ? AND status = 'approved'", (tid,), fetchone=True)["c"] >= t["capacity"]:
            await q.answer("❌ ظرفیت تکمیل شد!", show_alert=True); return
        try:
            query("INSERT OR IGNORE INTO registrations (tournament_id, user_id) VALUES (?, ?)", (tid, user.id))
            await q.answer("✅ ثبت نام شد!", show_alert=True)
        except:
            await q.answer("⚠️ قبلا ثبت نام کردید!", show_alert=True)

    elif data == "my_profile":
        p = query("SELECT * FROM players WHERE user_id = ?", (user.id,), fetchone=True)
        txt = f"👤 پروفایل:\n\n🆔 {get_name(user)}\n🏆 برد: {p['total_wins']}\n👑 قهرمانی: {p['championships']}" if p else "❌ یافت نشد!"
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]]))

    elif data == "leaderboard":
        pl = query("SELECT * FROM players ORDER BY championships DESC, total_wins DESC LIMIT 10", fetchall=True)
        txt = "📊 رتبه بندی:\n\n"
        for i, p in enumerate(pl, 1): txt += f"{i}. {get_name_db(p)}\n   🏆 {p['total_wins']} برد | 👑 {p['championships']} قهرمانی\n\n"
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]]))

    elif data == "rules":
        await q.edit_message_text("📋 قوانین:\n\n🎯 ۵ پرتاب\n🎲 امتیاز ۱-۶۰\n🏆 بیشتر = برنده\n🔄 برنده صعود\n👑 فینال = قهرمان", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]]))

    elif data == "admin_panel":
        if not is_admin: await q.answer("❌ دسترسی ندارید!", show_alert=True); return
        await q.edit_message_text("👑 پنل مدیریت:", reply_markup=admin_panel_keyboard())

    elif data == "create_tournament":
        if not is_admin: await q.answer("❌ غیرمجاز!", show_alert=True); return
        context.user_data["creating"] = True
        await q.edit_message_text("📝 نام جام را وارد کنید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لغو", callback_data="admin_panel")]]))

    elif data == "pending_players":
        if not is_admin: await q.answer("❌ غیرمجاز!", show_alert=True); return
        t = query("SELECT * FROM tournaments WHERE status = 'open' ORDER BY id DESC LIMIT 1", fetchone=True)
        if not t: await q.answer("❌ جام فعال ندارید!", show_alert=True); return
        pending = query("SELECT * FROM registrations WHERE tournament_id = ? AND status = 'pending'", (t["id"],), fetchall=True)
        if not pending:
            await q.edit_message_text("✅ بازیکنی در انتظار نیست.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")]]))
        else:
            txt = "👥 در انتظار تایید:\n\n"
            kb = []
            for r in pending:
                pn = get_name_db(query("SELECT * FROM players WHERE user_id = ?", (r["user_id"],), fetchone=True))
                txt += f"👤 {pn}\n"
                kb.append([InlineKeyboardButton(f"✅ {pn}", callback_data=f"approve_{r['id']}"), InlineKeyboardButton("❌ رد", callback_data=f"reject_{r['id']}")])
            kb.append([InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")])
            await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("approve_"):
        if not is_admin: return
        query("UPDATE registrations SET status = 'approved' WHERE id = ?", (int(data.split("_")[1]),))
        await q.answer("✅ تایید شد!", show_alert=True)
        q.data = "pending_players"; await button_handler(update, context)

    elif data.startswith("reject_"):
        if not is_admin: return
        query("DELETE FROM registrations WHERE id = ?", (int(data.split("_")[1]),))
        await q.answer("❌ رد شد!", show_alert=True)
        q.data = "pending_players"; await button_handler(update, context)

    elif data == "draw_tournament":
        if not is_admin: return
        t = query("SELECT * FROM tournaments WHERE status = 'open' ORDER BY id DESC LIMIT 1", fetchone=True)
        if not t: await q.answer("❌ جام فعال ندارید!", show_alert=True); return
        players = query("SELECT user_id FROM registrations WHERE tournament_id = ? AND status = 'approved'", (t["id"],), fetchall=True)
        if len(players) < 2: await q.answer("❌ حداقل ۲ بازیکن!", show_alert=True); return
        plist = [p["user_id"] for p in players]
        random.shuffle(plist)
        cs = get_stages(len(plist))[0]
        query("DELETE FROM matches WHERE tournament_id = ?", (t["id"],))
        mo = 0
        for i in range(0, len(plist), 2):
            if i + 1 < len(plist):
                query("INSERT INTO matches (tournament_id, stage, player1_id, player2_id, match_order) VALUES (?, ?, ?, ?, ?)", (t["id"], cs, plist[i], plist[i+1], mo))
                mo += 1
        query("UPDATE tournaments SET status = 'active', stage = ? WHERE id = ?", (cs, t["id"]))
        await q.edit_message_text(f"✅ قرعه کشی انجام شد!\n\n📊 {cs}\n👥 {len(plist)} بازیکن\n🎯 {mo} مسابقه", reply_markup=admin_panel_keyboard())

# ==================== TEXT HANDLER ====================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text

    if context.user_data.get("creating") and user.id == ADMIN_ID:
        context.user_data["tournament_name"] = text
        context.user_data["creating"] = False
        context.user_data["capacity"] = True
        await update.message.reply_text(f"✅ نام: {text}\n\n📝 تعداد نفرات:")
        return

    if context.user_data.get("capacity") and user.id == ADMIN_ID:
        try:
            cap = int(text)
            if cap < 2: await update.message.reply_text("❌ حداقل ۲!"); return
            name = context.user_data.get("tournament_name", "جام دارت")
            query("INSERT INTO tournaments (name, capacity, created_by) VALUES (?, ?, ?)", (name, cap, user.id))
            context.user_data["capacity"] = False
            await update.message.reply_text(f"✅ جام ساخته شد!\n\n📋 {name}\n👥 {cap} نفر", reply_markup=admin_panel_keyboard())
        except ValueError: await update.message.reply_text("❌ عدد معتبر!")

# ==================== WEBHOOK ROUTE ====================
@flask_app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(application.process_update(update))
    loop.close()
    return "OK"

@flask_app.route("/")
def home():
    return "OK"

# ==================== SETUP WEBHOOK ====================
async def setup_webhook():
    await application.initialize()
    await application.start()
    await bot.set_webhook(url=f"{RENDER_URL}/{BOT_TOKEN}")

# ==================== MAIN ====================
def main():
    init_db()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(setup_webhook())
    loop.close()
    
    print("🤖 ربات با Webhook راه اندازی شد!")
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
