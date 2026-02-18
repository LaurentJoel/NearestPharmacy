"""
Cache Module - Redis-backed Caching
=====================================
Uses Flask-Caching with Redis for scalable caching.
Falls back to SimpleCache if Redis is unavailable.

Integration:
    The parent app can configure Redis URL via REDIS_URL env var
    or pass it through init_pharmacy_module().

Cache invalidation:
    Call clear_pharmacy_cache() after the daily scraper runs
    to ensure fresh data is served.
"""
import os
from flask_caching import Cache

# Module-level cache instance
cache = Cache()

# Default cache config — uses Redis if available, falls back to SimpleCache
_default_config = {
    'CACHE_TYPE': 'RedisCache',
    'CACHE_REDIS_URL': os.getenv('REDIS_URL', 'redis://localhost:6379/0'),
    'CACHE_DEFAULT_TIMEOUT': 300,  # 5 minutes default TTL
    'CACHE_KEY_PREFIX': 'pharmacy:',  # Namespace to avoid key collisions with parent app
}


def init_cache(app, redis_url=None):
    """
    Initialize the cache with the Flask app.
    
    Args:
        app: Flask application instance.
        redis_url: Optional Redis URL override.
    
    Falls back to SimpleCache if Redis connection fails.
    """
    config = _default_config.copy()
    
    if redis_url:
        config['CACHE_REDIS_URL'] = redis_url
    
    # Try Redis first, fall back to SimpleCache
    try:
        app.config.update(config)
        cache.init_app(app)
        # Test the connection
        with app.app_context():
            cache.set('_ping', 'pong', timeout=5)
            result = cache.get('_ping')
            if result == 'pong':
                cache.delete('_ping')
                print("[Cache] Redis connected successfully")
                return
    except Exception as e:
        print(f"[Cache] Redis unavailable ({e}), falling back to SimpleCache")
    
    # Fallback to in-memory SimpleCache
    config['CACHE_TYPE'] = 'SimpleCache'
    config.pop('CACHE_REDIS_URL', None)
    app.config.update(config)
    cache.init_app(app)
    print("[Cache] Using SimpleCache (in-memory)")


def make_cache_key_nearby(lat, lon, radius, date_str):
    """
    Create a cache key for nearby pharmacies query.
    Rounds coordinates to 3 decimal places (~100m precision)
    so nearby users share cache hits.
    """
    lat_key = round(lat, 3)
    lon_key = round(lon, 3)
    return f"nearby:{lat_key}:{lon_key}:{radius}:{date_str}"


def make_cache_key_search(lat, lon, radius, limit):
    """Cache key for pharmacy search (all pharmacies, no duty filter)."""
    lat_key = round(lat, 3)
    lon_key = round(lon, 3)
    return f"search:{lat_key}:{lon_key}:{radius}:{limit}"


def clear_pharmacy_cache():
    """
    Clear all pharmacy cache entries.
    Call this after the daily scraper runs to ensure fresh data.
    
    Usage from scraper:
        from app.cache import clear_pharmacy_cache
        clear_pharmacy_cache()
    """
    try:
        cache.clear()
        print("[Cache] All pharmacy cache cleared")
    except Exception as e:
        print(f"[Cache] Warning: could not clear cache: {e}")
