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
RENDER_URL = "https://omidrea-1.onrender.com"

# ==================== FLASK ====================
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Bot is running!"

# ==================== DATABASE ====================
DB_PATH = "dart_cup.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS players (user_id INTEGER PRIMARY KEY, username TEXT, full_name TEXT, total_wins INTEGER DEFAULT 0, championships INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS tournaments (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, capacity INTEGER NOT NULL, stage TEXT DEFAULT 'waiting', status TEXT DEFAULT 'open', created_by INTEGER, winner_id INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS registrations (id INTEGER PRIMARY KEY AUTOINCREMENT, tournament_id INTEGER NOT NULL, user_id INTEGER NOT NULL, status TEXT DEFAULT 'pending', created_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(tournament_id, user_id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS matches (id INTEGER PRIMARY KEY AUTOINCREMENT, tournament_id INTEGER NOT NULL, stage TEXT NOT NULL, player1_id INTEGER, player2_id INTEGER, player1_score INTEGER DEFAULT 0, player2_score INTEGER DEFAULT 0, winner_id INTEGER, status TEXT DEFAULT 'waiting', match_order INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS throws (id INTEGER PRIMARY KEY AUTOINCREMENT, match_id INTEGER NOT NULL, player_id INTEGER NOT NULL, throw_number INTEGER NOT NULL, score INTEGER NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS boosters (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, booster_type TEXT NOT NULL, quantity INTEGER DEFAULT 0, UNIQUE(user_id, booster_type))''')
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
    stages = {2: ["فینال"], 4: ["نیمه نهایی", "فینال"], 8: ["یک چهارم نهایی", "نیمه نهایی", "فینال"], 16: ["یک هشتم نهایی", "یک چهارم نهایی", "نیمه نهایی", "فینال"], 32: ["یک شانزدهم نهایی", "یک هشتم نهایی", "یک چهارم نهایی", "نیمه نهایی", "فینال"]}
    for s in [32, 16, 8, 4, 2]:
        if n >= s: return stages[s]
    return ["مرحله ۱", "فینال"]

