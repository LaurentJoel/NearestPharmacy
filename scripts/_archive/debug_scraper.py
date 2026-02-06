"""Debug script to test scraper matching"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.auto_daily_scraper import AutoDailyScraper

scraper = AutoDailyScraper()

# Scrape just Yaounde
pharmacies = scraper.scrape_city('centre', 'yaounde')
print(f'Scraped {len(pharmacies)} pharmacies from Yaounde')

if pharmacies:
    print('First 5:')
    for p in pharmacies[:5]:
        print(f"  {p['nom']}")

# Try matching
scraper.load_pharmacy_cache()
matched = 0
for p in pharmacies[:10]:
    result = scraper.find_pharmacy_match(p['nom'], p['ville'])
    if result:
        matched += 1
        print(f"  MATCHED: {p['nom']} -> ID {result}")
    else:
        print(f"  NO MATCH: {p['nom']}")

print(f'Matched {matched}/{min(len(pharmacies), 10)}')
