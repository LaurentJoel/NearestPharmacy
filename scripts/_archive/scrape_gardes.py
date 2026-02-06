"""
Web Scraper for Pharmacies de Garde - annuaire-medical.cm
Scrapes the daily duty schedule and updates the database.
"""
import requests
from bs4 import BeautifulSoup
from datetime import datetime, date
import re
import psycopg2
from psycopg2 import extras
import time
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class PharmacyGardeScraper:
    """
    Scrapes pharmacy duty schedules from annuaire-medical.cm
    """
    
    BASE_URL = "https://www.annuaire-medical.cm"
    GARDE_INDEX_URL = f"{BASE_URL}/fr/pharmacies-de-garde"
    
    # All cities organized by region
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
    
    def __init__(self, db_config=None):
        """
        Initialize scraper with optional database configuration.
        
        Args:
            db_config: Dict with host, port, database, user, password
        """
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        self.db_config = db_config
        self.session = requests.Session()
        self.session.headers.update(self.headers)
    
    def get_city_url(self, region: str, city: str) -> str:
        """Generate URL for a city's garde page."""
        return f"{self.BASE_URL}/pharmacies-de-garde/{region}/pharmacies-de-garde-{city}"
    
    def fetch_page(self, url: str) -> str:
        """Fetch HTML content from URL."""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"Error fetching {url}: {e}")
            return None
    
    def parse_garde_page(self, html: str, city: str) -> list:
        """
        Parse pharmacy garde information from a city page.
        
        Returns list of dicts with pharmacy info:
        [{'nom': str, 'telephone': str, 'adresse': str, 'ville': str}]
        """
        if not html:
            return []
        
        soup = BeautifulSoup(html, 'lxml')
        pharmacies = []
        
        # Find carousel items containing pharmacy info
        carousel_items = soup.find_all('div', class_='carousel-item')
        
        for item in carousel_items:
            # Get all text content
            text = item.get_text(separator='\n', strip=True)
            
            # Parse pharmacy entries (format: "PHARMACIE NAME PHONE CITY: ADDRESS")
            lines = text.split('\n')
            
            for line in lines:
                line = line.strip()
                if line.upper().startswith('PHARMACIE'):
                    pharmacy = self.parse_pharmacy_line(line, city)
                    if pharmacy:
                        pharmacies.append(pharmacy)
        
        return pharmacies
    
    def parse_pharmacy_line(self, line: str, city: str) -> dict:
        """
        Parse a single pharmacy line.
        
        Format examples:
        - "PHARMACIE PALAIS 691 54 16 18 Yaoundé: ETOUDI STATIONNEMENT"
        - "PHARMACIE DU CENTRE 222 23 45 67"
        """
        try:
            # Extract phone number (pattern: multiple digits with spaces)
            phone_pattern = r'(\d{3}\s*\d{2}\s*\d{2}\s*\d{2})'
            phone_match = re.search(phone_pattern, line)
            
            if phone_match:
                phone = phone_match.group(1).strip()
                phone_idx = line.find(phone)
                nom = line[:phone_idx].strip()
                remaining = line[phone_idx + len(phone):].strip()
                
                # Try to extract address (after "City:")
                if ':' in remaining:
                    adresse = remaining.split(':', 1)[1].strip()
                else:
                    adresse = remaining
            else:
                nom = line
                phone = ''
                adresse = ''
            
            return {
                'nom': nom,
                'telephone': phone,
                'adresse': adresse,
                'ville': city.title().replace('-', ' ')
            }
        except Exception as e:
            print(f"Error parsing line: {line} - {e}")
            return None
    
    def scrape_city(self, region: str, city: str) -> list:
        """Scrape garde pharmacies for a single city."""
        url = self.get_city_url(region, city)
        print(f"Scraping: {city.title()} ({region})")
        
        html = self.fetch_page(url)
        pharmacies = self.parse_garde_page(html, city)
        
        print(f"  Found {len(pharmacies)} pharmacies de garde")
        return pharmacies
    
    def scrape_all_cities(self) -> dict:
        """
        Scrape all cities in Cameroon.
        
        Returns dict: {city_name: [pharmacies]}
        """
        all_gardes = {}
        
        for region, cities in self.CITIES.items():
            print(f"\n=== Region: {region.upper()} ===")
            
            for city in cities:
                pharmacies = self.scrape_city(region, city)
                if pharmacies:
                    all_gardes[city] = pharmacies
                
                # Be polite to the server
                time.sleep(1)
        
        return all_gardes
    
    def save_to_database(self, gardes: dict, garde_date: date = None):
        """
        Save scraped garde data to database.
        
        Args:
            gardes: Dict from scrape_all_cities()
            garde_date: Date for the garde (default: today)
        """
        if not self.db_config:
            print("No database configuration provided")
            return
        
        if garde_date is None:
            garde_date = date.today()
        
        try:
            conn = psycopg2.connect(**self.db_config)
            cursor = conn.cursor()
            
            for city, pharmacies in gardes.items():
                for pharmacy in pharmacies:
                    # Find or create pharmacy
                    cursor.execute("""
                        SELECT id FROM pharmacies 
                        WHERE LOWER(nom) = LOWER(%s) AND LOWER(ville) = LOWER(%s)
                    """, (pharmacy['nom'], pharmacy['ville']))
                    
                    result = cursor.fetchone()
                    
                    if result:
                        pharmacie_id = result[0]
                    else:
                        # Pharmacy not in database - log it
                        print(f"  New pharmacy found: {pharmacy['nom']} ({pharmacy['ville']})")
                        continue
                    
                    # Insert garde (ignore duplicates)
                    cursor.execute("""
                        INSERT INTO gardes (pharmacie_id, date_garde)
                        VALUES (%s, %s)
                        ON CONFLICT (pharmacie_id, date_garde) DO NOTHING
                    """, (pharmacie_id, garde_date))
            
            conn.commit()
            print(f"\nGarde data saved for {garde_date}")
            
        except Exception as e:
            print(f"Database error: {e}")
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()


def main():
    """Main function to run the scraper."""
    print("=" * 50)
    print("Pharmacies de Garde Scraper - Cameroon")
    print("=" * 50)
    print(f"Date: {date.today()}")
    print()
    
    # Initialize scraper
    scraper = PharmacyGardeScraper()
    
    # Scrape just Yaoundé for testing
    print("Testing with Yaoundé...")
    pharmacies = scraper.scrape_city('centre', 'yaounde')
    
    print("\nPharmacies de garde trouvées:")
    for p in pharmacies[:5]:  # Show first 5
        print(f"  - {p['nom']}")
        print(f"    Tel: {p['telephone']}")
        print(f"    Adresse: {p['adresse']}")
        print()
    
    # To scrape all cities:
    # all_gardes = scraper.scrape_all_cities()
    # print(f"\nTotal cities scraped: {len(all_gardes)}")


if __name__ == '__main__':
    main()
