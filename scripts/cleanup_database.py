"""
Database Cleanup Script
-----------------------
1. Detect city from GPS coordinates
2. Update city field for all pharmacies
3. Clean garbage from names
4. Remove duplicates
"""
import psycopg2
import re
import os
import math
from dotenv import load_dotenv

load_dotenv()

# City centers with coordinates
CITY_CENTERS = {
    'Yaoundé': (3.8480, 11.5021),
    'Douala': (4.0511, 9.7679),
    'Bamenda': (5.9527, 10.1582),
    'Bafoussam': (5.4737, 10.4179),
    'Garoua': (9.3014, 13.3984),
    'Maroua': (10.5956, 14.3159),
    'Ngaoundéré': (7.3167, 13.5833),
    'Bertoua': (4.5772, 13.6847),
    'Ebolowa': (2.9000, 11.1500),
    'Kribi': (2.9500, 9.9000),
    'Buea': (4.1594, 9.2306),
    'Limbe': (4.0167, 9.2000),
    'Kumba': (4.6333, 9.4167),
    'Nkongsamba': (4.9500, 9.9333),
    'Edéa': (3.8000, 10.1333),
    'Dschang': (5.4500, 10.0667),
    'Foumban': (5.7333, 10.9000),
    'Kousseri': (12.0833, 15.0333),
    'Sangmélima': (2.9333, 11.9833),
    'Bafia': (4.7500, 11.2333),
    'Mbalmayo': (3.5167, 11.5000),
    'Obala': (4.1667, 11.5333),
    'Mbouda': (5.6333, 10.2500),
    'Loum': (4.7167, 9.7333),
    'Tiko': (4.0750, 9.3600),
    'Mutengene': (4.0833, 9.3167),
    'Muyuka': (4.2833, 9.4000),
    'Banyo': (6.7500, 11.8167),
    'Batouri': (4.4333, 14.3500),
    'Meiganga': (6.5167, 14.3000),
    'Tibati': (6.4667, 12.6333),
    'Mamfe': (5.7667, 9.3000),
    'Wum': (6.3833, 10.0667),
    'Fundong': (6.2500, 10.2667),
    'Kumbo': (6.2000, 10.6667),
    'Nkambé': (6.6167, 10.6667),
    'Mokolo': (10.7333, 13.8000),
    'Mora': (11.0500, 14.1333),
    'Yagoua': (10.3333, 15.2333),
    'Kaélé': (10.1000, 14.4500),
    'Yokadouma': (3.5167, 15.0500),
    'Akonolinga': (3.7667, 12.2500),
    'Nanga-Eboko': (4.6833, 12.3667),
}


def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=os.getenv('DB_PORT', '5432'),
        dbname=os.getenv('DB_NAME', 'pharmacy_db'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', 'postgres')
    )


def detect_city(lat, lon):
    """Detect closest city from coordinates."""
    if lat is None or lon is None:
        return 'Inconnu'
    
    min_dist = float('inf')
    closest_city = 'Inconnu'
    
    for city, (city_lat, city_lon) in CITY_CENTERS.items():
        # Calculate distance in km
        lat_diff = (lat - city_lat) * 111
        lon_diff = (lon - city_lon) * 111 * math.cos(math.radians(lat))
        dist = math.sqrt(lat_diff**2 + lon_diff**2)
        
        if dist < min_dist:
            min_dist = dist
            closest_city = city
    
    # Only assign city if within 30km
    if min_dist > 30:
        return 'Autre'
    
    return closest_city


def clean_name(name):
    """Clean garbage from pharmacy name."""
    if not name:
        return name
    
    # Remove phone numbers (pattern: digits with spaces)
    name = re.sub(r'\d{3}\s*\d{2}\s*\d{2}\s*\d{2}', '', name)
    name = re.sub(r'\d{2,3}\s+\d{2}\s+\d{2}\s+\d{2}', '', name)
    
    # Remove city suffixes like "Nkongsamba:" or "Yaoundé:"
    name = re.sub(r'[A-Za-zéèêëàâäùûüôîïç\-]+\s*:\s*$', '', name)
    name = re.sub(r'[A-Za-zéèêëàâäùûüôîïç\-]+:.*$', '', name)
    
    # Clean up extra spaces
    name = re.sub(r'\s+', ' ', name).strip()
    
    return name


def main():
    print("=" * 60)
    print("DATABASE CLEANUP")
    print("=" * 60)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Step 1: Get all pharmacies
    cursor.execute("""
        SELECT id, nom, ville, ST_Y(geom) as lat, ST_X(geom) as lon 
        FROM pharmacies
    """)
    pharmacies = cursor.fetchall()
    print(f"Total pharmacies: {len(pharmacies)}")
    
    # Step 2: Update each pharmacy
    updates = 0
    city_counts = {}
    
    for pid, nom, ville, lat, lon in pharmacies:
        new_name = clean_name(nom)
        new_city = detect_city(lat, lon)
        
        # Track city counts
        city_counts[new_city] = city_counts.get(new_city, 0) + 1
        
        # Only update if changed
        if new_name != nom or new_city != ville:
            cursor.execute("""
                UPDATE pharmacies 
                SET nom = %s, ville = %s 
                WHERE id = %s
            """, (new_name, new_city, pid))
            updates += 1
    
    conn.commit()
    print(f"\nUpdated {updates} pharmacies")
    
    # Step 3: Show city distribution
    print("\nCity distribution after cleanup:")
    for city, count in sorted(city_counts.items(), key=lambda x: -x[1])[:15]:
        print(f"  {city}: {count}")
    
    # Step 4: Remove duplicates (same name + same city)
    cursor.execute("""
        DELETE FROM pharmacies a
        USING pharmacies b
        WHERE a.id < b.id
          AND LOWER(a.nom) = LOWER(b.nom)
          AND a.ville = b.ville
    """)
    duplicates = cursor.rowcount
    conn.commit()
    print(f"\nRemoved {duplicates} duplicate pharmacies")
    
    # Final count
    cursor.execute("SELECT COUNT(*) FROM pharmacies")
    final_count = cursor.fetchone()[0]
    print(f"\nFinal pharmacy count: {final_count}")
    
    # Show sample of cleaned data
    cursor.execute("""
        SELECT nom, ville FROM pharmacies 
        WHERE ville != 'Inconnu' AND ville != 'Autre'
        LIMIT 10
    """)
    print("\nSample cleaned data:")
    for nom, ville in cursor.fetchall():
        print(f"  {nom[:40]} | {ville}")
    
    cursor.close()
    conn.close()
    
    print("\n" + "=" * 60)
    print("CLEANUP COMPLETE!")
    print("=" * 60)


if __name__ == '__main__':
    main()
