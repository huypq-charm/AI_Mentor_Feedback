# db_collector.py (PHIÊN BẢN ĐÃ SỬA LỖI BIGINT)

import datetime
import logging
# 1. THÊM BigInteger VÀO IMPORT 👇
from sqlalchemy import create_engine, Column, String, Integer, BigInteger, Text, DateTime, func
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

# --- KHỞI TẠO SQLALCHEMY ---
Base = declarative_base()


# --- 2. ĐỊNH NGHĨA CÁC BẢNG (MODELS) ---

class MessageLog(Base):
    __tablename__ = "message_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.datetime.now)
    # 👇 SỬA Ở ĐÂY: Dùng BigInteger cho user_id
    user_id = Column(BigInteger, nullable=False, index=True)
    username = Column(String)
    message_text = Column(Text)
    ai_feedback_text = Column(Text)


class FeedbackLog(Base):
    __tablename__ = "feedback_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.datetime.now)
    # 👇 SỬA Ở ĐÂY: Dùng BigInteger cho user_id
    user_id = Column(BigInteger, nullable=False, index=True)
    ai_feedback_text = Column(Text)
    rating = Column(String(10))
    suggestion_id = Column(String(50), index=True)


class ContentDB(Base):
    __tablename__ = "content_db"
    suggestion_id = Column(String(50), primary_key=True)
    keyword = Column(String, nullable=False, index=True)
    suggestion_text = Column(Text)
    suggestion_link = Column(Text)
    rating_score = Column(Integer, default=0)


# --- CLASS COLLECTOR V2.1 ---
class CollectorV2:
    def __init__(self, database_url):
        self.engine = None
        self.Session = None
        try:
            # Tự động fix lỗi URL của Render nếu cần
            if database_url and database_url.startswith("postgres://"):
                database_url = database_url.replace("postgres://", "postgresql://", 1)

            self.engine = create_engine(database_url)
            self.Session = sessionmaker(bind=self.engine)
            logger.info(f"Kết nối SQLAlchemy tới database thành công.")
        except Exception as e:
            logger.error(f"Lỗi kết nối SQLAlchemy: {e}", exc_info=True)
            raise e

    def setup_database(self):
        """Tự động tạo tất cả các bảng nếu chưa tồn tại."""
        try:
            Base.metadata.create_all(self.engine)
            logger.info("SQLAlchemy: Đã tạo/kiểm tra các bảng thành công.")
        except Exception as e:
            logger.error(f"Lỗi setup_database (SQLAlchemy): {e}", exc_info=True)

    def _get_session(self):
        return self.Session()

    def log_message(self, user_id, username, message_text, ai_feedback):
        session = self._get_session()
        try:
            new_log = MessageLog(
                user_id=user_id,
                username=username,
                message_text=message_text,
                ai_feedback_text=ai_feedback
            )
            session.add(new_log)
            session.commit()
            return True
        except SQLAlchemyError as e:
            logger.error(f"Lỗi log_message (SQLAlchemy): {e}", exc_info=True)
            session.rollback()
            return False
        finally:
            session.close()

    def log_feedback(self, user_id, ai_text, rating, sugg_id):
        session = self._get_session()
        try:
            new_feedback = FeedbackLog(
                user_id=user_id,
                ai_feedback_text=ai_text,
                rating=rating,
                suggestion_id=sugg_id
            )
            session.add(new_feedback)
            session.commit()
            return True
        except SQLAlchemyError as e:
            logger.error(f"Lỗi log_feedback (SQLAlchemy): {e}", exc_info=True)
            session.rollback()
            return False
        finally:
            session.close()

    def get_all_content(self):
        session = self._get_session()
        try:
            records = session.query(ContentDB).all()
            return [rec.__dict__ for rec in records]
        except SQLAlchemyError as e:
            logger.error(f"Lỗi get_all_content (SQLAlchemy): {e}", exc_info=True)
            return []
        finally:
            session.close()

    def update_suggestion_score(self, sugg_id, rating):
        session = self._get_session()
        try:
            record = session.query(ContentDB).filter_by(suggestion_id=sugg_id).first()
            if record:
                value_change = 1 if rating == "good" else -1
                record.rating_score = (record.rating_score or 0) + value_change
                session.commit()
                logger.info(f"Đã cập nhật điểm (thay đổi {value_change}) cho {sugg_id}")
                return True
            else:
                logger.warning(f"Không tìm thấy Sugg_ID {sugg_id} để cập nhật điểm.")
                return False
        except SQLAlchemyError as e:
            logger.error(f"Lỗi update_suggestion_score (SQLAlchemy): {e}", exc_info=True)
            session.rollback()
            return False
        finally:
            session.close()

    def get_inactive_users(self, days_inactive=3):
        session = self._get_session()
        try:
            cutoff_time = datetime.datetime.now() - datetime.timedelta(days=days_inactive)
            users = (
                session.query(MessageLog.user_id)
                .group_by(MessageLog.user_id)
                .having(func.max(MessageLog.timestamp) < cutoff_time)
                .all()
            )
            user_list = [{"user_id": user[0]} for user in users]
            logger.info(f"Smart Scheduler: Tìm thấy {len(user_list)} người dùng không hoạt động.")
            return user_list
        except SQLAlchemyError as e:
            logger.error(f"Lỗi get_inactive_users (SQLAlchemy): {e}", exc_info=True)
            return []
        finally:
            session.close()