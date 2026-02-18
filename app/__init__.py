"""
Pharmacy Module - Flask Blueprint Package
==========================================
This module can be used standalone OR integrated into a parent Flask app.

Standalone usage:
    from app import create_app
    app = create_app()
    app.run()

Integration into a parent app:
    from app import create_pharmacy_blueprint, init_pharmacy_module, ensure_tables_exist

    # Option A: Let the module use the parent's DB
    ensure_tables_exist(db_config={...}, schema='pharmacy')
    bp = create_pharmacy_blueprint(db_config={...}, schema='pharmacy')
    parent_app.register_blueprint(bp, url_prefix='/pharmacy/api')

    # Option B: Let the module manage its own DB connection
    bp = create_pharmacy_blueprint(
        db_config={'host': 'localhost', 'port': '5432', 'database': 'pharmacy_db',
                   'user': 'postgres', 'password': 'postgres'},
        schema='pharmacy'
    )
    parent_app.register_blueprint(bp, url_prefix='/pharmacy/api')
"""
from flask import Flask
from .config import PharmacyConfig


# ─── Module-level state (set during init) ───
_module_config = None


def get_module_config():
    """Get the current module configuration. Must call init_pharmacy_module first."""
    global _module_config
    if _module_config is None:
        # Fallback to default config (standalone mode)
        _module_config = PharmacyConfig()
    return _module_config


def init_pharmacy_module(config=None, db_config=None, schema='public'):
    """
    Initialize the pharmacy module with external configuration.
    Call this BEFORE registering the blueprint when integrating into a parent app.

    Args:
        config: A PharmacyConfig instance, or None to use defaults.
        db_config: Database connection dict with keys: host, port, database, user, password.
                   If provided, overrides config's DB settings.
        schema: PostgreSQL schema name for pharmacy tables (default: 'public').
    
    Returns:
        PharmacyConfig: The resolved configuration object.
    """
    global _module_config

    if config is not None:
        _module_config = config
    else:
        _module_config = PharmacyConfig()

    # Override DB config if provided externally
    if db_config:
        _module_config.DB_HOST = db_config.get('host', _module_config.DB_HOST)
        _module_config.DB_PORT = db_config.get('port', _module_config.DB_PORT)
        _module_config.DB_NAME = db_config.get('database', _module_config.DB_NAME)
        _module_config.DB_USER = db_config.get('user', _module_config.DB_USER)
        _module_config.DB_PASSWORD = db_config.get('password', _module_config.DB_PASSWORD)

    _module_config.DB_SCHEMA = schema

    return _module_config


def create_pharmacy_blueprint(db_config=None, schema='public', url_prefix=None, redis_url=None):
    """
    Create and return the pharmacy Flask Blueprint, ready to register on any Flask app.

    Args:
        db_config: Optional dict with DB connection params (host, port, database, user, password).
        schema: PostgreSQL schema for pharmacy tables (default: 'public').
        url_prefix: URL prefix for the blueprint routes (can also be set at register time).
        redis_url: Optional Redis URL for caching (default: redis://localhost:6379/0).

    Returns:
        flask.Blueprint: The configured pharmacy API blueprint.
    
    Usage in parent app:
        bp = create_pharmacy_blueprint(db_config={...}, schema='pharmacy')
        app.register_blueprint(bp, url_prefix='/pharmacy/api')
        
        # After registering, init cache in parent app:
        from app.cache import init_cache
        init_cache(parent_app, redis_url='redis://localhost:6379/1')
    """
    # Initialize module config
    config = init_pharmacy_module(db_config=db_config, schema=schema)
    
    if redis_url:
        config.REDIS_URL = redis_url

    # Import routes (this creates the blueprint)
    from .routes import api_bp
    return api_bp


def ensure_tables_exist(db_config=None, schema='pharmacy'):
    """
    Create the pharmacy tables if they don't exist.
    Safe to call multiple times (uses IF NOT EXISTS).

    Args:
        db_config: Optional dict with DB connection params. Uses module config if not provided.
        schema: PostgreSQL schema name (default: 'pharmacy').
    """
    from .database import get_db_connection

    if db_config:
        init_pharmacy_module(db_config=db_config, schema=schema)

    config = get_module_config()
    s = config.DB_SCHEMA

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Create schema
        cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {s}")

        # Enable PostGIS
        cursor.execute("CREATE EXTENSION IF NOT EXISTS postgis")

        # Create pharmacies table
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {s}.pharmacies (
                id SERIAL PRIMARY KEY,
                nom VARCHAR(255) NOT NULL,
                adresse VARCHAR(255),
                telephone VARCHAR(50),
                ville VARCHAR(100),
                region VARCHAR(100),
                geom GEOMETRY(Point, 4326),
                source VARCHAR(50) DEFAULT 'manual',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create gardes table
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {s}.gardes (
                id SERIAL PRIMARY KEY,
                pharmacie_id INTEGER REFERENCES {s}.pharmacies(id) ON DELETE CASCADE,
                date_garde DATE NOT NULL,
                nom_scrape VARCHAR(255),
                quarter_scrape VARCHAR(255),
                city_scrape VARCHAR(100),
                UNIQUE(pharmacie_id, date_garde)
            )
        """)

        # Create indexes
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_pharm_geom ON {s}.pharmacies USING GIST (geom)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_pharm_nom ON {s}.pharmacies (nom)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_pharm_ville ON {s}.pharmacies (ville)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_gardes_date ON {s}.gardes (date_garde)")
        cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_gardes_pharmacie ON {s}.gardes (pharmacie_id)")

        conn.commit()
        cursor.close()

    print(f"Pharmacy tables ensured in schema '{s}'")


def create_app(config=None):
    """
    Create a standalone Flask application (for running the module independently).
    
    Args:
        config: Optional PharmacyConfig instance.
    
    Returns:
        Flask: Configured Flask application.
    """
    app = Flask(__name__)

    resolved_config = init_pharmacy_module(config=config, schema='public')
    app.config.from_object(resolved_config)

    # Initialize Redis cache
    from .cache import init_cache
    init_cache(app, redis_url=resolved_config.REDIS_URL)

    # Register pharmacy blueprint
    from .routes import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')

    # Health check route
    @app.route('/')
    def health():
        return {
            'status': 'ok',
            'service': 'Nearest Pharmacy API',
            'version': '2.0.0',
            'mode': 'standalone'
        }

    return app
