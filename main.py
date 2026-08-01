import asyncio, random, datetime, json, os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "8642125258:AAFYNTNEP2MGkYvDuFVyl_SzaBqPfFX0chE")
MAIN_ADMINS = [int(x) for x in os.getenv("MAIN_ADMINS", "7832771827").split(",") if x]
PROTEST_THRESHOLD = 20
STATEMENT_COOLDOWN = 900

COUNTRIES = {
    "🇺🇸":"آمریکا","🇷🇺":"روسیه","🇨🇳":"چین","🇬🇧":"انگلیس","🇫🇷":"فرانسه",
    "🇩🇪":"آلمان","🇯🇵":"ژاپن","🇮🇹":"ایتالیا","🇨🇦":"کانادا","🇧🇷":"برزیل",
    "🇮🇳":"هند","🇦🇺":"استرالیا","🇰🇷":"کره جنوبی","🇹🇷":"ترکیه","🇸🇦":"عربستان",
    "🇮🇷":"ایران","🇮🇱":"اسرائیل","🇪🇬":"مصر","🇵🇰":"پاکستان","🇲🇽":"مکزیک",
    "🇪🇸":"اسپانیا","🇦🇷":"آرژانتین","🇿🇦":"آفریقای جنوبی","🇳🇬":"نیجریه","🇮🇩":"اندونزی"
}

BUILDING_COSTS = {
    "house": {"gold": 100}, "road": {"gold": 50}, "barrack": {"gold": 300},
    "hospital": {"gold": 250}, "school": {"gold": 200}, "factory": {"gold": 400},
    "farm": {"gold": 150}, "oil_rig": {"gold": 350}
}

class DB:
    FILE = "ww_data.json"
    def __init__(self):
        try:
            with open(self.FILE, 'r', encoding='utf-8') as f: self.data = json.load(f)
        except:
            self.data = {"players": {}, "cities": {}, "statements": [], "channel": None}
    def save(self):
        with open(self.FILE, 'w', encoding='utf-8') as f: json.dump(self.data, f, ensure_ascii=False, indent=2, default=str)
    def player(self, uid): return self.data["players"].get(str(uid))
    def city(self, uid): return self.data["cities"].get(str(uid))
    def create(self, uid, username, name, emoji):
        self.data["players"][str(uid)] = {"id": uid, "username": username, "name": name, "country": emoji, "country_name": COUNTRIES[emoji], "gold": 1000, "oil": 500, "food": 500, "power": 100, "wins": 0, "losses": 0, "banned": False, "last_statement": None}
        self.data["cities"][str(uid)] = {"name": "شهر جدید", "population": 100, "houses": 0, "roads": 0, "barracks": 0, "hospitals": 0, "schools": 0, "factories": 0, "farms": 0, "oil_rigs": 0, "happiness": 50, "support": 50, "gold_prod": 10}
        self.save()
    def update_player(self, uid, data): self.data["players"][str(uid)].update(data); self.save()
    def update_city(self, uid, data): self.data["cities"][str(uid)].update(data); self.save()
    def top_players(self, n=10):
        ps = list(self.data["players"].values()); ps.sort(key=lambda x: x.get("power", 0), reverse=True); return ps[:n]
    def add_statement(self, stmt): self.data.setdefault("statements", []).append(stmt); self.save()
    def pending_statements(self): return [s for s in self.data.get("statements", []) if not s.get("approved")]
    def approve_statement(self, idx):
        stmts = self.data.get("statements", [])
        if idx < len(stmts): stmts[idx]["approved"] = True; self.save(); return stmts[idx]
    def reject_statement(self, idx):
        stmts = self.data.get("statements", [])
        if idx < len(stmts): stmts.pop(idx); self.save()
    def get_channel(self): return self.data.get("channel")
    def set_channel(self, ch_id): self.data["channel"] = ch_id; self.save()

db = DB()