# ==================== HANDLERS ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not query("SELECT * FROM players WHERE user_id = ?", (user.id,), fetchone=True):
        query("INSERT INTO players (user_id, username, full_name) VALUES (?, ?, ?)", (user.id, user.username, user.full_name))
    is_admin = (user.id == ADMIN_ID)
    await update.message.reply_text(f"🎯 به ربات جام حذفی دارت خوش آمدید!\n\n👤 {get_name(user)}\n\nاز منوی زیر انتخاب کنید:", reply_markup=main_menu_keyboard(is_admin))

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
            await q.edit_message_text(f"🏆 جام دارت\n\n📋 نام جام: {t['name']}\n📊 مرحله: {t['stage']}\n👥 تعداد بازیکنان: {cnt}\n🎯 ظرفیت: {t['capacity']}", reply_markup=cup_menu_keyboard(t["id"]))
        else:
            await q.edit_message_text("❌ هیچ جام فعالی وجود ندارد.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]]))

    elif data.startswith("register_"):
        tid = int(data.split("_")[1])
        t = query("SELECT * FROM tournaments WHERE id = ?", (tid,), fetchone=True)
        if not t or t["status"] != "open":
            await q.answer("❌ در دسترس نیست!", show_alert=True)
            return
        if query("SELECT COUNT(*) as c FROM registrations WHERE tournament_id = ? AND status = 'approved'", (tid,), fetchone=True)["c"] >= t["capacity"]:
            await q.answer("❌ ظرفیت تکمیل شد!", show_alert=True)
            return
        try:
            query("INSERT OR IGNORE INTO registrations (tournament_id, user_id) VALUES (?, ?)", (tid, user.id))
            await q.answer("✅ ثبت نام شد. منتظر تایید باشید.", show_alert=True)
        except:
            await q.answer("⚠️ قبلا ثبت نام کرده اید!", show_alert=True)

    elif data == "my_profile":
        p = query("SELECT * FROM players WHERE user_id = ?", (user.id,), fetchone=True)
        txt = f"👤 پروفایل شما:\n\n🆔 {get_name(user)}\n🏆 برد: {p['total_wins']}\n👑 قهرمانی: {p['championships']}" if p else "❌ پروفایل یافت نشد!"
        if p:
            b = query("SELECT * FROM boosters WHERE user_id = ? AND quantity > 0", (user.id,), fetchall=True)
            if b:
                txt += "\n\n🎁 تقویتی ها:\n"
                em = {"accuracy": "🎯", "power": "🔥", "luck": "🍀"}
                nm = {"accuracy": "دقت", "power": "قدرت", "luck": "شانس"}
                for x in b: txt += f"{em.get(x['booster_type'],'')} {nm.get(x['booster_type'],'')}: {x['quantity']}\n"
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]]))

    elif data == "leaderboard":
        pl = query("SELECT * FROM players ORDER BY championships DESC, total_wins DESC LIMIT 10", fetchall=True)
        txt = "📊 رتبه بندی:\n\n"
        for i, p in enumerate(pl, 1): txt += f"{i}. {get_name_db(p)}\n   🏆 {p['total_wins']} برد | 👑 {p['championships']} قهرمانی\n\n"
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]]))

    elif data == "my_boosters":
        b = query("SELECT * FROM boosters WHERE user_id = ? AND quantity > 0", (user.id,), fetchall=True)
        em = {"accuracy": "🎯", "power": "🔥", "luck": "🍀"}
        nm = {"accuracy": "دقت", "power": "قدرت", "luck": "شانس"}
        txt = "🎁 تقویتی های شما:\n\n"
        if b:
            for x in b: txt += f"{em.get(x['booster_type'],'')} {nm.get(x['booster_type'],'')}: {x['quantity']}\n"
        else:
            txt = "❌ هیچ تقویتی ندارید!"
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]]))

    elif data == "rules":
        txt = "📋 قوانین:\n\n🎯 هر بازیکن ۵ پرتاب\n🎲 امتیاز ۱ تا ۶۰\n🏆 امتیاز بیشتر = برنده\n🔄 برنده به مرحله بعد\n👑 برنده فینال = قهرمان\n\n🎁 تقویتی‌ها:\n🎯 دقت: +۱۰\n🔥 قدرت: +۱۵\n🍀 شانس: ۱۰ تا ۳۰\n\n⚠️ مساوی = پرتاب اضافه"
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]]))

    elif data.startswith("bracket_"):
        tid = int(data.split("_")[1])
        t = query("SELECT * FROM tournaments WHERE id = ?", (tid,), fetchone=True)
        if not t: await q.answer("❌ یافت نشد!", show_alert=True); return
        matches = query("SELECT * FROM matches WHERE tournament_id = ? ORDER BY match_order", (tid,), fetchall=True)
        sm = {"waiting": "⏳", "active": "🎯", "finished": "✅"}
        txt = f"📋 جدول مسابقات\n🏆 {t['name']}\n📊 {t['stage']}\n\n"
        cs = None
        for m in matches:
            if m["stage"] != cs: cs = m["stage"]; txt += f"\n--- {cs} ---\n\n"
            p1 = get_name_db(query("SELECT * FROM players WHERE user_id = ?", (m["player1_id"],), fetchone=True))
            p2 = get_name_db(query("SELECT * FROM players WHERE user_id = ?", (m["player2_id"],), fetchone=True))
            txt += f"{sm.get(m['status'],'❓')} {p1} VS {p2}\n"
            if m["status"] == "finished": txt += f"   📊 {m['player1_score']} - {m['player2_score']}\n"
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="cup_menu")]]))

    elif data.startswith("champion_"):
        tid = int(data.split("_")[1])
        t = query("SELECT * FROM tournaments WHERE id = ?", (tid,), fetchone=True)
        if t and t["winner_id"]:
            w = query("SELECT * FROM players WHERE user_id = ?", (t["winner_id"],), fetchone=True)
            txt = f"👑 قهرمان جام\n\n🏆 {t['name']}\n\n👤 {get_name_db(w)}"
        else:
            txt = "❌ هنوز قهرمانی مشخص نشده!"
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="cup_menu")]]))

    elif data.startswith("my_match_"):
        tid = int(data.split("_")[2])
        m = query("SELECT * FROM matches WHERE tournament_id = ? AND (player1_id = ? OR player2_id = ?) AND status != 'finished' ORDER BY id LIMIT 1", (tid, user.id, user.id), fetchone=True)
        if not m: await q.answer("❌ مسابقه فعال ندارید!", show_alert=True); return
        p1 = get_name_db(query("SELECT * FROM players WHERE user_id = ?", (m["player1_id"],), fetchone=True))
        p2 = get_name_db(query("SELECT * FROM players WHERE user_id = ?", (m["player2_id"],), fetchone=True))
        txt = f"🎯 مسابقه شما\n\n📊 {m['stage']}\n\n👤 {p1}\n🆚\n👤 {p2}\n\n📊 {m['player1_score']} - {m['player2_score']}"
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="cup_menu")]]))

    elif data == "admin_panel":
        if not is_admin: await q.answer("❌ دسترسی ندارید!", show_alert=True); return
        await q.edit_message_text("👑 پنل مدیریت:", reply_markup=admin_panel_keyboard())

    elif data == "create_tournament":
        if not is_admin: await q.answer("❌ غیرمجاز!", show_alert=True); return
        context.user_data["creating_tournament"] = True
        await q.edit_message_text("📝 نام جام جدید را وارد کنید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لغو", callback_data="admin_panel")]]))

    elif data == "pending_players":
        if not is_admin: await q.answer("❌ غیرمجاز!", show_alert=True); return
        t = query("SELECT * FROM tournaments WHERE status = 'open' ORDER BY id DESC LIMIT 1", fetchone=True)
        if not t: await q.answer("❌ جام فعال ندارید!", show_alert=True); return
        pending = query("SELECT * FROM registrations WHERE tournament_id = ? AND status = 'pending'", (t["id"],), fetchall=True)
        if not pending:
            await q.edit_message_text("✅ هیچ بازیکنی در انتظار تایید نیست.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")]]))
        else:
            txt = "👥 بازیکنان در انتظار تایید:\n\n"
            kb = []
            for r in pending:
                pn = get_name_db(query("SELECT * FROM players WHERE user_id = ?", (r["user_id"],), fetchone=True))
                txt += f"👤 {pn}\n"
                kb.append([InlineKeyboardButton(f"✅ {pn}", callback_data=f"approve_{r['id']}"), InlineKeyboardButton("❌ رد", callback_data=f"reject_{r['id']}")])
            kb.append([InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")])
            await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("approve_"):
        if not is_admin: await q.answer("❌ غیرمجاز!", show_alert=True); return
        query("UPDATE registrations SET status = 'approved' WHERE id = ?", (int(data.split("_")[1]),))
        await q.answer("✅ تایید شد!", show_alert=True)
        q.data = "pending_players"; await button_handler(update, context)

    elif data.startswith("reject_"):
        if not is_admin: await q.answer("❌ غیرمجاز!", show_alert=True); return
        query("DELETE FROM registrations WHERE id = ?", (int(data.split("_")[1]),))
        await q.answer("❌ رد شد!", show_alert=True)
        q.data = "pending_players"; await button_handler(update, context)

    elif data == "draw_tournament":
        if not is_admin: await q.answer("❌ غیرمجاز!", show_alert=True); return
        t = query("SELECT * FROM tournaments WHERE status = 'open' ORDER BY id DESC LIMIT 1", fetchone=True)
        if not t: await q.answer("❌ جام فعال ندارید!", show_alert=True); return
        players = query("SELECT user_id FROM registrations WHERE tournament_id = ? AND status = 'approved'", (t["id"],), fetchall=True)
        if len(players) < 2: await q.answer("❌ حداقل ۲ بازیکن!", show_alert=True); return
        plist = [p["user_id"] for p in players]
        random.shuffle(plist)
        stages = get_stages(len(plist))
        cs = stages[0]
        query("DELETE FROM matches WHERE tournament_id = ?", (t["id"],))
        mo = 0
        for i in range(0, len(plist), 2):
            if i + 1 < len(plist):
                query("INSERT INTO matches (tournament_id, stage, player1_id, player2_id, match_order) VALUES (?, ?, ?, ?, ?)", (t["id"], cs, plist[i], plist[i+1], mo))
                mo += 1
        query("UPDATE tournaments SET status = 'active', stage = ? WHERE id = ?", (cs, t["id"]))
        for m in query("SELECT * FROM matches WHERE tournament_id = ? AND stage = ?", (t["id"], cs), fetchall=True):
            for uid in [m["player1_id"], m["player2_id"]]:
                try: await context.bot.send_message(chat_id=uid, text=f"🎯 مسابقه شروع شد!\n\n🏆 {t['name']}\n📊 {cs}\n\nروی دکمه زیر کلیک کنید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🎯 شروع مسابقه", callback_data=f"play_match_{m['id']}")]]))
                except: pass
        await q.edit_message_text(f"✅ قرعه کشی انجام شد!\n\n📊 {cs}\n👥 {len(plist)} بازیکن\n🎯 {mo} مسابقه", reply_markup=admin_panel_keyboard())

    elif data.startswith("play_match_"):
        mid = int(data.split("_")[2])
        m = query("SELECT * FROM matches WHERE id = ?", (mid,), fetchone=True)
        if not m: await q.answer("❌ یافت نشد!", show_alert=True); return
        if user.id not in [m["player1_id"], m["player2_id"]]: await q.answer("❌ شما در این مسابقه نیستید!", show_alert=True); return
        if m["status"] == "finished": await q.answer("❌ تمام شده!", show_alert=True); return
        query("UPDATE matches SET status = 'active' WHERE id = ?", (mid,))
        t1 = [random.randint(1, 60) for _ in range(5)]
        t2 = [random.randint(1, 60) for _ in range(5)]
        s1, s2 = sum(t1), sum(t2)
        for i, sc in enumerate(t1, 1): query("INSERT INTO throws (match_id, player_id, throw_number, score) VALUES (?, ?, ?, ?)", (mid, m["player1_id"], i, sc))
        for i, sc in enumerate(t2, 1): query("INSERT INTO throws (match_id, player_id, throw_number, score) VALUES (?, ?, ?, ?)", (mid, m["player2_id"], i, sc))
        if s1 == s2:
            e1, e2 = random.randint(1, 60), random.randint(1, 60)
            s1 += e1; s2 += e2
            query("INSERT INTO throws (match_id, player_id, throw_number, score) VALUES (?, ?, ?, ?)", (mid, m["player1_id"], 6, e1))
            query("INSERT INTO throws (match_id, player_id, throw_number, score) VALUES (?, ?, ?, ?)", (mid, m["player2_id"], 6, e2))
        wid = m["player1_id"] if s1 > s2 else m["player2_id"]
        query("UPDATE matches SET player1_score = ?, player2_score = ?, winner_id = ?, status = 'finished' WHERE id = ?", (s1, s2, wid, mid))
        query("UPDATE players SET total_wins = total_wins + 1 WHERE user_id = ?", (wid,))
        p1n = get_name_db(query("SELECT * FROM players WHERE user_id = ?", (m["player1_id"],), fetchone=True))
        p2n = get_name_db(query("SELECT * FROM players WHERE user_id = ?", (m["player2_id"],), fetchone=True))
        wn = get_name_db(query("SELECT * FROM players WHERE user_id = ?", (wid,), fetchone=True))
        rtxt = f"🎯 نتیجه مسابقه\n\n🏆 {p1n}\nپرتاب‌ها: {' - '.join(map(str,t1))}\nمجموع: {s1}\n\n🆚\n\n🏆 {p2n}\nپرتاب‌ها: {' - '.join(map(str,t2))}\nمجموع: {s2}\n\n👑 برنده: {wn}"
        for uid in [m["player1_id"], m["player2_id"]]:
            try: await context.bot.send_message(chat_id=uid, text=rtxt)
            except: pass
        # انتقال به مرحله بعد
        tour = query("SELECT * FROM tournaments WHERE id = ?", (m["tournament_id"],), fetchone=True)
        all_m = query("SELECT * FROM matches WHERE tournament_id = ? AND stage = ?", (m["tournament_id"], tour["stage"]), fetchall=True)
        if all(x["status"] == "finished" for x in all_m):
            total_p = query("SELECT COUNT(*) as c FROM registrations WHERE tournament_id = ? AND status = 'approved'", (m["tournament_id"],), fetchone=True)["c"]
            stages = get_stages(total_p)
            csi = stages.index(tour["stage"]) if tour["stage"] in stages else -1
            if csi + 1 < len(stages):
                ns = stages[csi + 1]
                winners = [x["winner_id"] for x in all_m]
                if len(winners) >= 2:
                    query("DELETE FROM matches WHERE tournament_id = ? AND stage = ?", (m["tournament_id"], ns))
                    mo = 0
                    for i in range(0, len(winners), 2):
                        if i + 1 < len(winners):
                            query("INSERT INTO matches (tournament_id, stage, player1_id, player2_id, match_order) VALUES (?, ?, ?, ?, ?)", (m["tournament_id"], ns, winners[i], winners[i+1], mo))
                            mo += 1
                    query("UPDATE tournaments SET stage = ? WHERE id = ?", (ns, m["tournament_id"]))
                    for nm in query("SELECT * FROM matches WHERE tournament_id = ? AND stage = ?", (m["tournament_id"], ns), fetchall=True):
                        for uid in [nm["player1_id"], nm["player2_id"]]:
                            try: await context.bot.send_message(chat_id=uid, text=f"🎉 صعود به {ns}!\n\n🏆 {tour['name']}\n\nمنتظر مسابقه باشید.")
                            except: pass
                else:
                    champ = winners[0]
                    query("UPDATE tournaments SET status = 'finished', winner_id = ? WHERE id = ?", (champ, m["tournament_id"]))
                    query("UPDATE players SET championships = championships + 1 WHERE user_id = ?", (champ,))
                    try: await context.bot.send_message(chat_id=champ, text=f"👑 تبریک! قهرمان جام {tour['name']} شدید!")
                    except: pass
        await q.answer("✅ مسابقه انجام شد!", show_alert=True)

    elif data == "view_matches":
        t = query("SELECT * FROM tournaments WHERE status = 'active' ORDER BY id DESC LIMIT 1", fetchone=True)
        if not t: txt = "❌ جام فعال ندارید!"
        else:
            matches = query("SELECT * FROM matches WHERE tournament_id = ? ORDER BY match_order", (t["id"],), fetchall=True)
            txt = f"📋 مسابقات {t['name']}\n📊 {t['stage']}\n\n"
            sm = {"waiting": "⏳", "active": "🎯", "finished": "✅"}
            for m in matches:
                p1n = get_name_db(query("SELECT * FROM players WHERE user_id = ?", (m["player1_id"],), fetchone=True))
                p2n = get_name_db(query("SELECT * FROM players WHERE user_id = ?", (m["player2_id"],), fetchone=True))
                txt += f"🎯 مسابقه {m['match_order']+1}:\n👤 {p1n} VS {p2n}\n📊 {m['player1_score']} - {m['player2_score']}\n"
                if m["winner_id"]: txt += f"🏆 برنده: {get_name_db(query('SELECT * FROM players WHERE user_id = ?', (m['winner_id'],), fetchone=True))}\n"
                txt += f"وضعیت: {sm.get(m['status'],'نامشخص')}\n\n"
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")]]))

    elif data == "view_champion":
        t = query("SELECT * FROM tournaments WHERE status = 'finished' ORDER BY id DESC LIMIT 1", fetchone=True)
        if t and t["winner_id"]:
            w = query("SELECT * FROM players WHERE user_id = ?", (t["winner_id"],), fetchone=True)
            txt = f"👑 قهرمان جام {t['name']}\n\n🏆 {get_name_db(w)}"
        else: txt = "❌ قهرمانی مشخص نشده!"
        await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")]]))

    elif data == "manage_boosters":
        if not is_admin: await q.answer("❌ غیرمجاز!", show_alert=True); return
        kb = [
            [InlineKeyboardButton("🎯 دادن دقت", callback_data="give_accuracy")],
            [InlineKeyboardButton("🔥 دادن قدرت", callback_data="give_power")],
            [InlineKeyboardButton("🍀 دادن شانس", callback_data="give_luck")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")],
        ]
        await q.edit_message_text("🎁 مدیریت تقویتی ها\n\nیک نوع را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(kb))

    elif data.startswith("give_"):
        if not is_admin: await q.answer("❌ غیرمجاز!", show_alert=True); return
        context.user_data["giving_booster"] = data.split("_")[1]
        context.user_data["booster_step"] = "select_player"
        await q.edit_message_text("👤 آیدی عددی بازیکن را وارد کنید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 لغو", callback_data="manage_boosters")]]))

