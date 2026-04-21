import logging
import re
import json
import os
from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# إعدادات التسجيل (Logging) لضمان مراقبة أداء البوت على Render
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- جلب التوكن من إعدادات السيرفر (Render) ---
TOKEN = os.getenv('BOT_TOKEN') 
ADMIN_GROUP_ID = -1003983944808 
DATA_FILE = "library_storage.json"

BORROWED_BOOKS = set()
ACTIVE_LOANS = {}

# بيانات المكتبة (المحتوى)
LIBRARY_DATA = {
    'تطوير الذات والإدارة': {
        'لا تحزن (لا تخزن)': 'نصائح لمواجهة الهموم والقلق والتركيز على الجانب الإيماني.',
        'مشوار الإصرار والتحدي': 'قصص ومواقف تحفزك على التمسك بأهدافك رغم الصعوبات.',
        'ركز': 'تعلم كيف تبتعد عن المشتتات وتوجه انتباهك الكامل لمهمة واحدة لتنجزها بإتقان.',
        'أول قاعدتين بالقيادة': 'يشرح أهم صفتين يجب أن تتوفر في القائد: كن قدوة، واهتم بفريقك.',
        'عندما تكون ناجياً ومحباً': 'يتحدث عن النجاح المتوازن الذي يجمع بين الإنجاز والراحة النفسية.'
    },
    'سلسلة آفاق العلمية': {
        'الطاقة المتجددة': 'يشرح كيف نستخرج الكهرباء من الشمس والرياح والماء.',
        'القوة المحركة': 'يتحدث عن المحركات والآلات وكيف تتحول الطاقة إلى حركة.',
        'الأبنية': 'يشرح هندسة البناء من البيوت البسيطة إلى ناطحات السحاب.',
        'الزلازل والبراكين': 'معلومات عن أسباب اهتزاز الأرض وانفجار الحمم من باطنها.',
        'الحرائق والفيضانات': 'يتناول أخطار الطبيعة وكيفية مواجهتها والحد من أضرارها.'
    },
    'العلوم الشرعية والتاريخ': {
        'السيرة النبوية': 'قصة حياة الرسول ﷺ منذ ولادته حتى وفاته بأسلوب تاريخي ممتع.',
        'الصحيح': 'مرجع للأحاديث النبوية الصحيحة التي وردت عن النبي ﷺ.',
        'تفسير العشر الأخير': 'شرح ميسر وبسيط لمعاني سور القرآن الكريم في الأجزاء الأخيرة.',
        'الفرح بالقرآن': 'يتحدث عن الراحة النفسية والإيمانية التي نجدها في تدبر القرآن.',
        'رجال من التاريخ': 'قصص مشوقة عن شخصيات عظيمة أثرت في التاريخ الإسلامي.',
        'كيف تعالج مريضك بالرقية': 'دليل حول الآيات والأدعية الشرعية الصحيحة للرقية.'
    },
    'روايات وكتب أدبية ومنهجية': {
        'آفاق بلا حدود': 'كتاب يوسع مداركك حول طموح الإنسان وقدراته غير المحدودة.',
        'اللوحة القتالية': 'عمل أدبي متميز يتناول التحديات بأسلوب درامي مشوق.',
        'عندما تكون الغربة أوطاناً': 'خواطر ومشاعر حول البحث عن الانتماء السلام الداخلي.',
        'قفص الموت الغامض': 'رواية إثارة وغموض تتطلب ذكاءً وتركيزاً لحل لغزها.',
        'إلى الظل': 'يتناول البحث عن الهدوء والسكينة بعيداً عن ضجيج الحياة.',
        'قواعد البحث العلمي': 'دليل تعليمي للخطوات الصحيحة لكتابة البحوث المدرسية المنظمة.'
    }
}

# --- إدارة البيانات ---
def save_data():
    serializable_loans = {}
    for uid, loan in ACTIVE_LOANS.items():
        copy_loan = loan.copy()
        copy_loan['date'] = loan['date'].isoformat()
        copy_loan['return_date'] = loan['return_date'].isoformat()
        serializable_loans[str(uid)] = copy_loan
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({"BORROWED_BOOKS": list(BORROWED_BOOKS), "ACTIVE_LOANS": serializable_loans}, f, ensure_ascii=False, indent=4)

def load_data():
    global BORROWED_BOOKS, ACTIVE_LOANS
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                BORROWED_BOOKS = set(data.get("BORROWED_BOOKS", []))
                raw_loans = data.get("ACTIVE_LOANS", {})
                ACTIVE_LOANS = {int(uid): {**l, 'date': datetime.fromisoformat(l['date']), 'return_date': datetime.fromisoformat(l['return_date'])} for uid, l in raw_loans.items()}
        except: pass

def format_date(dt):
    days = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
    return f"{days[dt.weekday()]} {dt.strftime('%Y/%m/%d')}"

def adjust_for_weekend(dt):
    if dt.weekday() == 4: return dt + timedelta(days=2)
    if dt.weekday() == 5: return dt + timedelta(days=1)
    return dt

