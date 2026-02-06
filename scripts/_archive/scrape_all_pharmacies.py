"""
Comprehensive Pharmacy Scraper for annuaire-medical.cm
Scrapes ALL pharmacies from the website (not just those on duty).

This will help enrich our data by:
1. Getting pharmacy names with correct city associations
2. Getting phone numbers and addresses
3. Matching with OpenStreetMap data to fill missing info
"""
import requests
from bs4 import BeautifulSoup
import json
import time
import re
import os
import sys
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class PharmacyDirectoryScraper:
    """
    Scrapes pharmacy directory from annuaire-medical.cm
    """
    
    BASE_URL = "https://www.annuaire-medical.cm"
    
    # All cities organized by region (from the website structure)
    REGIONS_CITIES = {
        'adamaoua': {
            'name': 'Adamaoua',
            'cities': ['banyo', 'ngaoundere']
        },
        'centre': {
            'name': 'Centre',
            'cities': ['bafia', 'mbalmayo', 'mbandjock', 'mbankomo', 'obala', 'sa-a', 'yaounde']
        },
        'est': {
            'name': 'Est',
            'cities': ['abong-mbang', 'batouri', 'bertoua', 'garoua-boulai']
        },
        'extreme-nord': {
            'name': 'Extrême-Nord',
            'cities': ['kousseri', 'maga', 'maroua', 'yagoua']
        },
        'littoral': {
            'name': 'Littoral',
            'cities': ['douala', 'edea', 'loum', 'mbanga', 'melong', 'nkongsamba']
        },
        'nord': {
            'name': 'Nord',
            'cities': ['figuil', 'garoua', 'guider', 'touboro']
        },
        'nord-ouest': {
            'name': 'Nord-Ouest',
            'cities': ['bamenda', 'mbengwy']
        },
        'ouest': {
            'name': 'Ouest',
            'cities': ['bafang', 'bafoussam', 'bagangte', 'bandja', 'bandjoun', 'dschang', 'foumban', 'foumbot', 'mbouda']
        },
        'sud': {
            'name': 'Sud',
            'cities': ['ambam', 'ebolowa', 'kribi', 'sangmelima']
        },
        'sud-ouest': {
            'name': 'Sud-Ouest',
            'cities': ['buea', 'kumba', 'likomba', 'limbe', 'mutengene', 'muyuka']
        }
    }
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8'
        })
        self.all_pharmacies = []
        self.errors = []
    
    def get_city_garde_url(self, region: str, city: str) -> str:
        """Get URL for a city's garde page."""
        return f"{self.BASE_URL}/pharmacies-de-garde/{region}/pharmacies-de-garde-{city}"
    
    def fetch_page(self, url: str, retries: int = 3) -> str:
        """Fetch HTML content with retry logic."""
        for attempt in range(retries):
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                return response.text
            except requests.RequestException as e:
                print(f"  Attempt {attempt + 1} failed: {e}")
                if attempt < retries - 1:
                    time.sleep(2)
        return None
    
    def parse_pharmacy_text(self, text: str, city: str, region: str) -> dict:
        """
        Parse pharmacy info from text.
        Format: "PHARMACIE NAME PHONE CITY: ADDRESS"
        """
        if not text or len(text) < 5:
            return None
        
        text = text.strip()
        
        # Skip non-pharmacy text
        if not any(keyword in text.upper() for keyword in ['PHARMAC', 'PHARMA']):
            return None
        
        # Extract phone number (Cameroon format: 6XX XX XX XX or 2XX XX XX XX)
        phone_patterns = [
            r'(\+?237\s*)?([26]\d{2}\s*\d{2}\s*\d{2}\s*\d{2})',
            r'(\d{3}\s+\d{2}\s+\d{2}\s+\d{2})',
            r'(\d{9})',
        ]
        
        phone = ''
        phone_match = None
        for pattern in phone_patterns:
            phone_match = re.search(pattern, text)
            if phone_match:
                phone = phone_match.group(0).strip()
                break
        
        # Extract name (before phone number)
        if phone_match:
            name = text[:phone_match.start()].strip()
            remaining = text[phone_match.end():].strip()
        else:
            name = text
            remaining = ''
        
        # Clean up name
        name = re.sub(r'\s+', ' ', name).strip()
        
        # Extract address (after "City:" or just the remaining text)
        address = ''
        if ':' in remaining:
            parts = remaining.split(':', 1)
            if len(parts) > 1:
                address = parts[1].strip()
        else:
            address = remaining.strip()
        
        # Clean address
        address = re.sub(r'\s+', ' ', address).strip()
        
        if not name or len(name) < 3:
            return None
        
        return {
            'nom': name,
            'telephone': phone,
            'adresse': address,
            'ville': city.replace('-', ' ').title(),
            'region': region
        }
    
    def scrape_city_page(self, region_key: str, city: str) -> list:
        """
        Scrape all pharmacies from a city's page.
        The garde page contains ALL pharmacies in the city (in carousel).
        """
        region_name = self.REGIONS_CITIES[region_key]['name']
        url = self.get_city_garde_url(region_key, city)
        
        print(f"  Scraping {city.title()} ({region_name})...")
        
        html = self.fetch_page(url)
        if not html:
            self.errors.append(f"Failed to fetch: {city}")
            return []
        
        soup = BeautifulSoup(html, 'lxml')
        pharmacies = []
        
        # Method 1: Find carousel items
        carousel_items = soup.find_all('div', class_='carousel-item')
        
        for item in carousel_items:
            # Get text content, line by line
            text_content = item.get_text(separator='\n')
            lines = [line.strip() for line in text_content.split('\n') if line.strip()]
            
            for line in lines:
                pharmacy = self.parse_pharmacy_text(line, city, region_name)
                if pharmacy:
                    # Check for duplicates
                    if not any(p['nom'] == pharmacy['nom'] and p['ville'] == pharmacy['ville'] 
                              for p in pharmacies):
                        pharmacies.append(pharmacy)
        
        # Method 2: Try finding pharmacy listings in other formats
        if not pharmacies:
            # Look for any text containing pharmacy names
            all_text = soup.get_text()
            lines = all_text.split('\n')
            for line in lines:
                pharmacy = self.parse_pharmacy_text(line, city, region_name)
                if pharmacy:
                    if not any(p['nom'] == pharmacy['nom'] for p in pharmacies):
                        pharmacies.append(pharmacy)
        
        return pharmacies
    
    def scrape_all_pharmacies(self) -> list:
        """
        Scrape ALL pharmacies from ALL cities.
        """
        print("=" * 60)
        print("Comprehensive Pharmacy Scraper - annuaire-medical.cm")
        print("=" * 60)
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        total_cities = sum(len(r['cities']) for r in self.REGIONS_CITIES.values())
        print(f"Scraping {total_cities} cities across {len(self.REGIONS_CITIES)} regions...")
        print()
        
        for region_key, region_data in self.REGIONS_CITIES.items():
            region_name = region_data['name']
            cities = region_data['cities']
            
            print(f"\n{'='*40}")
            print(f"Region: {region_name} ({len(cities)} cities)")
            print('='*40)
            
            for city in cities:
                pharmacies = self.scrape_city_page(region_key, city)
                
                if pharmacies:
                    self.all_pharmacies.extend(pharmacies)
                    print(f"    Found {len(pharmacies)} pharmacies")
                else:
                    print(f"    No pharmacies found")
                
                # Be polite to the server
                time.sleep(1.5)
        
        print(f"\n{'='*60}")
        print(f"SCRAPING COMPLETE")
        print(f"{'='*60}")
        print(f"Total pharmacies found: {len(self.all_pharmacies)}")
        if self.errors:
            print(f"Errors: {len(self.errors)}")
            for err in self.errors:
                print(f"  - {err}")
        
        return self.all_pharmacies
    
    def save_to_json(self, output_path: str = None):
        """Save scraped data to JSON file."""
        if output_path is None:
            output_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'data'
            )
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, 'pharmacies_annuaire_medical.json')
        
        data = {
            'scraped_at': datetime.now().isoformat(),
            'source': 'annuaire-medical.cm',
            'total_count': len(self.all_pharmacies),
            'pharmacies': self.all_pharmacies
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"\nSaved to: {output_path}")
        return output_path
    
    def get_summary_by_city(self) -> dict:
        """Get pharmacy count by city."""
        summary = {}
        for p in self.all_pharmacies:
            city = p['ville']
            if city not in summary:
                summary[city] = 0
            summary[city] += 1
        return dict(sorted(summary.items(), key=lambda x: -x[1]))


