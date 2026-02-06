"""
Merge ALL pharmacy data: OSM (430) + Website (164) = Maximum coverage
"""
import json
import re
import os
from xml.etree import ElementTree as ET
from xml.dom import minidom
from datetime import datetime
import math

# City coordinates for offset calculation
CITY_COORDS = {
    'yaounde': (3.8480, 11.5021), 'douala': (4.0511, 9.7679),
    'bafoussam': (5.4737, 10.4179), 'bamenda': (5.9527, 10.1582),
    'garoua': (9.3014, 13.3984), 'maroua': (10.5956, 14.3159),
    'ngaoundere': (7.3167, 13.5833), 'bertoua': (4.5772, 13.6847),
    'ebolowa': (2.9000, 11.1500), 'kribi': (2.9500, 9.9000),
    'limbe': (4.0167, 9.2000), 'buea': (4.1594, 9.2306),
    'kumba': (4.6333, 9.4167), 'nkongsamba': (4.9500, 9.9333),
}


def normalize_name(name):
    if not name: return ''
    name = name.lower()
    name = re.sub(r'[^\w\s]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    for prefix in ['pharmacie ', 'pharmacy ', 'pharma ', 'la ', 'de ']:
        while name.startswith(prefix):
            name = name[len(prefix):]
    return name


def load_osm_kml(kml_file):
    """Load 430 pharmacies from OSM KML."""
    print(f"Loading OSM KML: {kml_file}")
    tree = ET.parse(kml_file)
    root = tree.getroot()
    ns = {'kml': 'http://www.opengis.net/kml/2.2'}
    
    pharmacies = []
    for placemark in root.findall('.//kml:Placemark', ns):
        name_elem = placemark.find('kml:name', ns)
        desc_elem = placemark.find('kml:description', ns)
        coords_elem = placemark.find('.//kml:coordinates', ns)
        
        if not coords_elem or not coords_elem.text:
            continue
        
        coords = coords_elem.text.strip().split(',')
        if len(coords) < 2:
            continue
        
        name = name_elem.text if name_elem is not None else 'Pharmacie'
        desc = desc_elem.text if desc_elem is not None else ''
        
        # Parse city from description
        city = 'Inconnu'
        if 'City:' in desc:
            match = re.search(r'City:\s*([^\n]+)', desc)
            if match:
                city = match.group(1).strip()
        
        pharmacies.append({
            'nom': name,
            'lat': float(coords[1]),
            'lon': float(coords[0]),
            'ville': city,
            'telephone': '',
            'adresse': '',
            'source': 'osm'
        })
    
    print(f"  Loaded {len(pharmacies)} pharmacies from OSM")
    return pharmacies


def load_website_json(json_file):
    """Load 164 pharmacies from website."""
    print(f"Loading website JSON: {json_file}")
    
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    pharmacies = data.get('pharmacies', [])
    
    # Clean noise
    noise = ['Pharmacies de garde', 'Votre pharmacie', 'Inscrivez', 'N° Téléphone']
    cleaned = []
    for p in pharmacies:
        name = p.get('nom', '').strip()
        if not name or len(name) < 5:
            continue
        if any(n in name for n in noise):
            continue
        cleaned.append({
            'nom': name,
            'telephone': p.get('telephone', ''),
            'adresse': p.get('adresse', ''),
            'ville': p.get('ville', ''),
            'region': p.get('region', ''),
            'source': 'website'
        })
    
    print(f"  Loaded {len(cleaned)} pharmacies from website")
    return cleaned


def merge_all(osm_list, website_list):
    """Merge both lists, enriching OSM with website data."""
    print("\nMerging datasets...")
    
    # Create lookup from website by normalized name
    website_lookup = {}
    for p in website_list:
        key = normalize_name(p['nom'])
        if key:
            website_lookup[key] = p
    
    # Start with OSM data (has GPS)
    merged = []
    matched = 0
    
    for osm_p in osm_list:
        key = normalize_name(osm_p['nom'])
        
        if key in website_lookup:
            # Enrich with website data
            web_p = website_lookup[key]
            osm_p['telephone'] = web_p.get('telephone', '')
            osm_p['adresse'] = web_p.get('adresse', '')
            if osm_p['ville'] == 'Inconnu' and web_p.get('ville'):
                osm_p['ville'] = web_p['ville']
            osm_p['region'] = web_p.get('region', '')
            osm_p['source'] = 'merged'
            matched += 1
            # Remove from lookup to track unmatched
            del website_lookup[key]
        
        merged.append(osm_p)
    
    # Add remaining website pharmacies (not in OSM)
    print(f"  Matched & enriched: {matched}")
    print(f"  Website-only pharmacies to add: {len(website_lookup)}")
    
    city_counters = {}
    for key, web_p in website_lookup.items():
        # No OSM match - use city center coords
        city = web_p.get('ville', '').lower().replace(' ', '')
        if city not in city_counters:
            city_counters[city] = 0
        
        # Get base coords
        base_lat, base_lon = CITY_COORDS.get(city, (3.8480, 11.5021))
        
        # Add offset
        idx = city_counters[city]
        angle = idx * 0.5
        radius = 0.003 + (idx * 0.0005)
        lat = base_lat + radius * math.cos(angle)
        lon = base_lon + radius * math.sin(angle)
        city_counters[city] += 1
        
        merged.append({
            'nom': web_p['nom'],
            'lat': lat,
            'lon': lon,
            'ville': web_p.get('ville', 'Inconnu'),
            'telephone': web_p.get('telephone', ''),
            'adresse': web_p.get('adresse', ''),
            'region': web_p.get('region', ''),
            'source': 'website_only'
        })
    
    print(f"  TOTAL MERGED: {len(merged)}")
    return merged


def create_final_kml(pharmacies, output_file):
    """Create final KML with all pharmacies."""
    print(f"\nCreating KML: {output_file}")
    
    kml = ET.Element('kml', xmlns="http://www.opengis.net/kml/2.2")
    doc = ET.SubElement(kml, 'Document')
    
    name = ET.SubElement(doc, 'name')
    name.text = f'Toutes les Pharmacies du Cameroun ({len(pharmacies)})'
    
    desc = ET.SubElement(doc, 'description')
    desc.text = f'OSM + Website merge - {datetime.now().strftime("%Y-%m-%d")}'
    
    # Styles
    styles = [
        ('osmStyle', 'ff00ff00'),      # Green - OSM only
        ('mergedStyle', 'ff00ffff'),   # Cyan - Merged
        ('websiteStyle', 'ff0080ff'),  # Orange - Website only
    ]
    for sid, color in styles:
        style = ET.SubElement(doc, 'Style', id=sid)
        icon_style = ET.SubElement(style, 'IconStyle')
        c = ET.SubElement(icon_style, 'color')
        c.text = color
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
        folder = ET.SubElement(doc, 'Folder')
        fn = ET.SubElement(folder, 'name')
        fn.text = f'{city_name} ({len(cities[city_name])})'
        
        for p in cities[city_name]:
            pm = ET.SubElement(folder, 'Placemark')
            
            pn = ET.SubElement(pm, 'name')
            pn.text = p['nom']
            
            pd = ET.SubElement(pm, 'description')
            parts = []
            if p.get('adresse'): parts.append(f"Adresse: {p['adresse']}")
            if p.get('telephone'): parts.append(f"Tel: {p['telephone']}")
            parts.append(f"Ville: {p.get('ville', 'N/A')}")
            parts.append(f"Source: {p.get('source', 'unknown')}")
            pd.text = '\n'.join(parts)
            
            su = ET.SubElement(pm, 'styleUrl')
            src = p.get('source', '')
            if src == 'merged':
                su.text = '#mergedStyle'
            elif src == 'website_only':
                su.text = '#websiteStyle'
            else:
                su.text = '#osmStyle'
            
            point = ET.SubElement(pm, 'Point')
            coords = ET.SubElement(point, 'coordinates')
            coords.text = f"{p['lon']},{p['lat']},0"
    
    # Save
    xml_str = ET.tostring(kml, encoding='unicode')
    dom = minidom.parseString(xml_str)
    pretty = dom.toprettyxml(indent='  ')
    lines = [l for l in pretty.split('\n') if l.strip()]
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    
    print(f"  Cities: {len(cities)}")


def main():
    data_dir = 'data'
    
    # Load both sources
    osm_pharmacies = load_osm_kml(os.path.join(data_dir, 'pharmacies_cameroun.kml'))
    website_pharmacies = load_website_json(os.path.join(data_dir, 'pharmacies_annuaire_medical.json'))
    
    # Merge
    all_pharmacies = merge_all(osm_pharmacies, website_pharmacies)
    
    # Save JSON
    json_out = os.path.join(data_dir, 'pharmacies_all_merged.json')
    with open(json_out, 'w', encoding='utf-8') as f:
        json.dump({
            'created': datetime.now().isoformat(),
            'total': len(all_pharmacies),
            'pharmacies': all_pharmacies
        }, f, indent=2, ensure_ascii=False)
    print(f"\nSaved JSON: {json_out}")
    
    # Save KML
    kml_out = os.path.join(data_dir, 'pharmacies_all_merged.kml')
    create_final_kml(all_pharmacies, kml_out)
    
    # Stats
    osm_only = sum(1 for p in all_pharmacies if p['source'] == 'osm')
    merged = sum(1 for p in all_pharmacies if p['source'] == 'merged')
    web_only = sum(1 for p in all_pharmacies if p['source'] == 'website_only')
    
    print("\n" + "="*55)
    print("             FINAL SUMMARY")
    print("="*55)
    print(f"  TOTAL PHARMACIES: {len(all_pharmacies)}")
    print(f"  - OSM only (green):      {osm_only}")
    print(f"  - Merged (cyan):         {merged}")
    print(f"  - Website only (orange): {web_only}")
    print("="*55)
    
    # Per city
    cities = {}
    for p in all_pharmacies:
        c = p.get('ville', 'Inconnu')
        cities[c] = cities.get(c, 0) + 1
    
    print("\nTOP 15 CITIES:")
    for city, count in sorted(cities.items(), key=lambda x: -x[1])[:15]:
        print(f"  {city:20} {count:3}")


if __name__ == '__main__':
    main()
