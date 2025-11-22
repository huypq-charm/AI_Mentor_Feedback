import os
from sqlalchemy import create_engine
from dotenv import load_dotenv
from db_collector import Base  # Import Base từ file code của bạn

# Tải biến môi trường
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("Lỗi: Thiếu DATABASE_URL")
    exit()

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)


def update_schema():
    print("Đang kết nối DB để tạo bảng mới (nếu chưa có)...")
    engine = create_engine(DATABASE_URL)

    # Lệnh này sẽ tự động tạo bảng system_health nếu nó chưa tồn tại
    Base.metadata.create_all(engine)
    print("✅ Xong! Bảng system_health đã sẵn sàng.")


if __name__ == "__main__":
    update_schema()