# ==================== TEXT HANDLER ====================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text

    if context.user_data.get("creating_tournament") and user.id == ADMIN_ID:
        context.user_data["tournament_name"] = text
        context.user_data["creating_tournament"] = False
        context.user_data["setting_capacity"] = True
        await update.message.reply_text(f"✅ نام جام: {text}\n\n📝 تعداد نفرات را وارد کنید:")
        return

    if context.user_data.get("setting_capacity") and user.id == ADMIN_ID:
        try:
            cap = int(text)
            if cap < 2: await update.message.reply_text("❌ حداقل ۲ نفر!"); return
            name = context.user_data.get("tournament_name", "جام دارت")
            query("INSERT INTO tournaments (name, capacity, created_by) VALUES (?, ?, ?)", (name, cap, user.id))
            context.user_data["setting_capacity"] = False
            await update.message.reply_text(f"✅ جام جدید ساخته شد!\n\n📋 نام: {name}\n👥 ظرفیت: {cap} نفر", reply_markup=admin_panel_keyboard())
        except ValueError: await update.message.reply_text("❌ عدد معتبر وارد کنید!")
        return

    if context.user_data.get("booster_step") == "select_player" and user.id == ADMIN_ID:
        try:
            tid = int(text)
            context.user_data["booster_target"] = tid
            context.user_data["booster_step"] = "select_quantity"
            await update.message.reply_text("✅ بازیکن انتخاب شد.\n\n📝 تعداد را وارد کنید:")
        except ValueError: await update.message.reply_text("❌ آیدی عددی معتبر وارد کنید!")
        return

    if context.user_data.get("booster_step") == "select_quantity" and user.id == ADMIN_ID:
        try:
            qty = int(text)
            if qty < 1: await update.message.reply_text("❌ حداقل ۱!"); return
            tid = context.user_data["booster_target"]
            bt = context.user_data["giving_booster"]
            ex = query("SELECT * FROM boosters WHERE user_id = ? AND booster_type = ?", (tid, bt), fetchone=True)
            if ex: query("UPDATE boosters SET quantity = quantity + ? WHERE user_id = ? AND booster_type = ?", (qty, tid, bt))
            else: query("INSERT INTO boosters (user_id, booster_type, quantity) VALUES (?, ?, ?)", (tid, bt, qty))
            em = {"accuracy": "🎯", "power": "🔥", "luck": "🍀"}
            nm = {"accuracy": "دقت", "power": "قدرت", "luck": "شانس"}
            context.user_data["booster_step"] = None
            context.user_data["giving_booster"] = None
            context.user_data["booster_target"] = None
            await update.message.reply_text(f"✅ تقویتی داده شد!\n\n{em.get(bt,'')} {nm.get(bt,'')}\n👤 به بازیکن: {tid}\n📦 تعداد: {qty}", reply_markup=admin_panel_keyboard())
        except ValueError: await update.message.reply_text("❌ عدد معتبر وارد کنید!")
        return

# ==================== RUN BOT ====================
def run_bot():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    print("🤖 ربات راه اندازی شد!")
    app.run_polling()

# ==================== MAIN ====================
if __name__ == "__main__":
    init_db()
    threading.Thread(target=run_bot, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    print(f"🌐 Flask on port {port}")
    flask_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
