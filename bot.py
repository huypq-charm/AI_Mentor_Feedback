# FILE BOT CHÍNH (CHUẨN DAY 13 - v3.0 Hybrid - Tích hợp GEMINI)
from scrapers import scrape_python_news # <-- File mới tạo
import sqlite3
from db_collector import CollectorV2
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters,
    ContextTypes, CallbackQueryHandler
)
import datetime
import logging
import os
import httpx  # Cần cho thư viện telegram (và sau này)
import google.generativeai as genai  # <-- MỚI (Day 13)

# --- CẤU HÌNH (NÂNG CẤP Day 13) ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")  # <-- MỚI (Day 13)
DATABASE_URL = os.getenv("DATABASE_URL") # Đọc URL database từ môi trường

if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# --- THIẾT LẬP LOGGING ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- KIỂM TRA BIẾN MÔI TRƯỜNG ---
if not TELEGRAM_BOT_TOKEN:
    logger.error("LỖI: Biến môi trường TELEGRAM_BOT_TOKEN không được thiết lập.")
    exit()

if not GEMINI_API_KEY:
    logger.error("LỖI: Biến môi trường GEMINI_API_KEY không được thiết lập.")
    logger.error("Hãy lấy API Key từ Google AI Studio và thêm vào file .env")
    exit()

# --- CẤU HÌNH GEMINI v3.0 (MỚI Day 13) ---
try:
    genai.configure(api_key=GEMINI_API_KEY)

    # Cấu hình hệ thống (System Prompt) cho AI
    system_prompt = (
        "Bạn là 'AI Mentor', một trợ lý học tập thân thiện và chuyên nghiệp. "
        "Hãy luôn trả lời bằng tiếng Việt. "
        "Giữ câu trả lời ngắn gọn, tập trung vào việc giải thích khái niệm "
        "hoặc trả lời câu hỏi của người học. Không cần chào hỏi lại."
    )

    model_v3 = genai.GenerativeModel(
        model_name="gemini-2.5-flash-lite",  # Dùng Flash cho tốc độ
        system_instruction=system_prompt
    )
    logger.info("Đã cấu hình và khởi tạo thành công Gemini AI v3.0.")
except Exception as e:
    logger.error(f"Lỗi khởi tạo Gemini: {e}", exc_info=True)
    model_v3 = None  # Đánh dấu là bị lỗi

# --- KẾT NỐI DATABASE V2.0 (Như cũ) ---
try:
    db = CollectorV2(DATABASE_URL) # Truyền URL vào
    db.setup_database()
    content_records = db.get_all_content()
    logger.info(f"Đã tải {len(content_records)} gợi ý từ cache SQLite (v2.0).")
except Exception as e:
    logger.error(f"LỖI KHỞI ĐỘNG: Không thể kết nối DB {DATABASE_URL}: {e}", exc_info=True)
    exit()

if not DATABASE_URL:
    logger.error("LỖI: Biến môi trường DATABASE_URL không được thiết lập.")
    exit()

# --- BỘ MÁY GỢI Ý v2.0 (Day 09 - Giữ nguyên) ---
def get_suggestion_engine(message_text: str) -> tuple:
    # (Hàm này giữ nguyên 100% như Day 12)
    lower_message = message_text.lower()
    found_suggestions = []
    for record in content_records:
        keyword = str(record.get('Keyword', '')).lower()
        if keyword and keyword in lower_message:
            found_suggestions.append(record)
    if not found_suggestions:
        return None, None, None
    found_suggestions.sort(key=lambda x: x.get('Rating_Score', 0), reverse=True)
    best_suggestion = found_suggestions[0]
    return (
        best_suggestion.get('Suggestion_Text'),
        best_suggestion.get('Suggestion_Link'),
        best_suggestion.get('Suggestion_ID')
    )
# --- JOB 1: AUTO FEED (Cào dữ liệu) ---
async def auto_feed_job(context: ContextTypes.DEFAULT_TYPE):
    logger.info("JOB: Bắt đầu cào dữ liệu tự động...")

    # 1. Chạy scraper
    items = scrape_python_news()

    if items:
        # 2. Lưu vào DB (có check trùng)
        count = db.import_content_batch(items)
        msg = f"Đã cào được {len(items)} bài, thêm mới {count} bài."
        logger.info(msg)

        # 3. Ghi log sức khỏe
        db.log_health("Scraper", "OK", msg)
    else:
        db.log_health("Scraper", "WARNING", "Không cào được bài nào.")

