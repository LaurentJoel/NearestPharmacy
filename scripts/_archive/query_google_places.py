"""
Query Google Places API for Pharmacies in All Cameroon Cities
This script automates the "Pharmacy Yaounde", "Pharmacy Douala" searches.

REQUIREMENTS:
1. Google Maps API Key with Places API enabled
2. Get your key at: https://console.cloud.google.com/apis/credentials
3. Enable "Places API" in Google Cloud Console

USAGE:
    set GOOGLE_MAPS_API_KEY=your_api_key_here
    python scripts/query_google_places.py
"""
import requests
import json
import time
import os
from datetime import datetime
from xml.etree import ElementTree as ET
from xml.dom import minidom

# Google Places API endpoint
PLACES_TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
PLACES_NEARBY_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"

# All cities/towns in Cameroon to search
CAMEROON_LOCATIONS = [
    # Major Cities
    {"name": "Yaoundé", "lat": 3.8480, "lon": 11.5021},
    {"name": "Douala", "lat": 4.0511, "lon": 9.7679},
    {"name": "Bamenda", "lat": 5.9527, "lon": 10.1582},
    {"name": "Bafoussam", "lat": 5.4737, "lon": 10.4179},
    {"name": "Garoua", "lat": 9.3014, "lon": 13.3984},
    {"name": "Maroua", "lat": 10.5956, "lon": 14.3159},
    {"name": "Ngaoundéré", "lat": 7.3167, "lon": 13.5833},
    {"name": "Bertoua", "lat": 4.5772, "lon": 13.6847},
    {"name": "Ebolowa", "lat": 2.9000, "lon": 11.1500},
    {"name": "Kribi", "lat": 2.9500, "lon": 9.9000},
    
    # Regional Capitals
    {"name": "Buea", "lat": 4.1594, "lon": 9.2306},
    {"name": "Limbe", "lat": 4.0167, "lon": 9.2000},
    {"name": "Kumba", "lat": 4.6333, "lon": 9.4167},
    {"name": "Nkongsamba", "lat": 4.9500, "lon": 9.9333},
    {"name": "Edéa", "lat": 3.8000, "lon": 10.1333},
    {"name": "Dschang", "lat": 5.4500, "lon": 10.0667},
    {"name": "Foumban", "lat": 5.7333, "lon": 10.9000},
    {"name": "Kousseri", "lat": 12.0833, "lon": 15.0333},
    {"name": "Sangmélima", "lat": 2.9333, "lon": 11.9833},
    
    # Other Important Towns
    {"name": "Bafia", "lat": 4.7500, "lon": 11.2333},
    {"name": "Mbalmayo", "lat": 3.5167, "lon": 11.5000},
    {"name": "Obala", "lat": 4.1667, "lon": 11.5333},
    {"name": "Mbouda", "lat": 5.6333, "lon": 10.2500},
    {"name": "Loum", "lat": 4.7167, "lon": 9.7333},
    {"name": "Guider", "lat": 9.9333, "lon": 13.9500},
    {"name": "Bafang", "lat": 5.1500, "lon": 10.1833},
    {"name": "Foumbot", "lat": 5.5000, "lon": 10.6333},
    {"name": "Ambam", "lat": 2.3833, "lon": 11.2833},
    {"name": "Muyuka", "lat": 4.2833, "lon": 9.4000},
    {"name": "Mutengene", "lat": 4.0833, "lon": 9.3167},
    {"name": "Banyo", "lat": 6.7500, "lon": 11.8167},
    {"name": "Batouri", "lat": 4.4333, "lon": 14.3500},
    {"name": "Meiganga", "lat": 6.5167, "lon": 14.3000},
    {"name": "Tibati", "lat": 6.4667, "lon": 12.6333},
    {"name": "Tiko", "lat": 4.0750, "lon": 9.3600},
    {"name": "Mamfe", "lat": 5.7667, "lon": 9.3000},
    {"name": "Wum", "lat": 6.3833, "lon": 10.0667},
    {"name": "Fundong", "lat": 6.2500, "lon": 10.2667},
    {"name": "Kumbo", "lat": 6.2000, "lon": 10.6667},
    {"name": "Nkambé", "lat": 6.6167, "lon": 10.6667},
    {"name": "Mokolo", "lat": 10.7333, "lon": 13.8000},
    {"name": "Mora", "lat": 11.0500, "lon": 14.1333},
    {"name": "Yagoua", "lat": 10.3333, "lon": 15.2333},
    {"name": "Kaélé", "lat": 10.1000, "lon": 14.4500},
    {"name": "Garoua-Boulaï", "lat": 5.8833, "lon": 14.5500},
    {"name": "Yokadouma", "lat": 3.5167, "lon": 15.0500},
    {"name": "Moloundou", "lat": 2.0500, "lon": 15.2167},
    {"name": "Akonolinga", "lat": 3.7667, "lon": 12.2500},
    {"name": "Nanga-Eboko", "lat": 4.6833, "lon": 12.3667},
]


def get_api_key():
    """Get Google Maps API key from environment."""
    key = os.getenv('GOOGLE_MAPS_API_KEY')
    if not key:
        print("=" * 60)
        print("ERROR: GOOGLE_MAPS_API_KEY not set!")
        print("=" * 60)
        print()
        print("To use this script, you need a Google Maps API key:")
        print()
        print("1. Go to: https://console.cloud.google.com/apis/credentials")
        print("2. Create a new project (or use existing)")
        print("3. Click 'Create Credentials' → 'API Key'")
        print("4. Enable 'Places API' at: https://console.cloud.google.com/apis/library/places-backend.googleapis.com")
        print()
        print("Then run:")
        print("  set GOOGLE_MAPS_API_KEY=your_api_key_here")
        print("  python scripts/query_google_places.py")
        print()
        return None
    return key


def search_pharmacies_text(api_key, query, location=None):
    """
    Search for pharmacies using text query (like "Pharmacy Yaounde").
    This is similar to what you type in Google Earth Pro.
    """
    params = {
        'query': query,
        'key': api_key,
        'language': 'fr',  # French results
    }
    
    if location:
        params['location'] = f"{location['lat']},{location['lon']}"
        params['radius'] = 50000  # 50km radius
    
    results = []
    next_page_token = None
    
    # Google returns up to 60 results (3 pages of 20)
    for page in range(3):
        if page > 0 and next_page_token:
            params['pagetoken'] = next_page_token
            time.sleep(2)  # Required delay for pagination
        
        try:
            response = requests.get(PLACES_TEXT_SEARCH_URL, params=params, timeout=30)
            data = response.json()
            
            if data.get('status') != 'OK':
                if data.get('status') == 'ZERO_RESULTS':
                    break
                print(f"    API Error: {data.get('status')} - {data.get('error_message', '')}")
                break
            
            for place in data.get('results', []):
                results.append({
                    'name': place.get('name', ''),
                    'address': place.get('formatted_address', ''),
                    'lat': place['geometry']['location']['lat'],
                    'lon': place['geometry']['location']['lng'],
                    'place_id': place.get('place_id', ''),
                    'types': place.get('types', []),
                    'rating': place.get('rating'),
                    'user_ratings_total': place.get('user_ratings_total'),
                })
            
            next_page_token = data.get('next_page_token')
            if not next_page_token:
                break
                
        except Exception as e:
            print(f"    Request error: {e}")
            break
    
    return results


def search_all_cities(api_key):
    """Search for pharmacies in all Cameroon cities."""
    all_pharmacies = []
    seen_place_ids = set()  # Avoid duplicates
    
    print("\n" + "=" * 60)
    print("QUERYING GOOGLE PLACES FOR PHARMACIES IN CAMEROON")
    print("=" * 60)
    print(f"Cities to search: {len(CAMEROON_LOCATIONS)}")
    print()
    
    for i, loc in enumerate(CAMEROON_LOCATIONS, 1):
        city = loc['name']
        query = f"Pharmacy {city} Cameroon"
        
        print(f"[{i}/{len(CAMEROON_LOCATIONS)}] Searching: {query}...")
        
        results = search_pharmacies_text(api_key, query, loc)
        
        new_count = 0
        for pharmacy in results:
            if pharmacy['place_id'] not in seen_place_ids:
                seen_place_ids.add(pharmacy['place_id'])
                pharmacy['city'] = city
                all_pharmacies.append(pharmacy)
                new_count += 1
        
        print(f"    Found: {len(results)} results ({new_count} new)")
        
        # Be polite to the API
        time.sleep(0.5)
    
    print()
    print("=" * 60)
    print(f"TOTAL UNIQUE PHARMACIES FOUND: {len(all_pharmacies)}")
    print("=" * 60)
    
    return all_pharmacies


