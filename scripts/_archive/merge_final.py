"""
FINAL MERGE: ALL Pharmacies from OSM (430) + Website (164)
Creates the COMPLETE database for testing
"""
import json
import re
import os
from xml.etree import ElementTree as ET
from xml.dom import minidom
from datetime import datetime
import math

def normalize_name(name):
    if not name: return ''
    name = name.lower()
    name = re.sub(r'[^\w\s]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    for prefix in ['pharmacie ', 'pharmacy ', 'pharma ']:
        if name.startswith(prefix):
            name = name[len(prefix):]
    return name


def load_osm_kml(kml_file):
    """Load ALL 430 pharmacies from OSM KML."""
    print(f"Loading OSM: {kml_file}")
    
    with open(kml_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Simple regex extraction for reliability
    pharmacies = []
    
    # Find all placemarks
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
        
        name = name_match.group(1) if name_match else 'Pharmacie'
        coords_text = coords_match.text.strip() if hasattr(coords_match, 'text') else coords_match.group(1).strip()
        desc = desc_match.group(1) if desc_match else ''
        
        parts = coords_text.split(',')
        if len(parts) < 2:
            continue
        
        try:
            lon = float(parts[0])
            lat = float(parts[1])
        except:
            continue
        
        # Parse city from description
        city = 'Inconnu'
        if 'City:' in desc:
            city_match = re.search(r'City:\s*([^\n<]+)', desc)
            if city_match:
                city = city_match.group(1).strip()
        
        pharmacies.append({
            'nom': name,
            'lat': lat,
            'lon': lon,
            'ville': city,
            'telephone': '',
            'adresse': '',
            'source': 'osm'
        })
    
    print(f"  Loaded: {len(pharmacies)} pharmacies")
    return pharmacies


def load_website_json(json_file):
    """Load cleaned website pharmacies."""
    print(f"Loading website: {json_file}")
    
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    pharmacies = data.get('pharmacies', [])
    
    # Filter noise
    noise_words = ['Pharmacies de garde', 'Votre pharmacie', 'Inscrivez', 'N° Téléphone', "n'apparaît"]
    cleaned = []
    seen = set()
    
    for p in pharmacies:
        name = p.get('nom', '').strip()
        if not name or len(name) < 5:
            continue
        if any(n in name for n in noise_words):
            continue
        
        key = normalize_name(name)
        if key in seen:
            continue
        seen.add(key)
        
        cleaned.append({
            'nom': name,
            'telephone': p.get('telephone', ''),
            'adresse': p.get('adresse', ''),
            'ville': p.get('ville', ''),
            'region': p.get('region', ''),
            'source': 'website'
        })
    
    print(f"  Loaded: {len(cleaned)} unique pharmacies")
    return cleaned


def merge_all(osm_list, website_list):
    """Merge both lists: OSM is primary (has GPS), website enriches."""
    print(f"\nMerging {len(osm_list)} OSM + {len(website_list)} website...")
    
    # Create website lookup
    website_lookup = {}
    for p in website_list:
        key = normalize_name(p['nom'])
        if key:
            website_lookup[key] = p
    
    # Process OSM pharmacies + enrich with website data
    merged = []
    matched = 0
    matched_keys = set()
    
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
            matched_keys.add(key)
        
        merged.append(osm_p)
    
    # Add website-only pharmacies with estimated coordinates
    city_coords = {
        'yaounde': (3.8480, 11.5021), 'douala': (4.0511, 9.7679),
        'bamenda': (5.9527, 10.1582), 'garoua': (9.3014, 13.3984),
        'bafoussam': (5.4737, 10.4179), 'maroua': (10.5956, 14.3159),
        'ngaoundere': (7.3167, 13.5833), 'bertoua': (4.5772, 13.6847),
    }
    
    city_counters = {}
    web_only_count = 0
    
    for p in website_list:
        key = normalize_name(p['nom'])
        if key in matched_keys:
            continue  # Already merged
        
        # Get city coordinates
        city = p.get('ville', '').lower().replace(' ', '').replace('-', '')
        if city not in city_counters:
            city_counters[city] = 0
        
        base_lat, base_lon = city_coords.get(city, (3.8480, 11.5021))
        
        # Offset
        idx = city_counters[city]
        angle = idx * 0.5
        radius = 0.005 + (idx * 0.001)
        lat = base_lat + radius * math.cos(angle)
        lon = base_lon + radius * math.sin(angle)
        city_counters[city] += 1
        
        merged.append({
            'nom': p['nom'],
            'lat': lat,
            'lon': lon,
            'ville': p.get('ville', 'Inconnu'),
            'telephone': p.get('telephone', ''),
            'adresse': p.get('adresse', ''),
            'region': p.get('region', ''),
            'source': 'website_only'
        })
        web_only_count += 1
    
    print(f"  OSM pharmacies: {len(osm_list)}")
    print(f"  Matched with website: {matched}")
    print(f"  Website-only added: {web_only_count}")
    print(f"  TOTAL: {len(merged)}")
    
    return merged


def save_kml(pharmacies, output_file):
    """Save to KML."""
    print(f"\nSaving KML: {output_file}")
    
    kml = ET.Element('kml', xmlns="http://www.opengis.net/kml/2.2")
    doc = ET.SubElement(kml, 'Document')
    
    name = ET.SubElement(doc, 'name')
    name.text = f'Pharmacies Cameroun - COMPLETE ({len(pharmacies)})'
    
    # Styles
    for sid, color in [('osm', 'ff00ff00'), ('merged', 'ff00ffff'), ('website', 'ff0080ff')]:
        style = ET.SubElement(doc, 'Style', id=f'{sid}Style')
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
    
    # Sort by count
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
            if p.get('telephone'): parts.append(f"Tel: {p['telephone']}")
            if p.get('adresse'): parts.append(f"Adresse: {p['adresse']}")
            parts.append(f"Source: {p.get('source', 'osm')}")
            pd.text = '\n'.join(parts)
            
            su = ET.SubElement(pm, 'styleUrl')
            src = p.get('source', 'osm')
            su.text = f'#{src.replace("_only","")}Style'
            
            point = ET.SubElement(pm, 'Point')
            coords = ET.SubElement(point, 'coordinates')
            coords.text = f"{p['lon']},{p['lat']},0"
    
    # Save
    xml_str = ET.tostring(kml, encoding='unicode')
    dom = minidom.parseString(xml_str)
    pretty = '\n'.join([l for l in dom.toprettyxml(indent='  ').split('\n') if l.strip()])
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(pretty)


def main():
    data_dir = 'data'
    
    # Load both
    osm = load_osm_kml(os.path.join(data_dir, 'pharmacies_cameroun.kml'))
    website = load_website_json(os.path.join(data_dir, 'pharmacies_annuaire_medical.json'))
    
    # Merge
    all_pharmacies = merge_all(osm, website)
    
    # Save JSON
    json_out = os.path.join(data_dir, 'pharmacies_FINAL.json')
    with open(json_out, 'w', encoding='utf-8') as f:
        json.dump({
            'created': datetime.now().isoformat(),
            'total': len(all_pharmacies),
            'pharmacies': all_pharmacies
        }, f, indent=2, ensure_ascii=False)
    print(f"\nSaved: {json_out}")
    
    # Save KML
    kml_out = os.path.join(data_dir, 'pharmacies_FINAL.kml')
    save_kml(all_pharmacies, kml_out)
    print(f"Saved: {kml_out}")
    
    # Final stats
    print("\n" + "="*60)
    print("              FINAL DATABASE SUMMARY")
    print("="*60)
    print(f"  TOTAL PHARMACIES: {len(all_pharmacies)}")
    
    by_source = {}
    for p in all_pharmacies:
        s = p.get('source', 'osm')
        by_source[s] = by_source.get(s, 0) + 1
    
    print(f"\n  By source:")
    print(f"    OSM only:      {by_source.get('osm', 0):4}")
    print(f"    Merged:        {by_source.get('merged', 0):4}")
    print(f"    Website only:  {by_source.get('website_only', 0):4}")
    
    # Cities
    cities = {}
    for p in all_pharmacies:
        c = p.get('ville', 'Inconnu')
        cities[c] = cities.get(c, 0) + 1
    
    print(f"\n  TOTAL CITIES: {len(cities)}")
    print(f"\n  TOP 20 CITIES:")
    for city, cnt in sorted(cities.items(), key=lambda x: -x[1])[:20]:
        print(f"    {city:20} {cnt:4}")
    
    print("="*60)


if __name__ == '__main__':
    main()
