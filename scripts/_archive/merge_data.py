"""
Clean and Merge Pharmacy Data
1. Clean the scraped website data (remove noise)
2. Merge with OpenStreetMap data
3. Create enriched KML file with city info
"""
import json
import re
import os
from xml.etree import ElementTree as ET
from xml.dom import minidom
from datetime import datetime


def clean_website_data(input_file: str) -> list:
    """
    Clean the scraped data by removing noise entries.
    """
    print("Loading and cleaning website data...")
    
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    pharmacies = data.get('pharmacies', [])
    
    # Patterns to exclude (noise)
    noise_patterns = [
        r'^Pharmacies de garde',
        r'^Votre pharmacie',
        r'^Inscrivez votre pharmacie',
        r'^N° Téléphone',
        r'n\'apparaît pas',
        r'^est nouvelle',
    ]
    
    cleaned = []
    for p in pharmacies:
        name = p.get('nom', '').strip()
        
        # Skip empty names
        if not name or len(name) < 5:
            continue
        
        # Skip noise entries
        is_noise = False
        for pattern in noise_patterns:
            if re.search(pattern, name, re.IGNORECASE):
                is_noise = True
                break
        
        if is_noise:
            continue
        
        # Clean up the name
        name = re.sub(r'\s+', ' ', name).strip()
        
        # Skip if still looks like noise
        if any(x in name.lower() for x in ['listing', 'nouvelle', 'n° téléphone']):
            continue
        
        # Normalize phone number
        phone = p.get('telephone', '').strip()
        phone = re.sub(r'\s+', ' ', phone)
        
        cleaned.append({
            'nom': name,
            'telephone': phone,
            'adresse': p.get('adresse', '').strip(),
            'ville': p.get('ville', '').strip(),
            'region': p.get('region', '').strip()
        })
    
    print(f"  Original: {len(pharmacies)} entries")
    print(f"  After cleaning: {len(cleaned)} pharmacies")
    
    return cleaned


def normalize_name(name: str) -> str:
    """Normalize pharmacy name for matching."""
    if not name:
        return ''
    name = name.lower()
    name = re.sub(r'[^\w\s]', '', name)
    name = re.sub(r'\s+', ' ', name)
    name = name.strip()
    # Remove common prefixes
    for prefix in ['pharmacie ', 'pharmacy ', 'pharma ']:
        if name.startswith(prefix):
            name = name[len(prefix):]
    return name


def load_osm_kml(kml_file: str) -> list:
    """Load pharmacies from OSM KML file."""
    print(f"Loading OSM KML: {kml_file}")
    
    tree = ET.parse(kml_file)
    root = tree.getroot()
    
    ns = {'kml': 'http://www.opengis.net/kml/2.2'}
    
    pharmacies = []
    for placemark in root.findall('.//kml:Placemark', ns):
        name_elem = placemark.find('kml:name', ns)
        desc_elem = placemark.find('kml:description', ns)
        coords_elem = placemark.find('.//kml:coordinates', ns)
        
        if coords_elem is None:
            continue
        
        coords = coords_elem.text.strip().split(',')
        if len(coords) < 2:
            continue
        
        lon = float(coords[0])
        lat = float(coords[1])
        
        name = name_elem.text if name_elem is not None else 'Unknown'
        desc = desc_elem.text if desc_elem is not None else ''
        
        # Parse city from description
        city = ''
        if 'City:' in desc:
            match = re.search(r'City:\s*([^\n]+)', desc)
            if match:
                city = match.group(1).strip()
        
        pharmacies.append({
            'nom': name,
            'lat': lat,
            'lon': lon,
            'ville': city,
            'description': desc
        })
    
    print(f"  Loaded {len(pharmacies)} pharmacies from OSM")
    return pharmacies


def merge_data(osm_pharmacies: list, website_pharmacies: list) -> list:
    """
    Merge OSM and website data.
    - OSM provides GPS coordinates
    - Website provides city, phone, address
    """
    print("\nMerging data...")
    
    # Create lookup from website data by normalized name
    website_lookup = {}
    for p in website_pharmacies:
        normalized = normalize_name(p['nom'])
        if normalized and len(normalized) > 2:
            website_lookup[normalized] = p
    
    # Merge
    matched = 0
    for osm_p in osm_pharmacies:
        normalized_name = normalize_name(osm_p['nom'])
        
        if normalized_name in website_lookup:
            website_p = website_lookup[normalized_name]
            
            # Enrich OSM data with website info
            if not osm_p.get('ville') or osm_p['ville'] == 'Inconnu':
                osm_p['ville'] = website_p.get('ville', '')
            osm_p['telephone'] = website_p.get('telephone', '')
            osm_p['adresse'] = website_p.get('adresse', '')
            osm_p['region'] = website_p.get('region', '')
            osm_p['matched'] = True
            matched += 1
        else:
            osm_p['matched'] = False
    
    print(f"  Matched: {matched} pharmacies")
    print(f"  Unmatched: {len(osm_pharmacies) - matched} pharmacies")
    
    return osm_pharmacies


