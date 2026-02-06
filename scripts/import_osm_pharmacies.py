"""
Import Pharmacies from OpenStreetMap using Overpass API
This script fetches all pharmacies in Cameroon from OpenStreetMap and imports them into the database.

OpenStreetMap is a FREE source for pharmacy locations with GPS coordinates!
This is much faster than manually adding pharmacies in Google Earth Pro.
"""
import requests
import json
import psycopg2
import time
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Overpass API endpoint
OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def fetch_cameroon_pharmacies() -> list:
    """
    Fetch all pharmacies in Cameroon from OpenStreetMap via Overpass API.
    
    Returns list of pharmacies with lat, lon, name, and other tags.
    """
    print("Fetching pharmacies from OpenStreetMap...")
    print("This may take a minute...")
    
    # Overpass QL query to get all pharmacies in Cameroon
    # This finds all nodes/ways/relations tagged as amenity=pharmacy
    query = """
    [out:json][timeout:120];
    // Define Cameroon as the search area
    area["ISO3166-1"="CM"][admin_level=2]->.cameroon;
    
    // Find all pharmacies in Cameroon
    (
      node["amenity"="pharmacy"](area.cameroon);
      way["amenity"="pharmacy"](area.cameroon);
      relation["amenity"="pharmacy"](area.cameroon);
    );
    
    // Output with center coordinates for ways/relations
    out center;
    """
    
    try:
        response = requests.post(
            OVERPASS_URL,
            data={'data': query},
            timeout=180
        )
        response.raise_for_status()
        
        data = response.json()
        elements = data.get('elements', [])
        
        print(f"Found {len(elements)} pharmacies in OpenStreetMap!")
        return elements
        
    except requests.RequestException as e:
        print(f"Error fetching from Overpass API: {e}")
        return []


def parse_osm_pharmacy(element: dict) -> dict:
    """
    Parse an OSM element into a pharmacy dict.
    
    Args:
        element: OSM element from Overpass response
    
    Returns:
        Dict with nom, adresse, telephone, ville, latitude, longitude
    """
    tags = element.get('tags', {})
    
    # Get coordinates (different for nodes vs ways/relations)
    if element['type'] == 'node':
        lat = element.get('lat')
        lon = element.get('lon')
    else:
        # Ways and relations have center coordinates
        center = element.get('center', {})
        lat = center.get('lat')
        lon = center.get('lon')
    
    if not lat or not lon:
        return None
    
    # Extract pharmacy info from OSM tags
    pharmacy = {
        'nom': tags.get('name', 'Pharmacie (sans nom)'),
        'adresse': tags.get('addr:street', '') or tags.get('address', ''),
        'telephone': tags.get('phone', '') or tags.get('contact:phone', ''),
        'ville': tags.get('addr:city', '') or tags.get('addr:town', ''),
        'region': tags.get('addr:state', ''),
        'latitude': lat,
        'longitude': lon,
        'osm_id': element.get('id'),
        'osm_type': element.get('type')
    }
    
    return pharmacy


def import_to_database(pharmacies: list, db_config: dict):
    """
    Import pharmacies into PostgreSQL database.
    
    Args:
        pharmacies: List of pharmacy dicts
        db_config: Database connection config
    """
    if not pharmacies:
        print("No pharmacies to import")
        return
    
    print(f"\nImporting {len(pharmacies)} pharmacies to database...")
    
    try:
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        
        imported = 0
        skipped = 0
        
        for pharmacy in pharmacies:
            if not pharmacy:
                continue
            
            try:
                # Insert pharmacy (update if exists based on OSM ID)
                cursor.execute("""
                    INSERT INTO pharmacies (nom, adresse, telephone, ville, region, geom, source)
                    VALUES (%s, %s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), 'osm')
                    ON CONFLICT DO NOTHING
                    RETURNING id;
                """, (
                    pharmacy['nom'],
                    pharmacy['adresse'],
                    pharmacy['telephone'],
                    pharmacy['ville'],
                    pharmacy['region'],
                    pharmacy['longitude'],
                    pharmacy['latitude']
                ))
                
                if cursor.fetchone():
                    imported += 1
                else:
                    skipped += 1
                    
            except Exception as e:
                print(f"  Error importing {pharmacy['nom']}: {e}")
                skipped += 1
        
        conn.commit()
        print(f"Import complete: {imported} added, {skipped} skipped")
        
    except Exception as e:
        print(f"Database error: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def save_to_json(pharmacies: list, filename: str = 'osm_pharmacies_cameroon.json'):
    """Save pharmacies to JSON file for backup/review."""
    filepath = os.path.join(os.path.dirname(__file__), '..', 'data', filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    parsed = [parse_osm_pharmacy(p) for p in pharmacies if parse_osm_pharmacy(p)]
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(parsed, f, indent=2, ensure_ascii=False)
    
    print(f"Saved {len(parsed)} pharmacies to {filepath}")


def main():
    """Main function to fetch and import OSM pharmacies."""
    print("=" * 60)
    print("OpenStreetMap Pharmacy Importer - Cameroon")
    print("=" * 60)
    print()
    print("This script fetches ALL pharmacies in Cameroon from")
    print("OpenStreetMap (FREE!) and imports them into the database.")
    print()
    print("This is MUCH faster than manually adding pharmacies")
    print("in Google Earth Pro one by one!")
    print()
    print("-" * 60)
    
    # Fetch from OSM
    osm_elements = fetch_cameroon_pharmacies()
    
    if not osm_elements:
        print("No pharmacies found or error occurred")
        return
    
    # Parse elements
    pharmacies = []
    for element in osm_elements:
        parsed = parse_osm_pharmacy(element)
        if parsed:
            pharmacies.append(parsed)
    
    print(f"\nParsed {len(pharmacies)} pharmacies with valid coordinates")
    
    # Save to JSON for backup
    save_to_json(osm_elements)
    
    # Show sample
    print("\n--- Sample pharmacies found ---")
    for p in pharmacies[:5]:
        print(f"  {p['nom']}")
        print(f"    Location: {p['latitude']:.4f}, {p['longitude']:.4f}")
        if p['ville']:
            print(f"    City: {p['ville']}")
        print()
    
    # Ask user if they want to import to database
    print("\nTo import to database, run with --import flag and provide DB config:")
    print("  python import_osm_pharmacies.py --import")
    
    if '--import' in sys.argv:
        # Default database config (update as needed)
        db_config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': os.getenv('DB_PORT', '5432'),
            'database': os.getenv('DB_NAME', 'pharmacy_db'),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', 'postgres')
        }
        import_to_database(pharmacies, db_config)


if __name__ == '__main__':
    main()
