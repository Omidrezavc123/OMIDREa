import sqlite3
import random
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.error import TelegramError

# ==================== CONFIG ====================
BOT_TOKEN = "8642125258:AAFYNTNEP2MGkYvDuFVyl_SzaBqPfFX0chE"
ADMIN_ID = 7832771827  # آیدی عددی ادمین

# ==================== DATABASE ====================
DB_PATH = "dart_cup.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # بازیکنان
    c.execute('''CREATE TABLE IF NOT EXISTS players (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT,
        total_wins INTEGER DEFAULT 0,
        championships INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # تورنمنت‌ها
    c.execute('''CREATE TABLE IF NOT EXISTS tournaments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        capacity INTEGER NOT NULL,
        stage TEXT DEFAULT 'waiting',
        status TEXT DEFAULT 'open',
        created_by INTEGER,
        winner_id INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # ثبت‌نام‌ها
    c.execute('''CREATE TABLE IF NOT EXISTS registrations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tournament_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        status TEXT DEFAULT 'pending',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(tournament_id, user_id)
    )''')
    
    # مسابقات
    c.execute('''CREATE TABLE IF NOT EXISTS matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tournament_id INTEGER NOT NULL,
        stage TEXT NOT NULL,
        player1_id INTEGER,
        player2_id INTEGER,
        player1_score INTEGER DEFAULT 0,
        player2_score INTEGER DEFAULT 0,
        winner_id INTEGER,
        status TEXT DEFAULT 'waiting',
        match_order INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # پرتاب‌ها
    c.execute('''CREATE TABLE IF NOT EXISTS throws (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        match_id INTEGER NOT NULL,
        player_id INTEGER NOT NULL,
        throw_number INTEGER NOT NULL,
        score INTEGER NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # تقویتی‌ها
    c.execute('''CREATE TABLE IF NOT EXISTS boosters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        booster_type TEXT NOT NULL,
        quantity INTEGER DEFAULT 0,
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
    if fetchone:
        result = c.fetchone()
    elif fetchall:
        result = c.fetchall()
    else:
        result = None
    conn.close()
    return result

# ==================== KEYBOARDS ====================
def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("🏆 جام و مسابقات", callback_data="cup_menu")],
        [InlineKeyboardButton("👤 پروفایل من", callback_data="my_profile")],
    ]
    return InlineKeyboardMarkup(keyboard)

def cup_menu_keyboard(tournament_id=None):
    keyboard = []
    if tournament_id:
        keyboard.append([InlineKeyboardButton("✅ ثبت نام در جام", callback_data=f"register_{tournament_id}")])
        keyboard.append([InlineKeyboardButton("📋 جدول مسابقات", callback_data=f"bracket_{tournament_id}")])
        keyboard.append([InlineKeyboardButton("🎯 مسابقه من", callback_data=f"my_match_{tournament_id}")])
        keyboard.append([InlineKeyboardButton("👑 قهرمان جام", callback_data=f"champion_{tournament_id}")])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")])
    return InlineKeyboardMarkup(keyboard)

def admin_panel_keyboard():
    keyboard = [
        [InlineKeyboardButton("➕ ساخت جام جدید", callback_data="create_tournament")],
        [InlineKeyboardButton("👥 بازیکنان ثبت‌نامی", callback_data="pending_players")],
        [InlineKeyboardButton("🎲 قرعه‌کشی جام", callback_data="draw_tournament")],
        [InlineKeyboardButton("▶️ شروع مرحله", callback_data="start_stage")],
        [InlineKeyboardButton("📋 مشاهده مسابقات", callback_data="view_matches")],
        [InlineKeyboardButton("🏆 مشاهده قهرمان", callback_data="view_champion")],
        [InlineKeyboardButton("🎁 مدیریت تقویتی‌ها", callback_data="manage_boosters")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)

# ==================== HELPERS ====================
def get_player_name(user):
    if user.username:
        return f"@{user.username}"
    elif user.full_name:
        return user.full_name
    return f"User {user.id}"

def get_stages(total_players):
    stages = {
        2: ["فینال"],
        4: ["نیمه‌نهایی", "فینال"],
        8: ["یک‌چهارم نهایی", "نیمه‌نهایی", "فینال"],
        16: ["یک‌هشتم نهایی", "یک‌چهارم نهایی", "نیمه‌نهایی", "فینال"],
        32: ["یک‌شانزدهم نهایی", "یک‌هشتم نهایی", "یک‌چهارم نهایی", "نیمه‌نهایی", "فینال"],
    }
    return stages.get(total_players, ["مرحله ۱", "فینال"])

# ==================== HANDLERS ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # ذخیره بازیکن
    existing = query("SELECT * FROM players WHERE user_id = ?", (user.id,), fetchone=True)
    if not existing:
        query(
            "INSERT INTO players (user_id, username, full_name) VALUES (?, ?, ?)",
            (user.id, user.username, user.full_name)
        )
    
    # نمایش منوی اصلی
    if user.id == ADMIN_ID:
        keyboard = [
            [InlineKeyboardButton("🏆 جام و مسابقات", callback_data="cup_menu")],
            [InlineKeyboardButton("👤 پروفایل من", callback_data="my_profile")],
            [InlineKeyboardButton("👑 پنل مدیریت", callback_data="admin_panel")],
        ]
    else:
        keyboard = main_menu_keyboard().inline_keyboard
    
    await update.message.reply_text(
        f"🎯 به ربات جام حذفی دارت خوش آمدید!\n\n"
        f"👤 {get_player_name(user)}\n\n"
        f"از منوی زیر انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_data = update.callback_query
    await query_data.answer()
    data = query_data.data
    user = update.effective_user
    
    # منوی اصلی
    if data == "main_menu":
        text = "📋 منوی اصلی:"
        if user.id == ADMIN_ID:
            keyboard = [
                [InlineKeyboardButton("🏆 جام و مسابقات", callback_data="cup_menu")],
                [InlineKeyboardButton("👤 پروفایل من", callback_data="my_profile")],
                [InlineKeyboardButton("👑 پنل مدیریت", callback_data="admin_panel")],
            ]
        else:
            keyboard = main_menu_keyboard().inline_keyboard
        await query_data.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    # منوی جام
    elif data == "cup_menu":
        active_tournament = query(
            "SELECT * FROM tournaments WHERE status = 'open' OR status = 'active' ORDER BY id DESC LIMIT 1",
            fetchone=True
        )
        
        text = "🏆 جام دارت\n\n"
        
        if active_tournament:
            players_count = query(
                "SELECT COUNT(*) as count FROM registrations WHERE tournament_id = ? AND status = 'approved'",
                (active_tournament['id'],), fetchone=True
            )['count']
            
            text += f"📋 نام جام: {active_tournament['name']}\n"
            text += f"📊 مرحله: {active_tournament['stage']}\n"
            text += f"👥 تعداد بازیکنان: {players_count}\n"
            text += f"🎯 ظرفیت: {active_tournament['capacity']}\n"
            
            await query_data.edit_message_text(
                text,
                reply_markup=cup_menu_keyboard(active_tournament['id'])
            )
        else:
            text += "❌ هیچ جام فعالی وجود ندارد."
            keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]]
            await query_data.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    # ثبت‌نام در جام
    elif data.startswith("register_"):
        tournament_id = int(data.split("_")[1])
        tournament = query("SELECT * FROM tournaments WHERE id = ?", (tournament_id,), fetchone=True)
        
        if not tournament or tournament['status'] != 'open':
            await query_data.answer("❌ این جام در دسترس نیست!", show_alert=True)
            return
        
        # بررسی ظرفیت
        approved = query(
            "SELECT COUNT(*) as count FROM registrations WHERE tournament_id = ? AND status = 'approved'",
            (tournament_id,), fetchone=True
        )['count']
        
        if approved >= tournament['capacity']:
            await query_data.answer("❌ ظرفیت جام تکمیل شده است!", show_alert=True)
            return
        
        # ثبت‌نام
        try:
            query(
                "INSERT OR IGNORE INTO registrations (tournament_id, user_id) VALUES (?, ?)",
                (tournament_id, user.id)
            )
            await query_data.answer("✅ ثبت‌نام شما انجام شد. منتظر تأیید ادمین باشید.", show_alert=True)
        except:
            await query_data.answer("⚠️ شما قبلاً ثبت‌نام کرده‌اید!", show_alert=True)
    
    # پروفایل من
    elif data == "my_profile":
        player = query("SELECT * FROM players WHERE user_id = ?", (user.id,), fetchone=True)
        if player:
            text = f"👤 پروفایل شما:\n\n"
            text += f"🆔 نام: {get_player_name(user)}\n"
            text += f"🏆 تعداد برد: {player['total_wins']}\n"
            text += f"👑 تعداد قهرمانی: {player['championships']}\n"
            
            # تقویتی‌ها
            boosters = query(
                "SELECT * FROM boosters WHERE user_id = ? AND quantity > 0",
                (user.id,), fetchall=True
            )
            if boosters:
                text += "\n🎁 تقویتی‌های شما:\n"
                emoji_map = {"accuracy": "🎯", "power": "🔥", "luck": "🍀"}
                name_map = {"accuracy": "دقت", "power": "قدرت", "luck": "شانس"}
                for b in boosters:
                    text += f"{emoji_map.get(b['booster_type'], '')} {name_map.get(b['booster_type'], '')}: {b['quantity']} عدد\n"
        else:
            text = "❌ پروفایل شما یافت نشد!"
        
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]]
        await query_data.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    # پنل ادمین
    elif data == "admin_panel":
        if user.id != ADMIN_ID:
            await query_data.answer("❌ شما دسترسی ندارید!", show_alert=True)
            return
        await query_data.edit_message_text("👑 پنل مدیریت جام:", reply_markup=admin_panel_keyboard())
    
    # ساخت جام جدید
    elif data == "create_tournament":
        if user.id != ADMIN_ID:
            await query_data.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        context.user_data['creating_tournament'] = True
        await query_data.edit_message_text(
            "📝 نام جام جدید را وارد کنید:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لغو", callback_data="admin_panel")]])
        )
    
    # قرعه‌کشی
    elif data == "draw_tournament":
        if user.id != ADMIN_ID:
            await query_data.answer("❌ دسترسی غیرمجاز!", show_alert=True)
            return
        
        tournament = query(
            "SELECT * FROM tournaments WHERE status = 'open' ORDER BY id DESC LIMIT 1",
            fetchone=True
        )
        
        if not tournament:
            await query_data.answer("❌ هیچ جام فعالی وجود ندارد!", show_alert=True)
            return
        
        # دریافت بازیکنان تأیید شده
        players = query(
            "SELECT user_id FROM registrations WHERE tournament_id = ? AND status = 'approved'",
            (tournament['id'],), fetchall=True
        )
        
        if len(players) < 2:
            await query_data.answer("❌ حداقل ۲ بازیکن نیاز است!", show_alert=True)
            return
        
        # بر هم زدن تصادفی
        player_list = [p['user_id'] for p in players]
        random.shuffle(player_list)
        
        # ساخت مراحل
        stages = get_stages(len(player_list))
        current_stage = stages[0]
        
        # حذف مسابقات قبلی
        query("DELETE FROM matches WHERE tournament_id = ?", (tournament['id'],))
        
        # ساخت مسابقات
        match_order = 0
        for i in range(0, len(player_list), 2):
            if i + 1 < len(player_list):
                query(
                    "INSERT INTO matches (tournament_id, stage, player1_id, player2_id, match_order) VALUES (?, ?, ?, ?, ?)",
                    (tournament['id'], current_stage, player_list[i], player_list[i+1], match_order)
                )
                match_order += 1
        
        # به‌روزرسانی وضعیت جام
        query(
            "UPDATE tournaments SET status = 'active', stage = ? WHERE id = ?",
            (current_stage, tournament['id'])
        )
        
        await query_data.edit_message_text(
            f"✅ قرعه‌کشی انجام شد!\n\n"
            f"📊 مرحله: {current_stage}\n"
            f"👥 تعداد بازیکنان: {len(player_list)}\n"
            f"🎯 تعداد مسابقات: {match_order}",
            reply_markup=admin_panel_keyboard()
        )
    
    # مشاهده مسابقات
    elif data == "view_matches":
        tournament = query(
            "SELECT * FROM tournaments WHERE status = 'active' ORDER BY id DESC LIMIT 1",
            fetchone=True
        )
        
        if not tournament:
            text = "❌ هیچ جام فعالی وجود ندارد!"
        else:
            matches = query(
                "SELECT * FROM matches WHERE tournament_id = ? ORDER BY match_order",
                (tournament['id'],), fetchall=True
            )
            
            text = f"📋 مسابقات جام {tournament['name']}\n"
            text += f"📊 مرحله: {tournament['stage']}\n\n"
            
            status_map = {"waiting": "⏳ منتظر", "active": "🎯 در حال بازی", "finished": "✅ پایان یافته"}
            
            for m in matches:
                p1 = query("SELECT * FROM players WHERE user_id = ?", (m['player1_id'],), fetchone=True)
                p2 = query("SELECT * FROM players WHERE user_id = ?", (m['player2_id'],), fetchone=True)
                p1_name = p1['full_name'] or f"User {p1['user_id']}" if p1 else "ناشناس"
                p2_name = p2['full_name'] or f"User {p2['user_id']}" if p2 else "ناشناس"
                
                text += f"🎯 مسابقه {m['match_order']+1}:\n"
                text += f"👤 {p1_name} VS {p2_name}\n"
                text += f"📊 {m['player1_score']} - {m['player2_score']}\n"
                if m['winner_id']:
                    winner = query("SELECT * FROM players WHERE user_id = ?", (m['winner_id'],), fetchone=True)
                    text += f"🏆 برنده: {winner['full_name'] if winner else 'نامشخص'}\n"
                text += f"وضعیت: {status_map.get(m['status'], 'نامشخص')}\n\n"
        
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")]]
        await query_data.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    # مشاهده قهرمان
    elif data == "view_champion":
        tournament = query(
            "SELECT * FROM tournaments WHERE status = 'finished' ORDER BY id DESC LIMIT 1",
            fetchone=True
        )
        
        if tournament and tournament['winner_id']:
            winner = query("SELECT * FROM players WHERE user_id = ?", (tournament['winner_id'],), fetchone=True)
            text = f"👑 قهرمان جام {tournament['name']}\n\n"
            text += f"🏆 {winner['full_name'] or f'User {winner['user_id']}'}\n"
        else:
            text = "❌ هنوز قهرمانی مشخص نشده است!"
        
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")]]
        await query_data.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text
    
    # ساخت جام جدید (ادمین)
    if context.user_data.get('creating_tournament') and user.id == ADMIN_ID:
        context.user_data['tournament_name'] = text
        context.user_data['creating_tournament'] = False
        context.user_data['setting_capacity'] = True
        
        await update.message.reply_text(
            f"✅ نام جام: {text}\n\n"
            f"📝 حالا تعداد نفرات را وارد کنید:"
        )
        return
    
    # تنظیم ظرفیت
    if context.user_data.get('setting_capacity') and user.id == ADMIN_ID:
        try:
            capacity = int(text)
            if capacity < 2:
                await update.message.reply_text("❌ حداقل ۲ نفر!")
                return
            
            name = context.user_data.get('tournament_name', 'جام دارت')
            
            query(
                "INSERT INTO tournaments (name, capacity, created_by) VALUES (?, ?, ?)",
                (name, capacity, user.id)
            )
            
            context.user_data['setting_capacity'] = False
            
            await update.message.reply_text(
                f"✅ جام جدید ساخته شد!\n\n"
                f"📋 نام: {name}\n"
                f"👥 ظرفیت: {capacity} نفر",
                reply_markup=admin_panel_keyboard()
            )
        except ValueError:
            await update.message.reply_text("❌ لطفاً یک عدد معتبر وارد کنید!")

# ==================== MAIN ====================
def main():
    init_db()
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(CommandHandler("admin", lambda u, c: admin_panel_handler(u, c)))
    
    # هندلر متن
    from telegram.ext import MessageHandler, filters
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    
    print("🤖 ربات جام حذفی دارت راه‌اندازی شد!")
    app.run_polling()

async def admin_panel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ دسترسی غیرمجاز!")
        return
    await update.message.reply_text("👑 پنل مدیریت:", reply_markup=admin_panel_keyboard())

if __name__ == "__main__":
    main()
