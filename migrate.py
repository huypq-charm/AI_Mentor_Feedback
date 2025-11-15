# migrate.py
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from db_collector import CollectorV2  # Import module v2.0

# --- TÊN FILE DB MỚI ---
DB_FILE = "aimentor.db"

# --- CODE KẾT NỐI GOOGLE SHEET CŨ ---
GOOGLE_SHEET_NAME = "AIMentor_Data"
try:
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    client = gspread.oauth(
        credentials_filename="client_secret.json",
        authorized_user_filename="token.json"
    )
    sheet_content = client.open(GOOGLE_SHEET_NAME).worksheet("Content_DB")
    content_records = sheet_content.get_all_records()
    print(f"Đã đọc {len(content_records)} dòng từ Google Sheet 'Content_DB'.")
except Exception as e:
    print(f"Lỗi kết nối Google Sheet: {e}")
    exit()

# --- KẾT NỐI VÀ GHI VÀO SQLITE V2.0 ---
try:
    # 1. Khởi tạo DB
    db = CollectorV2(DB_FILE)
    db.setup_database()  # Tạo bảng

    # 2. Lấy cursor để chèn dữ liệu
    cursor = db.conn.cursor()

    # 3. Lặp qua dữ liệu cũ và chèn vào bảng mới
    sql = """INSERT OR REPLACE INTO content_db 
             (suggestion_id, keyword, suggestion_text, suggestion_link, rating_score)
             VALUES (?, ?, ?, ?, ?)"""

    count = 0
    for record in content_records:
        cursor.execute(sql, (
            record['Suggestion_ID'],
            record['Keyword'],
            record['Suggestion_Text'],
            record['Suggestion_Link'],
            record['Rating_Score']
        ))
        count += 1

    db.conn.commit()
    print(f"Đã di chuyển thành công {count} dòng vào {DB_FILE} (bảng content_db).")

except Exception as e:
    print(f"Lỗi trong quá trình di chuyển: {e}")