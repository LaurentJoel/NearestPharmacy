"""
Daily Pharmacy Duty Scraper - Scrapes website and updates database
Matches scraped pharmacies with database using fuzzy matching
"""
import requests
from bs4 import BeautifulSoup
from datetime import datetime, date
import re
import psycopg2
import os
import time
from dotenv import load_dotenv

load_dotenv()


class DailyGardeScraper:
    """Scrapes daily pharmacy duty info and updates database."""
    
    BASE_URL = "https://www.annuaire-medical.cm"
    
    # City URLs to scrape
    CITIES = {
        'centre': ['yaounde'],
        'littoral': ['douala'],
        'nord-ouest': ['bamenda'],
        'ouest': ['bafoussam', 'dschang'],
        'nord': ['garoua'],
        'extreme-nord': ['maroua'],
        'adamaoua': ['ngaoundere'],
        'est': ['bertoua'],
        'sud': ['ebolowa'],
        'sud-ouest': ['buea', 'limbe', 'kumba'],
    }
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.db_conn = None
        
    def get_db_connection(self):
        """Get database connection."""
        if not self.db_conn or self.db_conn.closed:
            self.db_conn = psycopg2.connect(
                host=os.getenv('DB_HOST', 'localhost'),
                port=os.getenv('DB_PORT', '5432'),
                dbname=os.getenv('DB_NAME', 'pharmacy_db'),
                user=os.getenv('DB_USER', 'postgres'),
                password=os.getenv('DB_PASSWORD', 'postgres')
            )
        return self.db_conn
    
    def normalize_name(self, name):
        """Normalize pharmacy name for matching."""
        if not name:
            return ''
        name = name.lower()
        name = re.sub(r'[^\w\s]', '', name)
        name = re.sub(r'\s+', ' ', name).strip()
        # Remove common prefixes
        for prefix in ['pharmacie ', 'pharmacy ', 'pharma ']:
            if name.startswith(prefix):
                name = name[len(prefix):]
        return name.strip()
    
    def get_city_url(self, region, city):
        """Generate URL for city garde page."""
        return f"{self.BASE_URL}/pharmacies-de-garde/{region}/pharmacies-de-garde-{city}"
    
    def scrape_city(self, region, city):
        """Scrape garde pharmacies for a city."""
        url = self.get_city_url(region, city)
        print(f"  Scraping {city.title()}...")
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            html = response.text
        except Exception as e:
            print(f"    Error: {e}")
            return []
        
        soup = BeautifulSoup(html, 'lxml')
        pharmacies = []
        
        # Find carousel items
        carousel_items = soup.find_all('div', class_='carousel-item')
        
        for item in carousel_items:
            text = item.get_text(separator='\n', strip=True)
            lines = text.split('\n')
            
            for line in lines:
                line = line.strip()
                if line.upper().startswith('PHARMACIE') or line.upper().startswith('PHARMACY'):
                    pharmacy = self.parse_pharmacy_line(line, city)
                    if pharmacy:
                        pharmacies.append(pharmacy)
        
        print(f"    Found {len(pharmacies)} pharmacies de garde")
        return pharmacies
    
    def parse_pharmacy_line(self, line, city):
        """Parse a pharmacy line from the website."""
        try:
            # Extract phone number
            phone_pattern = r'(\d{3}\s*\d{2}\s*\d{2}\s*\d{2})'
            phone_match = re.search(phone_pattern, line)
            
            if phone_match:
                phone = phone_match.group(1).strip()
                phone_idx = line.find(phone)
                nom = line[:phone_idx].strip()
            else:
                nom = line.split(':')[0].strip() if ':' in line else line
                phone = ''
            
            # Clean name
            nom = re.sub(r'\s+', ' ', nom).strip()
            
            return {
                'nom': nom,
                'telephone': phone,
                'ville': city.title().replace('-', ' ')
            }
        except Exception as e:
            print(f"    Parse error: {e}")
            return None
    
    def find_pharmacy_in_db(self, pharmacy_name, city_name):
        """
        Find pharmacy in database using fuzzy matching.
        Returns pharmacy_id or None.
        """
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        normalized_name = self.normalize_name(pharmacy_name)
        
        # Try exact match first
        cursor.execute("""
            SELECT id, nom, ville FROM pharmacies 
            WHERE LOWER(nom) LIKE %s AND LOWER(ville) = LOWER(%s)
            LIMIT 1
        """, (f'%{normalized_name}%', city_name))
        
        result = cursor.fetchone()
        if result:
            cursor.close()
            return result[0]
        
        # Try fuzzy match (name contains key words)
        words = normalized_name.split()
        if len(words) >= 2:
            # Take last 2 significant words
            key_words = [w for w in words if len(w) > 2][-2:]
            if key_words:
                pattern = '%' + '%'.join(key_words) + '%'
                cursor.execute("""
                    SELECT id, nom, ville FROM pharmacies 
                    WHERE LOWER(nom) LIKE LOWER(%s) AND LOWER(ville) = LOWER(%s)
                    LIMIT 1
                """, (pattern, city_name))
                
                result = cursor.fetchone()
                if result:
                    cursor.close()
                    return result[0]
        
        # Try without city restriction for partial match
        cursor.execute("""
            SELECT id, nom, ville FROM pharmacies 
            WHERE LOWER(nom) LIKE %s
            LIMIT 1
        """, (f'%{normalized_name}%',))
        
        result = cursor.fetchone()
        cursor.close()
        
        return result[0] if result else None
    
    def update_gardes(self, pharmacies, garde_date=None):
        """Update gardes table with today's duty pharmacies."""
        if garde_date is None:
            garde_date = date.today()
        
        conn = self.get_db_connection()
        cursor = conn.cursor()
        
        matched = 0
        unmatched = []
        
        for pharmacy in pharmacies:
            pharmacy_id = self.find_pharmacy_in_db(pharmacy['nom'], pharmacy['ville'])
            
            if pharmacy_id:
                # Insert garde entry
                cursor.execute("""
                    INSERT INTO gardes (pharmacie_id, date_garde)
                    VALUES (%s, %s)
                    ON CONFLICT (pharmacie_id, date_garde) DO NOTHING
                """, (pharmacy_id, garde_date))
                matched += 1
            else:
                unmatched.append(pharmacy['nom'])
        
        conn.commit()
        cursor.close()
        
        return matched, unmatched
    
    def scrape_and_update(self):
        """Main function: scrape all cities and update database."""
        print("=" * 60)
        print("DAILY PHARMACY DUTY SCRAPER")
        print("=" * 60)
        print(f"Date: {date.today()}")
        print()
        
        all_pharmacies = []
        
        for region, cities in self.CITIES.items():
            print(f"\nRegion: {region.upper()}")
            
            for city in cities:
                pharmacies = self.scrape_city(region, city)
                all_pharmacies.extend(pharmacies)
                time.sleep(0.5)  # Be polite
        
        print(f"\n{'='*60}")
        print(f"Total pharmacies scraped: {len(all_pharmacies)}")
        
        # Update database
        print("\nUpdating database...")
        matched, unmatched = self.update_gardes(all_pharmacies)
        
        print(f"  Matched & inserted: {matched}")
        print(f"  Unmatched: {len(unmatched)}")
        
        if unmatched:
            print("\n  Unmatched pharmacies (not in database):")
            for name in unmatched[:10]:
                print(f"    - {name}")
            if len(unmatched) > 10:
                print(f"    ... and {len(unmatched) - 10} more")
        
        # Get count of today's gardes
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM gardes WHERE date_garde = %s", (date.today(),))
        today_count = cursor.fetchone()[0]
        cursor.close()
        
        print(f"\n{'='*60}")
        print(f"TOTAL PHARMACIES ON DUTY TODAY: {today_count}")
        print("=" * 60)
        
        return matched, unmatched


def main():
    scraper = DailyGardeScraper()
    scraper.scrape_and_update()


if __name__ == '__main__':
    main()
