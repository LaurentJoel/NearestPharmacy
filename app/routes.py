"""
API Routes - Pharmacy Endpoints
================================
All SQL queries use schema-qualified table names for integration support.
"""
from flask import Blueprint, request, jsonify
from datetime import date
import unicodedata
from .database import get_db_cursor, test_connection, qualified_table
from . import get_module_config


def normalize_city(name):
    """Strip accents and lowercase for accent-insensitive city comparison."""
    if not name:
        return ''
    name = name.lower().strip()
    name = unicodedata.normalize('NFD', name)
    name = ''.join(c for c in name if unicodedata.category(c) != 'Mn')
    return name

api_bp = Blueprint('pharmacy_api', __name__)


@api_bp.route('/health', methods=['GET'])
def health_check():
    """Check API and database health."""
    db_status = test_connection()
    return jsonify({
        'api': 'ok',
        'database': db_status
    })


@api_bp.route('/pharmacies/nearby', methods=['GET'])
def get_nearby_pharmacies():
    """
    Get pharmacies on duty near a given location.
    
    Query Parameters:
        lat (float): User's latitude (required)
        lon (float): User's longitude (required)
        distance_m (int): Search radius in meters (default: 5000)
        date (str): Date in YYYY-MM-DD format (default: today)
    
    Returns:
        JSON with list of nearby pharmacies on duty, sorted by distance
    """
    try:
        # Parse and validate parameters
        user_lat = request.args.get('lat', type=float)
        user_lon = request.args.get('lon', type=float)
        
        if user_lat is None or user_lon is None:
            return jsonify({
                'success': False,
                'error': "Les paramètres 'lat' et 'lon' sont requis."
            }), 400
        
        # Validate coordinate ranges
        if not (-90 <= user_lat <= 90):
            return jsonify({
                'success': False,
                'error': "Latitude doit être entre -90 et 90."
            }), 400
            
        if not (-180 <= user_lon <= 180):
            return jsonify({
                'success': False,
                'error': "Longitude doit être entre -180 et 180."
            }), 400
        
        # Get optional parameters with defaults
        config = get_module_config()
        distance_m = request.args.get('distance_m', type=int, default=config.DEFAULT_SEARCH_RADIUS_M)
        date_str = request.args.get('date', type=str, default=str(date.today()))
        
        # Limit maximum search radius
        distance_m = min(distance_m, config.MAX_SEARCH_RADIUS_M)
        
        # PostGIS query to find nearby pharmacies on duty
        # This query:
        # 1. Creates a point from user's coordinates
        # 2. Joins pharmacies with garde schedules for the given date
        # 3. Filters pharmacies within the search radius
        # 4. Calculates distance and sorts by nearest first
        # PostGIS query to find nearby pharmacies on duty
        # Modified to include Unmatched pharmacies (scraped but no GPS match yet)
        
        # We need two parts matching the same columns for UNION:
        # 1. Matched pharmacies (with distance)
        # 2. Unmatched pharmacies (distance = NULL)
        
        # 1. Infer User's City (to filter unmatched pharmacies)
        # We find the city of the nearest known pharmacy to the user
        
        # Dictionary of coordinates for all Cameroon cities covered by the scraper.
        # Used to infer the user's city when no nearby pharmacy is found in the DB.
        FALLBACK_CITY_COORDS = {
            # Adamaoua
            'Banyo':       (6.7500, 11.8167),
            'Ngaoundéré':  (7.3167, 13.5833),
            # Centre
            'Bafia':       (4.7500, 11.2333),
            'Mbalmayo':    (3.5167, 11.5000),
            'Mbandjock':   (4.4500, 11.9000),
            'Mbankomo':    (3.7833, 11.3833),
            'Obala':       (4.1667, 11.5333),
            'Sa A':        (4.3667, 11.4500),
            'Yaoundé':     (3.8667, 11.5167),
            # Est
            'Abong-Mbang': (3.9833, 13.1833),
            'Batouri':     (4.4333, 14.3667),
            'Bertoua':     (4.5833, 13.6833),
            'Garoua-Boulai': (5.8833, 14.5500),
            # Extrême-Nord
            'Kousseri':    (12.0767, 15.0306),
            'Maga':        (10.8500, 14.9500),
            'Maroua':      (10.5956, 14.3159),
            'Yagoua':      (10.3417, 15.2333),
            # Littoral
            'Douala':      (4.0511, 9.7679),
            'Edea':        (3.8000, 10.1333),
            'Loum':        (4.7167, 9.7333),
            'Mbanga':      (4.5000, 9.5667),
            'Melong':      (5.1167, 9.9500),
            'Nkongsamba':  (4.9500, 9.9333),
            # Nord
            'Figuil':      (9.7583, 13.9667),
            'Garoua':      (9.3000, 13.3833),
            'Guider':      (9.9333, 13.9500),
            'Touboro':     (7.7667, 15.3667),
            # Nord-Ouest
            'Bamenda':     (5.9597, 10.1597),
            'Mbengwy':     (6.1000, 10.0000),
            # Ouest
            'Bafang':      (5.1667, 10.1833),
            'Bafoussam':   (5.4737, 10.4176),
            'Bangangté':   (5.1500, 10.5333),
            'Bandja':      (5.3333, 10.3667),
            'Bandjoun':    (5.3667, 10.4167),
            'Dschang':     (5.4500, 10.0500),
            'Foumban':     (5.7167, 10.8833),
            'Foumbot':     (5.5167, 10.6167),
            'Mbouda':      (5.6333, 10.2500),
            # Sud
            'Ambam':       (2.3833, 11.2833),
            'Ebolowa':     (2.9000, 11.1500),
            'Kribi':       (2.9500, 9.9167),
            'Sangmelima':  (2.9333, 11.9833),
            # Sud-Ouest
            'Buea':        (4.1597, 9.2311),
            'Kumba':       (4.6333, 9.4500),
            'Likomba':     (4.0833, 9.2667),
            'Limbe':       (4.0167, 9.2000),
            'Mutengene':   (4.0917, 9.3083),
            'Muyuka':      (4.2833, 9.4167),
        }
        
        # Step A: Find nearest in DB
        t_pharmacies = qualified_table('pharmacies')
        t_gardes = qualified_table('gardes')
        
        city_inference_query = f"""
            SELECT ville, ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography) as dist_m
            FROM {t_pharmacies} 
            ORDER BY geom <-> ST_SetSRID(ST_MakePoint(%s, %s), 4326) 
            LIMIT 1
        """
        
        inferred_city = None
        min_dist = float('inf')
        
        with get_db_cursor() as cursor:
            cursor.execute(city_inference_query, (user_lon, user_lat, user_lon, user_lat))
            result = cursor.fetchone()
            if result:
                inferred_city = result['ville']
                min_dist = result['dist_m']
        
        # Step B: Check fallback cities (simple Euclidean check is enough for selection, or Haversine)
        # We use a rough approximation or just skip if DB match is very close (< 5km)
        if min_dist > 5000: # If nearest DB match is > 5km away, check fallbacks
            from math import radians, cos, sin, asin, sqrt
            def haversine(lon1, lat1, lon2, lat2):
                R = 6371000 # Radius of earth in meters
                dLat = radians(lat2 - lat1)
                dLon = radians(lon2 - lon1)
                a = sin(dLat/2) * sin(dLat/2) + cos(radians(lat1)) * cos(radians(lat2)) * sin(dLon/2) * sin(dLon/2)
                c = 2 * asin(sqrt(a))
                return R * c

            for city_name, (f_lat, f_lon) in FALLBACK_CITY_COORDS.items():
                dist = haversine(user_lon, user_lat, f_lon, f_lat)
                if dist < min_dist:
                    min_dist = dist
                    inferred_city = city_name
        
        # PostGIS query to find nearby pharmacies on duty
        # Modified to include Unmatched pharmacies ONLY if they match inferred city
        
        sql_query = f"""
            WITH user_location AS (
                SELECT ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography AS geom
            )
            SELECT * FROM (
                -- 1. MATCHED PHARMACIES
                -- Filter by city_scrape to exclude pharmacies with wrong GPS
                -- (some pharmacies from other cities have default Yaoundé coords)
                SELECT 
                    p.id,
                    p.nom,
                    p.adresse,
                    p.telephone,
                    p.ville,
                    ST_Y(p.geom) AS latitude,
                    ST_X(p.geom) AS longitude,
                    ST_Distance(p.geom::geography, u.geom) AS distance_m,
                    g.nom_scrape,
                    g.quarter_scrape,
                    'matched' as type
                FROM 
                    {t_pharmacies} p
                    INNER JOIN {t_gardes} g ON p.id = g.pharmacie_id
                    CROSS JOIN user_location u
                WHERE 
                    g.date_garde = %s
                    AND ST_DWithin(p.geom::geography, u.geom, %s)
                    AND (%s IS NULL OR lower(g.city_scrape) = %s)
                
                UNION ALL
                
                -- 2. UNMATCHED PHARMACIES
                -- Filter by inferred city to avoid showing irrelevant pharmacies
                -- Use approx_lat/approx_lon for approximate positioning on map
                SELECT 
                    NULL as id,
                    g.nom_scrape as nom,
                    g.quarter_scrape as adresse,
                    '' as telephone, 
                    g.city_scrape as ville,
                    g.approx_lat as latitude,
                    g.approx_lon as longitude,
                    CASE WHEN g.approx_lat IS NOT NULL AND g.approx_lon IS NOT NULL
                        THEN ST_Distance(
                            ST_SetSRID(ST_MakePoint(g.approx_lon, g.approx_lat), 4326)::geography,
                            u.geom
                        )
                        ELSE NULL
                    END as distance_m,
                    g.nom_scrape,
                    g.quarter_scrape,
                    'unmatched' as type
                FROM 
                    {t_gardes} g
                    CROSS JOIN user_location u
                WHERE 
                    g.date_garde = %s
                    AND g.pharmacie_id IS NULL
                    AND (%s IS NULL OR lower(g.city_scrape) = %s) -- Filter by city (normalized)
            ) combined_results
            ORDER BY 
                CASE WHEN distance_m IS NULL THEN 1 ELSE 0 END, -- Matched first
                distance_m ASC, -- Then by distance
                nom ASC; -- Unmatched by name
        """
        
        with get_db_cursor() as cursor:
            # Params:
            # 1. user_lon (Point)
            # 2. user_lat (Point)
            # 3. date (Matched)
            # 4. radius (Matched)
            # 5. normalized_city IS NULL check (Matched city filter)
            # 6. normalized_city (Matched city filter)
            # 7. date (Unmatched)
            # 8. normalized_city IS NULL check (Unmatched Filter)
            # 9. normalized_city (Unmatched Filter)
            normalized_inferred = normalize_city(inferred_city) if inferred_city else None
            cursor.execute(sql_query, (
                user_lon, user_lat, 
                date_str, distance_m,
                normalized_inferred, normalized_inferred,
                date_str, 
                normalized_inferred, normalized_inferred
            ))
            rows = cursor.fetchall()
            
            pharmacies = []
            for row in rows:
                dist_m = row['distance_m']
                pharmacies.append({
                    'id': row['id'],
                    'nom': row['nom'],
                    'adresse': row['adresse'],
                    'telephone': row['telephone'],
                    'ville': row['ville'],
                    'latitude': row['latitude'],
                    'longitude': row['longitude'],
                    'distance_m': round(dist_m, 2) if dist_m is not None else None,
                    'type': row['type'],
                    'nom_scrape': row['nom_scrape'],
                    'quarter_scrape': row['quarter_scrape']
                })
        
        return jsonify({
            'success': True,
            'count': len(pharmacies),
            'search_params': {
                'user_lat': user_lat,
                'user_lon': user_lon,
                'radius_m': distance_m,
                'date': date_str
            },
            'pharmacies': pharmacies
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f"Une erreur interne est survenue: {str(e)}"
        }), 500


