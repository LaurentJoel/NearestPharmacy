"""
Integration Example - How to use NearestPharmacy as a feature module
=====================================================================

This file shows how a parent Flask app would integrate the pharmacy feature.
"""
from flask import Flask

# ──────────────────────────────────────────────
# PARENT APP (your main application)
# ──────────────────────────────────────────────

parent_app = Flask(__name__)

# Parent app's own routes
@parent_app.route('/')
def home():
    return {'app': 'My Main App', 'features': ['pharmacy', 'other']}


# ──────────────────────────────────────────────
# OPTION 1: Shared database (recommended)
# The pharmacy tables live in a 'pharmacy' schema
# inside the parent's existing database.
# ──────────────────────────────────────────────

def integrate_option_1():
    from app import create_pharmacy_blueprint, ensure_tables_exist

    # Parent app's existing database config
    parent_db_config = {
        'host': 'localhost',
        'port': '5432',
        'database': 'parent_app_db',  # Your existing DB
        'user': 'postgres',
        'password': 'your_password'
    }

    # Step 1: Create pharmacy tables in the 'pharmacy' schema (safe to call multiple times)
    ensure_tables_exist(db_config=parent_db_config, schema='pharmacy')

    # Step 2: Create and register the pharmacy blueprint
    pharmacy_bp = create_pharmacy_blueprint(
        db_config=parent_db_config,
        schema='pharmacy'
    )
    parent_app.register_blueprint(pharmacy_bp, url_prefix='/pharmacy/api')

    # Now the pharmacy API is available at:
    #   GET /pharmacy/api/pharmacies/nearby?lat=3.848&lon=11.502
    #   GET /pharmacy/api/pharmacies/search?lat=3.848&lon=11.502
    #   GET /pharmacy/api/gardes
    #   GET /pharmacy/api/health


# ──────────────────────────────────────────────
# OPTION 2: Separate database
# The pharmacy module uses its own database.
# ──────────────────────────────────────────────

def integrate_option_2():
    from app import create_pharmacy_blueprint

    pharmacy_bp = create_pharmacy_blueprint(
        db_config={
            'host': 'localhost',
            'port': '5432',
            'database': 'pharmacy_db',  # Separate DB
            'user': 'postgres',
            'password': 'postgres'
        },
        schema='public'  # No need for schema isolation with separate DB
    )
    parent_app.register_blueprint(pharmacy_bp, url_prefix='/pharmacy/api')


# ──────────────────────────────────────────────
# OPTION 3: Use an external connection pool
# For advanced setups with connection pooling.
# ──────────────────────────────────────────────

def integrate_option_3():
    from app import create_pharmacy_blueprint
    from app.database import set_external_pool
    import psycopg2.pool

    # Create a shared connection pool
    pool = psycopg2.pool.ThreadedConnectionPool(
        minconn=2,
        maxconn=10,
        host='localhost',
        port='5432',
        database='parent_app_db',
        user='postgres',
        password='your_password'
    )

    # Inject the pool into the pharmacy module
    set_external_pool(pool)

    pharmacy_bp = create_pharmacy_blueprint(schema='pharmacy')
    parent_app.register_blueprint(pharmacy_bp, url_prefix='/pharmacy/api')


# ──────────────────────────────────────────────
# SCRAPER INTEGRATION
# Run the daily scraper from your parent app's scheduler
# ──────────────────────────────────────────────

def integrate_scraper():
    from scripts.auto_daily_scraper import AutoDailyScraper

    # Option A: Let scraper use parent's DB config
    scraper = AutoDailyScraper(
        db_config={
            'host': 'localhost',
            'port': '5432',
            'dbname': 'parent_app_db',
            'user': 'postgres',
            'password': 'your_password'
        },
        schema='pharmacy'
    )

    # Option B: Pass an existing connection
    # scraper = AutoDailyScraper(db_connection=my_existing_conn, schema='pharmacy')

    # Run the scraper (call this from your scheduler)
    total = scraper.run()
    print(f"Scraped {total} pharmacies on duty today")


# ──────────────────────────────────────────────
# Run the parent app
# ──────────────────────────────────────────────

if __name__ == '__main__':
    integrate_option_1()  # Choose your preferred option
    parent_app.run(debug=True, host='0.0.0.0', port=8000)
