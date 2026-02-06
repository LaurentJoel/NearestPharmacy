"""
Correct Scraper - City-Based Matching
=====================================
This scraper:
1. Scrapes pharmacies on duty for each CITY from the website
2. Only matches to pharmacies in the database that are IN THAT SAME CITY
3. Ensures only correct pharmacies are marked as on duty

Run daily at 8:00 AM.
"""
import requests
import re
import psycopg2
from datetime import date
from dotenv import load_dotenv
import os
import time
import unicodedata

load_dotenv()

# City name mapping (website format -> database format)
CITY_MAPPING = {
    'yaounde': 'Yaoundé',
    'douala': 'Douala',
    'bamenda': 'Bamenda',
    'bafoussam': 'Bafoussam',
    'garoua': 'Garoua',
    'maroua': 'Maroua',
    'ngaoundere': 'Ngaoundéré',
    'bertoua': 'Bertoua',
    'ebolowa': 'Ebolowa',
    'kribi': 'Kribi',
    'buea': 'Buea',
    'limbe': 'Limbe',
    'kumba': 'Kumba',
    'nkongsamba': 'Nkongsamba',
    'edea': 'Edéa',
    'dschang': 'Dschang',
    'foumban': 'Foumban',
    'bafia': 'Bafia',
    'mbalmayo': 'Mbalmayo',
    'obala': 'Obala',
    'mbouda': 'Mbouda',
    'loum': 'Loum',
    'banyo': 'Banyo',
    'batouri': 'Batouri',
    'sangmelima': 'Sangmélima',
    'kousseri': 'Kousseri',
    'yagoua': 'Yagoua',
    'maga': 'Maga',
    'figuil': 'Figuil',
    'guider': 'Guider',
    'touboro': 'Touboro',
    'bafang': 'Bafang',
    'bagangte': 'Bagangte',
    'bandja': 'Bandja',
    'bandjoun': 'Bandjoun',
    'foumbot': 'Foumbot',
    'ambam': 'Ambam',
    'likomba': 'Likomba',
    'mutengene': 'Mutengene',
    'muyuka': 'Muyuka',
    'mbanga': 'Mbanga',
    'melong': 'Melong',
    'abong-mbang': 'Abong-Mbang',
    'garoua-boulai': 'Garoua-Boulai',
    'mbandjock': 'Mbandjock',
    'mbankomo': 'Mbankomo',
    'sa-a': 'Sa\'a',
    'mbengwy': 'Mbengwi',
}


