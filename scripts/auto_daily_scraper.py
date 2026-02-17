"""
Auto Daily Scraper - Pharmacy Duty (Gardes)
============================================
This script:
1. Scrapes today's duty pharmacies from annuaire-medical.cm
2. Deletes old garde entries (yesterday and before)
3. Matches scraped pharmacies with database using fuzzy matching
4. Inserts into gardes table

Schedule: Run daily at 8:00 AM (duty period is 8AM today to 8AM tomorrow)

Usage:
    Standalone:
        python scripts/auto_daily_scraper.py
    
    From parent app:
        from scripts.auto_daily_scraper import AutoDailyScraper
        scraper = AutoDailyScraper(db_connection=my_conn, schema='pharmacy')
        scraper.run()

For Windows Task Scheduler or cron job at 8:00 AM daily.
"""
import requests
from bs4 import BeautifulSoup
from datetime import datetime, date, timedelta
import re
import psycopg2
import os
import time
import unicodedata
from dotenv import load_dotenv

load_dotenv()


def normalize_name(name):
    """
    Normalize pharmacy name for matching.
    Handles accents, case, common abbreviations.
    """
    if not name:
        return ''
    
    # Convert to lowercase
    name = name.lower()
    
    # Remove accents
    name = unicodedata.normalize('NFD', name)
    name = ''.join(c for c in name if unicodedata.category(c) != 'Mn')
    
    # Remove punctuation and extra spaces
    name = re.sub(r'[^\w\s]', ' ', name)
    name = re.sub(r'\s+', ' ', name).strip()
    
    # Remove common prefixes
    prefixes = ['pharmacie ', 'pharmacy ', 'pharma ', 'la ', 'le ', 'les ', 'de ', 'du ', 'd ', 'des ']
    for prefix in prefixes:
        if name.startswith(prefix):
            name = name[len(prefix):]
    
    return name.strip()


def get_key_words(name):
    """Extract key words from pharmacy name for fuzzy matching."""
    normalized = normalize_name(name)
    words = normalized.split()
    # Filter short words and common words
    stop_words = {'de', 'du', 'la', 'le', 'les', 'des', 'et', 'a', 'au', 'aux'}
    key_words = [w for w in words if len(w) > 2 and w not in stop_words]
    return key_words