@api_bp.route('/pharmacies/search', methods=['GET'])
def search_nearby_pharmacies():
    """
    Find ALL nearby pharmacies (regardless of duty status).
    Uses PostGIS ST_Distance for accurate geodesic distance calculation.
    
    Algorithm: Uses geography type for accurate Earth-surface distance (Haversine/Spheroid)
    
    Query Parameters:
        lat (float): User's latitude (required)
        lon (float): User's longitude (required)
        radius (int): Search radius in meters (default: 10000 = 10km)
        limit (int): Maximum results (default: 50)
    
    Returns:
        JSON with list of nearby pharmacies, sorted by distance (nearest first)
    """
    try:
        # Parse and validate parameters
        user_lat = request.args.get('lat', type=float)
        user_lon = request.args.get('lon', type=float)
        
        if user_lat is None or user_lon is None:
            return jsonify({
                'success': False,
                'error': "Les paramètres 'lat' et 'lon' sont requis."
            }), 400
        
        # Validate coordinate ranges
        if not (-90 <= user_lat <= 90):
            return jsonify({
                'success': False,
                'error': "Latitude doit être entre -90 et 90."
            }), 400
            
        if not (-180 <= user_lon <= 180):
            return jsonify({
                'success': False,
                'error': "Longitude doit être entre -180 et 180."
            }), 400
        
        # Get optional parameters
        radius_m = request.args.get('radius', type=int, default=10000)  # Default 10km
        limit = request.args.get('limit', type=int, default=50)
        
        # Limit maximum search radius to 50km
        radius_m = min(radius_m, 50000)
        limit = min(limit, 200)
        
        # PostGIS query using geography type for accurate distance
        # ST_Distance with geography calculates geodesic distance (accounts for Earth's curvature)
        t_pharmacies = qualified_table('pharmacies')
        sql_query = f"""
            SELECT 
                p.id,
                p.nom,
                p.adresse,
                p.telephone,
                p.ville,
                ST_Y(p.geom) AS latitude,
                ST_X(p.geom) AS longitude,
                ST_Distance(
                    p.geom::geography, 
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography
                ) AS distance_m
            FROM 
                {t_pharmacies} p
            WHERE 
                ST_DWithin(
                    p.geom::geography, 
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, 
                    %s
                )
            ORDER BY 
                distance_m ASC
            LIMIT %s;
        """
        
        with get_db_cursor() as cursor:
            cursor.execute(sql_query, (user_lon, user_lat, user_lon, user_lat, radius_m, limit))
            rows = cursor.fetchall()
            
            pharmacies = []
            for row in rows:
                pharmacies.append({
                    'id': row['id'],
                    'nom': row['nom'],
                    'adresse': row['adresse'],
                    'telephone': row['telephone'],
                    'ville': row['ville'],
                    'latitude': row['latitude'],
                    'longitude': row['longitude'],
                    'distance_m': round(row['distance_m'], 2),
                    'distance_km': round(row['distance_m'] / 1000, 2)
                })
        
        return jsonify({
            'success': True,
            'count': len(pharmacies),
            'algorithm': 'PostGIS ST_Distance (geodesic/spheroid)',
            'search_params': {
                'user_lat': user_lat,
                'user_lon': user_lon,
                'radius_m': radius_m,
                'limit': limit
            },
            'pharmacies': pharmacies
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f"Une erreur interne est survenue: {str(e)}"
        }), 500


