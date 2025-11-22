# FILE BOT CHÍNH (CHUẨN DAY 18 - Maintenance)

import sqlite3
from db_collector import CollectorV2
from scrapers import scrape_python_news  # (Day 17)
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

# [DAY 18] ID Admin để nhận báo cáo (Thay bằng ID thật của bạn!)
ADMIN_IDS = [5929406140]

# --- THIẾT LẬP LOGGING ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- XỬ LÝ URL DATABASE ---
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# --- KẾT NỐI DATABASE ---
try:
    db = CollectorV2(DATABASE_URL)
    db.setup_database()
    content_records = db.get_all_content()
    logger.info(f"Đã tải {len(content_records)} gợi ý từ database.")
except Exception as e:
    logger.error(f"LỖI KHỞI ĐỘNG DB: {e}", exc_info=True)
    exit()

# --- CẤU HÌNH GEMINI ---
try:
    genai.configure(api_key=GEMINI_API_KEY)
    model_v3 = genai.GenerativeModel(
        model_name="models/gemini-flash-latest",
        system_instruction="Bạn là AI Mentor, trả lời ngắn gọn, thân thiện bằng tiếng Việt."
    )
except Exception:
    model_v3 = None


# --- CÁC HÀM LOGIC (v1.0, v2.0, v3.0) ---
# (Giữ nguyên logic cũ để file gọn hơn, chỉ thay đổi Scheduler bên dưới)

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


# --- CÁC JOB SCHEDULER (QUAN TRỌNG DAY 18) ---

# 1. Nhắc nhở học tập (Đã tối ưu Day 18 - Không spam đêm)
async def smart_scheduler_job(context: ContextTypes.DEFAULT_TYPE):
    # Kiểm tra giờ (8h sáng -> 21h tối mới chạy)
    current_hour = datetime.datetime.now().hour
    if current_hour < 8 or current_hour > 21:
        logger.info("SCHEDULER: Giờ nghỉ ngơi. Bỏ qua.")
        return

    logger.info("SCHEDULER: Đang chạy Job kiểm tra người dùng...")
    inactive_users = db.get_inactive_users(days_inactive=3)

    if not inactive_users: return

    msg = "Chào bạn, đã lâu không thấy bạn tương tác. Bạn có muốn tiếp tục học không?"
    for user in inactive_users:
        try:
            await context.bot.send_message(chat_id=user['user_id'], text=msg)
            logger.info(f"SCHEDULER: Đã nhắc nhở {user['user_id']}")
        except:
            pass


# 2. Auto Feed (Scraper)
async def auto_feed_job(context: ContextTypes.DEFAULT_TYPE):
    logger.info("JOB: Bắt đầu cào dữ liệu...")
    items = scrape_python_news()  # Hàm từ scrapers.py
    if items:
        count = db.import_content_batch(items)
        msg = f"Đã cào được {len(items)} bài, thêm mới {count} bài."
        logger.info(msg)
        db.log_health("Scraper", "OK", msg)

        # Reload cache
        global content_records
        content_records = db.get_all_content()
    else:
        db.log_health("Scraper", "WARNING", "Không cào được bài nào.")


# 3. Alive Check
async def alive_check_job(context: ContextTypes.DEFAULT_TYPE):
    db.log_health("System", "ALIVE", "Bot đang chạy ổn định.")


# 4. [MỚI DAY 18] Báo cáo Admin
async def daily_report_job(context: ContextTypes.DEFAULT_TYPE):
    logger.info("REPORT: Đang tổng hợp báo cáo...")
    errors = db.get_recent_errors(hours=24)

    if not errors:
        report_text = "✅ **Báo cáo ngày:** Hệ thống ổn định. Không lỗi."
    else:
        report_text = f"⚠️ **CẢNH BÁO:** Có {len(errors)} lỗi trong 24h qua:\n"
        for err in errors[:5]:
            report_text += f"- [{err.get('component')}] {err.get('message')}\n"

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=report_text, parse_mode="Markdown")
        except:
            pass


# 5. [MỚI DAY 18] Dọn dẹp Database
async def maintenance_job(context: ContextTypes.DEFAULT_TYPE):
    logger.info("MAINTENANCE: Dọn dẹp log cũ...")
    count = db.clean_old_logs(days_keep=30)
    if count > 0:
        msg = f"🧹 Đã dọn dẹp {count} dòng log cũ."
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(chat_id=admin_id, text=msg)
            except:
                pass


# --- HANDLERS & MAIN ---

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    message_text = message.text

    logger.info(f"[v3.0] Nhận: {message_text}")
    history = context.user_data.setdefault('history', [])
    history.append({"role": "user", "content": message_text})

    # Logic Hybrid
    sugg_text, sugg_link, sugg_id = get_suggestion_engine(message_text)
    final_feedback = ""
    callback_type = "std"
    callback_id = ""

    if sugg_id:
        final_feedback = f"Gợi ý:\n\n💡 **{sugg_text}**\n{sugg_link}"
        callback_type = "sugg"
        callback_id = sugg_id
    else:
        try:
            final_feedback = await get_gemini_feedback_v3(message_text, history[-10:])
        except Exception as e:
            logger.error(f"Gemini Error: {e}")
            final_feedback = get_ai_feedback_v1_0(message_text)

    history.append({"role": "ai", "content": final_feedback})
    context.user_data['history'] = history[-20:]

    # Ghi log
    try:
        db.log_message(user_id, username, message_text, final_feedback)
    except Exception as e:
        logger.error(f"DB Error: {e}")

    # Gửi tin
    keyboard = [[
        InlineKeyboardButton("👍 Hữu ích", callback_data=f"fb_{callback_type}_{callback_id}_good"),
        InlineKeyboardButton("👎 Không hữu ích", callback_data=f"fb_{callback_type}_{callback_id}_bad"),
    ]]
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
    await update.message.reply_text("Chào bạn! AI Mentor v3.1 sẵn sàng!")


def main():
    logger.info("Khởi động Bot v3.1 (Day 18)...")
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # --- ĐĂNG KÝ JOBS ---
    jq = application.job_queue
    # 1. Nhắc nhở: Mỗi 24h (86400s)
    jq.run_repeating(smart_scheduler_job, interval=86400, first=10)
    # 2. Alive Check: Mỗi 1h (3600s)
    jq.run_repeating(alive_check_job, interval=3600, first=20)
    # 3. Auto Feed: Mỗi 6h (21600s)
    jq.run_repeating(auto_feed_job, interval=21600, first=30)
    # 4. [DAY 18] Báo cáo Admin: Mỗi 24h (86400s)
    jq.run_repeating(daily_report_job, interval=86400, first=60)
    # 5. [DAY 18] Dọn dẹp: Mỗi tuần (604800s)
    jq.run_repeating(maintenance_job, interval=604800, first=120)

    # Handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(button_click, pattern="^fb_"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()


if __name__ == "__main__":
    main()