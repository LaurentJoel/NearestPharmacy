import requests
import re

def debug_bamenda():
    url = 'https://www.annuaire-medical.cm/pharmacies-de-garde/nord-ouest/pharmacies-de-garde-bamenda'
    headers = {'User-Agent': 'Mozilla/5.0'}
    r = requests.get(url, headers=headers)
    html = r.text
    
    print(f"HTML Length: {len(html)}")
    
    # 1. Check strict regex (Block)
    pattern = r'(PHARMACIE\s+[A-Z\s\'\-ÉÈÊËÀÂÄÙÛÜÔÎÏÇ]{3,50})(.*)'
    matches = re.finditer(pattern, html, re.IGNORECASE)
    print("\n[BLOCK REGEX RESULTS]")
    for m in matches:
        print(f"  FOUND: {m.group(1).strip()[:40]}...")

    # 2. Check simple regex (Name only)
    pattern_simple = r'(PHARMACIE\s+[A-Z\s\'\-ÉÈÊËÀÂÄÙÛÜÔÎÏÇ]{3,50})'
    matches_simple = re.findall(pattern_simple, html, re.IGNORECASE)
    print(f"\n[SIMPLE REGEX COUNTS]: {len(matches_simple)}")
    
    # 3. Check for English "PHARMACY" (Bamenda is Anglophone!)
    pattern_eng = r'([A-Z\s\'\-]{3,30}\s+PHARMACY)'
    matches_eng = re.findall(pattern_eng, html, re.IGNORECASE)
    print(f"\n[ENGLISH REGEX COUNTS]: {len(matches_eng)}")
    for m in matches_eng:
        print(f"  ENG FOUND: {m.strip()}")

debug_bamenda()
