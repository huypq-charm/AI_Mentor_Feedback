# FILE BOT CHÍNH (CHUẨN DAY 20 - Retry System & Better AI)

import sqlite3
from db_collector import CollectorV2
from scrapers import scrape_python_news
# [DAY 20] Import Retry Manager
from retry_manager import RetryManager

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ContextTypes, CallbackQueryHandler
)
import datetime
import logging
import os
import httpx
import google.generativeai as genai

# --- CẤU HÌNH ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DATABASE_URL = os.getenv("DATABASE_URL")

# Thay bằng ID Telegram thật của bạn
ADMIN_IDS = [5929406140]

# --- CẤU HÌNH LOGGING ---
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S"
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)
logging.getLogger("googleapiclient").setLevel(logging.WARNING)

logger = logging.getLogger("AI_Mentor_Bot")

# --- BIẾN CỜ (LOCKS) ---
job_locks = {
    "scheduler": False,
    "scraper": False
}

# --- KHỞI TẠO CÁC MODULE ---
if not TELEGRAM_BOT_TOKEN or not GEMINI_API_KEY:
    logger.error("Lỗi: Thiếu API Key.")
    exit()

# Xử lý URL Database
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# 1. Database
try:
    db = CollectorV2(DATABASE_URL)
    db.setup_database()
    content_records = db.get_all_content()
    logger.info(f"DB: Đã tải {len(content_records)} gợi ý.")
except Exception as e:
    logger.error(f"LỖI KHỞI ĐỘNG DB: {e}", exc_info=True)
    exit()

# 2. [DAY 20] Retry Manager
retry_mgr = RetryManager()

# 3. [DAY 20] Cấu hình Gemini (Prompt Tốt hơn)
try:
    genai.configure(api_key=GEMINI_API_KEY)

    # System Prompt nâng cao
    system_prompt = """
    Bạn là AI Mentor, một trợ lý học tập nhiệt tình và chuyên nghiệp.
    Quy tắc:
    1. Luôn trả lời bằng tiếng Việt.
    2. Nếu câu hỏi về lập trình, hãy đưa ra ví dụ code ngắn gọn (trong block code).
    3. Văn phong: Thân thiện, khuyến khích (dùng emoji 🚀, 💡).
    4. Nếu người dùng hỏi tin tức, hãy tóm tắt ý chính.
    5. Không chào hỏi lại nếu không cần thiết, đi thẳng vào vấn đề.
    """

    model_v3 = genai.GenerativeModel(
        model_name="models/gemini-flash-latest",
        system_instruction=system_prompt
    )
except Exception:
    model_v3 = None
    logger.warning("Gemini Error: Chuyển sang chế độ Fallback.")


# ==============================================================================
# CÁC HÀM HỖ TRỢ (HELPER)
# ==============================================================================

# [DAY 20] Hàm gửi tin nhắn an toàn (Wrapper)
async def send_message_safe(bot, chat_id, text, parse_mode=None):
    try:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)
        return True
    except Exception as e:
        logger.error(f"Gửi tin thất bại cho {chat_id}: {e}")
        # Lưu vào Retry Queue để xử lý sau
        retry_mgr.add_message(chat_id, text, reason=e)
        return False


def get_suggestion_engine(message_text: str) -> tuple:
    lower_message = message_text.lower()
    found_suggestions = []
    for record in content_records:
        keyword = str(record.get('Keyword', '')).lower()
        if keyword and keyword in lower_message:
            found_suggestions.append(record)
    if not found_suggestions: return None, None, None
    found_suggestions.sort(key=lambda x: x.get('Rating_Score', 0), reverse=True)
    best = found_suggestions[0]
    return (best.get('Suggestion_Text'), best.get('Suggestion_Link'), best.get('Suggestion_ID'))


def get_ai_feedback_v1_0(message_text: str) -> str:
    if "xin chào" in message_text.lower(): return "Chào bạn! Bạn cần mình hỗ trợ gì hôm nay?"
    return "Cảm ơn bạn đã chia sẻ. Mình đã ghi nhận thông tin này."


