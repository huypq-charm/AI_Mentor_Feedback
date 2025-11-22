import requests
from bs4 import BeautifulSoup
import logging
import random

logger = logging.getLogger(__name__)

# Giả lập trình duyệt thật để tránh bị chặn (User-Agent Rotation)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36"
]


def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5"
    }


# --- CẤU HÌNH 10 NGUỒN DỮ LIỆU ---
# Mỗi nguồn là một dict chứa thông tin cách để tìm Tiêu đề và Link
SOURCES = [
    {
        "name": "Real Python",
        "url": "https://realpython.com/",
        "container": {"tag": "div", "class_": "card-body"},
        "title": {"tag": "h2"},
        "link": {"tag": "a"}
    },
    {
        "name": "FreeCodeCamp",
        "url": "https://www.freecodecamp.org/news/",
        "container": {"tag": "article", "class_": "post-card"},
        "title": {"tag": "h2"},
        "link": {"tag": "a"}
    },
    {
        "name": "Hacker News",
        "url": "https://news.ycombinator.com/",
        "container": {"tag": "tr", "class_": "athing"},
        "title": {"tag": "span", "class_": "titleline"},
        "link": {"tag": "a"}
    },
    {
        "name": "Python.org",
        "url": "https://www.python.org/blogs/",
        "container": {"tag": "h3", "class_": "event-title"},  # Cấu trúc hơi khác, thẻ h3 chứa link luôn
        "title": {},  # Title nằm trong thẻ a
        "link": {"tag": "a"}
    },
    {
        "name": "MIT News (AI)",
        "url": "https://news.mit.edu/topic/artificial-intelligence2",
        "container": {"tag": "h3", "class_": "term-page--news-article--item--title"},
        "title": {"tag": "span"},
        "link": {"tag": "a"}
    },
    {
        "name": "The Verge (Tech)",
        "url": "https://www.theverge.com/tech",
        "container": {"tag": "h2", "class_": "font-polysans"},
        "title": {},
        "link": {"tag": "a"}
    },
    {
        "name": "Ars Technica",
        "url": "https://arstechnica.com/gadgets/",
        "container": {"tag": "header"},  # Trong Ars, header chứa h2 và a
        "title": {"tag": "h2"},
        "link": {"tag": "a"}
    },
    {
        "name": "InfoWorld",
        "url": "https://www.infoworld.com/category/python/",
        "container": {"tag": "div", "class_": "post-cont"},
        "title": {"tag": "h3"},
        "link": {"tag": "a"}
    },
    {
        "name": "ScienceDaily (AI)",
        "url": "https://www.sciencedaily.com/news/computers_math/artificial_intelligence/",
        "container": {"tag": "h3", "class_": "latest-head"},
        "title": {},
        "link": {"tag": "a"}
    },
    {
        "name": "Phys.org (Tech)",
        "url": "https://phys.org/technology-news/",
        "container": {"tag": "article", "class_": "sorted-article"},
        "title": {"tag": "h3"},
        "link": {"tag": "a"}
    }
]


def scrape_all_sources():
    """Hàm chính để chạy qua 10 nguồn và lấy dữ liệu"""
    all_results = []
    logger.info(f"SCRAPER: Bắt đầu quét {len(SOURCES)} nguồn dữ liệu...")

    for source in SOURCES:
        try:
            logger.info(f"Scraping: {source['name']}...")
            response = requests.get(source['url'], headers=get_headers(), timeout=15)

            if response.status_code != 200:
                logger.warning(f"-> Thất bại {source['name']} (Status {response.status_code})")
                continue

            soup = BeautifulSoup(response.content, 'html.parser')

            # Tìm các container
            containers = soup.find_all(source['container'].get('tag'), class_=source['container'].get('class_'))

            count_per_site = 0
            for item in containers[:3]:  # Lấy tối đa 3 bài mỗi web
                try:
                    # Tìm Link
                    link_node = item
                    if source['link']:
                        link_node = item.find(source['link'].get('tag'), class_=source['link'].get('class_'))

                    if not link_node or not link_node.has_attr('href'): continue

                    url_link = link_node['href']
                    # Xử lý link tương đối (/news/...)
                    if url_link.startswith("/"):
                        base_url = "/".join(source['url'].split("/")[:3])
                        url_link = base_url + url_link

                    # Tìm Title
                    title_text = ""
                    if source['title']:
                        title_node = item.find(source['title'].get('tag'), class_=source['title'].get('class_'))
                        if title_node: title_text = title_node.get_text().strip()
                    else:
                        # Nếu không cấu hình title, lấy text của chính link_node
                        title_text = link_node.get_text().strip()

                    if title_text and url_link:
                        all_results.append({
                            'keyword': source['name'],  # Dùng tên web làm keyword
                            'text': f"[{source['name']}] {title_text}",
                            'link': url_link
                        })
                        count_per_site += 1
                except Exception as e:
                    continue  # Bỏ qua bài lỗi, sang bài tiếp

            logger.info(f"-> {source['name']}: Lấy được {count_per_site} bài.")

        except Exception as e:
            logger.error(f"-> Lỗi nguồn {source['name']}: {e}")

    logger.info(f"SCRAPER: Tổng cộng thu thập được {len(all_results)} bài viết.")
    return all_results