class AutoDailyScraper:
    """
    Scrapes pharmacy duty info and updates database.
    Designed to run once daily at 8:00 AM.
    """
    
    BASE_URL = "https://www.annuaire-medical.cm"
    
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
    
    # GPS coordinates for all scraped cities (lat, lon)
    CITY_COORDS = {
        # Adamaoua
        'Banyo':           (6.7500, 11.8167),
        'Ngaoundéré':      (7.3167, 13.5833),
        # Centre
        'Bafia':           (4.7500, 11.2333),
        'Mbalmayo':        (3.5167, 11.5000),
        'Mbandjock':       (4.4500, 11.9000),
        'Mbankomo':        (3.7833, 11.3833),
        'Obala':           (4.1667, 11.5333),
        'Sa A':            (4.3667, 11.4500),
        'Yaounde':         (3.8667, 11.5167),
        # Est
        'Abong Mbang':     (3.9833, 13.1833),
        'Batouri':         (4.4333, 14.3667),
        'Bertoua':         (4.5833, 13.6833),
        'Garoua Boulai':   (5.8833, 14.5500),
        # Extreme-Nord
        'Kousseri':        (12.0767, 15.0306),
        'Maga':            (10.8500, 14.9500),
        'Maroua':          (10.5956, 14.3159),
        'Yagoua':          (10.3417, 15.2333),
        # Littoral
        'Douala':          (4.0511, 9.7679),
        'Edea':            (3.8000, 10.1333),
        'Loum':            (4.7167, 9.7333),
        'Mbanga':          (4.5000, 9.5667),
        'Melong':          (5.1167, 9.9500),
        'Nkongsamba':      (4.9500, 9.9333),
        # Nord
        'Figuil':          (9.7583, 13.9667),
        'Garoua':          (9.3000, 13.3833),
        'Guider':          (9.9333, 13.9500),
        'Touboro':         (7.7667, 15.3667),
        # Nord-Ouest
        'Bamenda':         (5.9597, 10.1597),
        'Mbengwy':         (6.1000, 10.0000),
        # Ouest
        'Bafang':          (5.1667, 10.1833),
        'Bafoussam':       (5.4737, 10.4176),
        'Bagangte':        (5.1500, 10.5333),
        'Bandja':          (5.3333, 10.3667),
        'Bandjoun':        (5.3667, 10.4167),
        'Dschang':         (5.4500, 10.0500),
        'Foumban':         (5.7167, 10.8833),
        'Foumbot':         (5.5167, 10.6167),
        'Mbouda':          (5.6333, 10.2500),
        # Sud
        'Ambam':           (2.3833, 11.2833),
        'Ebolowa':         (2.9000, 11.1500),
        'Kribi':           (2.9500, 9.9167),
        'Sangmelima':      (2.9333, 11.9833),
        # Sud-Ouest
        'Buea':            (4.1597, 9.2311),
        'Kumba':           (4.6333, 9.4500),
        'Likomba':         (4.0833, 9.2667),
        'Limbe':           (4.0167, 9.2000),
        'Mutengene':       (4.0917, 9.3083),
        'Muyuka':          (4.2833, 9.4167),
    }
    
    # Known quarter/neighborhood GPS coordinates for major cities
    # Used to more precisely locate pharmacies when quarter info is available
    QUARTER_COORDS = {
        'yaounde': {
            # Central & popular quarters
            'centre ville':      (3.8667, 11.5167),
            'centre':            (3.8667, 11.5167),
            'marche central':    (3.8660, 11.5183),
            'poste centrale':    (3.8667, 11.5167),
            'avenue kennedy':    (3.8667, 11.5150),
            'hippodrome':        (3.8756, 11.5200),
            'nlongkak':          (3.8800, 11.5167),
            'bastos':            (3.8917, 11.5100),
            'golf':              (3.8850, 11.5050),
            'tsinga':            (3.8833, 11.5033),
            'messa':             (3.8722, 11.5043),
            'camp yeyap':        (3.8700, 11.5000),
            'briqueterie':       (3.8761, 11.5120),
            'mokolo':            (3.8750, 11.5100),
            'mvog mbi':          (3.8600, 11.5250),
            'mvog ada':          (3.8644, 11.5277),
            'mvog atangana mballa': (3.8489, 11.5193),
            'mvolyé':            (3.8550, 11.5017),
            'nsimeyong':         (3.8352, 11.4944),
            'nkoldongo':         (3.8560, 11.5273),
            'essos':             (3.8737, 11.5403),
            'omnisport':         (3.8833, 11.5433),
            'omnisports':        (3.8833, 11.5433),
            'mfandena':          (3.8800, 11.5350),
            'biyem assi':        (3.8373, 11.4850),
            'biyem-assi':        (3.8373, 11.4850),
            'mendong':           (3.8400, 11.4700),
            'simbock':           (3.8212, 11.4719),
            'nkolbisson':        (3.8600, 11.4600),
            'oyom abang':        (3.8751, 11.4754),
            'etoudi':            (3.8950, 11.5250),
            'olembe':            (3.9167, 11.5333),
            'ngoussou':          (3.8943, 11.5492),
            'ngousso':           (3.8943, 11.5492),
            'chapelle ngousso':  (3.8943, 11.5492),
            'ekounou':           (3.8440, 11.5405),
            'ahala':             (3.7947, 11.4899),
            'nsam':              (3.8251, 11.5077),
            'obili':             (3.8512, 11.4935),
            'melen':             (3.8504, 11.4866),
            'efoulan':           (3.8357, 11.5069),
            'elig edzoa':        (3.8867, 11.5282),
            'madagascar':        (3.8828, 11.4927),
            'awae escalier':     (3.8370, 11.5037),
            'odza':              (3.8075, 11.5303),
            'petit marche odza': (3.8075, 11.5303),
            'tongolo':           (3.9068, 11.5251),
            'kondengui':         (3.8650, 11.5380),
            'etoa meki':         (3.8834, 11.5263),
            'carrefour meec':    (3.8700, 11.4850),
            'fokou etoudi':      (3.8950, 11.5250),
            'olezoa':            (3.8465, 11.5148),
            'mobil olezoa':      (3.8465, 11.5148),
            'mimboman':          (3.8600, 11.5500),
            'mimboman chapelle': (3.8600, 11.5500),
            'cinema abbia':      (3.8671, 11.5170),
            'nouvelle route omnisports': (3.8806, 11.5389),
            'ecole de guerre':   (3.8212, 11.4719),
            'face feicom':       (3.8600, 11.5500),
            'carrefour amitie':  (3.8498, 11.5157),
            'cite verte':        (3.8800, 11.4950),
            'emana':             (3.9050, 11.5250),
            'nkolmesseng':       (3.8450, 11.5150),
            'ngoa ekele':        (3.8595, 11.5046),
            'mvog betsi':        (3.8500, 11.5300),
            'damas':             (3.8600, 11.5350),
            'nkomo':             (3.8450, 11.5451),
            'etoa':              (3.8834, 11.5263),
            'obobogo':           (3.8300, 11.4900),
            'mvan':              (3.8350, 11.5150),
            'anguissa':          (3.8550, 11.5250),
            'elig essono':       (3.8580, 11.5220),
            'messa dead end':    (3.8722, 11.5043),
            'nkomkana':          (3.8400, 11.5200),
        },
        'douala': {
            'akwa':              (4.0500, 9.7000),
            'akwa nord':         (4.0600, 9.7100),
            'bonanjo':           (4.0400, 9.6900),
            'bonapriso':         (4.0400, 9.7150),
            'bali':              (4.0300, 9.6900),
            'deido':             (4.0600, 9.7350),
            'bonaberi':          (4.0700, 9.6700),
            'ndokoti':           (4.0400, 9.7400),
            'makepe':            (4.0650, 9.7550),
            'kotto':             (4.0680, 9.7600),
            'bonamoussadi':      (4.0750, 9.7450),
            'logpom':            (4.0600, 9.7700),
            'logbessou':         (4.0550, 9.7600),
            'bepanda':           (4.0500, 9.7550),
            'cite des palmiers': (4.0450, 9.7600),
            'new bell':          (4.0350, 9.7300),
            'village':           (4.0450, 9.7350),
            'madagascar':        (4.0350, 9.7350),
            'bassa':             (4.0250, 9.7500),
            'pk8':               (4.0600, 9.7850),
            'pk10':              (4.0700, 9.7950),
            'pk12':              (4.0800, 9.8050),
            'pk14':              (4.0900, 9.8150),
            'yassa':             (4.0200, 9.7800),
            'japoma':            (4.0100, 9.7700),
            'nyalla':            (4.0100, 9.7800),
            'omnisports':        (4.0300, 9.7600),
            'bapenda':           (4.0200, 9.7000),
        },
    }
    
    # Default coordinates that indicate a pharmacy was never properly geocoded.
    # These are Yaoundé-center defaults injected during original data import.
    DEFAULT_COORDS = [
        (3.8530, 11.5021),
        (3.8533, 11.5050),
        (3.8480, 11.5020),
        (3.8518, 11.5080),
        (3.8486, 11.5101),
        (3.8443, 11.5103),
        (3.8400, 11.5081),
        (3.8371, 11.5037),
        (3.8395, 11.4923),
        (3.8450, 11.4884),
    ]
    
    def __init__(self, db_connection=None, db_config=None, schema='public'):
        """
        Initialize scraper.
        
        Args:
            db_connection: An existing psycopg2 connection (from parent app). Optional.
            db_config: Dict with keys: host, port, dbname, user, password. Optional.
            schema: PostgreSQL schema for pharmacy tables (default: 'public').
        """
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.db_conn = db_connection
        self._db_config = db_config
        self.schema = schema
        self._pharmacy_cache = None  # Cache all pharmacies from DB
        
    def get_db_connection(self):
        """Get database connection. Uses external connection if provided."""
        if self.db_conn and not self.db_conn.closed:
            return self.db_conn
        
        if self._db_config:
            self.db_conn = psycopg2.connect(**self._db_config)
        else:
            self.db_conn = psycopg2.connect(
                host=os.getenv('DB_HOST', 'localhost'),
                port=os.getenv('DB_PORT', '5432'),
                dbname=os.getenv('DB_NAME', 'pharmacy_db'),
                user=os.getenv('DB_USER', 'postgres'),
                password=os.getenv('DB_PASSWORD', 'postgres')
            )
        
        # Set search_path for schema support
        if self.schema != 'public':
            cursor = self.db_conn.cursor()
            cursor.execute(f"SET search_path TO {self.schema}, public")
            cursor.close()
        
        return self.db_conn
    
    def _table(self, name):
        """Return schema-qualified table name."""
        return f"{self.schema}.{name}"
    
    def load_pharmacy_cache(self):
        """Load all pharmacies from database for matching."""
        if self._pharmacy_cache is not None:
            return
        
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT id, nom, ville, ST_Y(geom) as lat, ST_X(geom) as lon FROM {self._table('pharmacies')}")
        rows = cursor.fetchall()
        cursor.close()
        
        self._pharmacy_cache = []
        for row in rows:
            self._pharmacy_cache.append({
                'id': row[0],
                'nom': row[1],
                'ville': row[2],
                'lat': row[3],
                'lon': row[4],
                'normalized': normalize_name(row[1]),
                'key_words': get_key_words(row[1])
            })
        
        print(f"  Loaded {len(self._pharmacy_cache)} pharmacies from database")
    
    def _is_default_coord(self, lat, lon):
        """Check if coordinates are one of the known default/placeholder values."""
        for def_lat, def_lon in self.DEFAULT_COORDS:
            if abs(lat - def_lat) < 0.001 and abs(lon - def_lon) < 0.001:
                return True
        return False
    
    def _get_city_key(self, city_name):
        """Normalize city name to match CITY_COORDS keys."""
        if not city_name:
            return None
        # Remove accents for matching
        normalized = unicodedata.normalize('NFD', city_name)
        normalized = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
        normalized = normalized.strip()
        
        # Try exact match first
        for key in self.CITY_COORDS:
            key_norm = unicodedata.normalize('NFD', key)
            key_norm = ''.join(c for c in key_norm if unicodedata.category(c) != 'Mn')
            if key_norm.lower() == normalized.lower():
                return key
        return None
    
    def geocode_quarter(self, city_name, quarter_text):
        """
        Try to find GPS coordinates from quarter/address text.
        Returns (lat, lon) or None.
        """
        if not quarter_text:
            return None
        
        # Normalize city name for quarter lookup
        city_key = city_name.lower().strip() if city_name else ''
        city_key = unicodedata.normalize('NFD', city_key)
        city_key = ''.join(c for c in city_key if unicodedata.category(c) != 'Mn')
        
        if city_key not in self.QUARTER_COORDS:
            return None
        
        quarters = self.QUARTER_COORDS[city_key]
        
        # Normalize the quarter text
        qt = quarter_text.lower().strip()
        qt = unicodedata.normalize('NFD', qt)
        qt = ''.join(c for c in qt if unicodedata.category(c) != 'Mn')
        
        # Strategy 1: Direct match with a quarter name
        for q_name, coords in quarters.items():
            if q_name in qt or qt in q_name:
                return coords
        
        # Strategy 2: Check each word in the quarter text against known quarters
        qt_words = re.sub(r'[^\w\s]', ' ', qt).split()
        for word in qt_words:
            if len(word) < 4:
                continue
            for q_name, coords in quarters.items():
                q_words = q_name.split()
                for q_word in q_words:
                    if len(q_word) < 4:
                        continue
                    if word == q_word:
                        return coords
        
        return None
    
    def get_best_coordinates(self, city_name, quarter_text):
        """
        Get the best available GPS coordinates for a pharmacy.
        Priority: quarter coords > city center coords > None.
        Returns (lat, lon) or None.
        """
        # Try quarter-level precision first
        quarter_coords = self.geocode_quarter(city_name, quarter_text)
        if quarter_coords:
            return quarter_coords
        
        # Fall back to city center
        city_key = self._get_city_key(city_name)
        if city_key:
            return self.CITY_COORDS[city_key]
        
        return None
    
    def fix_pharmacy_coordinates(self, matched_entries):
        """
        Fix GPS coordinates for pharmacies that have default/placeholder coords.
        Uses city and quarter data from scraping to relocate them.
        
        Args:
            matched_entries: list of dicts with pharmacie_id, nom, adresse, ville
        
        Returns:
            Number of pharmacies fixed
        """
        conn = self.get_db_connection()
        cursor = conn.cursor()
        fixed_count = 0
        
        for entry in matched_entries:
            pharmacy_id = entry['pharmacie_id']
            city_name = entry.get('ville', '')
            quarter = entry.get('adresse', '')
            
            # Find this pharmacy in cache to check its current coords
            db_pharm = None
            for p in self._pharmacy_cache:
                if p['id'] == pharmacy_id:
                    db_pharm = p
                    break
            
            if not db_pharm:
                continue
            
            current_lat = db_pharm.get('lat', 0) or 0
            current_lon = db_pharm.get('lon', 0) or 0
            
            # Only fix if the current coordinates are default/placeholder
            if not self._is_default_coord(current_lat, current_lon):
                continue
            
            # Get best coordinates from city/quarter
            new_coords = self.get_best_coordinates(city_name, quarter)
            if not new_coords:
                continue
            
            new_lat, new_lon = new_coords
            
            # Also fix the ville if it's wrong (e.g., "Yaoundé" for a Kumba pharmacy)
            city_key = self._get_city_key(city_name)
            correct_ville = city_key if city_key else city_name
            
            cursor.execute(f"""
                UPDATE {self._table('pharmacies')} 
                SET geom = ST_SetSRID(ST_MakePoint(%s, %s), 4326),
                    ville = %s,
                    updated_at = NOW()
                WHERE id = %s
            """, (new_lon, new_lat, correct_ville, pharmacy_id))
            
            if cursor.rowcount > 0:
                fixed_count += 1
                # Update cache too
                db_pharm['lat'] = new_lat
                db_pharm['lon'] = new_lon
                db_pharm['ville'] = correct_ville
        
        conn.commit()
        cursor.close()
        return fixed_count
    
    def get_city_url(self, region, city):
        """Generate URL for city garde page."""
        return f"{self.BASE_URL}/pharmacies-de-garde/{region}/pharmacies-de-garde-{city}"
    
    def scrape_city(self, region, city):
        """Scrape garde pharmacies for a city."""
        url = self.get_city_url(region, city)
        
        try:
            response = self.session.get(url, timeout=60)  # Increased timeout
            response.raise_for_status()
            html = response.text
        except Exception as e:
            print(f"    Error scraping {city}: {e}")
            return []
        
        # Try lxml first, fall back to html.parser
        try:
            soup = BeautifulSoup(html, 'lxml')
        except:
            soup = BeautifulSoup(html, 'html.parser')
        
        pharmacies = []
        
        # Find pharmacy entries — site uses both 'ligne_pers' and 'pharma_line' classes
        pharmacy_divs = soup.find_all('div', class_=['ligne_pers', 'pharma_line'])
        
        if pharmacy_divs:
            for item in pharmacy_divs:
                strong = item.find('strong')
                if not strong:
                    continue
                nom = strong.get_text(strip=True)
                # Match any entry containing "pharmacie" or "pharmacy" anywhere in the name
                nom_upper = nom.upper()
                if 'PHARMACIE' not in nom_upper and 'PHARMACY' not in nom_upper:
                    continue
                
                # Get full text: "NAME | PHONE | CITY: ADDRESS | PHONE2"
                full_text = item.get_text(separator=' | ', strip=True)
                pharmacy = self.parse_pharmacy_line(full_text, city)
                if pharmacy:
                    pharmacies.append(pharmacy)
        else:
            # Fallback: try carousel items (legacy site structure)
            carousel_items = soup.find_all('div', class_='carousel-item')
            for item in carousel_items:
                text = item.get_text(separator='\n', strip=True)
                lines = text.split('\n')
                for line in lines:
                    line = line.strip()
                    if not line.upper().startswith('PHARMACIE') and not line.upper().startswith('PHARMACY'):
                        continue
                    pharmacy = self.parse_pharmacy_line(line, city)
                    if pharmacy:
                        pharmacies.append(pharmacy)
        
        return pharmacies
    
    def parse_pharmacy_line(self, line, city):
        """Parse a pharmacy line from the website.
        
        Handles pipe-separated format: "NAME | PHONE | CITY: ADDRESS | PHONE2"
        Also handles legacy inline format: "NAME PHONE CITY: ADDRESS"
        """
        try:
            # Phone pattern: 3 digits then 2-digit groups (e.g. 234 89 72 04 or 655 43 96 62)
            phone_pattern = r'(\d{3}\s*\d{2}\s*\d{2}\s*\d{2})'
            
            # If pipe-separated, split into parts
            if ' | ' in line:
                parts = [p.strip() for p in line.split(' | ')]
                nom = parts[0]
                phone = ''
                adresse = ''
                
                for part in parts[1:]:
                    phone_match = re.match(phone_pattern, part)
                    if phone_match and not phone:
                        phone = phone_match.group(1).strip()
                    elif ':' in part:
                        # "Yaoundé: ADDRESS TEXT"
                        adresse = part.split(':', 1)[1].strip()
                    elif not phone:
                        # Might be address without colon
                        adresse = part
            else:
                # Legacy format: extract phone first, then name/address
                phone_match = re.search(phone_pattern, line)
                if phone_match:
                    phone = phone_match.group(1).strip()
                    phone_idx = line.find(phone)
                    nom = line[:phone_idx].strip()
                    remaining = line[phone_idx + len(phone):].strip()
                    if ':' in remaining:
                        adresse = remaining.split(':', 1)[1].strip()
                    else:
                        adresse = remaining
                else:
                    nom = line.split(':')[0].strip() if ':' in line else line.strip()
                    phone = ''
                    adresse = ''
            
            # Clean name: remove trailing pipes/spaces
            nom = re.sub(r'[\s|]+$', '', nom)
            nom = re.sub(r'\s+', ' ', nom).strip()
            
            if not nom:
                return None
            
            # Normalize city name
            city_display = city.title().replace('-', ' ')
            if city_display == 'Ngaoundere':
                city_display = 'Ngaoundéré'
            
            return {
                'nom': nom,
                'telephone': phone,
                'adresse': adresse,
                'ville': city_display
            }
        except Exception as e:
            return None
    
    def find_pharmacy_match(self, scraped_name, scraped_city):
        """
        Find matching pharmacy in database using fuzzy matching.
        NOTE: Most pharmacies have city='Inconnu', so we match by name only.
        Returns pharmacy_id or None.
        """
        self.load_pharmacy_cache()
        
        scraped_normalized = normalize_name(scraped_name)
        scraped_keys = set(get_key_words(scraped_name))
        
        if not scraped_normalized or len(scraped_normalized) < 3:
            return None
        
        best_match = None
        best_score = 0
        
        for db_pharmacy in self._pharmacy_cache:
            score = 0
            db_normalized = db_pharmacy['normalized']
            db_keys = set(db_pharmacy['key_words'])
            
            # Method 1: Exact normalized match = 100 points (instant win)
            if scraped_normalized == db_normalized:
                return db_pharmacy['id']
            
            # Method 2: One name contains the other
            if len(scraped_normalized) > 4 and len(db_normalized) > 4:
                if scraped_normalized in db_normalized:
                    score = max(score, 70)
                elif db_normalized in scraped_normalized:
                    score = max(score, 70)
            
            # Method 3: Key word overlap
            if db_keys and scraped_keys:
                overlap = db_keys.intersection(scraped_keys)
                if overlap:
                    # Score based on overlap
                    overlap_score = len(overlap) * 25
                    
                    # Bonus if more than half of words match
                    max_words = max(len(db_keys), len(scraped_keys))
                    if len(overlap) >= max_words / 2:
                        overlap_score += 20
                    
                    # Bonus for matching distinctive words (longer words)
                    long_overlap = [w for w in overlap if len(w) > 4]
                    if long_overlap:
                        overlap_score += len(long_overlap) * 15
                    
                    score = max(score, overlap_score)
            
            # Method 4: Check if main distinctive word matches
            if scraped_keys and db_keys:
                # Get longest word from each (usually most distinctive)
                scraped_main = max(scraped_keys, key=len) if scraped_keys else ''
                db_main = max(db_keys, key=len) if db_keys else ''
                
                if scraped_main and db_main and len(scraped_main) > 3 and len(db_main) > 3:
                    if scraped_main == db_main:
                        score = max(score, 60)
                    elif scraped_main in db_main or db_main in scraped_main:
                        score = max(score, 45)
            
            if score > best_score:
                best_score = score
                best_match = db_pharmacy['id']
        
        # Require minimum score of 35 for a match
        if best_score >= 35:
            return best_match
        
        return None
    
    def delete_old_gardes(self):
        """Delete yesterday's and older garde entries."""
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        yesterday = date.today() - timedelta(days=1)
        
        cursor.execute(f"DELETE FROM {self._table('gardes')} WHERE date_garde <= %s", (yesterday,))
        deleted = cursor.rowcount
        
        conn.commit()
        cursor.close()
        
        print(f"  Deleted {deleted} old garde entries (before {date.today()})")
        return deleted
    
    def insert_gardes(self, matched_entries, unmatched_entries=None, garde_date=None):
        """Insert scraped pharmacies into gardes table.
        
        Args:
            matched_entries: list of dicts with keys: pharmacie_id, nom, adresse, ville
            unmatched_entries: list of dicts with keys: nom, adresse, ville (no DB match)
            garde_date: date for the garde (default: today)
        """
        if garde_date is None:
            garde_date = date.today()
        
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        inserted = 0
        
        # Clear old unmatched entries for this date (no UNIQUE constraint on NULL pharmacie_id)
        cursor.execute(f"""
            DELETE FROM {self._table('gardes')} 
            WHERE date_garde = %s AND pharmacie_id IS NULL
        """, (garde_date,))
        
        # Insert matched pharmacies (with pharmacie_id)
        for entry in matched_entries:
            cursor.execute(f"""
                INSERT INTO {self._table('gardes')} 
                    (pharmacie_id, date_garde, nom_scrape, quarter_scrape, city_scrape)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (pharmacie_id, date_garde) DO UPDATE
                    SET nom_scrape = EXCLUDED.nom_scrape,
                        quarter_scrape = EXCLUDED.quarter_scrape,
                        city_scrape = EXCLUDED.city_scrape
            """, (
                entry['pharmacie_id'], garde_date,
                entry['nom'], entry.get('adresse', ''), entry.get('ville', '')
            ))
            inserted += cursor.rowcount
        
        # Insert unmatched pharmacies (no pharmacie_id)
        if unmatched_entries:
            for entry in unmatched_entries:
                cursor.execute(f"""
                    INSERT INTO {self._table('gardes')} 
                        (pharmacie_id, date_garde, nom_scrape, quarter_scrape, city_scrape,
                         approx_lat, approx_lon)
                    VALUES (NULL, %s, %s, %s, %s, %s, %s)
                """, (
                    garde_date,
                    entry['nom'], entry.get('adresse', ''), entry.get('ville', ''),
                    entry.get('latitude'), entry.get('longitude')
                ))
                inserted += cursor.rowcount
        
        conn.commit()
        cursor.close()
        
        return inserted
    
    def run(self):
        """
        Main execution: scrape, clean old data, insert new data.
        """
        print("=" * 60)
        print("AUTO DAILY SCRAPER - Pharmacy Duty (Gardes)")
        print("=" * 60)
        print(f"Execution Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Duty Period: Today 8:00 AM to Tomorrow 8:00 AM")
        print()
        
        # Step 1: Delete old gardes
        print("[Step 1] Cleaning old garde entries...")
        self.delete_old_gardes()
        
        # Step 2: Scrape all cities
        print("\n[Step 2] Scraping pharmacy duty from website...")
        all_scraped = []
        city_count = 0
        
        for region, cities in self.CITIES.items():
            for city in cities:
                city_count += 1
                pharmacies = self.scrape_city(region, city)
                if pharmacies:
                    print(f"    {city.title()}: {len(pharmacies)} pharmacies de garde")
                    all_scraped.extend(pharmacies)
                time.sleep(0.3)  # Be polite to the server
        
        print(f"\n  Total scraped: {len(all_scraped)} from {city_count} cities")
        
        # Step 3: Match with database
        print("\n[Step 3] Matching with database...")
        matched_entries = []  # dicts with pharmacie_id + scraped data
        unmatched_entries = []  # dicts with scraped data only
        seen_ids = set()  # Avoid duplicate pharmacie_ids
        
        for pharmacy in all_scraped:
            pharmacy_id = self.find_pharmacy_match(pharmacy['nom'], pharmacy['ville'])
            if pharmacy_id:
                if pharmacy_id not in seen_ids:  # Avoid duplicates
                    seen_ids.add(pharmacy_id)
                    matched_entries.append({
                        'pharmacie_id': pharmacy_id,
                        'nom': pharmacy['nom'],
                        'adresse': pharmacy.get('adresse', ''),
                        'ville': pharmacy.get('ville', '')
                    })
            else:
                unmatched_entries.append({
                    'nom': pharmacy['nom'],
                    'adresse': pharmacy.get('adresse', ''),
                    'ville': pharmacy.get('ville', '')
                })
        
        print(f"  Matched: {len(matched_entries)}")
        print(f"  Unmatched: {len(unmatched_entries)}")
        
        if unmatched_entries and len(unmatched_entries) <= 20:
            print("\n  Unmatched pharmacies (not in database):")
            for entry in unmatched_entries:
                print(f"    - {entry['nom']} ({entry['ville']})")
        
        # Step 3.5: Fix mislocated pharmacy GPS coordinates
        print("\n[Step 3.5] Fixing mislocated pharmacy coordinates...")
        fixed = self.fix_pharmacy_coordinates(matched_entries)
        print(f"  Fixed GPS for {fixed} pharmacies using city/quarter data")
        
        # Enrich unmatched entries with approximate coordinates
        enriched = 0
        for entry in unmatched_entries:
            coords = self.get_best_coordinates(entry.get('ville', ''), entry.get('adresse', ''))
            if coords:
                entry['latitude'] = coords[0]
                entry['longitude'] = coords[1]
                enriched += 1
        if enriched:
            print(f"  Enriched {enriched} unmatched pharmacies with approximate coordinates")
        
        # Step 4: Insert gardes
        print("\n[Step 4] Inserting today's gardes...")
        inserted = self.insert_gardes(matched_entries, unmatched_entries)
        print(f"  Inserted: {inserted} garde entries for {date.today()}")
        
        # Summary
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {self._table('gardes')} WHERE date_garde = %s", (date.today(),))
        total_today = cursor.fetchone()[0]
        cursor.close()
        
        print("\n" + "=" * 60)
        print(f"SUMMARY: {total_today} pharmacies on duty today")
        print("=" * 60)
        print(f"\nAPI endpoint now returns duty pharmacies:")
        print(f"  /api/pharmacies/nearby?lat=3.848&lon=11.502&radius=5000")
        
        return total_today


def main():
    scraper = AutoDailyScraper()
    scraper.run()


if __name__ == '__main__':
    main()
