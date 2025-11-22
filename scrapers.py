import requests
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)


def scrape_python_news():
    """
    Ví dụ: Cào tiêu đề bài viết từ trang 'Real Python' (hoặc trang tương tự).
    Trả về list các dict: {'keyword': ..., 'text': ..., 'link': ...}
    """
    logger.info("Bắt đầu cào dữ liệu Real Python...")
    url = "https://realpython.com/"
    results = []

    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')

            # Tìm các thẻ chứa bài viết (Lưu ý: cấu trúc web có thể thay đổi)
            cards = soup.find_all('div', class_='card-body')

            for card in cards[:5]:  # Lấy 5 bài mới nhất
                title_tag = card.find('h2')
                link_tag = card.find('a')

                if title_tag and link_tag:
                    title = title_tag.get_text().strip()
                    link = "https://realpython.com" + link_tag['href']

                    # Tạo keyword đơn giản từ tiêu đề (lấy từ đầu tiên)
                    keyword = title.split()[0].lower()

                    results.append({
                        'keyword': keyword,
                        'text': f"Bài viết mới: {title}",
                        'link': link
                    })
        else:
            logger.error(f"Lỗi truy cập web: {response.status_code}")

    except Exception as e:
        logger.error(f"Lỗi Scraper: {e}")

    return results

# Bạn có thể thêm các hàm scrape_web2(), scrape_web3() ở đây...