async def get_gemini_feedback_v3(message_text: str, history: list) -> str:
    if not model_v3: raise Exception("Gemini chưa sẵn sàng.")
    gemini_history = []
    for msg in history:
        role = "user" if msg["role"] == "user" else "model"
        gemini_history.append({"role": role, "parts": [msg["content"]]})
    chat_session = model_v3.start_chat(history=gemini_history)
    response = await chat_session.send_message_async(message_text)
    return response.text


# ==============================================================================
# JOBS SCHEDULER
# ==============================================================================

# 1. Nhắc nhở học tập (Dùng send_message_safe)
async def smart_scheduler_job(context: ContextTypes.DEFAULT_TYPE):
    if job_locks["scheduler"]: return
    job_locks["scheduler"] = True

    try:
        current_hour = datetime.datetime.now().hour
        if current_hour < 8 or current_hour > 21: return

        logger.info("SCHEDULER: Quét người dùng...")
        inactive_users = db.get_inactive_users(days_inactive=3)

        if inactive_users:
            count = 0
            msg = "Chào bạn, đã lâu không thấy bạn tương tác. Bạn có muốn tiếp tục học không? 🚀"
            for user in inactive_users:
                # [DAY 20] Dùng hàm gửi an toàn
                success = await send_message_safe(context.bot, user['user_id'], msg)
                if success: count += 1
            logger.info(f"SCHEDULER: Đã gửi nhắc nhở cho {count} người.")

    except Exception as e:
        logger.error(f"Lỗi Scheduler: {e}")
    finally:
        job_locks["scheduler"] = False


# 2. [DAY 20] Retry Job (Xử lý tin nhắn lỗi)
async def retry_job(context: ContextTypes.DEFAULT_TYPE):
    # Lấy 5 tin nhắn lỗi ra để thử lại
    messages = retry_mgr.pop_batch(limit=5)
    if not messages: return

    logger.info(f"RETRY: Đang thử gửi lại {len(messages)} tin nhắn...")
    for item in messages:
        chat_id = item['chat_id']
        text = item['text']
        try:
            # Thử gửi lại lần nữa (không dùng wrapper để tránh lặp vô hạn trong queue này)
            await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
            logger.info(f"RETRY: Thành công cho {chat_id}")
        except Exception as e:
            logger.error(f"RETRY: Vẫn thất bại cho {chat_id}. Bỏ qua. Lỗi: {e}")


# 3. Auto Feed Scraper
async def auto_feed_job(context: ContextTypes.DEFAULT_TYPE):
    if job_locks["scraper"]: return
    job_locks["scraper"] = True
    try:
        logger.info("SCRAPER: Bắt đầu cào dữ liệu...")
        items = scrape_python_news()
        if items:
            count = db.import_content_batch(items)
            msg = f"Đã cào được {len(items)} bài, thêm mới {count} bài."
            logger.info(msg)
            db.log_health("Scraper", "OK", msg)
            global content_records
            content_records = db.get_all_content()
        else:
            db.log_health("Scraper", "WARNING", "Không cào được bài nào.")
    except Exception as e:
        logger.error(f"Lỗi Scraper: {e}")
        db.log_health("Scraper", "ERROR", str(e))
    finally:
        job_locks["scraper"] = False


# 4. Alive Check
async def alive_check_job(context: ContextTypes.DEFAULT_TYPE):
    db.log_health("System", "ALIVE", "Bot Running")


# 5. Báo cáo Admin
async def daily_report_job(context: ContextTypes.DEFAULT_TYPE):
    logger.info("REPORT: Tạo báo cáo...")
    errors = db.get_recent_errors(hours=24)
    total_content = len(content_records) if 'content_records' in globals() else 0

    report = f"📊 **BÁO CÁO NGÀY** ({datetime.datetime.now().strftime('%d/%m')})\n"
    report += f"- Tổng bài học: {total_content}\n"
    if not errors:
        report += "✅ Hệ thống ổn định."
    else:
        report += f"⚠️ Có {len(errors)} lỗi trong 24h qua."

    for admin_id in ADMIN_IDS:
        await send_message_safe(context.bot, admin_id, report, parse_mode="Markdown")


