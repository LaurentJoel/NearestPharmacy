import requests
import re

def debug_city(region, city):
    print(f"--- DEBUGGING {city.upper()} ---")
    url = f'https://www.annuaire-medical.cm/pharmacies-de-garde/{region}/pharmacies-de-garde-{city}'
    headers = {'User-Agent': 'Mozilla/5.0'}
    r = requests.get(url, headers=headers)
    html = r.text
    
    print(f"URL: {url}")
    print(f"HTML Length: {len(html)}")
    
    # Check what our current regex finds
    pattern = r'(PHARMACIE\s+[A-Z\s\'\-ÉÈÊËÀÂÄÙÛÜÔÎÏÇ]{3,50})(.*)'
    matches = re.finditer(pattern, html, re.IGNORECASE)
    
    print("\n--- REGEX MATCHES ---")
    count = 0
    for m in matches:
        raw_name = m.group(1).strip()
        print(f"[{count}] Raw: '{raw_name}'")
        count += 1
        if count > 5: break
        
    # Check fallback regex
    print("\n--- FALLBACK MATCHES ---")
    pattern_simple = r'(PHARMACIE\s+[A-Z\s\'\-ÉÈÊËÀÂÄÙÛÜÔÎÏÇ]{3,50})'
    matches_simple = re.findall(pattern_simple, html, re.IGNORECASE)
    for i, m in enumerate(matches_simple[:5]):
        print(f"[{i}] Simple: '{m.strip()}'")

debug_city('centre', 'yaounde')
debug_city('littoral', 'douala')