def create_enriched_kml(pharmacies: list, output_file: str):
    """Create enriched KML file with merged data."""
    print(f"\nCreating enriched KML: {output_file}")
    
    kml_ns = "http://www.opengis.net/kml/2.2"
    
    kml = ET.Element('kml', xmlns=kml_ns)
    document = ET.SubElement(kml, 'Document')
    
    name = ET.SubElement(document, 'name')
    name.text = 'Pharmacies du Cameroun (Enrichi)'
    
    desc = ET.SubElement(document, 'description')
    desc.text = f'Données enrichies OSM + annuaire-medical.cm - {datetime.now().strftime("%Y-%m-%d")}'
    
    # Style
    style = ET.SubElement(document, 'Style', id='pharmacyStyle')
    icon_style = ET.SubElement(style, 'IconStyle')
    icon = ET.SubElement(icon_style, 'Icon')
    href = ET.SubElement(icon, 'href')
    href.text = 'http://maps.google.com/mapfiles/kml/shapes/pharmacy.png'
    
    # Matched style (green)
    style_matched = ET.SubElement(document, 'Style', id='matchedStyle')
    icon_style_m = ET.SubElement(style_matched, 'IconStyle')
    color_m = ET.SubElement(icon_style_m, 'color')
    color_m.text = 'ff00ff00'  # Green
    icon_m = ET.SubElement(icon_style_m, 'Icon')
    href_m = ET.SubElement(icon_m, 'href')
    href_m.text = 'http://maps.google.com/mapfiles/kml/shapes/pharmacy.png'
    
    # Group by city
    cities = {}
    for p in pharmacies:
        city = p.get('ville', '') or p.get('region', '') or 'Inconnu'
        if city not in cities:
            cities[city] = []
        cities[city].append(p)
    
    # Create folders by city
    for city_name, city_pharmacies in sorted(cities.items(), key=lambda x: (-len(x[1]), x[0])):
        folder = ET.SubElement(document, 'Folder')
        folder_name = ET.SubElement(folder, 'name')
        folder_name.text = f'{city_name} ({len(city_pharmacies)} pharmacies)'
        
        for p in city_pharmacies:
            placemark = ET.SubElement(folder, 'Placemark')
            
            pm_name = ET.SubElement(placemark, 'name')
            pm_name.text = p['nom']
            
            # Build description
            desc_parts = []
            if p.get('adresse'):
                desc_parts.append(f"Adresse: {p['adresse']}")
            if p.get('telephone'):
                desc_parts.append(f"Téléphone: {p['telephone']}")
            if p.get('ville'):
                desc_parts.append(f"Ville: {p['ville']}")
            if p.get('region'):
                desc_parts.append(f"Région: {p['region']}")
            desc_parts.append(f"Source: {'Enrichi' if p.get('matched') else 'OSM uniquement'}")
            
            pm_desc = ET.SubElement(placemark, 'description')
            pm_desc.text = '\n'.join(desc_parts)
            
            style_url = ET.SubElement(placemark, 'styleUrl')
            style_url.text = '#matchedStyle' if p.get('matched') else '#pharmacyStyle'
            
            point = ET.SubElement(placemark, 'Point')
            coords = ET.SubElement(point, 'coordinates')
            coords.text = f"{p['lon']},{p['lat']},0"
    
    # Pretty print
    xml_str = ET.tostring(kml, encoding='unicode')
    dom = minidom.parseString(xml_str)
    pretty_xml = dom.toprettyxml(indent='  ')
    lines = [line for line in pretty_xml.split('\n') if line.strip()]
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    # Stats
    matched_count = sum(1 for p in pharmacies if p.get('matched'))
    print(f"  Total pharmacies: {len(pharmacies)}")
    print(f"  Matched (enriched): {matched_count}")
    print(f"  Unmatched (OSM only): {len(pharmacies) - matched_count}")
    print(f"  Cities: {len(cities)}")


def main():
    print("=" * 60)
    print("PHARMACY DATA CLEANING AND MERGING")
    print("=" * 60 + "\n")
    
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
    
    # Step 1: Clean website data
    website_file = os.path.join(data_dir, 'pharmacies_annuaire_medical.json')
    website_pharmacies = clean_website_data(website_file)
    
    # Save cleaned data
    cleaned_file = os.path.join(data_dir, 'pharmacies_website_cleaned.json')
    with open(cleaned_file, 'w', encoding='utf-8') as f:
        json.dump(website_pharmacies, f, indent=2, ensure_ascii=False)
    print(f"  Saved cleaned data to: {cleaned_file}")
    
    # Step 2: Load OSM data
    osm_file = os.path.join(data_dir, 'pharmacies_cameroun.kml')
    osm_pharmacies = load_osm_kml(osm_file)
    
    # Step 3: Merge
    merged = merge_data(osm_pharmacies, website_pharmacies)
    
    # Step 4: Create enriched KML
    output_file = os.path.join(data_dir, 'pharmacies_cameroun_enriched.kml')
    create_enriched_kml(merged, output_file)
    
    print("\n" + "=" * 60)
    print("COMPLETE!")
    print("=" * 60)
    print(f"\nEnriched KML file: {output_file}")
    print("\nOpen this file in Google Earth Pro to see:")
    print("  - Green icons = Matched with website data (city, phone, address)")
    print("  - Standard icons = OSM data only")


if __name__ == '__main__':
    main()
