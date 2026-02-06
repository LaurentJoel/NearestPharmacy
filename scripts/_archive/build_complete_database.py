"""
Complete Pharmacy Database Builder
Uses website data + geocoding to create comprehensive pharmacy list with GPS coordinates.

Strategy:
1. Use website scraped data (has city info, more complete)
2. Geocode using OpenStreetMap Nominatim (FREE!)
3. For pharmacies without exact address, use city center + offset
4. Merge with OSM data for existing coordinates
5. Create comprehensive KML
"""
import json
import requests
import time
import re
import os
import random
from xml.etree import ElementTree as ET
from xml.dom import minidom
from datetime import datetime
from typing import Optional, Tuple


# City coordinates for Cameroon major cities (fallback for geocoding)
CITY_COORDINATES = {
    'yaounde': (3.8480, 11.5021),
    'douala': (4.0511, 9.7679),
    'bafoussam': (5.4737, 10.4179),
    'bamenda': (5.9527, 10.1582),
    'garoua': (9.3014, 13.3984),
    'maroua': (10.5956, 14.3159),
    'ngaoundere': (7.3167, 13.5833),
    'bertoua': (4.5772, 13.6847),
    'ebolowa': (2.9000, 11.1500),
    'kribi': (2.9500, 9.9000),
    'limbe': (4.0167, 9.2000),
    'buea': (4.1594, 9.2306),
    'kumba': (4.6333, 9.4167),
    'nkongsamba': (4.9500, 9.9333),
    'edea': (3.8000, 10.1333),
    'bafia': (4.7500, 11.2333),
    'mbalmayo': (3.5167, 11.5000),
    'sangmelima': (2.9333, 11.9833),
    'dschang': (5.4500, 10.0667),
    'foumban': (5.7333, 10.9000),
    'kousseri': (12.0833, 15.0333),
    'batouri': (4.4333, 14.3500),
    'banyo': (6.7500, 11.8167),
    'obala': (4.1667, 11.5333),
    'mbouda': (5.6333, 10.2500),
    'loum': (4.7167, 9.7333),
    'guider': (9.9333, 13.9500),
    'touboro': (7.7833, 15.3667),
    'bafang': (5.1500, 10.1833),
    'foumbot': (5.5000, 10.6333),
    'ambam': (2.3833, 11.2833),
    'muyuka': (4.2833, 9.4000),
    'mutengene': (4.0833, 9.3167),
    'likomba': (4.0667, 9.2500),
}


def normalize_city_name(city: str) -> str:
    """Normalize city name for lookup."""
    if not city:
        return ''
    city = city.lower().strip()
    city = re.sub(r'[^a-z]', '', city)
    # Handle common variations
    variations = {
        'ngaoundere': 'ngaoundere',
        'ngaoundéré': 'ngaoundere',
        'yaounde': 'yaounde',
        'yaoundé': 'yaounde',
        'saa': 'saa',
        'garoua': 'garoua',
        'garouas': 'garoua',
    }
    return variations.get(city, city)


