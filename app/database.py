"""
Database Connection and Utilities
=================================
Supports both standalone connections and shared DB from a parent app.
The parent app can inject a connection pool via init_pharmacy_module().
"""
import psycopg2
from psycopg2 import extras
from contextlib import contextmanager


# ─── External connection pool (set by parent app) ───
_external_pool = None


def set_external_pool(pool):
    """
    Set an external connection pool (e.g., psycopg2.pool or SQLAlchemy engine).
    When set, get_db_connection() will use this pool instead of creating new connections.
    
    Args:
        pool: A connection pool with getconn()/putconn() methods,
              or an object with connect() method.
    """
    global _external_pool
    _external_pool = pool


def _get_config():
    """Get the module config (avoids circular imports)."""
    from . import get_module_config
    return get_module_config()


def get_schema():
    """Get the current schema name for table-qualified queries."""
    return _get_config().DB_SCHEMA


def qualified_table(table_name):
    """
    Return a schema-qualified table name.
    
    Args:
        table_name: The base table name (e.g., 'pharmacies').
    
    Returns:
        str: Schema-qualified name (e.g., 'pharmacy.pharmacies' or 'public.pharmacies').
    """
    schema = get_schema()
    return f"{schema}.{table_name}"


@contextmanager
def get_db_connection():
    """
    Context manager for database connections.
    Uses external pool if set, otherwise creates a new psycopg2 connection.
    
    Usage:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
    """
    global _external_pool
    conn = None
    from_pool = False
    
    try:
        if _external_pool is not None:
            # Try pool-style getconn()
            if hasattr(_external_pool, 'getconn'):
                conn = _external_pool.getconn()
                from_pool = True
            # Try engine-style connect()
            elif hasattr(_external_pool, 'connect'):
                conn = _external_pool.connect()
            else:
                conn = psycopg2.connect(**_get_config().get_db_config())
        else:
            conn = psycopg2.connect(**_get_config().get_db_config())
        
        # Set search_path to include the module schema
        schema = get_schema()
        if schema != 'public':
            cursor = conn.cursor()
            cursor.execute(f"SET search_path TO {schema}, public")
            cursor.close()
        
        yield conn
    finally:
        if conn:
            if from_pool and hasattr(_external_pool, 'putconn'):
                _external_pool.putconn(conn)
            else:
                conn.close()


@contextmanager
def get_db_cursor(commit=False):
    """
    Context manager for database cursors with DictCursor.
    
    Args:
        commit: If True, commits the transaction after cursor closes.
    
    Usage:
        with get_db_cursor() as cursor:
            cursor.execute(query)
            results = cursor.fetchall()
    """
    with get_db_connection() as conn:
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        try:
            yield cursor
            if commit:
                conn.commit()
        finally:
            cursor.close()


def test_connection():
    """Test database connection and PostGIS availability."""
    try:
        with get_db_cursor() as cursor:
            # Check PostgreSQL version
            cursor.execute("SELECT version();")
            pg_version = cursor.fetchone()[0]
            
            # Check PostGIS version
            cursor.execute("SELECT PostGIS_Version();")
            postgis_version = cursor.fetchone()[0]
            
            # Check schema
            schema = get_schema()
            
            return {
                'status': 'connected',
                'postgresql': pg_version,
                'postgis': postgis_version,
                'schema': schema
            }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }
