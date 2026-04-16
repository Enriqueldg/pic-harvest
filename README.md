# pic-harvest

Crawl a website and download images that meet a minimum size threshold.

## How it works

1. Reads `robots.txt` to discover sitemaps (falls back to `/sitemap.xml`).
2. Recursively expands sitemap index files (up to 5 levels deep).
3. Scrapes every page URL found in the sitemaps for `<img>` tags.
4. Downloads images whose dimensions meet the configured minimum, skipping files already on disk.

Page crawling and image downloading are both parallelised with a thread pool.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Usage

```python
from src.pic_harvest import PicHarvest

harvester = PicHarvest(
    base_url="https://example.com",
    formats=[".jpg", ".jpeg", ".png", ".webp"],  # optional
    min_width=300,   # optional, default 300
    min_height=300,  # optional, default 300
)

harvester.crawl()           # discover sitemaps and pages
harvester.get_all_pics_urls(workers=10)   # scrape image URLs in parallel
harvester.download_all_pics(workers=5)   # download in parallel
```

Downloaded images are saved to `downloaded_pics/` at the repo root.
Filenames are prefixed with an 8-character URL hash to avoid collisions.

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `base_url` | — | Root URL of the site to crawl |
| `formats` | `.jpg .jpeg .png .gif .webp` | Image extensions to collect |
| `min_width` | `300` | Minimum image width in pixels |
| `min_height` | `300` | Minimum image height in pixels |