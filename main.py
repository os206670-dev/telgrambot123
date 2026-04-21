import logging
import json
import os
from datetime import datetime, timedelta
from flask import Flask
from threading import Thread
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# --- 1. سيرفر Flask لإبقاء البوت حياً (لـ Render Web Service) ---
server = Flask('')

@server.route('/')
def home():
    return "البوت يعمل بكفاءة!"

def run():
    port = int(os.environ.get("PORT", 8080))
    server.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()

# --- 2. الإعدادات والبيانات ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

TOKEN = "8254293210:AAFuREZZ4vVneXRs3i3A4K_pwdzH7qdQhHQ"
ADMIN_GROUP_ID = -1003983944808 
DATA_FILE = "library_data.json"

BORROWED_BOOKS = set()
ACTIVE_LOANS = {}

LIBRARY_DATA = {
    'تطوير الذات والإدارة': {
        'لا تحزن (لا تخزن)': 'نصائح لمواجهة الهموم والقلق والمركزة على الجانب الإيماني.',
        'مشوار الإصرار والتحدي': 'قصص ومواقف تحفزك على التمسك بأهدافك رغم الصعوبات.',
        'ركز': 'تعلم كيف تبتعد عن المشتتات وتوجه انتباهك الكامل لمهمة واحدة.',
        'أول قاعدتين بالقيادة': 'يشرح أهم صفتين في القائد: كن قدوة، واهتم بفريقك.',
        'عندما تكون ناجياً ومحباً': 'النجاح المتوازن الذي يجمع بين الإنجاز والراحة النفسية.'
    },
    'سلسلة آفاق العلمية': {
        'الطاقة المتجددة': 'كيف نستخرج الكهرباء من الشمس والرياح والماء.',
        'القوة المحركة': 'يتحدث عن المحركات والآلات وتحول الطاقة لحركة.',
        'الأبنية': 'هندسة البناء من البيوت البسيطة لناطحات السحاب.',
        'الزلازل والبراكين': 'أسباب اهتزاز الأرض وانفجار الحمم.',
        'الحرائق والفيضانات': 'أخطار الطبيعة وكيفية مواجهتها.'
    },
    'العلوم الشرعية والتاريخ': {
        'السيرة النبوية': 'قصة حياة الرسول ﷺ بأسلوب تاريخي ممتع.',
        'الصحيح': 'مرجع للأحاديث النبوية الصحيحة.',
        'تفسير العشر الأخير': 'شرح ميسر لمعاني سور القرآن الكريم.',
        'الفرح بالقرآن': 'الراحة النفسية في تدبر القرآن.',
        'رجال من التاريخ': 'قصص عن شخصيات عظيمة أثرت في التاريخ الإسلامي.',
        'كيف تعالج مريضك بالرقية': 'دليل حول الرقية الشرعية الصحيحة.'
    },
    'روايات وكتب أدبية ومنهجية': {
        'آفاق بلا حدود': 'يوسع مداركك حول طموح الإنسان وقدراته.',
        'اللوحة القتالية': 'عمل أدبي يتناول التحديات بأسلوب درامي.',
        'عندما تكون الغربة أوطاناً': 'خواطر حول البحث عن السلام الداخلي.',
        'قفص الموت الغامض': 'رواية إثارة وغموض تتطلب ذكاءً.',
        'إلى الظل': 'البحث عن الهدوء والسكينة بعيداً عن ضجيج الحياة.',
        'قواعد البحث العلمي': 'الخطوات الصحيحة لكتابة البحوث المنظمة.'
    }
}

# --- 3. وظائف إدارة الذاكرة ---
def save_data():
    try:
        serializable_loans = {}
        for uid, loan in ACTIVE_LOANS.items():
            copy_loan = loan.copy()
            copy_loan['date'] = loan['date'].isoformat()
            copy_loan['return_date'] = loan['return_date'].isoformat()
            serializable_loans[str(uid)] = copy_loan
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"BORROWED_BOOKS": list(BORROWED_BOOKS), "ACTIVE_LOANS": serializable_loans}, f, ensure_ascii=False, indent=4)
    except: pass

def load_data():
    global BORROWED_BOOKS, ACTIVE_LOANS
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                BORROWED_BOOKS = set(data.get("BORROWED_BOOKS", []))
                for uid, l in data.get("ACTIVE_LOANS", {}).items():
                    ACTIVE_LOANS[int(uid)] = {**l, 'date': datetime.fromisoformat(l['date']), 'return_date': datetime.fromisoformat(l['return_date'])}
        except: pass

def format_date(dt):
    days = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
    return f"{days[dt.weekday()]} {dt.strftime('%Y/%m/%d')}"