def normalize_name(name):
    """Normalize pharmacy name for matching."""
    if not name:
        return ''
    name = name.lower()
    name = unicodedata.normalize('NFD', name)
    name = ''.join(c for c in name if unicodedata.category(c) != 'Mn')
    name = re.sub(r'[^\w\s]', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()
    for prefix in ['pharmacie ', 'pharmacy ', 'pharma ', 'la ', 'le ', 'les ', 'de ', 'du ', 'd ', 'des ']:
        if name.startswith(prefix):
            name = name[len(prefix):]
    return name.strip()


def scrape_city(region, city_url_name):
    """Scrape pharmacies on duty for a specific city."""
    url = f'https://www.annuaire-medical.cm/pharmacies-de-garde/{region}/pharmacies-de-garde-{city_url_name}'
    try:
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=60)
        html = r.text
    except Exception as e:
        return []
    
    # Updated regex to capture full lines or blocks
    # Looking for lines starting with PHARMACIE
    lines = html.split('\n')
    pharmacies = []
    
    current_pharmacy = {}
    
    # Parsing strategy: Look for "PHARMACIE ..." then extract details nearby
    # This website structure is messy, so we use a robust text extraction
    
    # Find all text blocks that look like pharmacies
    # Pattern: PHARMACIE [NAME] ... [Phone] ... [Quarter/Address]
    
    # 1. FRENCH FORMAT: PHARMACIE [NAME]
    # Example: "PHARMACIE DU SOLEIL 22 22 22 22 Mvog-Mbi"
    pattern_fr = r'(PHARMACIE\s+[A-Z\s\'\-ÉÈÊËÀÂÄÙÛÜÔÎÏÇ]{3,50})(.*)'
    matches_fr = re.finditer(pattern_fr, html, re.IGNORECASE)
    
    # 2. ENGLISH FORMAT: [NAME] PHARMACY or PHARMACY [NAME]
    # Example: "VILEN PHARMACY ..."
    pattern_en = r'([A-Z\s\'\-]{3,30}\s+PHARMACY)(.*)'
    matches_en = re.finditer(pattern_en, html, re.IGNORECASE)

    # Blacklist of headers/non-pharmacies
    BLACKLIST = [
        "PHARMACIE DE GARDE", 
        "PHARMACIE DE NUIT", 
        "PHARMACIES DE GARDE", 
        "PAS SUR NOTRE LISTING",
        "NOTRE LISTING",
        "VOTRE PHARMACIE",
        "NOUVELLE PHARMACIE",
        "PHARMACY ON DUTY",
        "DUTY PHARMACY"
    ]

    def process_match(m, lang='fr'):
        raw_name = m.group(1).strip()
        rest = m.group(2).strip()
        
        # Clean name
        name = raw_name
        if lang == 'fr':
            name = re.sub(r'^\s*PHARMACIE\s+', '', name, flags=re.IGNORECASE).strip()
        else: # en
            name = re.sub(r'\s+PHARMACY\s*$', '', name, flags=re.IGNORECASE).strip()
            name = re.sub(r'^\s*PHARMACY\s+', '', name, flags=re.IGNORECASE).strip()

        # Check blacklist
        if any(bad in raw_name.upper() for bad in BLACKLIST) or any(bad in name.upper() for bad in BLACKLIST):
            return None
            
        # Extract phone
        phone = ''
        phone_match = re.search(r'(\d{2,3}[\s\.]?\d{2}[\s\.]?\d{2}[\s\.]?\d{2})', rest)
        if phone_match:
            phone = phone_match.group(1)
            rest = rest.replace(phone, '')
        
        # Clean address
        city_clean = city_url_name.replace('-', ' ')
        rest = re.sub(f'{city_clean}', '', rest, flags=re.IGNORECASE)
        address = re.sub(r'[:,\-]', ' ', rest).strip()
        address = re.sub(r'\s+', ' ', address).strip()
        
        if len(name) < 3:
            return None
            
        return {
            'name': "Pharmacie " + name.title(), # Standardize to French prefix for DB consistency
            'raw_name': raw_name,
            'phone': phone,
            'quarter': address
        }

    # Process French Matches
    for m in matches_fr:
        p = process_match(m, 'fr')
        if p: pharmacies.append(p)
        
    # Process English Matches
    for m in matches_en:
        p = process_match(m, 'en')
        if p and not any(existing['raw_name'] == p['raw_name'] for existing in pharmacies):
            pharmacies.append(p)
    
    # FALLBACK STRATEGY:
    # If we found nothing or very few (e.g. < 2), try simpler name extraction
    if len(pharmacies) < 2:
        # Simple regex for just the name (FR)
        matches_simple_fr = re.findall(r'(PHARMACIE\s+[A-Z\s\'\-ÉÈÊËÀÂÄÙÛÜÔÎÏÇ]{3,50})', html, re.IGNORECASE)
        # Simple regex for just the name (EN)
        matches_simple_en = re.findall(r'([A-Z\s\'\-]{3,30}\s+PHARMACY)', html, re.IGNORECASE)
        
        existing_names = set(p['raw_name'] for p in pharmacies)
        
        for raw_name in matches_simple_fr + matches_simple_en:
            raw_name = raw_name.strip()
            
            if any(bad in raw_name.upper() for bad in BLACKLIST):
                continue
            if raw_name in existing_names:
                continue
            
            # Clean name
            name = raw_name
            name = re.sub(r'^\s*PHARMACIE\s+', '', name, flags=re.IGNORECASE)
            name = re.sub(r'\s+PHARMACY\s*$', '', name, flags=re.IGNORECASE).strip()
            
            if len(name) < 3:
                continue
                
            pharmacies.append({
                'name': "Pharmacie " + name.title(),
                'raw_name': raw_name,
                'phone': '', 
                'quarter': 'Non spécifié'
            })
            existing_names.add(raw_name)
            
    return pharmacies


def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=os.getenv('DB_PORT', '5432'),
        dbname=os.getenv('DB_NAME', 'pharmacy_db'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', 'postgres')
    )


def match_pharmacy_in_city(scraped_name, db_city_name, cursor):
    """
    Match a scraped pharmacy name ONLY to pharmacies in the SAME city in database.
    Returns pharmacy_id or None.
    """
    scraped_norm = normalize_name(scraped_name)
    if not scraped_norm or len(scraped_norm) < 3:
        return None
    
    # Get pharmacies in this city only
    cursor.execute("""
        SELECT id, nom FROM pharmacies 
        WHERE ville = %s OR ville ILIKE %s
    """, (db_city_name, f'%{db_city_name}%'))
    
    city_pharmacies = cursor.fetchall()
    
    best_match = None
    best_score = 0
    
    for pid, pname in city_pharmacies:
        db_norm = normalize_name(pname)
        
        # Exact match
        if scraped_norm == db_norm:
            return pid
        
        # Contains match
        if len(scraped_norm) > 4 and len(db_norm) > 4:
            if scraped_norm in db_norm or db_norm in scraped_norm:
                score = 70
                if score > best_score:
                    best_score = score
                    best_match = pid
        
        # Word overlap
        scraped_words = set(scraped_norm.split())
        db_words = set(db_norm.split())
        overlap = scraped_words.intersection(db_words)
        long_overlap = [w for w in overlap if len(w) > 4]
        if long_overlap:
            score = len(long_overlap) * 30
            if score > best_score:
                best_score = score
                best_match = pid
    
    if best_score >= 30:
        return best_match
    
    return None


