"""
Import Pharmacies from KMZ/KML files (Google Earth Pro Export)
KMZ files are zipped KML files - this script handles both formats.

Usage:
    python import_kmz.py path/to/file.kmz --import
    python import_kmz.py path/to/file.kml --import
"""
import xml.etree.ElementTree as ET
import zipfile
import psycopg2
import re
import sys
import os
import json
import tempfile

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def extract_kmz(kmz_path: str) -> str:
    """
    Extract KML content from a KMZ file.
    KMZ is just a zipped KML file.
    
    Returns the path to the extracted KML file.
    """
    print(f"Extracting KMZ file: {kmz_path}")
    
    # Create temp directory for extraction
    temp_dir = tempfile.mkdtemp()
    
    try:
        with zipfile.ZipFile(kmz_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        # Find the KML file inside
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                if file.endswith('.kml'):
                    kml_path = os.path.join(root, file)
                    print(f"Found KML: {kml_path}")
                    return kml_path
        
        raise FileNotFoundError("No KML file found in KMZ archive")
        
    except zipfile.BadZipFile:
        raise ValueError("Invalid KMZ file (not a valid zip archive)")


def parse_kml_content(kml_path: str) -> list:
    """
    Parse pharmacy locations from a KML file.
    
    Expected structure:
    - <Placemark> for each pharmacy
    - <name> = Pharmacy name
    - <description> = Address, phone (optional)
    - <Point><coordinates> = lon,lat,altitude
    
    Returns list of pharmacy dicts.
    """
    print(f"Parsing KML file: {kml_path}")
    
    # KML namespace
    namespaces = {
        'kml': 'http://www.opengis.net/kml/2.2',
        'kml21': 'http://earth.google.com/kml/2.1',
        'kml20': 'http://earth.google.com/kml/2.0'
    }
    
    try:
        tree = ET.parse(kml_path)
        root = tree.getroot()
    except Exception as e:
        print(f"Error parsing KML: {e}")
        return []
    
    pharmacies = []
    
    # Try to find placemarks with different namespace patterns
    placemarks = []
    
    # Try standard KML 2.2 namespace
    placemarks = root.findall('.//{http://www.opengis.net/kml/2.2}Placemark')
    
    # Try Google Earth namespace
    if not placemarks:
        placemarks = root.findall('.//{http://earth.google.com/kml/2.1}Placemark')
    
    # Try without namespace
    if not placemarks:
        placemarks = root.findall('.//Placemark')
    
    print(f"Found {len(placemarks)} placemarks")
    
    for placemark in placemarks:
        pharmacy = extract_placemark_data(placemark)
        if pharmacy:
            pharmacies.append(pharmacy)
    
    print(f"Parsed {len(pharmacies)} valid pharmacies")
    return pharmacies


def extract_placemark_data(placemark) -> dict:
    """Extract pharmacy data from a single placemark element."""
    
    # Helper to find element with or without namespace
    def find_element(parent, tag):
        # Try with namespace
        elem = parent.find(f'{{http://www.opengis.net/kml/2.2}}{tag}')
        if elem is None:
            elem = parent.find(f'{{http://earth.google.com/kml/2.1}}{tag}')
        if elem is None:
            elem = parent.find(tag)
        return elem
    
    # Get name
    name_elem = find_element(placemark, 'name')
    name = name_elem.text.strip() if name_elem is not None and name_elem.text else 'Unknown'
    
    # Skip if name doesn't look like a pharmacy
    # (optional - remove this check if your KML only contains pharmacies)
    # if 'pharmac' not in name.lower() and 'pharma' not in name.lower():
    #     return None
    
    # Get description
    desc_elem = find_element(placemark, 'description')
    description = desc_elem.text.strip() if desc_elem is not None and desc_elem.text else ''
    
    # Get coordinates - need to search recursively
    coords_elem = None
    for elem in placemark.iter():
        if 'coordinates' in elem.tag.lower():
            coords_elem = elem
            break
    
    if coords_elem is None or not coords_elem.text:
        return None
    
    coords_text = coords_elem.text.strip()
    
    # Handle both single point and path coordinates
    # Format: longitude,latitude,altitude (first point if multiple)
    first_coord = coords_text.split()[0] if ' ' in coords_text else coords_text
    parts = first_coord.split(',')
    
    if len(parts) < 2:
        return None
    
    try:
        longitude = float(parts[0])
        latitude = float(parts[1])
    except ValueError:
        return None
    
    # Validate coordinates are in Cameroon region
    # Cameroon bounds: roughly lat 1.5-13, lon 8.5-16.5
    if not (1.5 <= latitude <= 14 and 8 <= longitude <= 17):
        print(f"  Warning: {name} outside Cameroon bounds ({latitude}, {longitude})")
    
    # Parse address and phone from description
    address = ''
    phone = ''
    city = ''
    
    if description:
        # Clean HTML if present
        description = re.sub(r'<[^>]+>', ' ', description)
        description = description.strip()
        
        # Look for patterns
        addr_match = re.search(r'(?:Address|Adresse)\s*:\s*([^\n]+)', description, re.I)
        if addr_match:
            address = addr_match.group(1).strip()
        
        phone_match = re.search(r'(?:Phone|Tel|Téléphone)\s*:\s*([^\n]+)', description, re.I)
        if phone_match:
            phone = phone_match.group(1).strip()
        
        city_match = re.search(r'(?:City|Ville)\s*:\s*([^\n]+)', description, re.I)
        if city_match:
            city = city_match.group(1).strip()
        
        # If no structured data, use description as address
        if not address and len(description) < 200:
            address = description
    
    return {
        'nom': name,
        'adresse': address,
        'telephone': phone,
        'ville': city,
        'latitude': latitude,
        'longitude': longitude
    }


def save_to_json(pharmacies: list, output_path: str):
    """Save pharmacies to JSON file for review."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(pharmacies, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(pharmacies)} pharmacies to {output_path}")


def import_to_database(pharmacies: list, db_config: dict):
    """Import pharmacies into PostgreSQL/PostGIS database."""
    if not pharmacies:
        print("No pharmacies to import")
        return
    
    print(f"\nImporting {len(pharmacies)} pharmacies to database...")
    
    try:
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        
        imported = 0
        updated = 0
        
        for pharmacy in pharmacies:
            # Check if pharmacy already exists (by name and approximate location)
            cursor.execute("""
                SELECT id FROM pharmacies 
                WHERE LOWER(nom) = LOWER(%s)
                AND ST_DWithin(
                    geom::geography, 
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                    100  -- within 100 meters
                )
            """, (pharmacy['nom'], pharmacy['longitude'], pharmacy['latitude']))
            
            existing = cursor.fetchone()
            
            if existing:
                # Update existing pharmacy
                cursor.execute("""
                    UPDATE pharmacies 
                    SET adresse = COALESCE(NULLIF(%s, ''), adresse),
                        telephone = COALESCE(NULLIF(%s, ''), telephone),
                        ville = COALESCE(NULLIF(%s, ''), ville),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (
                    pharmacy['adresse'],
                    pharmacy['telephone'],
                    pharmacy['ville'],
                    existing[0]
                ))
                updated += 1
                print(f"  ↻ Updated: {pharmacy['nom']}")
            else:
                # Insert new pharmacy
                cursor.execute("""
                    INSERT INTO pharmacies (nom, adresse, telephone, ville, geom, source)
                    VALUES (%s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), 'google_earth')
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
                    print(f"  ✓ Added: {pharmacy['nom']}")
        
        conn.commit()
        print(f"\n{'='*50}")
        print(f"Import complete!")
        print(f"  New pharmacies: {imported}")
        print(f"  Updated: {updated}")
        print(f"  Total in file: {len(pharmacies)}")
        
    except Exception as e:
        print(f"Database error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def main():
    """Main function to import KMZ/KML file."""
    print("=" * 60)
    print("Google Earth Pro KMZ/KML Importer")
    print("=" * 60)
    print()
    
    # Get file path from command line
    if len(sys.argv) < 2:
        print("Usage: python import_kmz.py <file.kmz|file.kml> [--import]")
        print()
        print("Examples:")
        print("  python import_kmz.py pharmacies.kmz           # Preview only")
        print("  python import_kmz.py pharmacies.kmz --import  # Import to DB")
        print("  python import_kmz.py pharmacies.kml --import  # KML file")
        return
    
    file_path = sys.argv[1]
    
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return
    
    # Determine file type and get KML path
    if file_path.lower().endswith('.kmz'):
        kml_path = extract_kmz(file_path)
    elif file_path.lower().endswith('.kml'):
        kml_path = file_path
    else:
        print("Error: File must be .kmz or .kml")
        return
    
    # Parse pharmacies
    pharmacies = parse_kml_content(kml_path)
    
    if not pharmacies:
        print("No pharmacies found in file")
        return
    
    # Save to JSON for review
    json_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'data',
        'imported_pharmacies.json'
    )
    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    save_to_json(pharmacies, json_path)
    
    # Show sample
    print("\n--- Sample pharmacies ---")
    for p in pharmacies[:5]:
        print(f"  {p['nom']}")
        print(f"    Coords: {p['latitude']:.6f}, {p['longitude']:.6f}")
        if p['adresse']:
            print(f"    Address: {p['adresse'][:50]}...")
        print()
    
    # Import to database if requested
    if '--import' in sys.argv:
        print("\nImporting to database...")
        db_config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': os.getenv('DB_PORT', '5432'),
            'database': os.getenv('DB_NAME', 'pharmacy_db'),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', 'postgres')
        }
        import_to_database(pharmacies, db_config)
    else:
        print("\nTo import to database, run with --import flag:")
        print(f"  python import_kmz.py {file_path} --import")


if __name__ == '__main__':
    main()
