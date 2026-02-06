"""
Database Connection and Utilities
"""
import psycopg2
from psycopg2 import extras
from contextlib import contextmanager
from .config import Config


@contextmanager
def get_db_connection():
    """
    Context manager for database connections.
    Automatically handles connection closing.
    
    Usage:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query)
    """
    conn = None
    try:
        conn = psycopg2.connect(**Config.get_db_config())
        yield conn
    finally:
        if conn:
            conn.close()


@contextmanager
def get_db_cursor(commit=False):
    """
    Context manager for database cursors with DictCursor.
    
    Args:
        commit: If True, commits the transaction after cursor closes
    
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
            
            return {
                'status': 'connected',
                'postgresql': pg_version,
                'postgis': postgis_version
            }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e)
        }