def main():
    print("=" * 60)
    print("CORRECT CITY-BASED SCRAPER")
    print("=" * 60)
    print(f"Date: {date.today()}")
    
    # All cities with their regions
    CITIES = {
        'adamaoua': ['banyo', 'ngaoundere'],
        'centre': ['bafia', 'mbalmayo', 'mbandjock', 'mbankomo', 'obala', 'sa-a', 'yaounde'],
        'est': ['abong-mbang', 'batouri', 'bertoua', 'garoua-boulai'],
        'extreme-nord': ['kousseri', 'maga', 'maroua', 'yagoua'],
        'littoral': ['douala', 'edea', 'loum', 'mbanga', 'melong', 'nkongsamba'],
        'nord': ['figuil', 'garoua', 'guider', 'touboro'],
        'nord-ouest': ['bamenda', 'mbengwy'],
        'ouest': ['bafang', 'bafoussam', 'bagangte', 'bandja', 'bandjoun', 'dschang', 'foumban', 'foumbot', 'mbouda'],
        'sud': ['ambam', 'ebolowa', 'kribi', 'sangmelima'],
        'sud-ouest': ['buea', 'kumba', 'likomba', 'limbe', 'mutengene', 'muyuka']
    }
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Delete old gardes
    cursor.execute("DELETE FROM gardes WHERE date_garde < CURRENT_DATE")
    print(f"\nDeleted old gardes")
    
    # Also delete today's gardes to refresh
    cursor.execute("DELETE FROM gardes WHERE date_garde = CURRENT_DATE")
    conn.commit()
    
    total_matched = 0
    city_stats = {}
    
    for region, cities in CITIES.items():
        print(f"\n{region.upper()}:")
        
        for city_url in cities:
            # Get database city name
            db_city = CITY_MAPPING.get(city_url, city_url.title())
            
            # Scrape this city
            scraped_names = scrape_city(region, city_url)
            
            if not scraped_names:
                continue
            
            # Match only to pharmacies in THIS city
            matched_count = 0
            scraped_count = 0
            
            for p in scraped_names:
                scraped_count += 1
                name = p['name']
                raw_name = p['raw_name'][:254]
                phone = p['phone']
                quarter = p['quarter'][:254] if p['quarter'] else ''
                
                # Try to find match
                pharmacy_id = match_pharmacy_in_city(name, db_city, cursor)
                
                if pharmacy_id:
                    # MATCH FOUND: Insert with ID
                    cursor.execute("""
                        INSERT INTO gardes (pharmacie_id, date_garde, nom_scrape, quarter_scrape, city_scrape)
                        VALUES (%s, CURRENT_DATE, %s, %s, %s)
                        ON CONFLICT (pharmacie_id, date_garde) DO UPDATE 
                        SET nom_scrape = EXCLUDED.nom_scrape, quarter_scrape = EXCLUDED.quarter_scrape, city_scrape = EXCLUDED.city_scrape
                    """, (pharmacy_id, raw_name, quarter, db_city))
                    matched_count += cursor.rowcount
                else:
                    # NO MATCH: Insert with NULL ID
                    cursor.execute("""
                        SELECT id FROM gardes 
                        WHERE pharmacie_id IS NULL 
                          AND date_garde = CURRENT_DATE 
                          AND nom_scrape = %s
                    """, (raw_name,))
                    
                    if not cursor.fetchone():
                        cursor.execute("""
                            INSERT INTO gardes (pharmacie_id, date_garde, nom_scrape, quarter_scrape, city_scrape)
                            VALUES (NULL, CURRENT_DATE, %s, %s, %s)
                        """, (raw_name, quarter, db_city))
            
            conn.commit()
            
            if scraped_count > 0:
                print(f"  {db_city}: Scraped {scraped_count}, Matched {matched_count}")
                city_stats[db_city] = matched_count
                total_matched += matched_count
            
            time.sleep(0.3)
    
    # Summary
    cursor.execute("SELECT COUNT(*) FROM gardes WHERE date_garde = CURRENT_DATE")
    total_today = cursor.fetchone()[0]
    
    print("\n" + "=" * 60)
    print(f"TOTAL PHARMACIES ON DUTY TODAY: {total_today}")
    print("=" * 60)
    
    print("\nBy city (Matched + Unmatched):")
    cursor.execute("""
        SELECT city_scrape, COUNT(*) 
        FROM gardes 
        WHERE date_garde = CURRENT_DATE
        GROUP BY city_scrape
        ORDER BY COUNT(*) DESC
    """)
    for ville, count in cursor.fetchall():
        print(f"  {ville}: {count}")
    
    cursor.close()
    conn.close()
    
    print("\nAPI endpoint ready:")
    print("  /api/pharmacies/nearby?lat=3.8667&lon=11.5167&radius=10000")


if __name__ == '__main__':
    main()
