"""Quick summary of pharmacy database"""
import json

with open('data/pharmacies_complete.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

pharmacies = data['pharmacies']
cities = {}
for p in pharmacies:
    city = p['ville']
    cities[city] = cities.get(city, 0) + 1

osm_count = sum(1 for p in pharmacies if p.get('coord_source') == 'osm')
city_count = sum(1 for p in pharmacies if p.get('coord_source') == 'city_center')

print("=" * 55)
print("        PHARMACY DATABASE SUMMARY")
print("=" * 55)
print(f"\n  TOTAL PHARMACIES: {len(pharmacies)}")
print(f"  TOTAL CITIES: {len(cities)}")
print(f"\n  Coordinates from OSM (exact): {osm_count}")
print(f"  Coordinates from city center: {city_count}")
print("\n" + "=" * 55)
print("        PHARMACIES PER CITY (sorted by count)")
print("=" * 55)

for city, count in sorted(cities.items(), key=lambda x: -x[1]):
    bar = "█" * count
    print(f"  {city:20} {count:3}  {bar}")

print("\n" + "=" * 55)
