import time
import random
import logging
import os
from dotenv import load_dotenv
from db_collector import CollectorV2

# Cấu hình logging chỉ hiện Info
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("Lỗi: Thiếu DATABASE_URL")
    exit()

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)


def run_stress_test(num_records=1000):
    print(f"🔥 BẮT ĐẦU STRESS TEST: Ghi {num_records} log giả...")

    db = CollectorV2(DATABASE_URL)

    start_time = time.time()

    # 1. Test Ghi (Write)
    success_count = 0
    for i in range(num_records):
        user_id = random.randint(1000000, 9999999)
        # Giả lập ghi log tin nhắn
        res = db.log_message(
            user_id=user_id,
            username=f"User_{i}",
            message_text=f"Stress test message {i} - Load testing...",
            ai_feedback_text="Stress test AI response"
        )
        if res: success_count += 1

        if i % 100 == 0:
            print(f"-> Đã ghi {i} dòng...")

    duration = time.time() - start_time
    print(f"✅ KẾT THÚC GHI. Thành công: {success_count}/{num_records}")
    print(f"⏱️ Thời gian: {duration:.2f}s (Trung bình: {num_records / duration:.0f} req/s)")

    # 2. Test Đọc (Read - Tìm kiếm)
    print("\n🔎 BẮT ĐẦU TEST ĐỌC (Tìm kiếm User không hoạt động)...")
    start_read = time.time()

    # Gọi hàm tìm user inactive (query này khá nặng vì dùng Group By và Having)
    users = db.get_inactive_users(days_inactive=0)

    read_duration = time.time() - start_read
    print(f"✅ KẾT THÚC ĐỌC. Tìm thấy {len(users)} user.")
    print(f"⏱️ Thời gian Query: {read_duration:.4f}s")


if __name__ == "__main__":
    # Chạy thử với 500 dòng (bạn có thể tăng lên 1000, 5000 nếu muốn thử thách Render)
    run_stress_test(num_records=500)