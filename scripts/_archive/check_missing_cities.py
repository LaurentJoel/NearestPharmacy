
import psycopg2

cities = ['Bandjoun', 'Bangangté', 'Bafang', 'Foumban', 'Foumbot']
print(f"Checking cities: {cities}")

try:
    conn = psycopg2.connect(host='localhost', dbname='pharmacy_db', user='postgres', password='mkounga10')
    cur = conn.cursor()
    
    for city in cities:
        # Check if city exists in pharmacies table
        cur.execute("SELECT count(*) FROM pharmacies WHERE ville ILIKE %s", (f"%{city}%",))
        count = cur.fetchone()[0]
        print(f" - {city}: {count} pharmacies")
        
    conn.close()

except Exception as e:
    print(f"Error: {e}")