# --- 4. معالجات البوت ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    load_data()
    user_id = update.effective_user.id
    if user_id in ACTIVE_LOANS:
        loan = ACTIVE_LOANS[user_id]
        kb = [[InlineKeyboardButton("📥 طلب إرجاع الكتاب الآن", callback_data="req_ret")]]
        await update.message.reply_text(f"📍 **أهلاً بك!**\n\nأنت تستعير حالياً: **{loan['book']}**\n📅 موعد الإرجاع: {format_date(loan['return_date'])}", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
        return
    await update.message.reply_text("✨ **مرحباً بك في مكتبة ابن العميد**\n\nيرجى كتابة **اسمك الثلاثي**:")
    context.user_data['step'] = 'NAME'

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step = context.user_data.get('step')
    if not step: return
    text = update.message.text.strip()
    if step == 'NAME':
        context.user_data['student_name'] = text
        await update.message.reply_text(f"مرحباً {text}، أرسل **فصلك**:")
        context.user_data['step'] = 'CLASS'
    elif step == 'CLASS':
        context.user_data['student_class'] = text
        await update.message.reply_text("📞 أرسل **رقم جوالك**:")
        context.user_data['step'] = 'PHONE'
    elif step == 'PHONE':
        context.user_data['student_phone'] = text
        kb = [[InlineKeyboardButton(cat, callback_data=f"cat_{cat}")] for cat in LIBRARY_DATA.keys()]
        await update.message.reply_text("✅ تم التسجيل! اختر القسم:", reply_markup=InlineKeyboardMarkup(kb))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if query.data.startswith("cat_"):
        cat = query.data.split("_", 1)[1]
        context.user_data['current_cat'] = cat
        btns = [[InlineKeyboardButton(f"{'🔴' if b in BORROWED_BOOKS else '🟢'} {b}", callback_data=f"info_{b}")] for b in LIBRARY_DATA[cat].keys()]
        btns.append([InlineKeyboardButton("🔙 العودة", callback_data="back")])
        await query.edit_message_text(f"📚 **قسم: {cat}**", reply_markup=InlineKeyboardMarkup(btns), parse_mode='Markdown')

    elif query.data.startswith("info_"):
        book = query.data.split("_", 1)[1]
        cat = context.user_data.get('current_cat')
        desc = LIBRARY_DATA[cat][book]
        kb = [[InlineKeyboardButton("✅ تأكيد الاستعارة", callback_data=f"brw_{book}")]] if book not in BORROWED_BOOKS and user_id not in ACTIVE_LOANS else []
        kb.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"cat_{cat}")])
        await query.edit_message_text(f"📖 **{book}**\n\n{desc}", reply_markup=InlineKeyboardMarkup(kb))

    elif query.data.startswith("brw_"):
        book = query.data.split("_", 1)[1]
        now = datetime.now()
        ret_date = now + timedelta(days=7)
        BORROWED_BOOKS.add(book)
        loan = {'book': book, 'name': context.user_data.get('student_name'), 'class': context.user_data.get('student_class'), 'phone': context.user_data.get('student_phone'), 'date': now, 'return_date': ret_date}
        ACTIVE_LOANS[user_id] = loan
        save_data()
        await query.edit_message_text(f"🎉 تمت الاستعارة!\n📅 الإرجاع: {format_date(ret_date)}")
        admin_report = f"🔔 **إشعار استعارة**\n👤 {loan['name']}\n🏫 الفصل: {loan['class']}\n📞 الجوال: {loan['phone']}\n📚 الكتاب: {book}"
        await context.bot.send_message(chat_id=ADMIN_GROUP_ID, text=admin_report)

    elif query.data == "req_ret":
        loan = ACTIVE_LOANS.get(user_id)
        if loan:
            kb = [[InlineKeyboardButton("✅ تأكيد الاستلام", callback_data=f"conf_ret_{user_id}")]]
            await context.bot.send_message(chat_id=ADMIN_GROUP_ID, text=f"📥 طلب إرجاع من {loan['name']}\nالكتاب: {loan['book']}", reply_markup=InlineKeyboardMarkup(kb))
            await query.edit_message_text("⏳ تم إرسال طلبك للإدارة.")

    elif query.data.startswith("conf_ret_"):
        uid = int(query.data.split("_")[2])
        if uid in ACTIVE_LOANS:
            book = ACTIVE_LOANS[uid]['book']
            BORROWED_BOOKS.discard(book)
            del ACTIVE_LOANS[uid]
            save_data()
            await query.edit_message_text(f"✅ تم استلام ({book})")
            try: await context.bot.send_message(chat_id=uid, text=f"✅ تم تأكيد إرجاع ({book}) بنجاح.")
            except: pass

    elif query.data == "back":
        kb = [[InlineKeyboardButton(cat, callback_data=f"cat_{cat}")] for cat in LIBRARY_DATA.keys()]
        await query.edit_message_text("📂 الأقسام:", reply_markup=InlineKeyboardMarkup(kb))

# --- 5. التشغيل النهائي ---
def main():
    load_data()
    keep_alive() # تشغيل Flask في الخلفية
    
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(handle_callback))
    
    print("البوت بدأ العمل...")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