def geocode_nominatim(query: str, country: str = 'Cameroon') -> Optional[Tuple[float, float]]:
    """
    Geocode using OpenStreetMap Nominatim (FREE, but rate limited).
    Returns (latitude, longitude) or None.
    """
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        'q': f"{query}, {country}",
        'format': 'json',
        'limit': 1
    }
    headers = {
        'User-Agent': 'PharmacyCameroon/1.0 (education project)'
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data:
                return (float(data[0]['lat']), float(data[0]['lon']))
    except Exception as e:
        print(f"    Geocoding error: {e}")
    
    return None


def get_city_coords(city: str) -> Tuple[float, float]:
    """Get coordinates for a city, with fallback to defaults."""
    normalized = normalize_city_name(city)
    
    if normalized in CITY_COORDINATES:
        return CITY_COORDINATES[normalized]
    
    # Try geocoding
    coords = geocode_nominatim(city)
    if coords:
        return coords
    
    # Default to Yaoundé center
    return (3.8480, 11.5021)


def add_offset(lat: float, lon: float, index: int) -> Tuple[float, float]:
    """
    Add small offset to coordinates to spread out pharmacies in same city.
    This prevents all pharmacies from appearing on the same spot.
    """
    # Create a spiral pattern offset
    angle = index * 0.5  # radians
    radius = 0.003 + (index * 0.0005)  # roughly 300m + 50m per pharmacy
    
    import math
    lat_offset = radius * math.cos(angle)
    lon_offset = radius * math.sin(angle)
    
    return (lat + lat_offset, lon + lon_offset)


def load_osm_pharmacies(kml_file: str) -> dict:
    """Load OSM pharmacies and create lookup by normalized name."""
    print("Loading OSM pharmacies for matching...")
    
    tree = ET.parse(kml_file)
    root = tree.getroot()
    ns = {'kml': 'http://www.opengis.net/kml/2.2'}
    
    lookup = {}
    for placemark in root.findall('.//kml:Placemark', ns):
        name_elem = placemark.find('kml:name', ns)
        coords_elem = placemark.find('.//kml:coordinates', ns)
        
        if name_elem is None or coords_elem is None:
            continue
        
        name = name_elem.text or ''
        coords = coords_elem.text.strip().split(',')
        if len(coords) < 2:
            continue
        
        normalized = normalize_name_for_matching(name)
        if normalized:
            lookup[normalized] = {
                'lat': float(coords[1]),
                'lon': float(coords[0]),
                'original_name': name
            }
    
    print(f"  Loaded {len(lookup)} pharmacies from OSM")
    return lookup


def normalize_name_for_matching(name: str) -> str:
    """Normalize pharmacy name for matching."""
    if not name:
        return ''
    name = name.lower()
    name = re.sub(r'[^\w\s]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    # Remove common prefixes
    for prefix in ['pharmacie ', 'pharmacy ', 'pharma ', 'la ', 'le ', 'de ', 'du ', "d'"]:
        while name.startswith(prefix):
            name = name[len(prefix):]
    return name.strip()


def build_complete_database(website_file: str, osm_kml_file: str) -> list:
    """
    Build complete pharmacy database from website + OSM data.
    """
    print("\n" + "="*60)
    print("BUILDING COMPLETE PHARMACY DATABASE")
    print("="*60 + "\n")
    
    # Load website data
    print("Loading website data...")
    with open(website_file, 'r', encoding='utf-8') as f:
        raw_data = json.load(f)
    
    raw_pharmacies = raw_data.get('pharmacies', [])
    print(f"  Raw entries: {len(raw_pharmacies)}")
    
    # Clean and filter
    pharmacies = []
    seen_names = set()
    
    noise_patterns = [
        r'^Pharmacies de garde',
        r'^Votre pharmacie',
        r'^Inscrivez',
        r'n\'apparaît pas',
        r'^est nouvelle',
        r'N° Téléphone',
    ]
    
    for p in raw_pharmacies:
        name = p.get('nom', '').strip()
        
        # Skip noise
        if not name or len(name) < 5:
            continue
        
        is_noise = any(re.search(pattern, name, re.I) for pattern in noise_patterns)
        if is_noise:
            continue
        
        # Skip duplicates
        name_key = normalize_name_for_matching(name) + '_' + normalize_city_name(p.get('ville', ''))
        if name_key in seen_names:
            continue
        seen_names.add(name_key)
        
        pharmacies.append({
            'nom': name,
            'telephone': p.get('telephone', '').strip(),
            'adresse': p.get('adresse', '').strip(),
            'ville': p.get('ville', '').strip(),
            'region': p.get('region', '').strip(),
        })
    
    print(f"  After cleaning: {len(pharmacies)} unique pharmacies")
    
    # Load OSM data for coordinate matching
    osm_lookup = load_osm_pharmacies(osm_kml_file)
    
    # Add coordinates to each pharmacy
    print("\nAdding GPS coordinates...")
    
    city_counters = {}  # To track pharmacies per city for offset
    matched_osm = 0
    geocoded = 0
    city_coords_used = 0
    
    for p in pharmacies:
        normalized_name = normalize_name_for_matching(p['nom'])
        city = p['ville']
        
        # Try to match with OSM data
        if normalized_name in osm_lookup:
            osm_data = osm_lookup[normalized_name]
            p['lat'] = osm_data['lat']
            p['lon'] = osm_data['lon']
            p['coord_source'] = 'osm'
            matched_osm += 1
        else:
            # Use city coordinates with offset
            city_key = normalize_city_name(city)
            if city_key not in city_counters:
                city_counters[city_key] = 0
            
            base_lat, base_lon = get_city_coords(city)
            lat, lon = add_offset(base_lat, base_lon, city_counters[city_key])
            city_counters[city_key] += 1
            
            p['lat'] = lat
            p['lon'] = lon
            p['coord_source'] = 'city_center'
            city_coords_used += 1
    
    print(f"  Matched with OSM: {matched_osm}")
    print(f"  City center + offset: {city_coords_used}")
    
    return pharmacies


def create_complete_kml(pharmacies: list, output_file: str):
    """Create KML with all pharmacies."""
    print(f"\nCreating complete KML: {output_file}")
    
    kml = ET.Element('kml', xmlns="http://www.opengis.net/kml/2.2")
    document = ET.SubElement(kml, 'Document')
    
    name = ET.SubElement(document, 'name')
    name.text = 'Toutes les Pharmacies du Cameroun'
    
    desc = ET.SubElement(document, 'description')
    desc.text = f'Base complète - {len(pharmacies)} pharmacies - {datetime.now().strftime("%Y-%m-%d")}'
    
    # Styles
    for style_id, color in [('osmStyle', 'ff00ff00'), ('cityStyle', 'ff0080ff'), ('defaultStyle', 'ffffffff')]:
        style = ET.SubElement(document, 'Style', id=style_id)
        icon_style = ET.SubElement(style, 'IconStyle')
        color_elem = ET.SubElement(icon_style, 'color')
        color_elem.text = color
        icon = ET.SubElement(icon_style, 'Icon')
        href = ET.SubElement(icon, 'href')
        href.text = 'http://maps.google.com/mapfiles/kml/shapes/pharmacy.png'
    
    # Group by city
    cities = {}
    for p in pharmacies:
        city = p.get('ville', 'Inconnu') or 'Inconnu'
        if city not in cities:
            cities[city] = []
        cities[city].append(p)
    
    # Create folders
    for city_name in sorted(cities.keys(), key=lambda x: (-len(cities[x]), x)):
        city_pharmacies = cities[city_name]
        
        folder = ET.SubElement(document, 'Folder')
        folder_name = ET.SubElement(folder, 'name')
        folder_name.text = f'{city_name} ({len(city_pharmacies)} pharmacies)'
        
        for p in city_pharmacies:
            placemark = ET.SubElement(folder, 'Placemark')
            
            pm_name = ET.SubElement(placemark, 'name')
            pm_name.text = p['nom']
            
            # Description
            desc_parts = []
            if p.get('adresse'):
                desc_parts.append(f"Adresse: {p['adresse']}")
            if p.get('telephone'):
                desc_parts.append(f"Téléphone: {p['telephone']}")
            desc_parts.append(f"Ville: {p.get('ville', 'N/A')}")
            desc_parts.append(f"Région: {p.get('region', 'N/A')}")
            desc_parts.append(f"Source coords: {p.get('coord_source', 'unknown')}")
            
            pm_desc = ET.SubElement(placemark, 'description')
            pm_desc.text = '\n'.join(desc_parts)
            
            # Style based on source
            style_url = ET.SubElement(placemark, 'styleUrl')
            source = p.get('coord_source', '')
            if source == 'osm':
                style_url.text = '#osmStyle'
            elif source == 'city_center':
                style_url.text = '#cityStyle'
            else:
                style_url.text = '#defaultStyle'
            
            point = ET.SubElement(placemark, 'Point')
            coords = ET.SubElement(point, 'coordinates')
            coords.text = f"{p['lon']},{p['lat']},0"
    
    # Save
    xml_str = ET.tostring(kml, encoding='unicode')
    dom = minidom.parseString(xml_str)
    pretty_xml = dom.toprettyxml(indent='  ')
    lines = [l for l in pretty_xml.split('\n') if l.strip()]
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    print(f"  Total pharmacies: {len(pharmacies)}")
    print(f"  Cities: {len(cities)}")
    
    # Print city breakdown
    print("\n  Top cities:")
    for city in sorted(cities.keys(), key=lambda x: -len(cities[x]))[:10]:
        print(f"    {city}: {len(cities[city])} pharmacies")


def main():
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
    
    website_file = os.path.join(data_dir, 'pharmacies_annuaire_medical.json')
    osm_file = os.path.join(data_dir, 'pharmacies_cameroun.kml')
    output_file = os.path.join(data_dir, 'pharmacies_complete.kml')
    
    # Build complete database
    pharmacies = build_complete_database(website_file, osm_file)
    
    # Save to JSON
    json_output = os.path.join(data_dir, 'pharmacies_complete.json')
    with open(json_output, 'w', encoding='utf-8') as f:
        json.dump({
            'created_at': datetime.now().isoformat(),
            'total_count': len(pharmacies),
            'pharmacies': pharmacies
        }, f, indent=2, ensure_ascii=False)
    print(f"\nSaved JSON: {json_output}")
    
    # Create KML
    create_complete_kml(pharmacies, output_file)
    
    print("\n" + "="*60)
    print("COMPLETE!")
    print("="*60)
    print(f"\nKML file: {output_file}")
    print("\nColor coding in Google Earth Pro:")
    print("  🟢 Green = Exact coordinates from OSM")
    print("  🟠 Orange = City center (need manual adjustment)")


if __name__ == '__main__':
    main()
