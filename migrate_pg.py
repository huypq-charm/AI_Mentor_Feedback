# migrate_pg.py
# Script để di chuyển dữ liệu từ SQLite (v2.0) sang PostgreSQL (v2.1)

import os
import sqlite3
import logging
from dotenv import load_dotenv
from sqlalchemy.exc import IntegrityError

# Đảm bảo bạn import CollectorV2 và ContentDB
# TỪ file db_collector.py (phiên bản SQLAlchemy) MỚI của bạn
try:
    from db_collector import CollectorV2, ContentDB, Base
except ImportError:
    print("LỖI: Không thể import 'CollectorV2' hoặc 'ContentDB' từ db_collector.py.")
    print("Hãy chắc chắn file db_collector.py của bạn là phiên bản SQLAlchemy (Day 12+).")
    exit()

# --- CẤU HÌNH ---
# 1. Tải biến môi trường (sẽ đọc DATABASE_URL từ .env)
load_dotenv()

# 2. Nguồn (SQLite)
OLD_DB_FILE = "aimentor.db"  # File SQLite cũ

# 3. Đích (PostgreSQL)
DATABASE_URL = os.getenv("DATABASE_URL")

# --- THIẾT LẬP LOGGING ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# --- HÀM TRỢ GIÚP ĐỌC SQLITE ---
def read_from_sqlite(db_file):
    """Đọc tất cả content_db từ file SQLite."""
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        # Đặt row_factory để trả về kết quả dạng dict (giống tên cột)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        logger.info(f"Đang đọc từ bảng 'content_db' trong {db_file}...")
        cursor.execute("SELECT * FROM content_db")
        records = cursor.fetchall()

        # Chuyển đổi [sqlite3.Row] thành [dict] chuẩn
        record_dicts = [dict(row) for row in records]
        logger.info(f"Tìm thấy {len(record_dicts)} dòng trong SQLite.")
        return record_dicts

    except sqlite3.Error as e:
        logger.error(f"Lỗi khi đọc SQLite: {e}")
        return []
    finally:
        if conn:
            conn.close()


# --- HÀM CHÍNH ĐỂ DI CHUYỂN ---
def migrate():
    # 1. Kiểm tra các kết nối
    if not os.path.exists(OLD_DB_FILE):
        logger.error(f"Lỗi: Không tìm thấy file nguồn '{OLD_DB_FILE}'.")
        return

    if not DATABASE_URL:
        logger.error("Lỗi: Không tìm thấy 'DATABASE_URL' trong file .env.")
        logger.error("Hãy copy 'External Database URL' từ Render vào file .env.")
        return

    logger.info("--- BẮT ĐẦU DI CHUYỂN DỮ LIỆU ---")
    logger.info(f"Nguồn: SQLite ({OLD_DB_FILE})")
    logger.info(f"Đích: PostgreSQL (trên Render)")

    # 2. Đọc dữ liệu từ Nguồn (SQLite)
    source_records = read_from_sqlite(OLD_DB_FILE)
    if not source_records:
        logger.warning("Không có dữ liệu trong 'content_db' (SQLite) để di chuyển.")
        return

    # 3. Kết nối tới Đích (PostgreSQL)
    try:
        db_collector = CollectorV2(DATABASE_URL)
        # Chạy setup_database để đảm bảo bảng tồn tại
        db_collector.setup_database()

        # Lấy một session để làm việc
        session = db_collector._get_session()
        logger.info("Kết nối tới PostgreSQL trên Render thành công.")
    except Exception as e:
        logger.error(f"Lỗi khi kết nối PostgreSQL: {e}")
        logger.error("Vui lòng kiểm tra lại 'External Database URL' trong file .env.")
        return

    # 4. Ghi dữ liệu vào Đích (PostgreSQL)
    count_success = 0
    count_skipped = 0

    try:
        for record_dict in source_records:
            # Tạo một object ContentDB (SQLAlchemy) từ dict
            new_content = ContentDB(
                suggestion_id=record_dict.get('suggestion_id'),
                keyword=record_dict.get('keyword'),
                suggestion_text=record_dict.get('suggestion_text'),
                suggestion_link=record_dict.get('suggestion_link'),
                rating_score=record_dict.get('rating_score', 0)
            )

            # Thêm vào session
            session.add(new_content)

            # Commit (lưu) vào database
            # Chúng ta commit từng cái một để bắt lỗi (ví dụ: trùng lặp)
            try:
                session.commit()
                count_success += 1
                logger.info(f"Đã thêm: {new_content.suggestion_id}")
            except IntegrityError:
                # Lỗi này xảy ra nếu 'suggestion_id' đã tồn tại (do bạn chạy script 2 lần)
                session.rollback()  # Hoàn tác lại
                logger.warning(f"Bỏ qua: {new_content.suggestion_id} (đã tồn tại).")
                count_skipped += 1
            except Exception as e_inner:
                logger.error(f"Lỗi khi thêm {new_content.suggestion_id}: {e_inner}")
                session.rollback()

    except Exception as e:
        logger.error(f"Lỗi nghiêm trọng trong quá trình di chuyển: {e}")
    finally:
        session.close()
        logger.info("--- DI CHUYỂN HOÀN TẤT ---")
        logger.info(f"Đã thêm mới: {count_success} dòng.")
        logger.info(f"Bỏ qua (trùng lặp): {count_skipped} dòng.")


if __name__ == "__main__":
    migrate()