@api_bp.route('/pharmacies', methods=['GET'])
def get_all_pharmacies():
    """
    Get all pharmacies (optionally filtered by city).
    
    Query Parameters:
        ville (str): Filter by city name (optional)
        limit (int): Maximum number of results (default: 100)
    """
    try:
        ville = request.args.get('ville', type=str)
        limit = request.args.get('limit', type=int, default=100)
        
        t_pharmacies = qualified_table('pharmacies')
        
        if ville:
            sql_query = f"""
                SELECT id, nom, adresse, telephone, ville,
                       ST_Y(geom) AS latitude, ST_X(geom) AS longitude
                FROM {t_pharmacies}
                WHERE LOWER(ville) = LOWER(%s)
                ORDER BY nom
                LIMIT %s;
            """
            params = (ville, limit)
        else:
            sql_query = f"""
                SELECT id, nom, adresse, telephone, ville,
                       ST_Y(geom) AS latitude, ST_X(geom) AS longitude
                FROM {t_pharmacies}
                ORDER BY ville, nom
                LIMIT %s;
            """
            params = (limit,)
        
        with get_db_cursor() as cursor:
            cursor.execute(sql_query, params)
            rows = cursor.fetchall()
            
            pharmacies = []
            for row in rows:
                pharmacies.append({
                    'id': row['id'],
                    'nom': row['nom'],
                    'adresse': row['adresse'],
                    'telephone': row['telephone'],
                    'ville': row['ville'],
                    'latitude': row['latitude'],
                    'longitude': row['longitude']
                })
        
        return jsonify({
            'success': True,
            'count': len(pharmacies),
            'pharmacies': pharmacies
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f"Une erreur interne est survenue: {str(e)}"
        }), 500


