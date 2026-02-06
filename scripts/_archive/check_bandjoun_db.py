import psycopg2
try:
    conn = psycopg2.connect(host='localhost', dbname='pharmacy_db', user='postgres', password='mkounga10')
    cur = conn.cursor()
    cur.execute("SELECT city_scrape, count(*) FROM gardes WHERE city_scrape ILIKE 'Bandjoun' GROUP BY city_scrape")
    print("Bandjoun DB Entries:", cur.fetchall())
except Exception as e:
    print(e)
