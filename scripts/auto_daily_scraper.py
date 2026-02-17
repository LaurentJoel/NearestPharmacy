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
        cursor.execute(f"SELECT id, nom, ville FROM {self._table('pharmacies')}")
        rows = cursor.fetchall()
        cursor.close()
        
        self._pharmacy_cache = []
        for row in rows:
            self._pharmacy_cache.append({
                'id': row[0],
                'nom': row[1],
                'ville': row[2],
                'normalized': normalize_name(row[1]),
                'key_words': get_key_words(row[1])
            })
        
        print(f"  Loaded {len(self._pharmacy_cache)} pharmacies from database")
    
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
        
        # Find carousel items (each contains pharmacie info)
        carousel_items = soup.find_all('div', class_='carousel-item')
        
        for item in carousel_items:
            text = item.get_text(separator='\n', strip=True)
            lines = text.split('\n')
            
            for line in lines:
                line = line.strip()
                # Skip non-pharmacy lines
                if not line.upper().startswith('PHARMACIE') and not line.upper().startswith('PHARMACY'):
                    continue
                
                pharmacy = self.parse_pharmacy_line(line, city)
                if pharmacy:
                    pharmacies.append(pharmacy)
        
        return pharmacies
    
    def parse_pharmacy_line(self, line, city):
        """Parse a pharmacy line from the website."""
        try:
            # Extract phone number (pattern: XXX XX XX XX)
            phone_pattern = r'(\d{3}\s*\d{2}\s*\d{2}\s*\d{2})'
            phone_match = re.search(phone_pattern, line)
            
            if phone_match:
                phone = phone_match.group(1).strip()
                phone_idx = line.find(phone)
                nom = line[:phone_idx].strip()
                remaining = line[phone_idx + len(phone):].strip()
                
                # Extract address (after "City:")
                if ':' in remaining:
                    adresse = remaining.split(':', 1)[1].strip()
                else:
                    adresse = remaining
            else:
                nom = line.split(':')[0].strip() if ':' in line else line.strip()
                phone = ''
                adresse = ''
            
            # Clean name
            nom = re.sub(r'\s+', ' ', nom).strip()
            
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
    
    def insert_gardes(self, matched_pharmacies, garde_date=None):
        """Insert matched pharmacies into gardes table."""
        if garde_date is None:
            garde_date = date.today()
        
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        inserted = 0
        for pharmacy_id in matched_pharmacies:
            cursor.execute(f"""
                INSERT INTO {self._table('gardes')} (pharmacie_id, date_garde)
                VALUES (%s, %s)
                ON CONFLICT (pharmacie_id, date_garde) DO NOTHING
            """, (pharmacy_id, garde_date))
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
        matched_ids = []
        unmatched = []
        
        for pharmacy in all_scraped:
            pharmacy_id = self.find_pharmacy_match(pharmacy['nom'], pharmacy['ville'])
            if pharmacy_id:
                if pharmacy_id not in matched_ids:  # Avoid duplicates
                    matched_ids.append(pharmacy_id)
            else:
                unmatched.append(f"{pharmacy['nom']} ({pharmacy['ville']})")
        
        print(f"  Matched: {len(matched_ids)}")
        print(f"  Unmatched: {len(unmatched)}")
        
        if unmatched and len(unmatched) <= 20:
            print("\n  Unmatched pharmacies (not in database):")
            for name in unmatched:
                print(f"    - {name}")
        
        # Step 4: Insert gardes
        print("\n[Step 4] Inserting today's gardes...")
        inserted = self.insert_gardes(matched_ids)
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
