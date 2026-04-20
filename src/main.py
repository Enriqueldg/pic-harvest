from pic_harvest import PicHarvest

url = "https://www.warhammer-community.com"

harvester = PicHarvest(url)
harvester.crawl()
harvester.get_pages()
harvester.pages_urls = harvester.pages_urls[:2]
harvester.get_all_pages_pics_urls()
harvester.pics_urls = harvester.pics_urls[:3]
