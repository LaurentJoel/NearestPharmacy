
import psycopg2
import requests
import json

print("--- VERIFICATION: BANDJOUN ---")

# 1. Check Database
try:
    conn = psycopg2.connect(host='localhost', dbname='pharmacy_db', user='postgres', password='mkounga10')
    cur = conn.cursor()
    cur.execute("SELECT city_scrape, count(*) FROM gardes WHERE city_scrape ILIKE 'Bandjoun' GROUP BY city_scrape")
    results = cur.fetchall()
    print(f"DB Content for Bandjoun: {results}")
    conn.close()
except Exception as e:
    print(f"DB Error: {e}")

# 2. Check API
try:
    # Bandjoun Coords: 5.35, 10.41
    # Bafoussam Coords: 5.47, 10.41 (For reference)
    url = 'http://localhost:5000/api/pharmacies/nearby'
    params = {'lat': 5.35, 'lon': 10.41, 'radius': 10000}
    
    print(f"Requesting API: {url} with {params}")
    r = requests.get(url, params=params)
    
    if r.status_code == 200:
        data = r.json()
        print(f"API Count: {data.get('count')}")
        print(f"Debug Info: {data.get('debug_info')}")
        
        pharmacies = data.get('pharmacies', [])
        for p in pharmacies:
            print(f" - {p.get('name', 'Unknown')} ({p.get('ville', 'Unknown')})")
            
    else:
        print(f"API Failed: {r.status_code} - {r.text}")

except Exception as e:
    print(f"API Error: {e}")
