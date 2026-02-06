"""
Smart Merge Script - Detects city from GPS coordinates
Handles mixed-city files properly
"""
import zipfile
import re
import json
import os
import math
from xml.etree import ElementTree as ET
from xml.dom import minidom
from datetime import datetime
from glob import glob


# City center coordinates for detection
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
}


def detect_city(lat, lon, default_city="Inconnu"):
    """Detect the closest city based on GPS coordinates."""
    min_dist = float('inf')
    closest_city = default_city
    
    for city, (city_lat, city_lon) in CITY_CENTERS.items():
        # Calculate approximate distance in km
        lat_diff = (lat - city_lat) * 111
        lon_diff = (lon - city_lon) * 111 * math.cos(math.radians(lat))
        dist = math.sqrt(lat_diff**2 + lon_diff**2)
        
        if dist < min_dist:
            min_dist = dist
            closest_city = city
    
    # Only assign city if within 30km
    if min_dist > 30:
        return default_city
    
    return closest_city


def extract_kmz(kmz_path):
    try:
        with zipfile.ZipFile(kmz_path, 'r') as z:
            for name in z.namelist():
                if name.endswith('.kml'):
                    with z.open(name) as f:
                        return f.read().decode('utf-8')
    except Exception as e:
        print(f"  Error reading {kmz_path}: {e}")
    return None


def parse_kml_placemarks(kml_content, default_city):
    """Parse placemarks and detect actual city from coordinates."""
    pharmacies = []
    
    placemark_pattern = r'<Placemark[^>]*>(.*?)</Placemark>'
    name_pattern = r'<name[^>]*>(.*?)</name>'
    coords_pattern = r'<coordinates[^>]*>(.*?)</coordinates>'
    
    for match in re.finditer(placemark_pattern, kml_content, re.DOTALL | re.IGNORECASE):
        pm_content = match.group(1)
        
        name_match = re.search(name_pattern, pm_content, re.IGNORECASE)
        if not name_match:
            continue
        name = name_match.group(1).strip()
        name = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', name, flags=re.DOTALL)
        name = re.sub(r'<[^>]+>', '', name).strip()
        
        if not name or len(name) < 3:
            continue
        
        coords_match = re.search(coords_pattern, pm_content, re.IGNORECASE)
        if not coords_match:
            continue
        
        coords_text = coords_match.group(1).strip()
        first_coord = coords_text.split()[0] if ' ' in coords_text else coords_text
        parts = first_coord.split(',')
        
        if len(parts) < 2:
            continue
        
        try:
            lon = float(parts[0])
            lat = float(parts[1])
        except ValueError:
            continue
        
        # SMART CITY DETECTION
        detected_city = detect_city(lat, lon, default_city)
        
        pharmacies.append({
            'nom': name,
            'lat': lat,
            'lon': lon,
            'ville': detected_city,
            'telephone': '',
            'adresse': '',
            'source': 'google_earth_user'
        })
    
    return pharmacies


