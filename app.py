import sqlite3
import random
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# ==================== CONFIG ====================
BOT_TOKEN = "8642125258:AAFYNTNEP2MGkYvDuFVyl_SzaBqPfFX0chE"
ADMIN_ID = 123456789

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

def get_stages(total_players):
    stages = {
        2: ["فینال"],
        4: ["نیمه نهایی", "فینال"],
        8: ["یک چهارم نهایی", "نیمه نهایی", "فینال"],
        16: ["یک هشتم نهایی", "یک چهارم نهایی", "نیمه نهایی", "فینال"],
    }
    for size, stage_list in sorted(stages.items(), reverse=True):
        if total_players >= size:
            return stage_list
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
        "از منوی زیر انتخاب کنید:",
        reply_markup=main_menu_keyboard(is_admin)
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_data = update.callback_query
    await query_data.answer()
    data = query_data.data
    user = update.effective_user
    is_admin = (user.id == ADMIN_ID)
    
    if data == "main_menu":
        await query_data.edit_message_text(
            "📋 منوی اصلی:",
            reply_markup=main_menu_keyboard(is_admin)
        )
    
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
            
            await query_data.edit_message_text(text, reply_markup=cup_menu_keyboard(tournament["id"]))
        else:
            keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]]
            await query_data.edit_message_text("❌ هیچ جام فعالی وجود ندارد.", reply_markup=InlineKeyboardMarkup(keyboard))
    
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
    
    elif data == "my_profile":
        player = query("SELECT * FROM players WHERE user_id = ?", (user.id,), fetchone=True)
        if player:
            text = "👤 پروفایل شما:\n\n"
            text += "🆔 نام: " + get_player_name(user) + "\n"
            text += "🏆 تعداد برد: " + str(player["total_wins"]) + "\n"
            text += "👑 تعداد قهرمانی: " + str(player["championships"]) + "\n"
            
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
    
    elif data == "admin_panel":
        if not is_admin:
            await query_data.answer("❌ شما دسترسی ندارید!", show_alert=True)
            return
        await query_data.edit_message_text("👑 پنل مدیریت جام:", reply_markup=admin_panel_keyboard())
    
    elif data == "create_tournament":
        if not is_admin:
            await query_data.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        context.user_data["creating_tournament"] = True
        keyboard = [[InlineKeyboardButton("🔙 لغو", callback_data="admin_panel")]]
        await query_data.edit_message_text("📝 نام جام جدید را وارد کنید:", reply_markup=InlineKeyboardMarkup(keyboard))
    
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
        
        await query_data.edit_message_text(
            "✅ قرعه کشی انجام شد!\n\n"
            "📊 مرحله: " + current_stage + "\n"
            "👥 تعداد بازیکنان: " + str(len(player_list)) + "\n"
            "🎯 تعداد مسابقات: " + str(match_order),
            reply_markup=admin_panel_keyboard()
        )
    
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
                p1_name = p1["full_name"] if p1 else "ناشناس"
                p2_name = p2["full_name"] if p2 else "ناشناس"
                
                text += "🎯 مسابقه " + str(m["match_order"] + 1) + ":\n"
                text += "👤 " + p1_name + " VS " + p2_name + "\n"
                text += "📊 " + str(m["player1_score"]) + " - " + str(m["player2_score"]) + "\n"
                if m["winner_id"]:
                    winner = query("SELECT * FROM players WHERE user_id = ?", (m["winner_id"],), fetchone=True)
                    winner_name = winner["full_name"] if winner else "نامشخص"
                    text += "🏆 برنده: " + winner_name + "\n"
                text += "وضعیت: " + status_map.get(m["status"], "نامشخص") + "\n\n"
        
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")]]
        await query_data.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "view_champion":
        tournament = query("SELECT * FROM tournaments WHERE status = 'finished' ORDER BY id DESC LIMIT 1", fetchone=True)
        
        if tournament and tournament["winner_id"]:
            winner = query("SELECT * FROM players WHERE user_id = ?", (tournament["winner_id"],), fetchone=True)
            winner_name = winner["full_name"] if winner else "نامشخص"
            text = "👑 قهرمان جام " + tournament["name"] + "\n\n"
            text += "🏆 " + winner_name + "\n"
        else:
            text = "❌ هنوز قهرمانی مشخص نشده است!"
        
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")]]
        await query_data.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
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
            text = "✅ هیچ بازیکنی در انتظار تایید نیست."
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
            keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")])
        
        await query_data.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data.startswith("approve_"):
        if not is_admin:
            await query_data.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        reg_id = int(data.split("_")[1])
        query("UPDATE registrations SET status = 'approved' WHERE id = ?", (reg_id,))
        await query_data.answer("✅ بازیکن تایید شد!", show_alert=True)
        # بازگشت به لیست
        await button_handler(update, context)
    
    elif data.startswith("reject_"):
        if not is_admin:
            await query_data.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        reg_id = int(data.split("_")[1])
        query("DELETE FROM registrations WHERE id = ?", (reg_id,))
        await query_data.answer("❌ بازیکن رد شد!", show_alert=True)
        await button_handler(update, context)

def get_player_name_from_db(player):
    if not player:
        return "ناشناس"
    if player["username"]:
        return "@" + player["username"]
    if player["full_name"]:
        return player["full_name"]
    return "User " + str(player["user_id"])

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
                "👥 ظرفیت: " + str(capacity) + " نفر",
                reply_markup=admin_panel_keyboard()
            )
        except ValueError:
            await update.message.reply_text("❌ لطفا یک عدد معتبر وارد کنید!")

# ==================== MAIN ====================
def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    
    print("🤖 ربات جام حذفی دارت راه اندازی شد!")
    app.run_polling()

if __name__ == "__main__":
    main()