@api_bp.route('/gardes', methods=['GET'])
def get_gardes():
    """
    Get pharmacies on duty for a specific date.
    
    Query Parameters:
        date (str): Date in YYYY-MM-DD format (default: today)
        ville (str): Filter by city name (optional)
    """
    try:
        date_str = request.args.get('date', type=str, default=str(date.today()))
        ville = request.args.get('ville', type=str)
        
        t_pharmacies = qualified_table('pharmacies')
        t_gardes = qualified_table('gardes')
        
        if ville:
            sql_query = f"""
                SELECT 
                    p.id, p.nom, p.adresse, p.telephone, p.ville,
                    ST_Y(p.geom) AS latitude, ST_X(p.geom) AS longitude,
                    g.date_garde
                FROM {t_pharmacies} p
                INNER JOIN {t_gardes} g ON p.id = g.pharmacie_id
                WHERE g.date_garde = %s AND LOWER(p.ville) = LOWER(%s)
                ORDER BY p.nom;
            """
            params = (date_str, ville)
        else:
            sql_query = f"""
                SELECT 
                    p.id, p.nom, p.adresse, p.telephone, p.ville,
                    ST_Y(p.geom) AS latitude, ST_X(p.geom) AS longitude,
                    g.date_garde
                FROM {t_pharmacies} p
                INNER JOIN {t_gardes} g ON p.id = g.pharmacie_id
                WHERE g.date_garde = %s
                ORDER BY p.ville, p.nom;
            """
            params = (date_str,)
        
        with get_db_cursor() as cursor:
            cursor.execute(sql_query, params)
            rows = cursor.fetchall()
            
            pharmacies = []
            for row in rows:
                pharmacies.append({
                    'id': row['id'],
                    'nom': row['nom'],
                    'adresse': row['adresse'],
                    'telephone': row['telephone'],
                    'ville': row['ville'],
                    'latitude': row['latitude'],
                    'longitude': row['longitude'],
                    'date_garde': str(row['date_garde'])
                })
        
        return jsonify({
            'success': True,
            'date': date_str,
            'count': len(pharmacies),
            'pharmacies': pharmacies
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f"Une erreur interne est survenue: {str(e)}"
        }), 500