def normalize_name(name):
    if not name:
        return ''
    name = name.lower()
    name = re.sub(r'[^\w\s]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    for prefix in ['pharmacie ', 'pharmacy ', 'pharma ']:
        if name.startswith(prefix):
            name = name[len(prefix):]
    return name.strip()


def coords_are_close(lat1, lon1, lat2, lon2, threshold_m=200):
    lat_diff = abs(lat1 - lat2) * 111000
    lon_diff = abs(lon1 - lon2) * 111000 * math.cos(math.radians((lat1 + lat2) / 2))
    distance = math.sqrt(lat_diff**2 + lon_diff**2)
    return distance < threshold_m


def load_existing_data(kml_path):
    print(f"Loading existing data: {kml_path}")
    
    with open(kml_path, 'r', encoding='utf-8') as f:
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
        
        city = 'Inconnu'
        city_match = re.search(r'Ville:\s*([^\n<]+)', desc)
        if city_match:
            city = city_match.group(1).strip()
        
        source = 'osm'
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
    
    print(f"  Loaded {len(pharmacies)} pharmacies")
    return pharmacies


def merge_pharmacies(existing, new_pharmacies):
    """Merge new pharmacies, checking for duplicates across ALL cities."""
    print(f"\nMerging {len(new_pharmacies)} new pharmacies with {len(existing)} existing...")
    
    merged = list(existing)
    
    # Create lookup by normalized name AND city
    existing_lookup = {}
    for i, p in enumerate(merged):
        key = (normalize_name(p['nom']), p['ville'])
        if key not in existing_lookup:
            existing_lookup[key] = []
        existing_lookup[key].append(i)
    
    # Also create lookup by just name (for cross-city checks)
    name_lookup = {}
    for i, p in enumerate(merged):
        key = normalize_name(p['nom'])
        if key not in name_lookup:
            name_lookup[key] = []
        name_lookup[key].append(i)
    
    added = 0
    updated = 0
    skipped = 0
    city_counts = {}
    
    for new_p in new_pharmacies:
        new_name = normalize_name(new_p['nom'])
        new_city = new_p['ville']
        
        # Track city counts
        if new_city not in city_counts:
            city_counts[new_city] = {'added': 0, 'skipped': 0, 'updated': 0}
        
        # Check if exists in same city
        key = (new_name, new_city)
        if key in existing_lookup:
            for idx in existing_lookup[key]:
                existing_p = merged[idx]
                if coords_are_close(existing_p['lat'], existing_p['lon'], 
                                   new_p['lat'], new_p['lon']):
                    # Exact duplicate - skip
                    skipped += 1
                    city_counts[new_city]['skipped'] += 1
                    break
            else:
                # Same name, different location in same city - add
                merged.append(new_p)
                added += 1
                city_counts[new_city]['added'] += 1
            continue
        
        # Check if exists in ANY city with close coordinates
        if new_name in name_lookup:
            found_close = False
            for idx in name_lookup[new_name]:
                existing_p = merged[idx]
                if coords_are_close(existing_p['lat'], existing_p['lon'], 
                                   new_p['lat'], new_p['lon'], threshold_m=500):
                    # Same pharmacy, possibly different city name
                    if existing_p['ville'] == 'Inconnu':
                        # Update with detected city
                        merged[idx]['ville'] = new_city
                        merged[idx]['source'] = 'google_earth_updated'
                        updated += 1
                        city_counts[new_city]['updated'] += 1
                    else:
                        skipped += 1
                        city_counts[new_city]['skipped'] += 1
                    found_close = True
                    break
            
            if found_close:
                continue
        
        # New pharmacy - add it
        merged.append(new_p)
        added += 1
        city_counts[new_city]['added'] += 1
        
        # Update lookups
        if key not in existing_lookup:
            existing_lookup[key] = []
        existing_lookup[key].append(len(merged) - 1)
        if new_name not in name_lookup:
            name_lookup[new_name] = []
        name_lookup[new_name].append(len(merged) - 1)
    
    print(f"  Added: {added}")
    print(f"  Updated: {updated}")
    print(f"  Skipped (duplicates): {skipped}")
    print(f"\n  By detected city:")
    for city, counts in sorted(city_counts.items()):
        print(f"    {city}: +{counts['added']} added, {counts['updated']} updated, {counts['skipped']} skipped")
    print(f"\n  Total now: {len(merged)}")
    
    return merged


def save_merged_kml(pharmacies, output_file):
    print(f"\nSaving to: {output_file}")
    
    kml = ET.Element('kml', xmlns="http://www.opengis.net/kml/2.2")
    doc = ET.SubElement(kml, 'Document')
    
    name = ET.SubElement(doc, 'name')
    name.text = f'Pharmacies Cameroun - UPDATED ({len(pharmacies)})'
    
    styles = [
        ('osmStyle', 'ff00ff00'),
        ('mergedStyle', 'ff00ffff'),
        ('websiteStyle', 'ff0080ff'),
        ('userStyle', 'ffff00ff'),
        ('updatedStyle', 'ffffff00'),
    ]
    for sid, color in styles:
        style = ET.SubElement(doc, 'Style', id=sid)
        icon_style = ET.SubElement(style, 'IconStyle')
        c = ET.SubElement(icon_style, 'color')
        c.text = color
        icon = ET.SubElement(icon_style, 'Icon')
        href = ET.SubElement(icon, 'href')
        href.text = 'http://maps.google.com/mapfiles/kml/shapes/pharmacy.png'
    
    cities = {}
    for p in pharmacies:
        city = p.get('ville', 'Inconnu') or 'Inconnu'
        if city not in cities:
            cities[city] = []
        cities[city].append(p)
    
    for city_name in sorted(cities.keys(), key=lambda x: (-len(cities[x]), x)):
        folder = ET.SubElement(doc, 'Folder')
        fn = ET.SubElement(folder, 'name')
        fn.text = f'{city_name} ({len(cities[city_name])})'
        
        for p in cities[city_name]:
            pm = ET.SubElement(folder, 'Placemark')
            pn = ET.SubElement(pm, 'name')
            pn.text = p['nom']
            
            pd = ET.SubElement(pm, 'description')
            parts = [f"Ville: {p.get('ville', 'N/A')}"]
            if p.get('telephone'):
                parts.append(f"Tel: {p['telephone']}")
            if p.get('adresse'):
                parts.append(f"Adresse: {p['adresse'][:100]}")
            parts.append(f"Source: {p.get('source', 'unknown')}")
            pd.text = '\n'.join(parts)
            
            su = ET.SubElement(pm, 'styleUrl')
            src = p.get('source', 'osm')
            if 'user' in src:
                su.text = '#userStyle'
            elif 'updated' in src:
                su.text = '#updatedStyle'
            elif src == 'merged':
                su.text = '#mergedStyle'
            else:
                su.text = '#osmStyle'
            
            point = ET.SubElement(pm, 'Point')
            coords = ET.SubElement(point, 'coordinates')
            coords.text = f"{p['lon']},{p['lat']},0"
    
    xml_str = ET.tostring(kml, encoding='unicode')
    dom = minidom.parseString(xml_str)
    pretty = '\n'.join([l for l in dom.toprettyxml(indent='  ').split('\n') if l.strip()])
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(pretty)
    
    print(f"\n  Total: {len(pharmacies)}")
    print(f"  Top cities:")
    for city in sorted(cities.keys(), key=lambda x: -len(cities[x]))[:5]:
        print(f"    {city}: {len(cities[city])}")


# Main
file_pattern = "Ebolowa"  # Change this for different cities
data_dir = 'data'

print("=" * 60)
print(f"SMART MERGE - Processing {file_pattern} files")
print("=" * 60)

# Find files
kmz_files = glob(f'{data_dir}/Pharmacie {file_pattern}*.kmz')
print(f"\nFound {len(kmz_files)} KMZ files")

# Extract pharmacies with SMART CITY DETECTION
all_new = []
for f in sorted(kmz_files):
    content = extract_kmz(f)
    if content:
        pharmacies = parse_kml_placemarks(content, file_pattern)
        print(f"\n  {os.path.basename(f)}: {len(pharmacies)} placemarks")
        # Show detected cities
        city_counts = {}
        for p in pharmacies:
            city_counts[p['ville']] = city_counts.get(p['ville'], 0) + 1
        for city, count in city_counts.items():
            print(f"    → {city}: {count}")
        all_new.extend(pharmacies)

print(f"\nTotal extracted: {len(all_new)}")

# Load existing
existing_file = f'{data_dir}/pharmacies_UPDATED.kml'
existing = load_existing_data(existing_file)

# Merge with smart duplicate detection
merged = merge_pharmacies(existing, all_new)

# Save
save_merged_kml(merged, existing_file)

# Save JSON
json_file = f'{data_dir}/pharmacies_UPDATED.json'
with open(json_file, 'w', encoding='utf-8') as f:
    json.dump({'created': datetime.now().isoformat(), 'total': len(merged), 'pharmacies': merged}, f, indent=2, ensure_ascii=False)

print("\nDONE!")
