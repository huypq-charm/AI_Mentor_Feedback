# 🤖 AI Mentor Feedback (v3.0 - Hybrid)



Đây là dự án chatbot "AI Mentor" được xây dựng trên nền tảng Telegram. Bot này được thiết kế để trở thành một người cố vấn học tập ảo, có khả năng cung cấp phản hồi, gợi ý tài liệu học tập, và trả lời các câu hỏi phức tạp bằng AI.

Hệ thống được xây dựng theo kiến trúc "Hybrid", ưu tiên nội dung đã được kiểm duyệt (từ database) và sử dụng Model Ngôn ngữ Lớn (Google Gemini) làm phương án dự phòng thông minh.

---

## 🚀 Tính năng chính

* **Bộ não Hybrid (v3.0):**
    1.  **Ưu tiên 1 (Local DB):** Tự động tìm kiếm các gợi ý/tài liệu được lưu trữ sẵn trong database (PostgreSQL) dựa trên từ khóa.
    2.  **Ưu tiên 2 (Gemini AI):** Nếu không tìm thấy, bot sẽ sử dụng API của Google Gemini (`gemini-flash-latest`) để trả lời câu hỏi của người dùng.
    3.  **Ưu tiên 3 (Rule-Based):** Nếu Gemini lỗi, bot sẽ dùng logic `if-else` (v1.0) để đảm bảo luôn có phản hồi.
* **Học tập & Tự cải thiện:** Bot thu thập đánh giá "👍 Hữu ích" / "👎 Không hữu ích" từ người dùng. Các gợi ý (Ưu tiên 1) được đánh giá "👍" sẽ được ưu tiên hiển thị trong tương lai.
* **Bộ nhớ Ngữ cảnh (v1.1):** Bot ghi nhớ các tin nhắn trước đó trong một phiên (sử dụng `user_data`) để hiểu bối cảnh cuộc trò chuyện.
* **Lập lịch Thông minh (v2.0):** Một "Smart Scheduler" (Job Queue) chạy 24/7, tự động tìm và gửi tin nhắn nhắc nhở cho những người dùng không hoạt động sau 3 ngày.
* **Thu thập Dữ liệu v2.0:** Toàn bộ tin nhắn, phản hồi, và đánh giá được ghi log vào database PostgreSQL để phân tích và huấn luyện (training) trong tương lai.

---

## 🛠️ Ngăn xếp Công nghệ (Tech Stack)

* **Bot Framework:** `python-telegram-bot`
* **Database:** PostgreSQL (Triển khai trên Render.com)
* **ORM:** SQLAlchemy (Để giao tiếp với PostgreSQL)
* **AI (v3.0):** Google Gemini API (`gemini-flash-latest`)
* **Triển khai (Deployment):** Docker & Docker Compose
* **Nền tảng (Host):** Render.com (Background Worker + Free Postgres)

---

## 🐳 Cách chạy Dự án (Local)

Dự án này được thiết kế để chạy với Docker Compose.

**1. Chuẩn bị Môi trường:**

Đảm bảo bạn đã cài đặt **Docker Desktop** và nó đang chạy.

**2. Tạo file `.env`:**

Dự án này đọc tất cả các "bí mật" (API Keys) từ file `.env`. Hãy tạo một file tên là `.env` trong thư mục gốc và điền các thông tin sau:

```ini
# Lấy từ @BotFather trên Telegram
TELEGRAM_BOT_TOKEN=TOKEN_TELEGRAM_CUA_BAN

# Lấy từ Google AI Studio ([https://aistudio.google.com/](https://aistudio.google.com/))
GEMINI_API_KEY=KEY_GEMINI_CUA_BAN

# Dùng "Internal Database URL" nếu deploy trên Render
# Dùng "External Database URL" nếu chạy script migrate
DATABASE_URL=postgres://user:pass@host/dbname
```

**3. Khởi chạy Dịch vụ:**

Chạy lệnh sau từ terminal:

```bash
docker-compose up --build -d
```

**4. Xem Logs (Nhật ký):**

```bash
docker-compose logs -f
```

**5. Dừng Dịch vụ:**

```bash
docker-compose down
```

---

## ☁️ Triển khai lên Render.com (Miễn phí)

Dự án này được tối ưu để chạy trên Gói Miễn phí của Render.

1.  **Database (PostgreSQL):**
    * Tạo một "New PostgreSQL" trên Render (Free tier).
    * Copy giá trị **"Internal Database URL"**.

2.  **Di chuyển Dữ liệu (Chạy 1 lần):**
    * Thêm "External Database URL" vào file `.env` trên máy local.
    * Chạy script: `python migrate_pg.py` để bơm dữ liệu `content_db` từ SQLite (nếu có) lên Postgres.

3.  **Bot (Background Worker):**
    * Tạo một "New Background Worker" trên Render (Free tier).
    * Kết nối nó với repo GitHub này.
    * Trong tab "Environment", thêm 3 biến môi trường:
        * `TELEGRAM_BOT_TOKEN=8541077394:AAEfHsSIBRwa8eYsHS21IStnjwhxsmsfzwk`
        * `GEMINI_API_KEY=AIzaSyB19NjJjlHZm8kQWzM4VC1nKLFe9IxZHqU`
        * `DATABASE_URL=postgresql://aimentor_db_user:NinCDZ7ZQGlxELhs5NHpNrDzzF86uY69@dpg-d4c1s9ili9vc73bnhf9g-a/aimentor_db` (Dán giá trị "Internal Database URL" đã copy ở Bước 1).
    * **Start Command:** `python bot.py`
    * Nhấn "Deploy".
