# db_collector.py (PHIÊN BẢN DAY 18 - Maintenance)

import datetime
import logging
# Thêm 'delete' vào import
from sqlalchemy import create_engine, Column, String, Integer, BigInteger, Text, DateTime, func, delete
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

# --- KHỞI TẠO SQLALCHEMY ---
Base = declarative_base()


# --- ĐỊNH NGHĨA CÁC BẢNG (MODELS) ---

class MessageLog(Base):
    __tablename__ = "message_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.datetime.now)
    user_id = Column(BigInteger, nullable=False, index=True)
    username = Column(String)
    message_text = Column(Text)
    ai_feedback_text = Column(Text)


class FeedbackLog(Base):
    __tablename__ = "feedback_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.datetime.now)
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


class SystemHealth(Base):
    __tablename__ = "system_health"
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.datetime.now)
    component = Column(String(50))  # Ví dụ: "Scheduler", "Scraper", "Bot"
    status = Column(String(20))  # "OK", "ERROR", "WARNING", "ALIVE"
    message = Column(Text)


# --- CLASS COLLECTOR V2.2 ---
class CollectorV2:
    def __init__(self, database_url):
        self.engine = None
        self.Session = None
        try:
            if database_url and database_url.startswith("postgres://"):
                database_url = database_url.replace("postgres://", "postgresql://", 1)

            self.engine = create_engine(database_url)
            self.Session = sessionmaker(bind=self.engine)
            logger.info(f"Kết nối SQLAlchemy tới database thành công.")
        except Exception as e:
            logger.error(f"Lỗi kết nối SQLAlchemy: {e}", exc_info=True)
            raise e

    def setup_database(self):
        try:
            Base.metadata.create_all(self.engine)
            logger.info("SQLAlchemy: Đã tạo/kiểm tra các bảng thành công.")
        except Exception as e:
            logger.error(f"Lỗi setup_database (SQLAlchemy): {e}", exc_info=True)

    def _get_session(self):
        return self.Session()

    # --- CÁC HÀM LOGGING CƠ BẢN ---
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
            logger.error(f"Lỗi log_message: {e}", exc_info=True)
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
            logger.error(f"Lỗi log_feedback: {e}", exc_info=True)
            session.rollback()
            return False
        finally:
            session.close()

    def log_health(self, component, status, message):
        """Ghi log sức khỏe hệ thống (Day 17)"""
        session = self._get_session()
        try:
            health_log = SystemHealth(
                component=component,
                status=status,
                message=message
            )
            session.add(health_log)
            session.commit()
        except Exception as e:
            logger.error(f"Lỗi log_health: {e}")
        finally:
            session.close()

    # --- CÁC HÀM CONTENT & LEARNING ---
    def get_all_content(self):
        session = self._get_session()
        try:
            records = session.query(ContentDB).all()
            return [rec.__dict__ for rec in records]
        except SQLAlchemyError as e:
            logger.error(f"Lỗi get_all_content: {e}", exc_info=True)
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
            logger.error(f"Lỗi update_suggestion_score: {e}", exc_info=True)
            session.rollback()
            return False
        finally:
            session.close()

    def import_content_batch(self, items):
        """Lưu nội dung mới, check trùng lặp (Day 17)"""
        session = self._get_session()
        count_new = 0
        try:
            for item in items:
                exists = session.query(ContentDB).filter_by(suggestion_link=item['link']).first()
                if not exists:
                    new_id = f"AUTO_{int(datetime.datetime.now().timestamp())}_{count_new}"
                    new_content = ContentDB(
                        suggestion_id=new_id,
                        keyword=item['keyword'],
                        suggestion_text=item['text'],
                        suggestion_link=item['link'],
                        rating_score=0
                    )
                    session.add(new_content)
                    count_new += 1
            session.commit()
            return count_new
        except Exception as e:
            logger.error(f"Lỗi import_content_batch: {e}")
            session.rollback()
            return 0
        finally:
            session.close()

    # --- CÁC HÀM QUẢN TRỊ & BÁO CÁO (DAY 18) ---

    def clean_old_logs(self, days_keep=30):
        """Xóa log cũ (Day 18)"""
        session = self._get_session()
        try:
            cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days_keep)

            stmt1 = delete(MessageLog).where(MessageLog.timestamp < cutoff_date)
            result1 = session.execute(stmt1)

            stmt2 = delete(SystemHealth).where(SystemHealth.timestamp < cutoff_date)
            result2 = session.execute(stmt2)

            session.commit()
            deleted_count = result1.rowcount + result2.rowcount
            logger.info(f"DỌN RÁC: Đã xóa {deleted_count} dòng log cũ.")
            return deleted_count
        except Exception as e:
            logger.error(f"Lỗi clean_old_logs: {e}")
            session.rollback()
            return 0
        finally:
            session.close()

    def get_recent_errors(self, hours=24):
        """Lấy báo cáo lỗi (Day 18)"""
        session = self._get_session()
        try:
            cutoff_time = datetime.datetime.now() - datetime.timedelta(hours=hours)
            errors = session.query(SystemHealth).filter(
                SystemHealth.timestamp > cutoff_time,
                SystemHealth.status == 'ERROR'
            ).all()
            return [err.__dict__ for err in errors]
        except Exception as e:
            logger.error(f"Lỗi get_recent_errors: {e}")
            return []
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
            return user_list
        except SQLAlchemyError as e:
            logger.error(f"Lỗi get_inactive_users: {e}", exc_info=True)
            return []
        finally:
            session.close()