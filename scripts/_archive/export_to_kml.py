"""
Export Cameroon Pharmacies to KML for Google Earth Pro
This script fetches pharmacies from OpenStreetMap and creates a KML file
that you can open in Google Earth Pro!

Usage:
    python export_to_kml.py
    
Then open the generated file in Google Earth Pro to visualize and edit.
"""
import requests
import xml.etree.ElementTree as ET
from xml.dom import minidom
import os
import sys
from datetime import datetime

# Overpass API endpoint
OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def fetch_cameroon_pharmacies() -> list:
    """Fetch all pharmacies in Cameroon from OpenStreetMap."""
    print("Fetching pharmacies from OpenStreetMap...")
    print("This may take 1-2 minutes...")
    
    query = """
    [out:json][timeout:180];
    area["ISO3166-1"="CM"][admin_level=2]->.cameroon;
    (
      node["amenity"="pharmacy"](area.cameroon);
      way["amenity"="pharmacy"](area.cameroon);
    );
    out center;
    """
    
    try:
        response = requests.post(
            OVERPASS_URL,
            data={'data': query},
            timeout=200
        )
        response.raise_for_status()
        
        data = response.json()
        elements = data.get('elements', [])
        
        print(f"✓ Found {len(elements)} pharmacies!")
        return elements
        
    except requests.RequestException as e:
        print(f"Error fetching from OpenStreetMap: {e}")
        return []


def parse_osm_element(element: dict) -> dict:
    """Parse OSM element into pharmacy dict."""
    tags = element.get('tags', {})
    
    # Get coordinates
    if element['type'] == 'node':
        lat = element.get('lat')
        lon = element.get('lon')
    else:
        center = element.get('center', {})
        lat = center.get('lat')
        lon = center.get('lon')
    
    if not lat or not lon:
        return None
    
    return {
        'name': tags.get('name', 'Pharmacie'),
        'address': tags.get('addr:street', '') or tags.get('address', ''),
        'phone': tags.get('phone', '') or tags.get('contact:phone', ''),
        'city': tags.get('addr:city', '') or tags.get('addr:town', ''),
        'lat': lat,
        'lon': lon,
        'osm_id': element.get('id')
    }


def create_kml(pharmacies: list, output_path: str):
    """
    Create a KML file from pharmacy data.
    
    This KML can be opened in Google Earth Pro!
    """
    print(f"\nCreating KML file with {len(pharmacies)} pharmacies...")
    
    # KML namespace
    kml_ns = "http://www.opengis.net/kml/2.2"
    
    # Create root element
    kml = ET.Element('kml', xmlns=kml_ns)
    document = ET.SubElement(kml, 'Document')
    
    # Document name and description
    name = ET.SubElement(document, 'name')
    name.text = 'Pharmacies du Cameroun'
    
    desc = ET.SubElement(document, 'description')
    desc.text = f'Pharmacies exportées depuis OpenStreetMap - {datetime.now().strftime("%Y-%m-%d %H:%M")}'
    
    # Create pharmacy icon style
    style = ET.SubElement(document, 'Style', id='pharmacyStyle')
    icon_style = ET.SubElement(style, 'IconStyle')
    icon = ET.SubElement(icon_style, 'Icon')
    href = ET.SubElement(icon, 'href')
    href.text = 'http://maps.google.com/mapfiles/kml/shapes/pharmacy.png'
    scale = ET.SubElement(icon_style, 'scale')
    scale.text = '1.0'
    
    # Group by city (create folders)
    cities = {}
    for p in pharmacies:
        city = p.get('city', 'Inconnu') or 'Inconnu'
        if city not in cities:
            cities[city] = []
        cities[city].append(p)
    
    # Create folder for each city
    for city_name, city_pharmacies in sorted(cities.items()):
        folder = ET.SubElement(document, 'Folder')
        folder_name = ET.SubElement(folder, 'name')
        folder_name.text = f'{city_name} ({len(city_pharmacies)} pharmacies)'
        
        # Add placemarks for each pharmacy
        for pharmacy in city_pharmacies:
            placemark = ET.SubElement(folder, 'Placemark')
            
            # Name
            pm_name = ET.SubElement(placemark, 'name')
            pm_name.text = pharmacy['name']
            
            # Description with structured data
            pm_desc = ET.SubElement(placemark, 'description')
            desc_parts = []
            if pharmacy.get('address'):
                desc_parts.append(f"Address: {pharmacy['address']}")
            if pharmacy.get('phone'):
                desc_parts.append(f"Phone: {pharmacy['phone']}")
            if pharmacy.get('city'):
                desc_parts.append(f"City: {pharmacy['city']}")
            desc_parts.append(f"OSM ID: {pharmacy.get('osm_id', 'N/A')}")
            pm_desc.text = '\n'.join(desc_parts)
            
            # Style reference
            style_url = ET.SubElement(placemark, 'styleUrl')
            style_url.text = '#pharmacyStyle'
            
            # Point coordinates
            point = ET.SubElement(placemark, 'Point')
            coords = ET.SubElement(point, 'coordinates')
            coords.text = f"{pharmacy['lon']},{pharmacy['lat']},0"
    
    # Pretty print XML
    xml_str = ET.tostring(kml, encoding='unicode')
    dom = minidom.parseString(xml_str)
    pretty_xml = dom.toprettyxml(indent='  ')
    
    # Remove extra blank lines
    lines = [line for line in pretty_xml.split('\n') if line.strip()]
    pretty_xml = '\n'.join(lines)
    
    # Write to file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(pretty_xml)
    
    print(f"✓ KML file created: {output_path}")
    print(f"\nCities included: {len(cities)}")
    for city, pharmas in sorted(cities.items(), key=lambda x: -len(x[1]))[:10]:
        print(f"  - {city}: {len(pharmas)} pharmacies")


def main():
    print("=" * 60)
    print("OpenStreetMap → Google Earth Pro KML Exporter")
    print("=" * 60)
    print()
    print("This script will:")
    print("1. Fetch all pharmacies in Cameroon from OpenStreetMap")
    print("2. Create a KML file you can open in Google Earth Pro")
    print()
    print("-" * 60)
    
    # Fetch pharmacies
    osm_data = fetch_cameroon_pharmacies()
    
    if not osm_data:
        print("No pharmacies found or error occurred")
        return
    
    # Parse elements
    pharmacies = []
    for element in osm_data:
        parsed = parse_osm_element(element)
        if parsed:
            pharmacies.append(parsed)
    
    print(f"Parsed {len(pharmacies)} pharmacies with valid coordinates")
    
    # Create output path
    output_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'data'
    )
    os.makedirs(output_dir, exist_ok=True)
    
    output_path = os.path.join(output_dir, 'pharmacies_cameroun.kml')
    
    # Create KML
    create_kml(pharmacies, output_path)
    
    print()
    print("=" * 60)
    print("NEXT STEPS:")
    print("=" * 60)
    print()
    print("1. Open Google Earth Pro")
    print("2. Go to File → Open")
    print(f"3. Select: {output_path}")
    print("4. All pharmacies will appear on the map!")
    print()
    print("You can now:")
    print("  - View all pharmacies")
    print("  - Edit/delete incorrect entries")
    print("  - Add new pharmacies manually")
    print("  - Save as KMZ (File → Save Place As)")
    print()
    print("After editing, import to database with:")
    print("  python scripts/import_kmz.py data/your_file.kmz --import")


if __name__ == '__main__':
    main()