# 6. Dọn dẹp
async def maintenance_job(context: ContextTypes.DEFAULT_TYPE):
    count = db.clean_old_logs(days_keep=30)
    if count > 0:
        msg = f"🧹 Đã dọn dẹp {count} dòng log cũ."
        for admin_id in ADMIN_IDS:
            await send_message_safe(context.bot, admin_id, msg)


# ==============================================================================
# HANDLERS & MAIN
# ==============================================================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    message_text = message.text

    logger.info(f"Msg from [{username}]: {message_text}")
    history = context.user_data.setdefault('history', [])
    history.append({"role": "user", "content": message_text})

    sugg_text, sugg_link, sugg_id = get_suggestion_engine(message_text)
    final_feedback = ""
    callback_type = "std"
    callback_id = ""

    if sugg_id:
        final_feedback = f"Gợi ý:\n\n💡 **{sugg_text}**\n{sugg_link}"
        callback_type = "sugg"
        callback_id = sugg_id
        logger.info(f"-> DB Suggestion: {sugg_id}")
    else:
        try:
            final_feedback = await get_gemini_feedback_v3(message_text, history[-10:])
            logger.info("-> Gemini Answer")
        except Exception as e:
            logger.error(f"Gemini Error: {e}")
            final_feedback = get_ai_feedback_v1_0(message_text)
            logger.info("-> Fallback Answer")

    history.append({"role": "ai", "content": final_feedback})
    context.user_data['history'] = history[-20:]

    try:
        db.log_message(user_id, username, message_text, final_feedback)
    except Exception as e:
        logger.error(f"DB Log Error: {e}")

    keyboard = [[
        InlineKeyboardButton("👍 Hữu ích", callback_data=f"fb_{callback_type}_{callback_id}_good"),
        InlineKeyboardButton("👎 Không hữu ích", callback_data=f"fb_{callback_type}_{callback_id}_bad"),
    ]]

    # Gửi tin trực tiếp (không qua Retry cho tương tác realtime để user không phải đợi lâu nếu lỗi)
    await message.reply_text(final_feedback, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")


async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    parts = data.split('_')
    feedback_type = parts[1]
    rating = parts.pop()
    ai_text = query.message.text
    user_id = query.from_user.id
    sugg_id_logged = None

    if feedback_type == "sugg":
        sugg_id_logged = "_".join(parts[2:])
        try:
            db.update_suggestion_score(sugg_id_logged, rating)
        except:
            pass

    try:
        db.log_feedback(user_id, ai_text, rating, sugg_id_logged)
    except:
        pass

    await query.edit_message_text(text=f"{ai_text}\n\n[Cảm ơn bạn đã đánh giá!]")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Chào bạn! AI Mentor v3.2 (Retry System) sẵn sàng!")


def main():
    logger.info("--- KHỞI ĐỘNG AI MENTOR BOT v3.2 (Day 20) ---")
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    jq = application.job_queue
    # Đăng ký các Jobs
    jq.run_repeating(smart_scheduler_job, interval=86400, first=10)
    jq.run_repeating(retry_job, interval=300, first=15)  # [DAY 20] Retry Job (5 phút/lần)
    jq.run_repeating(alive_check_job, interval=3600, first=20)
    jq.run_repeating(auto_feed_job, interval=21600, first=30)
    jq.run_repeating(daily_report_job, interval=86400, first=60)
    jq.run_repeating(maintenance_job, interval=604800, first=120)

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(button_click, pattern="^fb_"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(
        MessageHandler(filters.Sticker.ALL | filters.PHOTO, lambda u, c: u.message.reply_text("Chỉ nhận text!")))

    logger.info("Bot đang chạy...")
    application.run_polling()


if __name__ == "__main__":
    main()