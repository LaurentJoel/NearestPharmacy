"""
Merge User's Yaoundé Pharmacy Files with Existing Data
Extracts 19 KMZ files and merges with pharmacies_FINAL.kml

Rules:
1. Add all new pharmacies from user files
2. Update pharmacies that were "Inconnu" with new coordinates if found
3. Avoid duplicates (same name in Yaoundé) unless coordinates differ significantly
4. Set city to "Yaoundé" for all pharmacies from user files
"""
import zipfile
import re
import json
import os
import tempfile
import math
from xml.etree import ElementTree as ET
from xml.dom import minidom
from datetime import datetime
from glob import glob


def extract_kmz(kmz_path):
    """Extract KML content from KMZ file."""
    try:
        with zipfile.ZipFile(kmz_path, 'r') as z:
            for name in z.namelist():
                if name.endswith('.kml'):
                    with z.open(name) as f:
                        return f.read().decode('utf-8')
    except Exception as e:
        print(f"  Error reading {kmz_path}: {e}")
    return None


def parse_kml_placemarks(kml_content):
    """Parse placemarks from KML content."""
    pharmacies = []
    
    # Use regex for reliability
    placemark_pattern = r'<Placemark[^>]*>(.*?)</Placemark>'
    name_pattern = r'<name[^>]*>(.*?)</name>'
    coords_pattern = r'<coordinates[^>]*>(.*?)</coordinates>'
    desc_pattern = r'<description[^>]*>(.*?)</description>'
    
    for match in re.finditer(placemark_pattern, kml_content, re.DOTALL | re.IGNORECASE):
        pm_content = match.group(1)
        
        # Get name
        name_match = re.search(name_pattern, pm_content, re.IGNORECASE)
        if not name_match:
            continue
        name = name_match.group(1).strip()
        
        # Clean CDATA
        name = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', name, flags=re.DOTALL)
        name = re.sub(r'<[^>]+>', '', name)  # Remove HTML tags
        name = name.strip()
        
        # Skip non-pharmacy entries
        if not name or len(name) < 3:
            continue
        
        # Get coordinates
        coords_match = re.search(coords_pattern, pm_content, re.IGNORECASE)
        if not coords_match:
            continue
        
        coords_text = coords_match.group(1).strip()
        # Handle multiple coordinates (take first point)
        first_coord = coords_text.split()[0] if ' ' in coords_text else coords_text
        parts = first_coord.split(',')
        
        if len(parts) < 2:
            continue
        
        try:
            lon = float(parts[0])
            lat = float(parts[1])
        except ValueError:
            continue
        
        # Get description
        description = ''
        desc_match = re.search(desc_pattern, pm_content, re.DOTALL | re.IGNORECASE)
        if desc_match:
            description = desc_match.group(1).strip()
            description = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', description, flags=re.DOTALL)
            description = re.sub(r'<[^>]+>', ' ', description)
            description = re.sub(r'\s+', ' ', description).strip()
        
        # Extract phone from description
        phone = ''
        phone_match = re.search(r'(\+?237\s*)?([26]\d{2}[\s\-]?\d{2}[\s\-]?\d{2}[\s\-]?\d{2})', description)
        if phone_match:
            phone = phone_match.group(0).strip()
        
        pharmacies.append({
            'nom': name,
            'lat': lat,
            'lon': lon,
            'ville': 'Yaoundé',  # All user files are for Yaoundé
            'telephone': phone,
            'adresse': description[:200] if description else '',
            'source': 'google_earth_user'
        })
    
    return pharmacies


