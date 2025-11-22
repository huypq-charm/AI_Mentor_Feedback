# FILE BOT CHÍNH (CHUẨN DAY 19 - Optimized Logging & Job Locking)

import sqlite3
from db_collector import CollectorV2
from scrapers import scrape_python_news
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

# --- [DAY 19] CẤU HÌNH LOGGING CHUẨN ---
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S"
)
# Tắt bớt log ồn ào của các thư viện bên thứ 3
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)
logging.getLogger("googleapiclient").setLevel(logging.WARNING)

logger = logging.getLogger("AI_Mentor_Bot")

# --- [DAY 19] BIẾN CỜ (LOCKS) ---
# Để ngăn chặn các job chạy chồng chéo lên nhau
job_locks = {
    "scheduler": False,
    "scraper": False
}

# --- KIỂM TRA BIẾN MÔI TRƯỜNG ---
if not TELEGRAM_BOT_TOKEN or not GEMINI_API_KEY:
    logger.error("Lỗi: Thiếu API Key trong biến môi trường.")
    exit()

# --- XỬ LÝ URL DATABASE ---
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# --- KẾT NỐI DATABASE ---
try:
    db = CollectorV2(DATABASE_URL)
    db.setup_database()
    content_records = db.get_all_content()
    logger.info(f"Đã tải {len(content_records)} gợi ý từ cache Database.")
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
    logger.warning("Gemini không khởi tạo được, sẽ dùng fallback v1.0")


# ==============================================================================
# CÁC HÀM LOGIC (CORE)
# ==============================================================================

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
# CÁC JOB SCHEDULER (NÂNG CẤP DAY 19)
# ==============================================================================

# 1. Nhắc nhở học tập (Có Locking & Check giờ)
async def smart_scheduler_job(context: ContextTypes.DEFAULT_TYPE):
    if job_locks["scheduler"]:
        logger.warning("SCHEDULER: Job trước chưa xong (Locked). Bỏ qua lần này.")
        return

    job_locks["scheduler"] = True
    try:
        # Check giờ (8h - 21h)
        current_hour = datetime.datetime.now().hour
        if current_hour < 8 or current_hour > 21:
            # logger.info("SCHEDULER: Giờ nghỉ ngơi.") -> Tắt log này cho đỡ rác
            return

        logger.info("SCHEDULER: Đang quét người dùng không hoạt động...")
        inactive_users = db.get_inactive_users(days_inactive=3)

        if inactive_users:
            count = 0
            msg = "Chào bạn, đã lâu không thấy bạn tương tác. Bạn có muốn tiếp tục học không?"
            for user in inactive_users:
                try:
                    await context.bot.send_message(chat_id=user['user_id'], text=msg)
                    count += 1
                except:
                    pass  # User block bot
            logger.info(f"SCHEDULER: Đã gửi nhắc nhở cho {count} người.")

    except Exception as e:
        logger.error(f"Lỗi Scheduler: {e}")
    finally:
        job_locks["scheduler"] = False  # Luôn mở khóa khi xong


# 2. Auto Feed Scraper (Có Locking)
async def auto_feed_job(context: ContextTypes.DEFAULT_TYPE):
    if job_locks["scraper"]:
        logger.warning("SCRAPER: Job trước chưa xong (Locked). Bỏ qua.")
        return

    job_locks["scraper"] = True
    try:
        logger.info("SCRAPER: Bắt đầu cào dữ liệu...")
        items = scrape_python_news()
        if items:
            count = db.import_content_batch(items)
            msg = f"Đã cào được {len(items)} bài, thêm mới {count} bài."
            logger.info(msg)
            db.log_health("Scraper", "OK", msg)

            # Reload cache ngay lập tức
            global content_records
            content_records = db.get_all_content()
        else:
            db.log_health("Scraper", "WARNING", "Không cào được bài nào.")

    except Exception as e:
        logger.error(f"Lỗi Scraper: {e}")
        db.log_health("Scraper", "ERROR", str(e))
    finally:
        job_locks["scraper"] = False


# 3. Alive Check
async def alive_check_job(context: ContextTypes.DEFAULT_TYPE):
    # Chỉ log vào DB, không in ra console để tránh rác log
    db.log_health("System", "ALIVE", "Bot Running")


# 4. [NÂNG CẤP DAY 19] Báo cáo Admin chi tiết
async def daily_report_job(context: ContextTypes.DEFAULT_TYPE):
    logger.info("REPORT: Đang tạo báo cáo ngày...")
    errors = db.get_recent_errors(hours=24)
    total_content = len(content_records) if 'content_records' in globals() else 0

    # Header báo cáo
    report = f"📊 **BÁO CÁO TRẠNG THÁI HỆ THỐNG**\n"
    report += f"📅 {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"

    # 1. Trạng thái Jobs
    report += "**1. Trạng thái Jobs:**\n"
    report += f"- Scheduler Lock: {'🔒' if job_locks['scheduler'] else '🟢'}\n"
    report += f"- Scraper Lock: {'🔒' if job_locks['scraper'] else '🟢'}\n\n"

    # 2. Dữ liệu
    report += "**2. Dữ liệu:**\n"
    report += f"- Tổng bài học: {total_content}\n\n"

    # 3. Sức khỏe
    if not errors:
        report += "✅ **Hệ thống ổn định (100%).**"
    else:
        report += f"⚠️ **Phát hiện {len(errors)} lỗi:**\n"
        for err in errors[:5]:
            report += f"- [{err.get('component')}] {err.get('message')}\n"
        if len(errors) > 5:
            report += f"... và {len(errors) - 5} lỗi khác."

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=report, parse_mode="Markdown")
        except:
            pass


# 5. Dọn dẹp
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


# ==============================================================================
# HANDLERS & MAIN
# ==============================================================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    message_text = message.text

    logger.info(f"Msg from [{username}]: {message_text}")  # Log ngắn gọn hơn
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
        logger.info(f"-> Trả lời bằng DB (v2.0): {sugg_id}")
    else:
        try:
            final_feedback = await get_gemini_feedback_v3(message_text, history[-10:])
            logger.info("-> Trả lời bằng Gemini (v3.0)")
        except Exception as e:
            logger.error(f"Gemini Error: {e}")
            final_feedback = get_ai_feedback_v1_0(message_text)
            logger.info("-> Trả lời bằng Fallback (v1.0)")

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
    logger.info("--- KHỞI ĐỘNG AI MENTOR BOT v3.1 (Day 19) ---")
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    jq = application.job_queue
    # Job Scheduler (Giây)
    jq.run_repeating(smart_scheduler_job, interval=86400, first=10)
    jq.run_repeating(alive_check_job, interval=3600, first=20)
    jq.run_repeating(auto_feed_job, interval=21600, first=30)
    jq.run_repeating(daily_report_job, interval=86400, first=60)
    jq.run_repeating(maintenance_job, interval=604800, first=120)

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(button_click, pattern="^fb_"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(
        MessageHandler(filters.Sticker.ALL | filters.PHOTO, lambda u, c: u.message.reply_text("Chỉ nhận text!")))
    application.add_handler(MessageHandler(filters.COMMAND, lambda u, c: u.message.reply_text("Lệnh không tồn tại.")))

    logger.info("Bot đang chạy... Nhấn Ctrl+C để dừng.")
    application.run_polling()


if __name__ == "__main__":
    main()