class Bot:
    def __init__(self):
        self.app = Application.builder().token(BOT_TOKEN).build()
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("menu", self.menu))
        self.app.add_handler(CommandHandler("country", self.country))
        self.app.add_handler(CommandHandler("city", self.city))
        self.app.add_handler(CommandHandler("attack", self.attack))
        self.app.add_handler(CommandHandler("ranking", self.ranking))
        self.app.add_handler(CommandHandler("statement", self.statement_cmd))
        self.app.add_handler(CommandHandler("admin", self.admin))
        self.app.add_handler(CommandHandler("setchannel", self.set_channel))
        self.app.add_handler(CallbackQueryHandler(self.buttons))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.text))
    def is_admin(self, uid): return uid in MAIN_ADMINS
    
    async def start(self, u, c):
        kb = []; row = []
        for e, n in COUNTRIES.items():
            row.append(InlineKeyboardButton(f"{e} {n}", callback_data=f"pick_{e}"))
            if len(row) == 3: kb.append(row); row = []
        if row: kb.append(row)
        await u.message.reply_text("🌍 جنگ جهانی\nکشور انتخاب کن:", reply_markup=InlineKeyboardMarkup(kb))
    
    async def menu(self, u, c):
        kb = [[InlineKeyboardButton("🏴 کشور من", callback_data="my_country"), InlineKeyboardButton("🏙 شهر من", callback_data="my_city")], [InlineKeyboardButton("⚔ حمله", callback_data="attack_menu"), InlineKeyboardButton("📜 بیانیه", callback_data="statement_menu")], [InlineKeyboardButton("🏆 رده‌بندی", callback_data="ranking_menu")]]
        if self.is_admin(u.effective_user.id): kb.append([InlineKeyboardButton("👑 مدیریت", callback_data="admin_panel")])
        await u.message.reply_text("🎮 منوی اصلی", reply_markup=InlineKeyboardMarkup(kb))
    
    async def buttons(self, u, c):
        q = u.callback_query; await q.answer(); d = q.data; uid = q.from_user.id
        
        if d.startswith("pick_"):
            emoji = d.replace("pick_", "")
            if db.player(uid): await q.answer("❌ قبلاً انتخاب کردی!", show_alert=True); return
            db.create(uid, q.from_user.username, q.from_user.first_name, emoji)
            await q.edit_message_text(f"✅ {COUNTRIES[emoji]} انتخاب شد!\n/menu")
        
        elif d == "main_menu":
            kb = [[InlineKeyboardButton("🏴 کشور من", callback_data="my_country"), InlineKeyboardButton("🏙 شهر من", callback_data="my_city")], [InlineKeyboardButton("⚔ حمله", callback_data="attack_menu"), InlineKeyboardButton("📜 بیانیه", callback_data="statement_menu")], [InlineKeyboardButton("🏆 رده‌بندی", callback_data="ranking_menu")]]
            if self.is_admin(uid): kb.append([InlineKeyboardButton("👑 مدیریت", callback_data="admin_panel")])
            await q.edit_message_text("🎮 منوی اصلی", reply_markup=InlineKeyboardMarkup(kb))
        
        elif d == "my_country":
            p = db.player(uid)
            if not p: await q.edit_message_text("❌"); return
            txt = f"🏴 {p['country_name']} {p['country']}\n⚡ قدرت: {p['power']:.0f}\n💰 طلا: {p['gold']:.0f}\n🏆 برد:{p['wins']} باخت:{p['losses']}"
            await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]]))
        
        elif d == "my_city":
            ct = db.city(uid)
            if not ct: await q.edit_message_text("❌"); return
            txt = f"🏙 {ct['name']}\n👥 {ct['population']}\n😊 رضایت: {ct['happiness']:.0f}%\n🏠 خانه:{ct['houses']} ⚔ پادگان:{ct['barracks']}\n💰 تولید: {ct['gold_prod']:.0f}/h"
            kb = [[InlineKeyboardButton("🏠 خانه", callback_data="b_house"), InlineKeyboardButton("⚔ پادگان", callback_data="b_barrack")], [InlineKeyboardButton("🏥 بیمارستان", callback_data="b_hospital"), InlineKeyboardButton("📚 مدرسه", callback_data="b_school")], [InlineKeyboardButton("🏭 کارخانه", callback_data="b_factory"), InlineKeyboardButton("🌾 مزرعه", callback_data="b_farm")], [InlineKeyboardButton("🛣️ جاده", callback_data="b_road"), InlineKeyboardButton("🛢 چاه نفت", callback_data="b_oil_rig")], [InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]]
            await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))
        
        elif d.startswith("b_"):
            btype = d.replace("b_", ""); p, ct = db.player(uid), db.city(uid)
            cost = BUILDING_COSTS.get(btype, {"gold": 100})
            if p['gold'] < cost['gold']: await q.answer("❌ طلا کم!", show_alert=True); return
            p['gold'] -= cost['gold']
            ct[btype + 's'] = ct.get(btype + 's', 0) + 1
            ct['happiness'] = min(100, ct['happiness'] + 10)
            ct['gold_prod'] += 5
            db.update_player(uid, p); db.update_city(uid, ct)
            await q.answer("✅ ساخته شد!", show_alert=True)
        
        elif d == "attack_menu":
            ps = [p for p in db.top_players(20) if p['id'] != uid][:10]
            kb = [[InlineKeyboardButton(f"{p['country']} {p['country_name']} (⚡{p['power']:.0f})", callback_data=f"atk_{p['id']}")] for p in ps]
            kb.append([InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")])
            await q.edit_message_text("⚔ انتخاب هدف:", reply_markup=InlineKeyboardMarkup(kb))
        
        elif d.startswith("atk_"):
            tid = int(d.replace("atk_", "")); atk, dfd = db.player(uid), db.player(tid)
            if not dfd: await q.edit_message_text("❌"); return
            if random.random() < (atk['power']/(atk['power']+dfd['power'])):
                stolen = min(dfd['gold']*0.2, dfd['gold']); dfd['gold'] -= stolen; atk['gold'] += stolen
                atk['wins'] += 1; dfd['losses'] += 1
                db.update_player(uid, atk); db.update_player(tid, dfd)
                await q.edit_message_text(f"🎉 پیروزی! +{stolen:.0f} طلا", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]]))
            else:
                atk['losses'] += 1; atk['power'] *= 0.9; db.update_player(uid, atk)
                await q.edit_message_text("💔 شکست!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]]))
        
        elif d == "ranking_menu":
            ps = db.top_players(10); txt = "🏆 رده‌بندی:\n"
            for i, p in enumerate(ps, 1):
                m = ["🥇","🥈","🥉"][i-1] if i<=3 else f"{i}."
                txt += f"{m} {p['country']} {p['country_name']} - ⚡{p['power']:.0f}\n"
            await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]]))
        
        elif d == "statement_menu":
            c.user_data['waiting'] = True
            await q.edit_message_text("📜 متن بیانیه را وارد کن:\n⏰ 15 دقیقه بین بیانیه‌ها")
        
        elif d == "admin_panel":
            if not self.is_admin(uid): await q.answer("❌", show_alert=True); return
            kb = [[InlineKeyboardButton("📋 تأیید بیانیه‌ها", callback_data="admin_approvals"), InlineKeyboardButton("📢 تنظیم کانال", callback_data="admin_channel")], [InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]]
            await q.edit_message_text("👑 پنل مدیریت", reply_markup=InlineKeyboardMarkup(kb))
        
        elif d == "admin_approvals":
            stmts = db.pending_statements()
            if not stmts: await q.edit_message_text("📋 بیانیه‌ای نیست!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="admin_panel")]])); return
            txt = "📋 در انتظار:\n"; kb = []
            for i, s in enumerate(stmts):
                txt += f"\n{i+1}. {s.get('country','?')}: {s.get('text','')[:40]}..."
                kb.append([InlineKeyboardButton(f"✅ {i+1}", callback_data=f"app_{i}"), InlineKeyboardButton(f"❌ {i+1}", callback_data=f"rej_{i}")])
            kb.append([InlineKeyboardButton("🔙 بازگشت", callback_data="admin_panel")])
            await q.edit_message_text(txt, reply_markup=InlineKeyboardMarkup(kb))
        
        elif d.startswith("app_"):
            i = int(d.replace("app_", "")); stmt = db.approve_statement(i)
            if stmt:
                ch = db.get_channel()
                if ch:
                    try: await c.bot.send_message(ch, f"📜 {stmt.get('country','')}:\n{stmt.get('text','')}")
                    except: pass
            await q.answer("✅", show_alert=True)
        
        elif d.startswith("rej_"):
            db.reject_statement(int(d.replace("rej_", "")))
            await q.answer("❌", show_alert=True)
        
        elif d == "admin_channel":
            await q.edit_message_text("📢 /setchannel [آیدی عددی]\nمثال: /setchannel -1001234567890")
    
    async def country(self, u, c):
        p = db.player(u.effective_user.id)
        if not p: await u.message.reply_text("❌ /start"); return
        await u.message.reply_text(f"🏴 {p['country_name']} {p['country']}\n⚡ قدرت: {p['power']:.0f}\n💰 طلا: {p['gold']:.0f}\n🏆 برد:{p['wins']} باخت:{p['losses']}")
    
    async def city(self, u, c):
        ct = db.city(u.effective_user.id)
        if not ct: await u.message.reply_text("❌ /start"); return
        await u.message.reply_text(f"🏙 {ct['name']}\n👥 {ct['population']}\n😊 رضایت: {ct['happiness']:.0f}%\n🏠 خانه:{ct['houses']} ⚔ پادگان:{ct['barracks']}")
    
    async def attack(self, u, c):
        if not c.args: await u.message.reply_text("/attack [user_id]"); return
        try: tid = int(c.args[0])
        except: await u.message.reply_text("❌"); return
        atk, dfd = db.player(u.effective_user.id), db.player(tid)
        if not atk or not dfd: await u.message.reply_text("❌"); return
        if random.random() < (atk['power']/(atk['power']+dfd['power'])):
            s = min(dfd['gold']*0.2, dfd['gold']); dfd['gold']-=s; atk['gold']+=s
            atk['wins']+=1; dfd['losses']+=1
            db.update_player(u.effective_user.id, atk); db.update_player(tid, dfd)
            await u.message.reply_text(f"🎉 +{s:.0f} طلا!")
        else:
            atk['losses']+=1; atk['power']*=0.9; db.update_player(u.effective_user.id, atk)
            await u.message.reply_text("💔 شکست!")
    
    async def ranking(self, u, c):
        ps = db.top_players(10); txt = "🏆 رده‌بندی:\n"
        for i,p in enumerate(ps,1):
            m = ["🥇","🥈","🥉"][i-1] if i<=3 else f"{i}."
            txt += f"{m} {p['country']} {p['country_name']} - ⚡{p['power']:.0f}\n"
        await u.message.reply_text(txt)
    
    async def statement_cmd(self, u, c):
        c.user_data['waiting'] = True
        await u.message.reply_text("📜 متن بیانیه:")
    
    async def text(self, u, c):
        uid = u.effective_user.id
        if c.user_data.get('waiting'):
            p = db.player(uid)
            if not p: return
            if p.get('last_statement'):
                el = (datetime.datetime.now() - datetime.datetime.fromisoformat(p['last_statement'])).total_seconds()
                if el < STATEMENT_COOLDOWN:
                    await u.message.reply_text(f"⏰ {int((STATEMENT_COOLDOWN-el)//60)} دقیقه صبر کن!"); c.user_data['waiting']=False; return
            db.add_statement({"user_id":uid,"country":p['country_name'],"text":u.message.text,"approved":False})
            p['last_statement'] = str(datetime.datetime.now()); db.update_player(uid, p)
            await u.message.reply_text("✅ ثبت شد!"); c.user_data['waiting'] = False
    
    async def admin(self, u, c):
        if not self.is_admin(u.effective_user.id): return
        kb = [[InlineKeyboardButton("📋 بیانیه‌ها", callback_data="admin_approvals"), InlineKeyboardButton("📢 کانال", callback_data="admin_channel")]]
        await u.message.reply_text("👑 پنل مدیریت", reply_markup=InlineKeyboardMarkup(kb))
    
    async def set_channel(self, u, c):
        if not self.is_admin(u.effective_user.id): return
        if not c.args: await u.message.reply_text("/setchannel [آیدی]"); return
        try: db.set_channel(int(c.args[0])); await u.message.reply_text(f"✅ {c.args[0]}")
        except: await u.message.reply_text("❌")
    
    async def protest_checker(self):
        while True:
            await asyncio.sleep(300)
            try:
                for uid, ct in db.data["cities"].items():
                    if ct['happiness'] < PROTEST_THRESHOLD or ct['support'] < PROTEST_THRESHOLD:
                        p = db.player(int(uid))
                        if not p: continue
                        sev = 1 if ct['happiness']>10 else 3 if ct['happiness']>5 else 5
                        p['power'] = max(10, p['power']-sev*10); p['gold'] = max(0, p['gold']-sev*50)
                        ct['happiness'] = max(0, ct['happiness']-5)
                        db.update_player(int(uid), p); db.update_city(int(uid), ct)
                        ch = db.get_channel()
                        if ch:
                            try: await self.app.bot.send_message(ch, f"📰 اعتراض در {p['country_name']} (رضایت:{ct['happiness']:.0f}%)")
                            except: pass
            except: pass

bot = Bot()
app = bot.app

async def main():
    asyncio.create_task(bot.protest_checker())
    print("🌍 World War Bot Started!")
    await app.run_polling()

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()
