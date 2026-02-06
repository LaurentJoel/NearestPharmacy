"""
Import Pharmacies from Google Earth Pro KML File
Use this if you want to manually add pharmacy locations.

For automatic import of all pharmacies, use import_osm_pharmacies.py instead!
"""
import xml.etree.ElementTree as ET
import psycopg2
import re
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def parse_kml_file(kml_path: str) -> list:
    """
    Parse pharmacy locations from a KML file.
    
    Expected KML structure:
    - <Placemark> for each pharmacy
    - <name> = Pharmacy name
    - <description> = Address, phone (optional)
    - <Point><coordinates> = lon,lat,altitude
    
    Returns list of pharmacy dicts.
    """
    print(f"Parsing KML file: {kml_path}")
    
    # KML namespace
    ns = {'kml': 'http://www.opengis.net/kml/2.2'}
    
    try:
        tree = ET.parse(kml_path)
        root = tree.getroot()
    except Exception as e:
        print(f"Error parsing KML: {e}")
        return []
    
    pharmacies = []
    
    # Find all Placemarks
    for placemark in root.iter('{http://www.opengis.net/kml/2.2}Placemark'):
        # Get name
        name_elem = placemark.find('kml:name', ns) or placemark.find('{http://www.opengis.net/kml/2.2}name')
        name = name_elem.text if name_elem is not None else 'Unknown'
        
        # Get description (may contain address/phone)
        desc_elem = placemark.find('kml:description', ns) or placemark.find('{http://www.opengis.net/kml/2.2}description')
        description = desc_elem.text if desc_elem is not None else ''
        
        # Get coordinates
        coords_elem = placemark.find('.//kml:coordinates', ns) or placemark.find('.//{http://www.opengis.net/kml/2.2}coordinates')
        if coords_elem is None or not coords_elem.text:
            continue
        
        coords_text = coords_elem.text.strip()
        # Format: longitude,latitude,altitude
        parts = coords_text.split(',')
        if len(parts) < 2:
            continue
        
        try:
            longitude = float(parts[0])
            latitude = float(parts[1])
        except ValueError:
            continue
        
        # Parse address and phone from description
        address = ''
        phone = ''
        city = ''
        
        if description:
            # Look for patterns like "Address: xxx" or "Phone: xxx"
            addr_match = re.search(r'(?:Address|Adresse)\s*:\s*(.+)', description, re.I)
            if addr_match:
                address = addr_match.group(1).strip()
            
            phone_match = re.search(r'(?:Phone|Tel|Telephone)\s*:\s*(.+)', description, re.I)
            if phone_match:
                phone = phone_match.group(1).strip()
            
            city_match = re.search(r'(?:City|Ville)\s*:\s*(.+)', description, re.I)
            if city_match:
                city = city_match.group(1).strip()
        
        pharmacies.append({
            'nom': name,
            'adresse': address,
            'telephone': phone,
            'ville': city,
            'latitude': latitude,
            'longitude': longitude
        })
    
    print(f"Found {len(pharmacies)} pharmacies in KML file")
    return pharmacies


def import_to_database(pharmacies: list, db_config: dict):
    """Import pharmacies from KML into database."""
    if not pharmacies:
        print("No pharmacies to import")
        return
    
    print(f"\nImporting {len(pharmacies)} pharmacies to database...")
    
    try:
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        
        imported = 0
        
        for pharmacy in pharmacies:
            cursor.execute("""
                INSERT INTO pharmacies (nom, adresse, telephone, ville, geom, source)
                VALUES (%s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), 'google_earth')
                ON CONFLICT DO NOTHING
                RETURNING id;
            """, (
                pharmacy['nom'],
                pharmacy['adresse'],
                pharmacy['telephone'],
                pharmacy['ville'],
                pharmacy['longitude'],
                pharmacy['latitude']
            ))
            
            if cursor.fetchone():
                imported += 1
                print(f"  ✓ {pharmacy['nom']}")
        
        conn.commit()
        print(f"\nImport complete: {imported} pharmacies added")
        
    except Exception as e:
        print(f"Database error: {e}")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def main():
    """Main function."""
    print("=" * 50)
    print("Google Earth Pro KML Importer")
    print("=" * 50)
    print()
    
    # Default KML file path
    kml_path = os.path.join(
        os.path.dirname(__file__), 
        '..', 'data', 
        'pharmacies_cameroon.kml'
    )
    
    # Allow custom path via command line
    if len(sys.argv) > 1:
        kml_path = sys.argv[1]
    
    if not os.path.exists(kml_path):
        print(f"KML file not found: {kml_path}")
        print()
        print("HOW TO CREATE A KML FILE:")
        print("-" * 40)
        print("1. Open Google Earth Pro")
        print("2. Navigate to each pharmacy location")
        print("3. Add Placemark (Ctrl+Shift+P)")
        print("4. Name: 'Pharmacie XYZ'")
        print("5. Description: 'Address: ..., Phone: ..., City: ...'")
        print("6. Right-click folder > Save Place As > KML")
        print()
        print("Or use import_osm_pharmacies.py to automatically")
        print("fetch all pharmacies from OpenStreetMap!")
        return
    
    # Parse KML
    pharmacies = parse_kml_file(kml_path)
    
    if not pharmacies:
        return
    
    # Show sample
    print("\n--- Sample pharmacies ---")
    for p in pharmacies[:3]:
        print(f"  {p['nom']}: {p['latitude']:.4f}, {p['longitude']:.4f}")
    
    # Import to database
    if '--import' in sys.argv:
        db_config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': os.getenv('DB_PORT', '5432'),
            'database': os.getenv('DB_NAME', 'pharmacy_db'),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', 'postgres')
        }
        import_to_database(pharmacies, db_config)
    else:
        print("\nRun with --import flag to import to database")


if __name__ == '__main__':
    main()
