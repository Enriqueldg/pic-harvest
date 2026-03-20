import os
from urllib import robotparser
from urllib.parse import urljoin, urlparse
import io
from PIL import Image
import certifi
import requests
from bs4 import BeautifulSoup

os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
os.environ['SSL_CERT_FILE'] = certifi.where()

class PicHarvest:
    base_url: str
    formats: list[str]
    pages_urls: list[str]
    pics_urls: list[str]
    sitemap: str

    def __init__(self, base_url: str, formats: list[str] = None):
        self.base_url = base_url
        self.formats = formats if formats else [".jpg", ".jpeg", ".png", ".gif", ".webp"]

        self.get_sitemap()
        self.get_pages()

    def get_sitemap(self):
        robot_parser = robotparser.RobotFileParser()
        robots_path = "/robots.txt"
        robot_parser.set_url(urljoin(self.base_url, robots_path))
        robot_parser.read()
        self.sitemap = robot_parser.site_maps()[0]

    def get_pages(self):
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'}
        r = requests.get(self.sitemap, headers=headers)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, 'xml')
        pags = soup.find_all('url')
        self.pages_urls = [p.find("loc").text for p in pags]

    def get_all_pics_urls(self):
        pics_urls = list()
        for page_url in self.pages_urls:
            pics_urls.extend(self.get_pics_urls_from_page(page_url))
        self.pics_urls = list(set(pics_urls))

    def get_pics_urls_from_page(self, url) -> list[str]:
        pics_urls = set()
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        for pic in soup.find_all('img'):
            pic_url = (
                pic.get('src') or
                pic.get('data-src') or
                pic.get('data-lazy-src') or
                pic.get('srcset')
            )
            if not pic_url:
                continue
            if ',' in pic_url:
                pic_url = pic_url.split(',')[0].split(' ')[0]

            full_url = urljoin(url, pic_url)
            ruta_path = urlparse(full_url).path
            if any(ruta_path.lower().endswith(ext) for ext in self.formats):
                pics_urls.add(full_url)
        return list(pics_urls)

    def download_all_pics(self):
        for url in self.pics_urls:
            self.download_pic_from_url(url)

    def download_pic_from_url(self, url: str):
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        if r.status_code == 200:
            content = r.content
            is_valid = self.is_valid(content, min_width=300, min_height=300)

            if is_valid:
                final_name = os.path.basename(url.split('?')[0])
                with open(f"/Users/kike/PycharmProjects/pic-harvest/downloaded_pics/{final_name}", 'wb') as f:
                    f.write(content)

    def is_valid(self, binary_content, min_width=200, min_height=200):
        try:
            pic = Image.open(io.BytesIO(binary_content))
            width, high = pic.size
            return width >= min_width and high >= min_height
        except Exception:
            return False
