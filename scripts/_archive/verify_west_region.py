
import requests
import json

def check_city(name, lat, lon):
    print(f"\n--- CHECKING {name.upper()} ({lat}, {lon}) ---")
    url = 'http://localhost:5000/api/pharmacies/nearby'
    try:
        r = requests.get(url, params={'lat': lat, 'lon': lon, 'radius': 10000})
        if r.status_code == 200:
            d = r.json()
            print(f"Count: {d.get('count')}")
            print(f"Debug Info: {d.get('debug_info')}")
            
            for p in d.get('pharmacies', []):
                print(f"  - {p.get('nom', 'Unknown')}")
        else:
            print(f"Error: {r.status_code}")
    except Exception as e:
        print(f"Exception: {e}")

# Bandjoun
check_city("Bandjoun", 5.35, 10.41)

# Bangangté
check_city("Bangangte", 5.14, 10.52)
