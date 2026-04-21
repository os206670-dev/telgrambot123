import logging
import re
import json
import os
from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# إعدادات السجلات
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- الإعدادات الأساسية ---
# تأكد أن التوكن صحيح هنا
TOKEN = "8254293210:AAFuREZZ4vVneXRs3i3A4K_pwdzH7qdQhHQ"
ADMIN_GROUP_ID = -1003983944808 
DATA_FILE = "library_storage.json"

BORROWED_BOOKS = set()
ACTIVE_LOANS = {}

# بيانات المكتبة (يمكنك إضافة المزيد هنا)
LIBRARY_DATA = {
    'تطوير الذات والإدارة': {
        'لا تحزن (لا تخزن)': 'نصائح لمواجهة الهموم والقلق والتركيز على الجانب الإيماني.',
        'مشوار الإصرار والتحدي': 'قصص ومواقف تحفزك على التمسك بأهدافك رغم الصعوبات.',
        'ركز': 'تعلم كيف تبتعد عن المشتتات وتوجه انتباهك الكامل لمهمة واحدة.'
    },
    'سلسلة آفاق العلمية': {
        'الطاقة المتجددة': 'يشرح كيف نستخرج الكهرباء من الشمس والرياح والماء.',
        'القوة المحركة': 'يتحدث عن المحركات والآلات وكيف تتحول الطاقة إلى حركة.'
    }
}

# --- وظائف مساعدة ---
def format_date(dt):
    days = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
    return f"{days[dt.weekday()]} {dt.strftime('%Y/%m/%d')}"

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

# --- المعالجات الرئيسية ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    load_data()
    user_id = update.effective_user.id
    if user_id in ACTIVE_LOANS:
        loan = ACTIVE_LOANS[user_id]
        kb = [[InlineKeyboardButton("📥 طلب إرجاع الكتاب", callback_data="req_ret")]]
        await update.message.reply_text(f"📍 **أهلاً بك مجدداً!**\n\nأنت تستعير حالياً: **{loan['book']}**\n📅 موعد الإرجاع: {format_date(loan['return_date'])}", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
        return
    await update.message.reply_text("✨ **مرحباً بك في نظام استعارة الكتب**\n\nلبدء الاستخدام، يرجى كتابة **اسمك الثلاثي**:")
    context.user_data['step'] = 'NAME'

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    step = context.user_data.get('step')
    if not step: return
    text = update.message.text.strip()

    if step == 'NAME':
        context.user_data['student_name'] = text
        await update.message.reply_text(f"مرحباً {text}، الآن أرسل **فصلك الدراسي** (مثال: 3/1):")
        context.user_data['step'] = 'CLASS'
    elif step == 'CLASS':
        context.user_data['student_class'] = text
        await update.message.reply_text("📞 أرسل **رقم جوالك** للتواصل:")
        context.user_data['step'] = 'PHONE'
    elif step == 'PHONE':
        context.user_data['student_phone'] = text
        kb = [[InlineKeyboardButton(cat, callback_data=f"cat_{cat}")] for cat in LIBRARY_DATA.keys()]
        await update.message.reply_text("✅ **تم التسجيل بنجاح!**\nتفضل باختيار قسم الكتب الذي تود تصفحه:", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
        context.user_data['step'] = 'DONE'

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data.startswith("cat_"):
        cat = data.split("_", 1)[1]
        context.user_data['current_cat'] = cat
        btns = [[InlineKeyboardButton(f"{'🔴' if b in BORROWED_BOOKS else '🟢'} {b}", callback_data=f"info_{b}")] for b in LIBRARY_DATA[cat].keys()]
        btns.append([InlineKeyboardButton("🔙 العودة للأقسام", callback_data="back")])
        await query.edit_message_text(f"📚 **كتب قسم: {cat}**", reply_markup=InlineKeyboardMarkup(btns), parse_mode='Markdown')

    elif data.startswith("info_"):
        book = data.split("_", 1)[1]
        cat = context.user_data.get('current_cat')
        desc = LIBRARY_DATA[cat][book]
        status = "🔴 مستعار حالياً" if book in BORROWED_BOOKS else "🟢 متاح للاستعارة"
        kb = [[InlineKeyboardButton("✅ تأكيد الاستعارة", callback_data=f"brw_{book}")]] if book not in BORROWED_BOOKS and user_id not in ACTIVE_LOANS else []
        kb.append([InlineKeyboardButton("🔙 رجوع", callback_data=f"cat_{cat}")])
        await query.edit_message_text(f"📖 **الكتاب:** {book}\n📌 **الحالة:** {status}\n\n📝 **عن الكتاب:**\n{desc}", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

    elif data.startswith("brw_"):
        book = data.split("_", 1)[1]
        now = datetime.now()
        ret_date = now + timedelta(days=7) # مدة الاستعارة 7 أيام
        
        BORROWED_BOOKS.add(book)
        loan_info = {
            'book': book,
            'name': context.user_data.get('student_name'),
            'class': context.user_data.get('student_class'),
            'phone': context.user_data.get('student_phone'),
            'date': now,
            'return_date': ret_date
        }
        ACTIVE_LOANS[user_id] = loan_info
        save_data()

        # رسالة للطالب
        await query.edit_message_text(f"🎉 **مبروك! تمت الاستعارة بنجاح.**\n\n📘 الكتاب: {book}\n📅 تاريخ الإرجاع: {format_date(ret_date)}")
        
        # رسالة للإدارة (لوحة التحكم)
        admin_msg = (
            f"🔔 **عملية استعارة جديدة:**\n\n"
            f"👤 **الطالب:** {loan_info['name']}\n"
            f"🏫 **الفصل:** {loan_info['class']}\n"
            f"📞 **الجوال:** {loan_info['phone']}\n"
            f"📚 **الكتاب:** {book}\n"
            f"🗓 **تاريخ الاستعارة:** {format_date(now)}\n"
            f"⌛ **موعد الإرجاع:** {format_date(ret_date)}"
        )
        await context.bot.send_message(chat_id=ADMIN_GROUP_ID, text=admin_msg, parse_mode='Markdown')

    elif data == "back":
        kb = [[InlineKeyboardButton(cat, callback_data=f"cat_{cat}")] for cat in LIBRARY_DATA.keys()]
        await query.edit_message_text("📂 **اختر القسم:**", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')

# --- تشغيل البوت ---
def main():
    load_data()
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
