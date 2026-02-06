"""
Import Pharmacies from KML/JSON to PostgreSQL/PostGIS Database
Loads all pharmacy data we've collected into the database.
"""
import psycopg2
import json
import os
import re
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()


def get_db_connection():
    """Get database connection from environment variables."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=os.getenv('DB_PORT', '5432'),
        dbname=os.getenv('DB_NAME', 'pharmacy_db'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', 'postgres')
    )


def load_from_json(json_file):
    """Load pharmacies from JSON file."""
    print(f"Loading from: {json_file}")
    
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    pharmacies = data.get('pharmacies', [])
    print(f"  Found {len(pharmacies)} pharmacies")
    return pharmacies


def load_from_kml(kml_file):
    """Load pharmacies from KML file."""
    print(f"Loading from: {kml_file}")
    
    with open(kml_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    pharmacies = []
    
    placemark_pattern = r'<Placemark>(.*?)</Placemark>'
    name_pattern = r'<name>(.*?)</name>'
    coords_pattern = r'<coordinates>(.*?)</coordinates>'
    desc_pattern = r'<description>(.*?)</description>'
    
    for match in re.finditer(placemark_pattern, content, re.DOTALL):
        pm_content = match.group(1)
        
        name_match = re.search(name_pattern, pm_content)
        coords_match = re.search(coords_pattern, pm_content)
        desc_match = re.search(desc_pattern, pm_content)
        
        if not coords_match:
            continue
        
        coords = coords_match.group(1).strip().split(',')
        if len(coords) < 2:
            continue
        
        try:
            lon = float(coords[0])
            lat = float(coords[1])
        except:
            continue
        
        name = name_match.group(1) if name_match else 'Unknown'
        desc = desc_match.group(1) if desc_match else ''
        
        # Parse fields from description
        city = 'Inconnu'
        city_match = re.search(r'Ville:\s*([^\n<]+)', desc)
        if city_match:
            city = city_match.group(1).strip()
        
        source = 'imported'
        source_match = re.search(r'Source:\s*([^\n<]+)', desc)
        if source_match:
            source = source_match.group(1).strip()
        
        phone = ''
        phone_match = re.search(r'Tel:\s*([^\n<]+)', desc)
        if phone_match:
            phone = phone_match.group(1).strip()
        
        address = ''
        addr_match = re.search(r'(?:Address|Adresse):\s*([^\n<]+)', desc)
        if addr_match:
            address = addr_match.group(1).strip()
        
        pharmacies.append({
            'nom': name,
            'lat': lat,
            'lon': lon,
            'ville': city,
            'telephone': phone,
            'adresse': address,
            'source': source
        })
    
    print(f"  Found {len(pharmacies)} pharmacies")
    return pharmacies


def import_to_database(pharmacies, clear_existing=False):
    """Import pharmacies to PostgreSQL database."""
    print("\nConnecting to database...")
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        print("  Connected!")
        
        # Optionally clear existing data
        if clear_existing:
            print("  Clearing existing pharmacies...")
            cur.execute("DELETE FROM gardes")
            cur.execute("DELETE FROM pharmacies")
            conn.commit()
        
        # Insert pharmacies
        print(f"  Importing {len(pharmacies)} pharmacies...")
        
        insert_sql = """
            INSERT INTO pharmacies (nom, adresse, telephone, ville, geom, source)
            VALUES (%s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s)
            ON CONFLICT DO NOTHING
        """
        
        inserted = 0
        skipped = 0
        
        for p in pharmacies:
            try:
                cur.execute(insert_sql, (
                    p['nom'][:255],
                    (p.get('adresse', '') or '')[:255],
                    (p.get('telephone', '') or '')[:50],
                    (p.get('ville', 'Inconnu') or 'Inconnu')[:100],
                    p['lon'],
                    p['lat'],
                    (p.get('source', 'imported') or 'imported')[:50]
                ))
                if cur.rowcount > 0:
                    inserted += 1
                else:
                    skipped += 1
            except Exception as e:
                print(f"    Error inserting {p['nom']}: {e}")
                skipped += 1
        
        conn.commit()
        
        print(f"\n  Inserted: {inserted}")
        print(f"  Skipped: {skipped}")
        
        # Get total count
        cur.execute("SELECT COUNT(*) FROM pharmacies")
        total = cur.fetchone()[0]
        print(f"  Total in database: {total}")
        
        # Get counts by city
        cur.execute("""
            SELECT ville, COUNT(*) 
            FROM pharmacies 
            GROUP BY ville 
            ORDER BY COUNT(*) DESC 
            LIMIT 15
        """)
        print("\n  Top cities:")
        for row in cur.fetchall():
            print(f"    {row[0]}: {row[1]}")
        
        cur.close()
        conn.close()
        
        return True
        
    except psycopg2.OperationalError as e:
        print(f"\n  ERROR: Cannot connect to database!")
        print(f"  {e}")
        print("\n  Make sure PostgreSQL is running and configured correctly.")
        print("  Check your .env file has correct DB settings.")
        return False
    except Exception as e:
        print(f"\n  ERROR: {e}")
        return False


def main():
    print("=" * 60)
    print("IMPORT PHARMACIES TO POSTGRESQL/POSTGIS")
    print("=" * 60)
    
    data_dir = 'data'
    
    # Try JSON first, then KML
    json_file = os.path.join(data_dir, 'pharmacies_UPDATED.json')
    kml_file = os.path.join(data_dir, 'pharmacies_UPDATED.kml')
    
    if os.path.exists(json_file):
        pharmacies = load_from_json(json_file)
    elif os.path.exists(kml_file):
        pharmacies = load_from_kml(kml_file)
    else:
        print("ERROR: No pharmacy data file found!")
        print(f"  Expected: {json_file} or {kml_file}")
        return
    
    if not pharmacies:
        print("No pharmacies to import!")
        return
    
    # Import with option to clear existing
    success = import_to_database(pharmacies, clear_existing=True)
    
    if success:
        print("\n" + "=" * 60)
        print("IMPORT COMPLETE!")
        print("=" * 60)
        print("\nYou can now test the API:")
        print("  python run.py")
        print("\nThen open: http://localhost:5000/health")
    else:
        print("\n" + "=" * 60)
        print("IMPORT FAILED - See errors above")
        print("=" * 60)


if __name__ == '__main__':
    main()