def normalize_name(name):
    """Normalize pharmacy name for comparison."""
    if not name:
        return ''
    name = name.lower()
    name = re.sub(r'[^\w\s]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    # Remove common prefixes
    for prefix in ['pharmacie ', 'pharmacy ', 'pharma ', 'la ', 'de ', 'du ']:
        if name.startswith(prefix):
            name = name[len(prefix):]
    return name.strip()


def coords_are_close(lat1, lon1, lat2, lon2, threshold_m=100):
    """Check if two coordinates are within threshold (meters)."""
    # Approximate distance calculation
    lat_diff = abs(lat1 - lat2) * 111000  # ~111km per degree
    lon_diff = abs(lon1 - lon2) * 111000 * math.cos(math.radians((lat1 + lat2) / 2))
    distance = math.sqrt(lat_diff**2 + lon_diff**2)
    return distance < threshold_m


def load_existing_data(kml_path):
    """Load existing pharmacies from KML file."""
    print(f"Loading existing data: {kml_path}")
    
    with open(kml_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    pharmacies = []
    
    placemark_pattern = r'<Placemark>(.*?)</Placemark>'
    name_pattern = r'<name>(.*?)</name>'
    coords_pattern = r'<coordinates>(.*?)</coordinates>'
    desc_pattern = r'<description>(.*?)</description>'
    style_pattern = r'<styleUrl>(.*?)</styleUrl>'
    
    for match in re.finditer(placemark_pattern, content, re.DOTALL):
        pm_content = match.group(1)
        
        name_match = re.search(name_pattern, pm_content)
        coords_match = re.search(coords_pattern, pm_content)
        desc_match = re.search(desc_pattern, pm_content)
        style_match = re.search(style_pattern, pm_content)
        
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
        style = style_match.group(1) if style_match else ''
        
        # Parse city from description
        city = 'Inconnu'
        city_match = re.search(r'Ville:\s*([^\n<]+)', desc)
        if city_match:
            city = city_match.group(1).strip()
        
        # Parse source
        source = 'osm'
        source_match = re.search(r'Source:\s*([^\n<]+)', desc)
        if source_match:
            source = source_match.group(1).strip()
        
        # Parse phone
        phone = ''
        phone_match = re.search(r'Tel:\s*([^\n<]+)', desc)
        if phone_match:
            phone = phone_match.group(1).strip()
        
        # Parse address
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
    """
    Merge new pharmacies with existing.
    - Update Yaoundé pharmacies that were Inconnu
    - Add new pharmacies not in existing
    - Avoid duplicates (same name + close location)
    """
    print(f"\nMerging {len(new_pharmacies)} new with {len(existing)} existing...")
    
    merged = list(existing)  # Start with existing
    
    # Create lookup for existing pharmacies by normalized name
    existing_lookup = {}
    for i, p in enumerate(merged):
        key = normalize_name(p['nom'])
        if key not in existing_lookup:
            existing_lookup[key] = []
        existing_lookup[key].append(i)
    
    added = 0
    updated = 0
    skipped = 0
    
    for new_p in new_pharmacies:
        new_name = normalize_name(new_p['nom'])
        
        if new_name in existing_lookup:
            # Check if it's a duplicate or should be updated
            found_match = False
            
            for idx in existing_lookup[new_name]:
                existing_p = merged[idx]
                
                # Check if coordinates are close
                if coords_are_close(existing_p['lat'], existing_p['lon'], 
                                   new_p['lat'], new_p['lon'], threshold_m=200):
                    # Same pharmacy, same location - check if we should update
                    if existing_p['ville'] == 'Inconnu' or existing_p['source'] == 'city_center':
                        # Update with new data
                        merged[idx]['lat'] = new_p['lat']
                        merged[idx]['lon'] = new_p['lon']
                        merged[idx]['ville'] = 'Yaoundé'
                        merged[idx]['source'] = 'google_earth_updated'
                        if new_p['telephone']:
                            merged[idx]['telephone'] = new_p['telephone']
                        if new_p['adresse']:
                            merged[idx]['adresse'] = new_p['adresse']
                        updated += 1
                    else:
                        skipped += 1
                    found_match = True
                    break
            
            if not found_match:
                # Same name but different location - add as new
                merged.append(new_p)
                added += 1
        else:
            # New pharmacy - add it
            merged.append(new_p)
            added += 1
            # Update lookup
            if new_name not in existing_lookup:
                existing_lookup[new_name] = []
            existing_lookup[new_name].append(len(merged) - 1)
    
    print(f"  Added: {added}")
    print(f"  Updated: {updated}")
    print(f"  Skipped (duplicates): {skipped}")
    print(f"  Total now: {len(merged)}")
    
    return merged


def save_merged_kml(pharmacies, output_file):
    """Save merged data to KML."""
    print(f"\nSaving to: {output_file}")
    
    kml = ET.Element('kml', xmlns="http://www.opengis.net/kml/2.2")
    doc = ET.SubElement(kml, 'Document')
    
    name = ET.SubElement(doc, 'name')
    name.text = f'Pharmacies Cameroun - UPDATED ({len(pharmacies)})'
    
    desc = ET.SubElement(doc, 'description')
    desc.text = f'Merged with user Yaoundé data - {datetime.now().strftime("%Y-%m-%d %H:%M")}'
    
    # Styles
    styles = [
        ('osmStyle', 'ff00ff00'),           # Green - OSM
        ('mergedStyle', 'ff00ffff'),        # Cyan - Merged
        ('websiteStyle', 'ff0080ff'),       # Orange - Website
        ('userStyle', 'ffff00ff'),          # Magenta - User added
        ('updatedStyle', 'ffffff00'),       # Yellow - Updated
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
            elif 'website' in src:
                su.text = '#websiteStyle'
            else:
                su.text = '#osmStyle'
            
            point = ET.SubElement(pm, 'Point')
            coords = ET.SubElement(point, 'coordinates')
            coords.text = f"{p['lon']},{p['lat']},0"
    
    # Save
    xml_str = ET.tostring(kml, encoding='unicode')
    dom = minidom.parseString(xml_str)
    pretty = '\n'.join([l for l in dom.toprettyxml(indent='  ').split('\n') if l.strip()])
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(pretty)
    
    print(f"  Total pharmacies: {len(pharmacies)}")
    print(f"  Yaoundé: {len(cities.get('Yaoundé', []))}")


def main():
    print("=" * 60)
    print("MERGING USER'S YAOUNDÉ PHARMACY FILES")
    print("=" * 60)
    
    data_dir = 'data'
    
    # Find all user KMZ files
    kmz_pattern = os.path.join(data_dir, 'Pharmacie Yaounde*.kmz')
    kmz_files = glob(kmz_pattern)
    
    print(f"\nFound {len(kmz_files)} user KMZ files")
    
    # Extract pharmacies from all KMZ files
    all_new_pharmacies = []
    
    for kmz_file in sorted(kmz_files):
        print(f"\nProcessing: {os.path.basename(kmz_file)}")
        
        kml_content = extract_kmz(kmz_file)
        if not kml_content:
            continue
        
        pharmacies = parse_kml_placemarks(kml_content)
        print(f"  Found {len(pharmacies)} placemarks")
        
        for p in pharmacies:
            print(f"    - {p['nom'][:50]}")
        
        all_new_pharmacies.extend(pharmacies)
    
    print(f"\n{'='*60}")
    print(f"Total new pharmacies from user files: {len(all_new_pharmacies)}")
    print("=" * 60)
    
    if not all_new_pharmacies:
        print("No pharmacies found in user files!")
        return
    
    # Load existing data
    existing_file = os.path.join(data_dir, 'pharmacies_FINAL.kml')
    existing = load_existing_data(existing_file)
    
    # Merge
    merged = merge_pharmacies(existing, all_new_pharmacies)
    
    # Save
    output_file = os.path.join(data_dir, 'pharmacies_UPDATED.kml')
    save_merged_kml(merged, output_file)
    
    # Also save JSON
    json_file = os.path.join(data_dir, 'pharmacies_UPDATED.json')
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump({
            'created': datetime.now().isoformat(),
            'total': len(merged),
            'pharmacies': merged
        }, f, indent=2, ensure_ascii=False)
    print(f"Saved JSON: {json_file}")
    
    print("\n" + "=" * 60)
    print("DONE!")
    print(f"Open in Google Earth Pro: {output_file}")
    print("=" * 60)


if __name__ == '__main__':
    main()
