import json
import os
import logging
import datetime

logger = logging.getLogger(__name__)
RETRY_FILE = "LogRetry.json"


class RetryManager:
    def __init__(self):
        # Nếu file chưa tồn tại thì tạo file rỗng
        if not os.path.exists(RETRY_FILE):
            self.save_queue([])

    def load_queue(self):
        """Đọc danh sách tin nhắn đang chờ thử lại"""
        try:
            with open(RETRY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Lỗi đọc Retry Queue: {e}")
            return []

    def save_queue(self, queue_data):
        """Lưu danh sách xuống file"""
        try:
            with open(RETRY_FILE, "w", encoding="utf-8") as f:
                json.dump(queue_data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            logger.error(f"Lỗi ghi Retry Queue: {e}")

    def add_message(self, chat_id, text, reason):
        """Thêm một tin nhắn thất bại vào hàng đợi"""
        queue = self.load_queue()
        queue.append({
            "chat_id": chat_id,
            "text": text,
            "added_at": str(datetime.datetime.now()),
            "reason": str(reason),
            "attempts": 0  # Số lần đã thử lại
        })
        self.save_queue(queue)
        logger.warning(f"RETRY: Đã thêm tin nhắn gửi cho {chat_id} vào hàng đợi.")

    def pop_batch(self, limit=5):
        """Lấy ra một nhóm tin nhắn để thử gửi lại"""
        queue = self.load_queue()
        if not queue:
            return []

        batch = queue[:limit]  # Lấy 5 tin đầu tiên
        remaining = queue[limit:]  # Giữ lại phần còn lại

        self.save_queue(remaining)  # Lưu lại danh sách đã bớt
        return batch