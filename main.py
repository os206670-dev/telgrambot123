import logging
import json
import os
from datetime import datetime, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

# إعدادات السجلات
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- الإعدادات الأساسية ---
TOKEN = "8254293210:AAFuREZZ4vVneXRs3i3A4K_pwdzH7qdQhHQ"
ADMIN_GROUP_ID = -1003983944808 
DATA_FILE = "library_data.json" # تخزين في مجلد المشروع الرئيسي

BORROWED_BOOKS = set()
ACTIVE_LOANS = {}

# --- قاعدة بيانات الكتب (مختصرة هنا للتوضيح، تأكد من وجود نسختك الكاملة) ---
LIBRARY_DATA = {
    'تطوير الذات والإدارة': {
        'لا تحزن (لا تخزن)': 'نصائح لمواجهة الهموم والقلق.',
        'مشوار الإصرار والتحدي': 'قصص ومواقف تحفزك.',
        'ركز': 'تعلم كيف تبتعد عن المشتتات.'
    }
    # ... أضف باقي الكتب هنا كما في الكود السابق
}

# --- وظائف إدارة الذاكرة ---
def save_data():
    try:
        serializable_loans = {}
        for uid, loan in ACTIVE_LOANS.items():
            copy_loan = loan.copy()
            # التأكد من تحويل التاريخ لنص ليُحفظ في JSON
            if isinstance(loan.get('date'), datetime):
                copy_loan['date'] = loan['date'].isoformat()
            if isinstance(loan.get('return_date'), datetime):
                copy_loan['return_date'] = loan['return_date'].isoformat()
            serializable_loans[str(uid)] = copy_loan
        
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({"BORROWED_BOOKS": list(BORROWED_BOOKS), "ACTIVE_LOANS": serializable_loans}, f, ensure_ascii=False, indent=4)
        logging.info("Data saved successfully.")
    except Exception as e:
        logging.error(f"Error saving data: {e}")

def load_data():
    global BORROWED_BOOKS, ACTIVE_LOANS
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                BORROWED_BOOKS = set(data.get("BORROWED_BOOKS", []))
                raw_loans = data.get("ACTIVE_LOANS", {})
                ACTIVE_LOANS = {}
                for uid, l in raw_loans.items():
                    ACTIVE_LOANS[int(uid)] = {
                        **l, 
                        'date': datetime.fromisoformat(l['date']) if 'date' in l else datetime.now(),
                        'return_date': datetime.fromisoformat(l['return_date']) if 'return_date' in l else datetime.now()
                    }
            logging.info("Data loaded successfully.")
        except Exception as e:
            logging.error(f"Error loading data: {e}")

# --- المعالجات الرئيسية ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    load_data()
    user_id = update.effective_user.id
    if user_id in ACTIVE_LOANS:
        loan = ACTIVE_LOANS[user_id]
        kb = [[InlineKeyboardButton("📥 طلب إرجاع الكتاب الآن", callback_data="req_ret")]]
        await update.message.reply_text(
            f"📍 **أهلاً بك!**\n\nأنت تستعير حالياً: **{loan['book']}**\n"
            f"إذا كنت قد سلمت الكتاب، اضغط على الزر أدناه لإرسال طلب إرجاع للإدارة.",
            reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("✨ **مرحباً بك في مكتبة ابن العميد**\n\nيرجى كتابة **اسمك الثلاثي**:")
        context.user_data['step'] = 'NAME'

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    data = query.data

    if data == "req_ret":
        loan = ACTIVE_LOANS.get(user_id)
        if loan:
            # إرسال زر التأكيد للإدارة
            kb = [[InlineKeyboardButton("✅ تأكيد استلام الكتاب", callback_data=f"conf_ret_{user_id}")]]
            await context.bot.send_message(
                chat_id=ADMIN_GROUP_ID,
                text=f"📥 **طلب إرجاع جديد:**\n👤 الطالب: {loan['name']}\n📚 الكتاب: {loan['book']}\n📞 الجوال: {loan['phone']}",
                reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown'
            )
            await query.edit_message_text("⏳ **تم إرسال الطلب للإدارة.**\nيرجى تسليم الكتاب فعلياً للمشرف ليقوم بتأكيد الاستلام من عنده.")

    elif data.startswith("conf_ret_"):
        # هذا الجزء يضغط عليه المشرف (أنت) في المجموعة
        target_uid = int(data.split("_")[2])
        if target_uid in ACTIVE_LOANS:
            book_name = ACTIVE_LOANS[target_uid]['book']
            BORROWED_BOOKS.discard(book_name)
            del ACTIVE_LOANS[target_uid]
            save_data() # حفظ الحذف فوراً
            await query.edit_message_text(f"✅ تم تأكيد استلام كتاب **({book_name})** وإعادته للمكتبة.")
            try:
                await context.bot.send_message(chat_id=target_uid, text=f"✨ تم تأكيد إرجاع كتاب **({book_name})** بنجاح. يمكنك الآن استعارة كتاب جديد!")
            except: pass
    # ... باقي معالجات الأقسام (cat_) والكتب (info_) كما هي