# --- معالجة الأوامر ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    load_data()
    user_id = update.effective_user.id
    if user_id in ACTIVE_LOANS:
        loan = ACTIVE_LOANS[user_id]
        kb = [[InlineKeyboardButton("📥 طلب إرجاع الكتاب الآن", callback_data="req_ret")]]
        if not loan.get('extended'):
            kb.append([InlineKeyboardButton("⏳ طلب تمديد (7 أيام)", callback_data="extend_loan")])
        await update.message.reply_text(f"أهلاً بك!\n\nلديك كتاب مستعار حالياً: **{loan['book']}**\nالموعد النهائي: {format_date(loan['return_date'])}", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
        return

    await update.message.reply_text("✨ مرحباً بك في مكتبة ابن العميد الرقمية\n\nيرجى كتابة **اسمك الثلاثي** للتسجيل:")
    context.user_data['step'] = 'NAME'

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step = context.user_data.get('step')
    if not step: return
    text = update.message.text.strip()

    if step == 'NAME':
        context.user_data['student_name'] = text
        await update.message.reply_text("📍 رائع، الآن أرسل فصلك الدراسي (مثال: 3/1):")
        context.user_data['step'] = 'CLASS'
    elif step == 'CLASS':
        context.user_data['student_class'] = text
        await update.message.reply_text("📞 أخيراً، أرسل رقم جوالك:")
        context.user_data['step'] = 'PHONE'
    elif step == 'PHONE':
        if re.match(r'^0\d{9}$', text):
            context.user_data['student_phone'] = text
            context.user_data['step'] = 'DONE'
            kb = [[InlineKeyboardButton(cat, callback_data=f"cat_{cat}")] for cat in LIBRARY_DATA.keys()]
            await update.message.reply_text("✅ تم التسجيل بنجاح.\nتفضل باختيار قسم لتصفح الكتب:", reply_markup=InlineKeyboardMarkup(kb))
        else:
            await update.message.reply_text("❌ رقم الجوال غير صحيح (يجب أن يبدأ بـ 0 ويتكون من 10 أرقام):")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data.startswith("cat_"):
        cat = data.split("_", 1)[1]
        context.user_data['current_cat'] = cat
        buttons = [[InlineKeyboardButton(f"{'🔴' if b in BORROWED_BOOKS else '🟢'} {b}", callback_data=f"info_{b}")] for b in LIBRARY_DATA[cat].keys()]
        buttons.append([InlineKeyboardButton("🔙 العودة للأقسام", callback_data="back_to_cats")])
        await query.edit_message_text(f"📚 قسم {cat}:", reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("info_"):
        book = data.split("_", 1)[1]
        cat = context.user_data.get('current_cat')
        if not cat:
            for c, bks in LIBRARY_DATA.items():
                if book in bks: cat = c; break
        desc = LIBRARY_DATA[cat][book]
        kb = [[InlineKeyboardButton("✅ طلب استعارة", callback_data=f"terms_{book}")]] if book not in BORROWED_BOOKS and user_id not in ACTIVE_LOANS else []
        kb.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"cat_{cat}")])
        await query.edit_message_text(f"📖 **{book}**\n\n{desc}", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

    elif data.startswith("terms_"):
        book = data.split("_", 1)[1]
        kb = [[InlineKeyboardButton("✅ أوافق"، callback_data=f"brw_{book}")], [InlineKeyboardButton("❌ إلغاء", callback_data="back_to_cats")]]
        await query.edit_message_text(f"⚠️ **شروط الاستعارة:**\n\n1- الحفاظ على نظافة الكتاب.\n2- الإرجاع في الموعد المحدد.\n\nهل توافق على استعارة ({book})؟", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

    elif data.startswith("brw_"):
        book = data.split("_", 1)[1]
        if book in BORROWED_BOOKS or user_id in ACTIVE_LOANS: return
        ret = adjust_for_weekend(datetime.now() + timedelta(days=7))
        BORROWED_BOOKS.add(book)
        ACTIVE_LOANS[user_id] = {'book': book, 'name': context.user_data.get('student_name'), 'class': context.user_data.get('student_class'), 'phone': context.user_data.get('student_phone'), 'date': datetime.now(), 'return_date': ret}
        save_data()
        await query.edit_message_text(f"✅ تمت الاستعارة!\n📖 الكتاب: {book}\n📅 الموعد: {format_date(ret)}")
        await context.bot.send_message(chat_id=ADMIN_GROUP_ID, text=f"🔔 استعارة جديدة: {ACTIVE_LOANS[user_id]['name']} - {book}")

    elif data == "req_ret":
        loan = ACTIVE_LOANS.get(user_id)
        if loan:
            kb = [[InlineKeyboardButton("✅ تم الاستلام"، callback_data=f"conf_{user_id}")]]
            await context.bot.send_message(chat_id=ADMIN_GROUP_ID, text=f"📥 طلب إرجاع: {loan['name']} - {loan['book']}", reply_markup=InlineKeyboardMarkup(kb))
            await query.edit_message_text("⏳ تم إرسال الطلب. يرجى تسليم الكتاب للمكتبة.")

    elif data.startswith("conf_"):
        uid = int(data.split("_")[1])
        if uid in ACTIVE_LOANS:
            book = ACTIVE_LOANS[uid]['book']
            BORROWED_BOOKS.discard(book)
            del ACTIVE_LOANS[uid]
            save_data()
            await query.edit_message_text(f"✅ تم تأكيد إرجاع {book}")
            try: await context.bot.send_message(chat_id=uid, text="✨ تم تأكيد الإرجاع بنجاح.")
            except: pass

    elif data == "back_to_cats":
        kb = [[InlineKeyboardButton(cat, callback_data=f"cat_{cat}")] for cat in LIBRARY_DATA.keys()]
        await query.edit_message_text("اختر القسم:", reply_markup=InlineKeyboardMarkup(kb))

# --- التشغيل ---
def main():
    load_data()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(handle_callback))
    
    # التشغيل بنظام Polling (مناسب لـ Render Background Worker)
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
