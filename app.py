import sqlite3
import random
import os
import threading
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# ==================== CONFIG ====================
BOT_TOKEN = "8642125258:AAFYNTNEP2MGkYvDuFVyl_SzaBqPfFX0chE"
ADMIN_ID = 7832771827
RENDER_URL = "https://omidrea-1.onrender.com"  # آدرس سرویس رندر

# ==================== FLASK ====================
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "OK"

# ==================== DATABASE ====================
DB_PATH = "dart_cup.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS players (
        user_id INTEGER PRIMARY KEY, username TEXT, full_name TEXT,
        total_wins INTEGER DEFAULT 0, championships INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS tournaments (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
        capacity INTEGER NOT NULL, stage TEXT DEFAULT 'waiting',
        status TEXT DEFAULT 'open', created_by INTEGER, winner_id INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS registrations (
        id INTEGER PRIMARY KEY AUTOINCREMENT, tournament_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL, status TEXT DEFAULT 'pending',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(tournament_id, user_id)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT, tournament_id INTEGER NOT NULL,
        stage TEXT NOT NULL, player1_id INTEGER, player2_id INTEGER,
        player1_score INTEGER DEFAULT 0, player2_score INTEGER DEFAULT 0,
        winner_id INTEGER, status TEXT DEFAULT 'waiting', match_order INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS throws (
        id INTEGER PRIMARY KEY AUTOINCREMENT, match_id INTEGER NOT NULL,
        player_id INTEGER NOT NULL, throw_number INTEGER NOT NULL,
        score INTEGER NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS boosters (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
        booster_type TEXT NOT NULL, quantity INTEGER DEFAULT 0,
        UNIQUE(user_id, booster_type)
    )''')
    
    conn.commit()
    conn.close()

def query(sql, params=(), fetchone=False, fetchall=False):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(sql, params)
    conn.commit()
    result = None
    if fetchone:
        result = c.fetchone()
    elif fetchall:
        result = c.fetchall()
    conn.close()
    return result

# ==================== KEYBOARDS ====================
def main_menu_keyboard(is_admin=False):
    keyboard = []
    keyboard.append([InlineKeyboardButton("🏆 جام و مسابقات", callback_data="cup_menu")])
    keyboard.append([InlineKeyboardButton("👤 پروفایل من", callback_data="my_profile")])
    keyboard.append([InlineKeyboardButton("📊 رتبه بندی", callback_data="leaderboard")])
    keyboard.append([InlineKeyboardButton("🎁 تقویتی های من", callback_data="my_boosters")])
    keyboard.append([InlineKeyboardButton("📋 قوانین بازی", callback_data="rules")])
    
    if is_admin:
        keyboard.append([InlineKeyboardButton("👑 پنل مدیریت", callback_data="admin_panel")])
    
    return InlineKeyboardMarkup(keyboard)

def cup_menu_keyboard(tournament_id):
    keyboard = [
        [InlineKeyboardButton("✅ ثبت نام در جام", callback_data=f"register_{tournament_id}")],
        [InlineKeyboardButton("📋 جدول مسابقات", callback_data=f"bracket_{tournament_id}")],
        [InlineKeyboardButton("🎯 مسابقه من", callback_data=f"my_match_{tournament_id}")],
        [InlineKeyboardButton("👑 قهرمان جام", callback_data=f"champion_{tournament_id}")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)

def admin_panel_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ ساخت جام جدید", callback_data="create_tournament")],
        [InlineKeyboardButton("👥 بازیکنان ثبت نامی", callback_data="pending_players")],
        [InlineKeyboardButton("🎲 قرعه کشی جام", callback_data="draw_tournament")],
        [InlineKeyboardButton("📋 مشاهده مسابقات", callback_data="view_matches")],
        [InlineKeyboardButton("🏆 قهرمان جام", callback_data="view_champion")],
        [InlineKeyboardButton("🎁 مدیریت تقویتی ها", callback_data="manage_boosters")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)

# ==================== HELPERS ====================
def get_player_name(user):
    if user.username:
        return "@" + user.username
    elif user.full_name:
        return user.full_name
    return "User " + str(user.id)

def get_player_name_from_db(player):
    if not player:
        return "ناشناس"
    if player["username"]:
        return "@" + player["username"]
    if player["full_name"]:
        return player["full_name"]
    return "User " + str(player["user_id"])

def get_stages(total_players):
    stages = {
        2: ["فینال"],
        4: ["نیمه نهایی", "فینال"],
        8: ["یک چهارم نهایی", "نیمه نهایی", "فینال"],
        16: ["یک هشتم نهایی", "یک چهارم نهایی", "نیمه نهایی", "فینال"],
        32: ["یک شانزدهم نهایی", "یک هشتم نهایی", "یک چهارم نهایی", "نیمه نهایی", "فینال"],
    }
    for size in [32, 16, 8, 4, 2]:
        if total_players >= size:
            return stages[size]
    return ["مرحله ۱", "فینال"]

# ==================== HANDLERS ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    existing = query("SELECT * FROM players WHERE user_id = ?", (user.id,), fetchone=True)
    if not existing:
        query("INSERT INTO players (user_id, username, full_name) VALUES (?, ?, ?)",
              (user.id, user.username, user.full_name))
    
    is_admin = (user.id == ADMIN_ID)
    await update.message.reply_text(
        "🎯 به ربات جام حذفی دارت خوش آمدید!\n\n"
        "👤 " + get_player_name(user) + "\n\n"
        "🌐 سرور: " + RENDER_URL + "\n\n"
        "از منوی زیر انتخاب کنید:",
        reply_markup=main_menu_keyboard(is_admin)
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_data = update.callback_query
    await query_data.answer()
    data = query_data.data
    user = update.effective_user
    is_admin = (user.id == ADMIN_ID)
    
    # ========== منوی اصلی ==========
    if data == "main_menu":
        await query_data.edit_message_text(
            "📋 منوی اصلی:\n🌐 " + RENDER_URL,
            reply_markup=main_menu_keyboard(is_admin)
        )
    
    # ========== منوی جام ==========
    elif data == "cup_menu":
        tournament = query(
            "SELECT * FROM tournaments WHERE status IN ('open', 'active') ORDER BY id DESC LIMIT 1",
            fetchone=True
        )
        if tournament:
            players_count = query(
                "SELECT COUNT(*) as count FROM registrations WHERE tournament_id = ? AND status = 'approved'",
                (tournament["id"],), fetchone=True
            )["count"]
            
            text = "🏆 جام دارت\n\n"
            text += "📋 نام جام: " + tournament["name"] + "\n"
            text += "📊 مرحله: " + tournament["stage"] + "\n"
            text += "👥 تعداد بازیکنان: " + str(players_count) + "\n"
            text += "🎯 ظرفیت: " + str(tournament["capacity"]) + "\n"
            text += "🌐 سرور: " + RENDER_URL + "\n"
            
            await query_data.edit_message_text(text, reply_markup=cup_menu_keyboard(tournament["id"]))
        else:
            keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]]
            await query_data.edit_message_text(
                "❌ هیچ جام فعالی وجود ندارد.\n🌐 " + RENDER_URL,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    
    # ========== ثبت نام ==========
    elif data.startswith("register_"):
        tournament_id = int(data.split("_")[1])
        tournament = query("SELECT * FROM tournaments WHERE id = ?", (tournament_id,), fetchone=True)
        
        if not tournament or tournament["status"] != "open":
            await query_data.answer("❌ این جام در دسترس نیست!", show_alert=True)
            return
        
        approved = query(
            "SELECT COUNT(*) as count FROM registrations WHERE tournament_id = ? AND status = 'approved'",
            (tournament_id,), fetchone=True
        )["count"]
        
        if approved >= tournament["capacity"]:
            await query_data.answer("❌ ظرفیت جام تکمیل شده است!", show_alert=True)
            return
        
        try:
            query("INSERT OR IGNORE INTO registrations (tournament_id, user_id) VALUES (?, ?)",
                  (tournament_id, user.id))
            await query_data.answer("✅ ثبت نام شما انجام شد. منتظر تایید ادمین باشید.", show_alert=True)
        except:
            await query_data.answer("⚠️ شما قبلا ثبت نام کرده اید!", show_alert=True)
    
    # ========== پروفایل ==========
    elif data == "my_profile":
        player = query("SELECT * FROM players WHERE user_id = ?", (user.id,), fetchone=True)
        if player:
            text = "👤 پروفایل شما:\n\n"
            text += "🆔 نام: " + get_player_name(user) + "\n"
            text += "🏆 تعداد برد: " + str(player["total_wins"]) + "\n"
            text += "👑 تعداد قهرمانی: " + str(player["championships"]) + "\n"
            text += "🌐 سرور: " + RENDER_URL + "\n"
            
            boosters = query("SELECT * FROM boosters WHERE user_id = ? AND quantity > 0",
                             (user.id,), fetchall=True)
            if boosters:
                text += "\n🎁 تقویتی های شما:\n"
                emoji_map = {"accuracy": "🎯", "power": "🔥", "luck": "🍀"}
                name_map = {"accuracy": "دقت", "power": "قدرت", "luck": "شانس"}
                for b in boosters:
                    text += emoji_map.get(b["booster_type"], "") + " "
                    text += name_map.get(b["booster_type"], "") + ": "
                    text += str(b["quantity"]) + " عدد\n"
        else:
            text = "❌ پروفایل شما یافت نشد!"
        
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]]
        await query_data.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    # ========== رتبه بندی ==========
    elif data == "leaderboard":
        players = query(
            "SELECT * FROM players ORDER BY championships DESC, total_wins DESC LIMIT 10",
            fetchall=True
        )
        text = "📊 رتبه بندی بازیکنان:\n\n"
        for i, p in enumerate(players, 1):
            name = get_player_name_from_db(p)
            text += str(i) + ". " + name + "\n"
            text += "   🏆 برد: " + str(p["total_wins"]) + " | 👑 قهرمانی: " + str(p["championships"]) + "\n\n"
        text += "🌐 " + RENDER_URL
        
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]]
        await query_data.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    # ========== تقویتی های من ==========
    elif data == "my_boosters":
        boosters = query(
            "SELECT * FROM boosters WHERE user_id = ? AND quantity > 0",
            (user.id,), fetchall=True
        )
        
        emoji_map = {"accuracy": "🎯", "power": "🔥", "luck": "🍀"}
        name_map = {"accuracy": "دقت", "power": "قدرت", "luck": "شانس"}
        
        if boosters:
            text = "🎁 تقویتی های شما:\n\n"
            for b in boosters:
                text += emoji_map.get(b["booster_type"], "") + " "
                text += name_map.get(b["booster_type"], "") + ": "
                text += str(b["quantity"]) + " عدد\n"
        else:
            text = "❌ شما هیچ تقویتی ندارید!"
        
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]]
        await query_data.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    # ========== قوانین ==========
    elif data == "rules":
        text = (
            "📋 قوانین جام حذفی دارت:\n\n"
            "🎯 هر بازیکن ۵ پرتاب دارد\n"
            "🎲 امتیازها تصادفی بین ۱ تا ۶۰ است\n"
            "🏆 بازیکن با امتیاز بیشتر برنده می‌شود\n"
            "🔄 برنده به مرحله بعد صعود می‌کند\n"
            "👑 برنده فینال قهرمان جام می‌شود\n\n"
            "🎁 تقویتی‌ها:\n"
            "🎯 دقت: +۱۰ امتیاز\n"
            "🔥 قدرت: +۱۵ امتیاز\n"
            "🍀 شانس: امتیاز تصادفی ۱۰ تا ۳۰\n\n"
            "⚠️ مساوی: پرتاب اضافه تا مشخص شدن برنده\n\n"
            "🌐 " + RENDER_URL
        )
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]]
        await query_data.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    # ========== جدول مسابقات ==========
    elif data.startswith("bracket_"):
        tournament_id = int(data.split("_")[1])
        tournament = query("SELECT * FROM tournaments WHERE id = ?", (tournament_id,), fetchone=True)
        
        if not tournament:
            await query_data.answer("❌ جام یافت نشد!", show_alert=True)
            return
        
        matches = query(
            "SELECT * FROM matches WHERE tournament_id = ? ORDER BY match_order",
            (tournament_id,), fetchall=True
        )
        
        status_map = {"waiting": "⏳", "active": "🎯", "finished": "✅"}
        
        text = "📋 جدول مسابقات\n"
        text += "🏆 " + tournament["name"] + "\n"
        text += "📊 مرحله: " + tournament["stage"] + "\n\n"
        
        current_stage = None
        for m in matches:
            if m["stage"] != current_stage:
                current_stage = m["stage"]
                text += "\n--- " + current_stage + " ---\n\n"
            
            p1 = query("SELECT * FROM players WHERE user_id = ?", (m["player1_id"],), fetchone=True)
            p2 = query("SELECT * FROM players WHERE user_id = ?", (m["player2_id"],), fetchone=True)
            p1_name = get_player_name_from_db(p1)
            p2_name = get_player_name_from_db(p2)
            
            text += status_map.get(m["status"], "❓") + " " + p1_name
            text += " VS " + p2_name + "\n"
            if m["status"] == "finished":
                text += "   📊 " + str(m["player1_score"]) + " - " + str(m["player2_score"]) + "\n"
        
        text += "\n🌐 " + RENDER_URL
        
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="cup_menu")]]
        await query_data.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    # ========== قهرمان جام ==========
    elif data.startswith("champion_"):
        tournament_id = int(data.split("_")[1])
        tournament = query("SELECT * FROM tournaments WHERE id = ?", (tournament_id,), fetchone=True)
        
        if tournament and tournament["winner_id"]:
            winner = query("SELECT * FROM players WHERE user_id = ?", (tournament["winner_id"],), fetchone=True)
            text = "👑 قهرمان جام\n\n"
            text += "🏆 " + tournament["name"] + "\n\n"
            text += "👤 " + get_player_name_from_db(winner) + "\n"
        else:
            text = "❌ هنوز قهرمانی مشخص نشده است!"
        
        text += "\n🌐 " + RENDER_URL
        
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="cup_menu")]]
        await query_data.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    # ========== مسابقه من ==========
    elif data.startswith("my_match_"):
        tournament_id = int(data.split("_")[2])
        match = query(
            "SELECT * FROM matches WHERE tournament_id = ? AND (player1_id = ? OR player2_id = ?) AND status != 'finished' ORDER BY id LIMIT 1",
            (tournament_id, user.id, user.id), fetchone=True
        )
        
        if not match:
            await query_data.answer("❌ شما مسابقه فعالی ندارید!", show_alert=True)
            return
        
        p1 = query("SELECT * FROM players WHERE user_id = ?", (match["player1_id"],), fetchone=True)
        p2 = query("SELECT * FROM players WHERE user_id = ?", (match["player2_id"],), fetchone=True)
        
        text = "🎯 مسابقه شما\n\n"
        text += "📊 مرحله: " + match["stage"] + "\n\n"
        text += "👤 " + get_player_name_from_db(p1) + "\n"
        text += "🆚\n"
        text += "👤 " + get_player_name_from_db(p2) + "\n\n"
        text += "📊 نتیجه: " + str(match["player1_score"]) + " - " + str(match["player2_score"]) + "\n"
        text += "\n🌐 " + RENDER_URL
        
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="cup_menu")]]
        await query_data.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    # ========== پنل ادمین ==========
    elif data == "admin_panel":
        if not is_admin:
            await query_data.answer("❌ شما دسترسی ندارید!", show_alert=True)
            return
        await query_data.edit_message_text(
            "👑 پنل مدیریت جام:\n🌐 " + RENDER_URL,
            reply_markup=admin_panel_keyboard()
        )
    
    # ========== ساخت جام ==========
    elif data == "create_tournament":
        if not is_admin:
            await query_data.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        context.user_data["creating_tournament"] = True
        keyboard = [[InlineKeyboardButton("🔙 لغو", callback_data="admin_panel")]]
        await query_data.edit_message_text(
            "📝 نام جام جدید را وارد کنید:\n🌐 " + RENDER_URL,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    # ========== بازیکنان ثبت نامی ==========
    elif data == "pending_players":
        if not is_admin:
            await query_data.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        
        tournament = query("SELECT * FROM tournaments WHERE status = 'open' ORDER BY id DESC LIMIT 1", fetchone=True)
        if not tournament:
            await query_data.answer("❌ هیچ جام فعالی وجود ندارد!", show_alert=True)
            return
        
        pending = query(
            "SELECT * FROM registrations WHERE tournament_id = ? AND status = 'pending'",
            (tournament["id"],), fetchall=True
        )
        
        if not pending:
            text = "✅ هیچ بازیکنی در انتظار تایید نیست.\n🌐 " + RENDER_URL
            keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")]]
        else:
            text = "👥 بازیکنان در انتظار تایید:\n\n"
            keyboard = []
            for reg in pending:
                player = query("SELECT * FROM players WHERE user_id = ?", (reg["user_id"],), fetchone=True)
                player_name = get_player_name_from_db(player)
                text += "👤 " + player_name + "\n"
                keyboard.append([
                    InlineKeyboardButton("✅ " + player_name, callback_data=f"approve_{reg['id']}"),
                    InlineKeyboardButton("❌ رد", callback_data=f"reject_{reg['id']}")
                ])
            text += "\n🌐 " + RENDER_URL
            keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")])
        
        await query_data.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    # ========== تایید بازیکن ==========
    elif data.startswith("approve_"):
        if not is_admin:
            await query_data.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        reg_id = int(data.split("_")[1])
        query("UPDATE registrations SET status = 'approved' WHERE id = ?", (reg_id,))
        await query_data.answer("✅ بازیکن تایید شد!", show_alert=True)
        new_data = "pending_players"
        query_data.data = new_data
        await button_handler(update, context)
    
    # ========== رد بازیکن ==========
    elif data.startswith("reject_"):
        if not is_admin:
            await query_data.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        reg_id = int(data.split("_")[1])
        query("DELETE FROM registrations WHERE id = ?", (reg_id,))
        await query_data.answer("❌ بازیکن رد شد!", show_alert=True)
        new_data = "pending_players"
        query_data.data = new_data
        await button_handler(update, context)
    
    # ========== قرعه کشی ==========
    elif data == "draw_tournament":
        if not is_admin:
            await query_data.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        
        tournament = query("SELECT * FROM tournaments WHERE status = 'open' ORDER BY id DESC LIMIT 1", fetchone=True)
        if not tournament:
            await query_data.answer("❌ هیچ جام فعالی وجود ندارد!", show_alert=True)
            return
        
        players = query("SELECT user_id FROM registrations WHERE tournament_id = ? AND status = 'approved'",
                        (tournament["id"],), fetchall=True)
        
        if len(players) < 2:
            await query_data.answer("❌ حداقل ۲ بازیکن نیاز است!", show_alert=True)
            return
        
        player_list = [p["user_id"] for p in players]
        random.shuffle(player_list)
        
        stages = get_stages(len(player_list))
        current_stage = stages[0]
        
        query("DELETE FROM matches WHERE tournament_id = ?", (tournament["id"],))
        
        match_order = 0
        for i in range(0, len(player_list), 2):
            if i + 1 < len(player_list):
                query(
                    "INSERT INTO matches (tournament_id, stage, player1_id, player2_id, match_order) VALUES (?, ?, ?, ?, ?)",
                    (tournament["id"], current_stage, player_list[i], player_list[i+1], match_order)
                )
                match_order += 1
        
        query("UPDATE tournaments SET status = 'active', stage = ? WHERE id = ?", (current_stage, tournament["id"]))
        
        # ارسال پیام به بازیکنان
        for match in query("SELECT * FROM matches WHERE tournament_id = ? AND stage = ?",
                           (tournament["id"], current_stage), fetchall=True):
            p1 = match["player1_id"]
            p2 = match["player2_id"]
            
            text = "🎯 مسابقه شما شروع شد!\n\n"
            text += "🏆 " + tournament["name"] + "\n"
            text += "📊 " + current_stage + "\n\n"
            text += "برای شروع مسابقه روی دکمه زیر کلیک کنید:\n"
            text += "🌐 " + RENDER_URL
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🎯 شروع مسابقه", callback_data=f"play_match_{match['id']}")]
            ])
            
            try:
                await context.bot.send_message(chat_id=p1, text=text, reply_markup=keyboard)
            except:
                pass
            
            try:
                await context.bot.send_message(chat_id=p2, text=text, reply_markup=keyboard)
            except:
                pass
        
        await query_data.edit_message_text(
            "✅ قرعه کشی انجام شد!\n\n"
            "📊 مرحله: " + current_stage + "\n"
            "👥 تعداد بازیکنان: " + str(len(player_list)) + "\n"
            "🎯 تعداد مسابقات: " + str(match_order) + "\n"
            "🌐 " + RENDER_URL,
            reply_markup=admin_panel_keyboard()
        )
    
    # ========== شروع مسابقه ==========
    elif data.startswith("play_match_"):
        match_id = int(data.split("_")[2])
        match = query("SELECT * FROM matches WHERE id = ?", (match_id,), fetchone=True)
        
        if not match:
            await query_data.answer("❌ مسابقه یافت نشد!", show_alert=True)
            return
        
        if user.id not in [match["player1_id"], match["player2_id"]]:
            await query_data.answer("❌ شما در این مسابقه نیستید!", show_alert=True)
            return
        
        if match["status"] == "finished":
            await query_data.answer("❌ این مسابقه تمام شده است!", show_alert=True)
            return
        
        query("UPDATE matches SET status = 'active' WHERE id = ?", (match_id,))
        
        p1_throws = [random.randint(1, 60) for _ in range(5)]
        p2_throws = [random.randint(1, 60) for _ in range(5)]
        
        p1_total = sum(p1_throws)
        p2_total = sum(p2_throws)
        
        for i, score in enumerate(p1_throws, 1):
            query("INSERT INTO throws (match_id, player_id, throw_number, score) VALUES (?, ?, ?, ?)",
                  (match_id, match["player1_id"], i, score))
        
        for i, score in enumerate(p2_throws, 1):
            query("INSERT INTO throws (match_id, player_id, throw_number, score) VALUES (?, ?, ?, ?)",
                  (match_id, match["player2_id"], i, score))
        
        if p1_total == p2_total:
            extra_p1 = random.randint(1, 60)
            extra_p2 = random.randint(1, 60)
            p1_total += extra_p1
            p2_total += extra_p2
            query("INSERT INTO throws (match_id, player_id, throw_number, score) VALUES (?, ?, ?, ?)",
                  (match_id, match["player1_id"], 6, extra_p1))
            query("INSERT INTO throws (match_id, player_id, throw_number, score) VALUES (?, ?, ?, ?)",
                  (match_id, match["player2_id"], 6, extra_p2))
        
        winner_id = match["player1_id"] if p1_total > p2_total else match["player2_id"]
        
        query("UPDATE matches SET player1_score = ?, player2_score = ?, winner_id = ?, status = 'finished' WHERE id = ?",
              (p1_total, p2_total, winner_id, match_id))
        
        query("UPDATE players SET total_wins = total_wins + 1 WHERE user_id = ?", (winner_id,))
        
        p1 = query("SELECT * FROM players WHERE user_id = ?", (match["player1_id"],), fetchone=True)
        p2 = query("SELECT * FROM players WHERE user_id = ?", (match["player2_id"],), fetchone=True)
        winner = query("SELECT * FROM players WHERE user_id = ?", (winner_id,), fetchone=True)
        
        result_text = "🎯 نتیجه مسابقه\n\n"
        result_text += "🏆 " + get_player_name_from_db(p1) + "\n"
        result_text += "پرتاب‌ها: " + " - ".join(str(s) for s in p1_throws) + "\n"
        result_text += "مجموع: " + str(p1_total) + "\n\n"
        result_text += "🆚\n\n"
        result_text += "🏆 " + get_player_name_from_db(p2) + "\n"
        result_text += "پرتاب‌ها: " + " - ".join(str(s) for s in p2_throws) + "\n"
        result_text += "مجموع: " + str(p2_total) + "\n\n"
        result_text += "👑 برنده: " + get_player_name_from_db(winner) + "\n"
        result_text += "🌐 " + RENDER_URL
        
        for uid in [match["player1_id"], match["player2_id"]]:
            try:
                await context.bot.send_message(chat_id=uid, text=result_text)
            except:
                pass
        
        # انتقال به مرحله بعد
        tournament = query("SELECT * FROM tournaments WHERE id = ?", (match["tournament_id"],), fetchone=True)
        all_matches = query("SELECT * FROM matches WHERE tournament_id = ? AND stage = ?",
                            (match["tournament_id"], tournament["stage"]), fetchall=True)
        
        all_finished = all(m["status"] == "finished" for m in all_matches)
        
        if all_finished:
            total_players = query(
                "SELECT COUNT(*) as count FROM registrations WHERE tournament_id = ? AND status = 'approved'",
                (match["tournament_id"],), fetchone=True
            )["count"]
            
            stages = get_stages(total_players)
            current_stage_index = stages.index(tournament["stage"]) if tournament["stage"] in stages else -1
            
            if current_stage_index + 1 < len(stages):
                next_stage = stages[current_stage_index + 1]
                winners = [m["winner_id"] for m in all_matches]
                
                if len(winners) >= 2:
                    query("DELETE FROM matches WHERE tournament_id = ? AND stage = ?",
                          (match["tournament_id"], next_stage))
                    
                    match_order = 0
                    for i in range(0, len(winners), 2):
                        if i + 1 < len(winners):
                            query(
                                "INSERT INTO matches (tournament_id, stage, player1_id, player2_id, match_order) VALUES (?, ?, ?, ?, ?)",
                                (match["tournament_id"], next_stage, winners[i], winners[i+1], match_order)
                            )
                            match_order += 1
                    
                    query("UPDATE tournaments SET stage = ? WHERE id = ?", (next_stage, match["tournament_id"]))
                    
                    for new_match in query("SELECT * FROM matches WHERE tournament_id = ? AND stage = ?",
                                           (match["tournament_id"], next_stage), fetchall=True):
                        for uid in [new_match["player1_id"], new_match["player2_id"]]:
                            try:
                                await context.bot.send_message(
                                    chat_id=uid,
                                    text="🎉 شما به مرحله " + next_stage + " صعود کردید!\n\n"
                                    "🏆 " + tournament["name"] + "\n\n"
                                    "منتظر شروع مسابقه باشید.\n"
                                    "🌐 " + RENDER_URL
                                )
                            except:
                                pass
                else:
                    champion = winners[0]
                    query("UPDATE tournaments SET status = 'finished', winner_id = ? WHERE id = ?",
                          (champion, match["tournament_id"]))
                    query("UPDATE players SET championships = championships + 1 WHERE user_id = ?", (champion,))
                    
                    try:
                        await context.bot.send_message(
                            chat_id=champion,
                            text="👑 تبریک! شما قهرمان جام " + tournament["name"] + " شدید!\n\n"
                            "🌐 " + RENDER_URL
                        )
                    except:
                        pass
        
        await query_data.answer("✅ مسابقه انجام شد!", show_alert=True)
    
    # ========== مشاهده مسابقات ==========
    elif data == "view_matches":
        tournament = query("SELECT * FROM tournaments WHERE status = 'active' ORDER BY id DESC LIMIT 1", fetchone=True)
        
        if not tournament:
            text = "❌ هیچ جام فعالی وجود ندارد!"
        else:
            matches = query("SELECT * FROM matches WHERE tournament_id = ? ORDER BY match_order",
                            (tournament["id"],), fetchall=True)
            
            text = "📋 مسابقات جام " + tournament["name"] + "\n"
            text += "📊 مرحله: " + tournament["stage"] + "\n\n"
            
            status_map = {"waiting": "⏳ منتظر", "active": "🎯 در حال بازی", "finished": "✅ پایان یافته"}
            
            for m in matches:
                p1 = query("SELECT * FROM players WHERE user_id = ?", (m["player1_id"],), fetchone=True)
                p2 = query("SELECT * FROM players WHERE user_id = ?", (m["player2_id"],), fetchone=True)
                p1_name = get_player_name_from_db(p1)
                p2_name = get_player_name_from_db(p2)
                
                text += "🎯 مسابقه " + str(m["match_order"] + 1) + ":\n"
                text += "👤 " + p1_name + " VS " + p2_name + "\n"
                text += "📊 " + str(m["player1_score"]) + " - " + str(m["player2_score"]) + "\n"
                if m["winner_id"]:
                    winner = query("SELECT * FROM players WHERE user_id = ?", (m["winner_id"],), fetchone=True)
                    text += "🏆 برنده: " + get_player_name_from_db(winner) + "\n"
                text += "وضعیت: " + status_map.get(m["status"], "نامشخص") + "\n\n"
        
        text += "🌐 " + RENDER_URL
        
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")]]
        await query_data.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    # ========== قهرمان ==========
    elif data == "view_champion":
        tournament = query("SELECT * FROM tournaments WHERE status = 'finished' ORDER BY id DESC LIMIT 1", fetchone=True)
        
        if tournament and tournament["winner_id"]:
            winner = query("SELECT * FROM players WHERE user_id = ?", (tournament["winner_id"],), fetchone=True)
            text = "👑 قهرمان جام " + tournament["name"] + "\n\n"
            text += "🏆 " + get_player_name_from_db(winner) + "\n"
        else:
            text = "❌ هنوز قهرمانی مشخص نشده است!"
        
        text += "\n🌐 " + RENDER_URL
        
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")]]
        await query_data.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    # ========== مدیریت تقویتی ها ==========
    elif data == "manage_boosters":
        if not is_admin:
            await query_data.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        
        keyboard = [
            [InlineKeyboardButton("🎯 دادن دقت", callback_data="give_accuracy")],
            [InlineKeyboardButton("🔥 دادن قدرت", callback_data="give_power")],
            [InlineKeyboardButton("🍀 دادن شانس", callback_data="give_luck")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")],
        ]
        await query_data.edit_message_text(
            "🎁 مدیریت تقویتی ها\n\nیک نوع را انتخاب کنید:\n🌐 " + RENDER_URL,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data.startswith("give_"):
        if not is_admin:
            await query_data.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        
        booster_type = data.split("_")[1]
        context.user_data["giving_booster"] = booster_type
        context.user_data["booster_step"] = "select_player"
        
        await query_data.edit_message_text(
            "👤 آیدی عددی بازیکن را وارد کنید:\n🌐 " + RENDER_URL,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لغو", callback_data="manage_boosters")]])
        )

# ==================== TEXT HANDLER ====================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text
    
    if context.user_data.get("creating_tournament") and user.id == ADMIN_ID:
        context.user_data["tournament_name"] = text
        context.user_data["creating_tournament"] = False
        context.user_data["setting_capacity"] = True
        await update.message.reply_text("✅ نام جام: " + text + "\n\n📝 حالا تعداد نفرات را وارد کنید:")
        return
    
    if context.user_data.get("setting_capacity") and user.id == ADMIN_ID:
        try:
            capacity = int(text)
            if capacity < 2:
                await update.message.reply_text("❌ حداقل ۲ نفر!")
                return
            
            name = context.user_data.get("tournament_name", "جام دارت")
            query("INSERT INTO tournaments (name, capacity, created_by) VALUES (?, ?, ?)",
                  (name, capacity, user.id))
            
            context.user_data["setting_capacity"] = False
            
            await update.message.reply_text(
                "✅ جام جدید ساخته شد!\n\n"
                "📋 نام: " + name + "\n"
                "👥 ظرفیت: " + str(capacity) + " نفر\n"
                "🌐 " + RENDER_URL,
                reply_markup=admin_panel_keyboard()
            )
        except ValueError:
            await update.message.reply_text("❌ لطفا یک عدد معتبر وارد کنید!")
        return
    
    if context.user_data.get("booster_step") == "select_player" and user.id == ADMIN_ID:
        try:
            target_id = int(text)
            context.user_data["booster_target"] = target_id
            context.user_data["booster_step"] = "select_quantity"
            await update.message.reply_text("✅ بازیکن انتخاب شد.\n\n📝 تعداد را وارد کنید:")
        except ValueError:
            await update.message.reply_text("❌ لطفا یک آیدی عددی معتبر وارد کنید!")
        return
    
    if context.user_data.get("booster_step") == "select_quantity" and user.id == ADMIN_ID:
        try:
            quantity = int(text)
            if quantity < 1:
                await update.message.reply_text("❌ حداقل ۱!")
                return
            
            target_id = context.user_data["booster_target"]
            booster_type = context.user_data["giving_booster"]
            
            existing = query("SELECT * FROM boosters WHERE user_id = ? AND booster_type = ?",
                             (target_id, booster_type), fetchone=True)
            
            if existing:
                query("UPDATE boosters SET quantity = quantity + ? WHERE user_id = ? AND booster_type = ?",
                      (quantity, target_id, booster_type))
            else:
                query("INSERT INTO boosters (user_id, booster_type, quantity) VALUES (?, ?, ?)",
                      (target_id, booster_type, quantity))
            
            emoji_map = {"accuracy": "🎯", "power": "🔥", "luck": "🍀"}
            name_map = {"accuracy": "دقت", "power": "قدرت", "luck": "شانس"}
            
            context.user_data["booster_step"] = None
            context.user_data["giving_booster"] = None
            context.user_data["booster_target"] = None
            
            await update.message.reply_text(
                "✅ تقویتی داده شد!\n\n"
                + emoji_map.get(booster_type, "") + " " + name_map.get(booster_type, "") + "\n"
                "👤 به بازیکن: " + str(target_id) + "\n"
                "📦 تعداد: " + str(quantity) + "\n"
                "🌐 " + RENDER_URL,
                reply_markup=admin_panel_keyboard()
            )
        except ValueError:
            await update.message.reply_text("❌ لطفا یک عدد معتبر وارد کنید!")
        return

# ==================== RUN BOT ====================
def run_bot():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    print("🤖 ربات جام حذفی دارت راه اندازی شد!")
    print("🌐 آدرس: " + RENDER_URL)
    app.run_polling()

# ==================== MAIN ====================
if __name__ == "__main__":
    init_db()
    
    # اجرای ربات در Thread جدا
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # اجرای Flask در Thread اصلی (مهم برای Render)
    port = int(os.environ.get("PORT", 10000))
    print("🌐 Flask running on port " + str(port))
    print("🌐 آدرس: " + RENDER_URL)
    flask_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
