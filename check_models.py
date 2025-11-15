# check_models.py
import google.generativeai as genai
import os
from dotenv import load_dotenv

# Tải biến môi trường từ file .env
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    print("Lỗi: Không tìm thấy GEMINI_API_KEY.")
    print("Hãy chắc chắn file .env của bạn ở cùng thư mục và đã có key.")
    exit()

print("Đang kết nối tới Google AI Studio...")

try:
    genai.configure(api_key=GEMINI_API_KEY)
    print("Kết nối thành công! Đang lấy danh sách models...\n")

    found_model = False
    for model in genai.list_models():
        # Chúng ta chỉ quan tâm đến models có thể 'generateContent'
        if 'generateContent' in model.supported_generation_methods:
            print(f"Tìm thấy model: {model.name}")
            found_model = True

    print("\n---")
    if found_model:
        print("TUYỆT VỜI! Hãy copy một 'model name' (ví dụ: 'models/gemini-1.0-pro') từ danh sách trên.")
        print("Sau đó, mở file 'bot.py' và thay thế 'gemini-1.0-pro' bằng tên model bạn vừa copy.")
    else:
        print("Không tìm thấy model nào. Có thể API Key của bạn chưa được kích hoạt cho dịch vụ này.")

except Exception as e:
    print(f"\nGặp lỗi khi kết nối hoặc liệt kê models: {e}")
    print("Vui lòng kiểm tra lại GEMINI_API_KEY và kết nối mạng.")