def enrich_osm_data(osm_file: str, annuaire_file: str, output_file: str):
    """
    Enrich OpenStreetMap data with annuaire-medical.cm data.
    Matches pharmacies by name to add missing city information.
    """
    print("\n" + "="*60)
    print("Enriching OpenStreetMap data with website data...")
    print("="*60)
    
    # Load OSM data
    with open(osm_file, 'r', encoding='utf-8') as f:
        osm_data = json.load(f)
    
    # Load annuaire data
    with open(annuaire_file, 'r', encoding='utf-8') as f:
        annuaire_data = json.load(f)
    
    annuaire_pharmacies = annuaire_data.get('pharmacies', [])
    
    # Create lookup by normalized name
    annuaire_lookup = {}
    for p in annuaire_pharmacies:
        normalized_name = normalize_name(p['nom'])
        annuaire_lookup[normalized_name] = p
    
    # Match and enrich
    matched = 0
    for osm_p in osm_data:
        if not osm_p.get('city') or osm_p.get('city') == 'Inconnu':
            normalized_name = normalize_name(osm_p.get('name', ''))
            
            if normalized_name in annuaire_lookup:
                annuaire_p = annuaire_lookup[normalized_name]
                osm_p['city'] = annuaire_p['ville']
                osm_p['phone'] = osm_p.get('phone') or annuaire_p.get('telephone', '')
                osm_p['address'] = osm_p.get('address') or annuaire_p.get('adresse', '')
                osm_p['matched_from'] = 'annuaire-medical.cm'
                matched += 1
    
    # Save enriched data
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(osm_data, f, indent=2, ensure_ascii=False)
    
    print(f"Matched and enriched: {matched} pharmacies")
    print(f"Saved to: {output_file}")
    return matched


