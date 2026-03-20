import os
from urllib import robotparser

import certifi
import requests
from bs4 import BeautifulSoup

os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()
os.environ['SSL_CERT_FILE'] = certifi.where()

class PicHarvest:
    base_url: str
    formats: list[str]
    pages_urls: list[str]
    pics_urls: set[str]
    sitemap: str

    def __init__(self, base_url: str, formats: list[str] = None):
        self.base_url = base_url
        self.formats = formats if formats else [".jpg", ".jpeg", ".png", ".gif", ".webp"]

    def init(self):
        self.get_sitemap()
        self.get_pages_urls()

    def get_sitemap(self):
        robot_parser = robotparser.RobotFileParser()
        robot_parser.set_url(f"{self.base_url}/robots.txt")
        robot_parser.read()
        self.sitemap = robot_parser.site_maps()[0]

    def get_pages_urls(self):
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'}
        r = requests.get(self.sitemap, headers=headers)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, 'xml')
        pags = soup.find_all('url')
        self.pages_urls = [p.find("loc").text for p in pags]

    def get_pics_url_from_url(url):
        pass
