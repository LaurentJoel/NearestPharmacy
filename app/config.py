"""
Application Configuration
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration."""
    
    # Database configuration
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = os.getenv('DB_PORT', '5432')
    DB_NAME = os.getenv('DB_NAME', 'pharmacy_db')
    DB_USER = os.getenv('DB_USER', 'postgres')
    DB_PASSWORD = os.getenv('DB_PASSWORD', 'postgres')
    
    # API configuration
    DEFAULT_SEARCH_RADIUS_M = int(os.getenv('DEFAULT_SEARCH_RADIUS_M', 5000))
    MAX_SEARCH_RADIUS_M = int(os.getenv('MAX_SEARCH_RADIUS_M', 50000))
    
    @classmethod
    def get_db_uri(cls):
        """Get database connection URI."""
        return f"postgresql://{cls.DB_USER}:{cls.DB_PASSWORD}@{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_NAME}"
    
    @classmethod
    def get_db_config(cls):
        """Get database configuration as dict."""
        return {
            'host': cls.DB_HOST,
            'port': cls.DB_PORT,
            'database': cls.DB_NAME,
            'user': cls.DB_USER,
            'password': cls.DB_PASSWORD
        }
