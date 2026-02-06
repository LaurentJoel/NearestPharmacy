
import os

FILE_PATH = r'c:\Users\laure\Desktop\NearestPharmacy\scripts\quick_scraper.py'

try:
    with open(FILE_PATH, 'r', encoding='utf-8') as f:
        content = f.read()

    # Block 1: Match Found
    old_block_1 = """                    cursor.execute(\"\"\"
                        INSERT INTO gardes (pharmacie_id, date_garde, nom_scrape, quarter_scrape, city_scrape)
                        VALUES (%s, CURRENT_DATE, %s, %s, %s)
                        ON CONFLICT (pharmacie_id, date_garde) DO UPDATE 
                        SET nom_scrape = EXCLUDED.nom_scrape, quarter_scrape = EXCLUDED.quarter_scrape, city_scrape = EXCLUDED.city_scrape
                    \"\"\", (pharmacy_id, raw_name, quarter, db_city))"""

    new_block_1 = """                    # Truncate
                    raw_name_trunc = raw_name[:254]
                    quarter_trunc = quarter[:254]
                    db_city_trunc = db_city[:254]

                    cursor.execute(\"\"\"
                        INSERT INTO gardes (pharmacie_id, date_garde, nom_scrape, quarter_scrape, city_scrape)
                        VALUES (%s, CURRENT_DATE, %s, %s, %s)
                        ON CONFLICT (pharmacie_id, date_garde) DO UPDATE 
                        SET nom_scrape = EXCLUDED.nom_scrape, quarter_scrape = EXCLUDED.quarter_scrape, city_scrape = EXCLUDED.city_scrape
                    \"\"\", (pharmacy_id, raw_name_trunc, quarter_trunc, db_city_trunc))"""

    if old_block_1 in content:
        content = content.replace(old_block_1, new_block_1)
        print("Block 1 patched.")
    else:
        print("Block 1 NOT found.")

    # Block 2: No Match
    # Note: Need to verify exact text for No Match block.
    # From Step 1301 view:
    old_block_2 = """                    cursor.execute(\"\"\"
                        SELECT id FROM gardes 
                        WHERE pharmacie_id IS NULL 
                          AND date_garde = CURRENT_DATE 
                          AND nom_scrape = %s
                    \"\"\", (raw_name,))
                    
                    if not cursor.fetchone():
                        cursor.execute(\"\"\"
                            INSERT INTO gardes (pharmacie_id, date_garde, nom_scrape, quarter_scrape, city_scrape)
                            VALUES (NULL, CURRENT_DATE, %s, %s, %s)
                        \"\"\", (raw_name, quarter, db_city))"""

    new_block_2 = """                    # Truncate
                    raw_name_trunc = p['raw_name'][:254]
                    quarter_trunc = p['quarter'][:254]
                    db_city_trunc = db_city[:254]

                    cursor.execute(\"\"\"
                        SELECT id FROM gardes 
                        WHERE pharmacie_id IS NULL 
                          AND date_garde = CURRENT_DATE 
                          AND nom_scrape = %s
                          AND city_scrape = %s
                    \"\"\", (raw_name_trunc, db_city_trunc))
                    
                    if not cursor.fetchone():
                        cursor.execute(\"\"\"
                            INSERT INTO gardes (pharmacie_id, date_garde, nom_scrape, quarter_scrape, city_scrape)
                            VALUES (NULL, CURRENT_DATE, %s, %s, %s)
                        \"\"\", (raw_name_trunc, quarter_trunc, db_city_trunc))"""

    if old_block_2 in content:
        content = content.replace(old_block_2, new_block_2)
        print("Block 2 patched.")
    else:
        # Try simplified match if indent differs slightly
        print("Block 2 NOT found (trying fuzzy?)")

    with open(FILE_PATH, 'w', encoding='utf-8') as f:
        f.write(content)
        
    print("File saved.")

except Exception as e:
    print(f"Error: {e}")