def save_to_json(pharmacies, output_file):
    """Save results to JSON."""
    data = {
        'source': 'Google Places API',
        'created': datetime.now().isoformat(),
        'total': len(pharmacies),
        'pharmacies': pharmacies
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"Saved JSON: {output_file}")


def save_to_kml(pharmacies, output_file):
    """Save results to KML for Google Earth Pro."""
    kml = ET.Element('kml', xmlns="http://www.opengis.net/kml/2.2")
    doc = ET.SubElement(kml, 'Document')
    
    name = ET.SubElement(doc, 'name')
    name.text = f'Pharmacies Cameroon - Google Places ({len(pharmacies)})'
    
    desc = ET.SubElement(doc, 'description')
    desc.text = f'Queried from Google Places API - {datetime.now().strftime("%Y-%m-%d")}'
    
    # Style
    style = ET.SubElement(doc, 'Style', id='pharmacyStyle')
    icon_style = ET.SubElement(style, 'IconStyle')
    color = ET.SubElement(icon_style, 'color')
    color.text = 'ff00ff00'  # Green
    icon = ET.SubElement(icon_style, 'Icon')
    href = ET.SubElement(icon, 'href')
    href.text = 'http://maps.google.com/mapfiles/kml/shapes/pharmacy.png'
    
    # Group by city
    cities = {}
    for p in pharmacies:
        city = p.get('city', 'Unknown')
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
            pn.text = p['name']
            
            pd = ET.SubElement(pm, 'description')
            parts = [f"Address: {p.get('address', 'N/A')}"]
            if p.get('rating'):
                parts.append(f"Rating: {p['rating']} ({p.get('user_ratings_total', 0)} reviews)")
            parts.append(f"City: {p.get('city', 'N/A')}")
            pd.text = '\n'.join(parts)
            
            su = ET.SubElement(pm, 'styleUrl')
            su.text = '#pharmacyStyle'
            
            point = ET.SubElement(pm, 'Point')
            coords = ET.SubElement(point, 'coordinates')
            coords.text = f"{p['lon']},{p['lat']},0"
    
    # Save
    xml_str = ET.tostring(kml, encoding='unicode')
    dom = minidom.parseString(xml_str)
    pretty = '\n'.join([l for l in dom.toprettyxml(indent='  ').split('\n') if l.strip()])
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(pretty)
    
    print(f"Saved KML: {output_file}")


def main():
    print()
    print("=" * 60)
    print("  GOOGLE PLACES PHARMACY SCRAPER FOR CAMEROON")
    print("=" * 60)
    print()
    
    # Get API key
    api_key = get_api_key()
    if not api_key:
        return
    
    print(f"API Key: {api_key[:8]}...{api_key[-4:]}")
    print()
    
    # Search all cities
    pharmacies = search_all_cities(api_key)
    
    if not pharmacies:
        print("No pharmacies found. Check your API key and quota.")
        return
    
    # Save results
    data_dir = 'data'
    os.makedirs(data_dir, exist_ok=True)
    
    json_file = os.path.join(data_dir, 'pharmacies_google_places.json')
    kml_file = os.path.join(data_dir, 'pharmacies_google_places.kml')
    
    save_to_json(pharmacies, json_file)
    save_to_kml(pharmacies, kml_file)
    
    # Print summary
    print()
    print("=" * 60)
    print("SUMMARY BY CITY:")
    print("=" * 60)
    
    cities = {}
    for p in pharmacies:
        city = p.get('city', 'Unknown')
        cities[city] = cities.get(city, 0) + 1
    
    for city, count in sorted(cities.items(), key=lambda x: -x[1])[:20]:
        print(f"  {city:25} {count:4}")
    
    print()
    print("=" * 60)
    print("DONE!")
    print(f"Open in Google Earth Pro: {kml_file}")
    print("=" * 60)


if __name__ == '__main__':
    main()