def normalize_name(name: str) -> str:
    """Normalize pharmacy name for matching."""
    if not name:
        return ''
    # Lowercase, remove special chars, normalize spaces
    name = name.lower()
    name = re.sub(r'[^\w\s]', '', name)
    name = re.sub(r'\s+', ' ', name)
    name = name.strip()
    # Remove common prefixes
    for prefix in ['pharmacie ', 'pharmacy ', 'pharma ']:
        if name.startswith(prefix):
            name = name[len(prefix):]
    return name


def main():
    """Main function to run the scraper."""
    print("\n" + "="*60)
    print("ANNUAIRE-MEDICAL.CM PHARMACY SCRAPER")
    print("="*60 + "\n")
    
    scraper = PharmacyDirectoryScraper()
    
    # Scrape all pharmacies
    pharmacies = scraper.scrape_all_pharmacies()
    
    if pharmacies:
        # Save to JSON
        json_path = scraper.save_to_json()
        
        # Print summary
        print("\n" + "-"*40)
        print("SUMMARY BY CITY:")
        print("-"*40)
        summary = scraper.get_summary_by_city()
        for city, count in list(summary.items())[:15]:
            print(f"  {city}: {count} pharmacies")
        if len(summary) > 15:
            print(f"  ... and {len(summary) - 15} more cities")
        
        # Sample pharmacies
        print("\n" + "-"*40)
        print("SAMPLE PHARMACIES:")
        print("-"*40)
        for p in pharmacies[:5]:
            print(f"  {p['nom']}")
            print(f"    City: {p['ville']} ({p['region']})")
            if p['telephone']:
                print(f"    Phone: {p['telephone']}")
            print()
    
    return pharmacies


if __name__ == '__main__':
    main()