# --- JOB 2: ALIVE CHECK (Kiểm tra sức sống) ---
async def alive_check_job(context: ContextTypes.DEFAULT_TYPE):
    # Chỉ đơn giản là ghi vào DB để biết bot còn chạy
    db.log_health("System", "ALIVE", "Bot đang chạy ổn định.")
    logger.info("JOB: Alive check logged.")

# --- BỘ NÃO v1.0 (Day 04 - Giữ lại làm Fallback) ---
def get_ai_feedback_v1_0(message_text: str) -> str:
    # (Hàm này giữ nguyên 100% như Day 12)
    lower_message = message_text.lower()
    if "xin chào" in lower_message:
        return "Chào bạn, rất vui được hỗ trợ bạn. Hôm nay bạn muốn học gì?"
    elif "cảm ơn" in lower_message:
        return "Không có gì! Mình luôn sẵn sàng giúp đỡ."
    # ... (các logic if-else khác)
    else:
        return "Cảm ơn bạn đã chia sẻ. Mình đã ghi nhận thông tin này."


# --- BỘ NÃO v3.0 (MỚI Day 13) ---
async def get_gemini_feedback_v3(message_text: str, history: list) -> str:
    if not model_v3:
        raise Exception("Mô hình Gemini v3.0 chưa được khởi tạo.")

    # 1. Chuyển đổi lịch sử chat
    # Gemini cần: [{'role': 'user', 'parts': [text]}, {'role': 'model', 'parts': [text]}]
    gemini_history = []
    for msg in history:
        role = "user" if msg["role"] == "user" else "model"
        gemini_history.append({
            "role": role,
            "parts": [msg["content"]]
        })

    # 2. Bắt đầu phiên chat mới với lịch sử cũ
    chat_session = model_v3.start_chat(history=gemini_history)

    # 3. Gửi tin nhắn mới và chờ phản hồi (async)
    response = await chat_session.send_message_async(message_text)

    return response.text


# --- SMART SCHEDULER JOB (Day 11 - Giữ nguyên) ---
async def smart_scheduler_job(context: ContextTypes.DEFAULT_TYPE):
    # (Hàm này giữ nguyên 100% như Day 12)
    logger.info("SCHEDULER: Đang chạy Job kiểm tra người dùng...")
    inactive_users = db.get_inactive_users(days_inactive=3)
    if not inactive_users:
        logger.info("SCHEDULER: Không có ai không hoạt động. Kết thúc Job.")
        return
    # ... (logic gửi tin nhắn)


