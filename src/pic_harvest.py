import io
import logging
import os
from pathlib import Path
from urllib import robotparser
from urllib.parse import urljoin, urlparse

import certifi
import requests
from bs4 import BeautifulSoup
from PIL import Image

os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
os.environ['SSL_CERT_FILE'] = certifi.where()

OUTPUT_DIR = Path(__file__).parent.parent / "downloaded_pics"
OUTPUT_DIR.mkdir(exist_ok=True)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

logger = logging.getLogger(__name__)


class PicHarvest:
    base_url: str
    formats: list[str]
    pages_urls: list[str]
    pics_urls: list[str]
    sitemaps: list[str]

    def __init__(
        self,
        base_url: str,
        formats: list[str] | None = None,
        min_width: int = 300,
        min_height: int = 300,
    ):
        self.base_url = base_url
        self.formats = formats if formats else [".jpg", ".jpeg", ".png", ".gif", ".webp"]
        self.min_width = min_width
        self.min_height = min_height
        self.sitemaps = []
        self.pages_urls = []
        self.pics_urls = []

    def crawl(self):
        self.get_sitemaps()
        self.get_pages()

    def get_sitemaps(self):
        robot_parser = robotparser.RobotFileParser()
        robot_parser.set_url(urljoin(self.base_url, "/robots.txt"))
        robot_parser.read()
        found = robot_parser.site_maps() or []
        if not found:
            found = [urljoin(self.base_url, "/sitemap.xml")]
        self.sitemaps = self._expand_sitemaps(found)

    def _expand_sitemaps(self, urls: list[str]) -> list[str]:
        """Recursively expand sitemap index files into individual sitemaps."""
        leaf_sitemaps = []
        for url in urls:
            try:
                r = requests.get(url, headers=HEADERS, timeout=10)
                r.raise_for_status()
            except requests.RequestException as e:
                logger.warning("Failed to fetch sitemap %s: %s", url, e)
                continue
            soup = BeautifulSoup(r.content, 'xml')
            nested = soup.find_all('sitemap')
            if nested:
                nested_urls = [s.find('loc').text for s in nested if s.find('loc')]
                leaf_sitemaps.extend(self._expand_sitemaps(nested_urls))
            else:
                leaf_sitemaps.append(url)
        return leaf_sitemaps

    def get_pages(self):
        pages = []
        for sitemap_url in self.sitemaps:
            try:
                r = requests.get(sitemap_url, headers=HEADERS, timeout=10)
                r.raise_for_status()
            except requests.RequestException as e:
                logger.warning("Failed to fetch sitemap page %s: %s", sitemap_url, e)
                continue
            soup = BeautifulSoup(r.content, 'xml')
            pages.extend(p.find('loc').text for p in soup.find_all('url') if p.find('loc'))
        self.pages_urls = list(dict.fromkeys(pages))

    def get_all_pics_urls(self):
        pics_urls = list()
        for page_url in self.pages_urls:
            pics_urls.extend(self.get_pics_urls_from_page(page_url))
        self.pics_urls = list(set(pics_urls))

    def get_pics_urls_from_page(self, url) -> list[str]:
        pics_urls = set()
        r = requests.get(url, headers=HEADERS, timeout=10)
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
        try:
            r_ctx = requests.get(url, timeout=10, stream=True)
            r_ctx.raise_for_status()
        except requests.RequestException as e:
            logger.warning("Failed to download %s: %s", url, e)
            return
        with r_ctx:
            chunks = []
            size_known = False
            for chunk in r_ctx.iter_content(chunk_size=4096):
                chunks.append(chunk)
                if not size_known:
                    try:
                        img = Image.open(io.BytesIO(b''.join(chunks)))
                        width, height = img.size
                        size_known = True
                        if width < self.min_width or height < self.min_height:
                            logger.debug("Skipping %s: dimensions %dx%d below threshold", url, width, height)
                            return
                    except Exception:
                        pass  # need more chunks to parse the header

            if not size_known:
                logger.warning("Could not determine dimensions for %s", url)
                return

            content = b''.join(chunks)
            final_name = os.path.basename(url.split('?')[0])
            with open(OUTPUT_DIR / final_name, 'wb') as f:
                f.write(content)

