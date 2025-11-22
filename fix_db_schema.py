# fix_db_schema.py
# Script này dùng để sửa lỗi kiểu dữ liệu Integer -> BigInteger trên PostgreSQL

import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Tải biến môi trường (cần file .env chứa DATABASE_URL External)
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("LỖI: Không tìm thấy DATABASE_URL trong file .env")
    print("Vui lòng đảm bảo file .env có chứa 'External Database URL' lấy từ Render.")
    exit()

# Fix lỗi tương thích Render (postgres -> postgresql)
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)


def fix_schema():
    print(f"Đang kết nối tới Database để nâng cấp schema...")
    try:
        engine = create_engine(DATABASE_URL)

        with engine.connect() as connection:
            # Bắt đầu một giao dịch (transaction)
            trans = connection.begin()
            try:
                print("--- BẮT ĐẦU SỬA LỖI ---")

                # 1. Sửa bảng message_logs
                print("1. Đang sửa bảng 'message_logs' (user_id -> BIGINT)...")
                connection.execute(text("ALTER TABLE message_logs ALTER COLUMN user_id TYPE BIGINT;"))

                # 2. Sửa bảng feedback_logs
                print("2. Đang sửa bảng 'feedback_logs' (user_id -> BIGINT)...")
                connection.execute(text("ALTER TABLE feedback_logs ALTER COLUMN user_id TYPE BIGINT;"))

                # Lưu thay đổi
                trans.commit()
                print("✅ THÀNH CÔNG! Database đã được nâng cấp lên BIGINT.")
                print("Bây giờ bot của bạn có thể lưu ID người dùng lớn (như 5929406140).")

            except Exception as e:
                trans.rollback()  # Hoàn tác nếu có lỗi
                print(f"❌ LỖI TRONG QUÁ TRÌNH SỬA DB: {e}")

    except Exception as e:
        print(f"❌ LỖI KẾT NỐI: {e}")


if __name__ == "__main__":
    fix_schema()