# --- HÀM XỬ LÝ TIN NHẮN (NÂNG CẤP "HYBRID" v3.0) ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    message_text = message.text

    logger.info(f"[v3.0] Nhận tin nhắn từ [{username}]: {message_text}")
    history = context.user_data.setdefault('history', [])
    history.append({"role": "user", "content": message_text})

    final_feedback = ""
    callback_type = "std"
    callback_id = ""

    # --- LOGIC HYBRID ---

    # ƯU TIÊN 1: Tìm trong DB v2.0 (Nhanh, Rẻ, Chính xác)
    sugg_text, sugg_link, sugg_id = get_suggestion_engine(message_text)

    if sugg_id:
        # Tìm thấy trong DB, dùng nó
        final_feedback = f"Mình nghĩ đây là nội dung bạn đang tìm:\n\n💡 **{sugg_text}**\n{sugg_link}"
        callback_type = "sugg"
        callback_id = sugg_id
        logger.info(f"Đã tìm thấy v2.0 (local): {sugg_id}")

    else:
        # ƯU TIÊN 2: Không tìm thấy, gọi GEMINI v3.0 (Thông minh)
        try:
            logger.info("v2.0 không có. Đang gọi Gemini v3.0...")
            # Lấy 10 tin nhắn cuối làm ngữ cảnh
            gemini_response = await get_gemini_feedback_v3(message_text, history[-10:])
            final_feedback = gemini_response
            callback_type = "std"  # Feedback của Gemini là "std" (chung)
            logger.info("Gemini v3.0 đã trả lời.")

        except Exception as e:
            # ƯU TIÊN 3: Gemini lỗi, dùng v1.0 (Dự phòng)
            logger.error(f"Lỗi gọi Gemini v3.0: {e}", exc_info=True)
            logger.info("Dùng fallback v1.0 (rule-based).")
            final_feedback = get_ai_feedback_v1_0(message_text)  # Dùng v1.0 làm fallback
            callback_type = "std"

    # --- Kết thúc Logic Hybrid ---

    # Cập nhật lịch sử (với câu trả lời cuối cùng)
    history.append({"role": "ai", "content": final_feedback})
    context.user_data['history'] = history[-20:]  # Nhớ 20 tin nhắn

    # Ghi log vào SQLite
    try:
        db.log_message(user_id, username, message_text, final_feedback)
    except Exception as e:
        logger.error(f"LỖI GHI LOG SQLite: {e}", exc_info=True)
        await message.reply_text("Lỗi nghiêm trọng: Không thể ghi log. Vui lòng báo admin.")
        return

    # Gửi tin nhắn và nút (như cũ)
    keyboard = [[
        InlineKeyboardButton("👍 Hữu ích", callback_data=f"fb_{callback_type}_{callback_id}_good"),
        InlineKeyboardButton("👎 Không hữu ích", callback_data=f"fb_{callback_type}_{callback_id}_bad"),
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Cần parse_mode="Markdown" để Gemini hiển thị code (```) hoặc **in đậm**
    await message.reply_text(final_feedback, reply_markup=reply_markup, parse_mode="Markdown")


# --- HÀM XỬ LÝ NÚT BẤM (v2.0 - Giữ nguyên) ---
async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # (Hàm này giữ nguyên 100% như Day 12)
    # Nó vẫn hoạt động vì logic "Learning" (update_suggestion_score)
    # chỉ kích hoạt khi feedback_type == "sugg" (Ưu tiên 1)
    # ...
    query = update.callback_query
    await query.answer()
    data = query.data
    logger.info(f"Nhận callback_data: {data}")
    parts = data.split('_')
    feedback_type = parts[1]
    rating = parts.pop()
    ai_text = query.message.text
    user_id = query.from_user.id
    sugg_id_logged = None
    if feedback_type == "sugg":
        sugg_id = "_".join(parts[2:])
        sugg_id_logged = sugg_id
        try:
            db.update_suggestion_score(sugg_id_logged, rating)
            global content_records
            for record in content_records:
                if record.get('Suggestion_ID') == sugg_id_logged:
                    record['Rating_Score'] += 1 if rating == "good" else -1
                    break
            logger.info(f"Đã cập nhật điểm v2.0 cho {sugg_id_logged}")
        except Exception as e:
            logger.error(f"Lỗi cập nhật điểm v2.0 cho {sugg_id_logged}: {e}", exc_info=True)
    try:
        db.log_feedback(user_id, ai_text, rating, sugg_id_logged)
        logger.info(f"Đã ghi feedback v2.0 vào SQLite.")
        await query.edit_message_text(text=f"{ai_text}\n\n[Cảm ơn bạn đã đánh giá!]")
    except Exception as e:
        logger.error(f"Lỗi ghi feedback v2.0: {e}", exc_info=True)
        await query.edit_message_text(text=f"{ai_text}\n\n[Lỗi: Không thể lưu đánh giá. Nhưng vẫn cảm ơn bạn!]")


# --- CÁC HÀM XỬ LÝ KHÁC (Giữ nguyên) ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Chào bạn! Tôi là AI Mentor Bot v3.0. Hãy hỏi tôi bất cứ điều gì!")  # Cập nhật tin nhắn chào mừng


async def non_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Mình hiện chỉ hiểu được tin nhắn văn bản thôi! 😊")


async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Rất tiếc, mình không hiểu lệnh đó. Bạn chỉ cần nhắn tin bình thường thôi nhé.")


# --- HÀM CHÍNH ĐỂ CHẠY BOT (Giữ nguyên) ---
def main():
    logger.info("Đang khởi động bot (v3.0 - Hybrid)...")
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    # --- SCHEDULERS ---
    job_queue = application.job_queue

    # 1. Nhắc nhở học tập (Cũ) - Chạy mỗi 24h
    job_queue.run_repeating(smart_scheduler_job, interval=86400, first=10)

    # 2. Alive Check (Mới) - Chạy mỗi 1 giờ (3600s)
    job_queue.run_repeating(alive_check_job, interval=3600, first=20)

    # 3. Auto Feed Scraper (Mới) - Chạy mỗi 6 giờ (21600s)
    job_queue.run_repeating(auto_feed_job, interval=21600, first=30)

    logger.info("Đã kích hoạt tất cả Scheduler (Reminder, Alive, Scraper).")
    job_queue.run_repeating(smart_scheduler_job, interval=86400, first=10)
    logger.info("Đã kích hoạt Smart Scheduler (chạy mỗi 24h, bắt đầu sau 10s).")
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(button_click, pattern="^fb_"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.Sticker.ALL | filters.PHOTO, non_text_message))
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    logger.info("Bot (v3.0) đang chạy! Nhấn Ctrl+C để dừng.")
    application.run_polling()


if __name__ == "__main__":
    main()