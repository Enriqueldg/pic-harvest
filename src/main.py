from pic_harvest import PicHarvest

base_url = "https://www.warhammer-community.com"
formats = ["jpg"]

pic_harvest = PicHarvest(base_url, formats)
pic_harvest.get_sitemap()
pic_harvest.get_urls()

print("Hola mundo!")