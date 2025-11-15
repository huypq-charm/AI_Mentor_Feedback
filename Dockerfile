# Sử dụng một ảnh (image) Python 3.11 gọn nhẹ
FROM python:3.11-slim

# Thiết lập thư mục làm việc bên trong container
WORKDIR /app

# Sao chép file requirements vào trước để tận dụng cache
COPY requirements.txt .

# Cài đặt các thư viện
RUN pip install -r requirements.txt

# Sao chép toàn bộ code (bot.py, db_collector.py) vào
COPY . .

# Lệnh sẽ chạy khi container khởi động
# (Giả sử bạn đã đổi tên file thành bot.py)
CMD ["python", "bot.py"]