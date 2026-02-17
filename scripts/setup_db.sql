-- ============================================
-- Nearest Pharmacy Database Setup Script
-- PostgreSQL with PostGIS Extension
-- ============================================
-- Supports schema-based isolation for integration into a parent app's database.
-- Default schema: 'public' (standalone mode)
-- For integration: change to 'pharmacy' or any custom schema.
--
-- Usage:
--   Standalone:  psql -U postgres -d pharmacy_db -f setup_db.sql
--   Integrated:  psql -U postgres -d parent_db -v schema=pharmacy -f setup_db.sql
-- ============================================

-- Set schema variable (defaults to 'public' if not passed via -v)
\set schema_name :schema
SELECT COALESCE(NULLIF(:'schema', ':schema'), 'public') AS resolved_schema \gset

-- Create database (run as postgres superuser)
-- CREATE DATABASE pharmacy_db;
-- \c pharmacy_db

-- Enable PostGIS extension
CREATE EXTENSION IF NOT EXISTS postgis;

-- Create schema (no-op for 'public')
DO $$
BEGIN
    IF :'resolved_schema' != 'public' THEN
        EXECUTE format('CREATE SCHEMA IF NOT EXISTS %I', :'resolved_schema');
    END IF;
END $$;

-- ============================================
-- TABLE: pharmacies
-- Stores all pharmacy locations in Cameroon
-- ============================================
CREATE TABLE IF NOT EXISTS :resolved_schema.pharmacies (
    id SERIAL PRIMARY KEY,
    nom VARCHAR(255) NOT NULL,
    adresse VARCHAR(255),
    telephone VARCHAR(50),
    ville VARCHAR(100),
    region VARCHAR(100),
    -- PostGIS geometry column for GPS coordinates (WGS84 / SRID 4326)
    geom GEOMETRY(Point, 4326),
    -- Metadata
    source VARCHAR(50) DEFAULT 'manual',  -- 'osm', 'google_places', 'manual'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- TABLE: gardes
-- Stores pharmacy duty schedules
-- ============================================
CREATE TABLE IF NOT EXISTS :resolved_schema.gardes (
    id SERIAL PRIMARY KEY,
    pharmacie_id INTEGER REFERENCES :resolved_schema.pharmacies(id) ON DELETE CASCADE,
    date_garde DATE NOT NULL,
    nom_scrape VARCHAR(255),
    quarter_scrape VARCHAR(255),
    city_scrape VARCHAR(100),
    -- Prevent duplicate entries for matched pharmacies
    UNIQUE(pharmacie_id, date_garde)
);

-- ============================================
-- INDEXES for performance
-- ============================================

-- Spatial index for fast distance queries (VERY IMPORTANT!)
CREATE INDEX IF NOT EXISTS idx_pharmacies_geom ON :resolved_schema.pharmacies USING GIST (geom);

-- Index on pharmacy name for text search
CREATE INDEX IF NOT EXISTS idx_pharmacies_nom ON :resolved_schema.pharmacies (nom);

-- Index on city for filtering
CREATE INDEX IF NOT EXISTS idx_pharmacies_ville ON :resolved_schema.pharmacies (ville);

-- Index on garde date for fast date filtering
CREATE INDEX IF NOT EXISTS idx_gardes_date ON :resolved_schema.gardes (date_garde);

-- Index on pharmacy foreign key
CREATE INDEX IF NOT EXISTS idx_gardes_pharmacie ON :resolved_schema.gardes (pharmacie_id);

-- ============================================
-- SAMPLE DATA for testing (only in standalone/public schema)
-- ============================================

-- Insert sample pharmacies in Yaoundé
INSERT INTO :resolved_schema.pharmacies (nom, adresse, telephone, ville, region, geom, source)
VALUES 
    ('Pharmacie du Centre', 'Avenue Kennedy', '222 23 45 67', 'Yaoundé', 'Centre', 
     ST_SetSRID(ST_MakePoint(11.5021, 3.8480), 4326), 'manual'),
    ('Pharmacie Palais', 'Etoudi Stationnement', '691 54 16 18', 'Yaoundé', 'Centre',
     ST_SetSRID(ST_MakePoint(11.5150, 3.8750), 4326), 'manual'),
    ('Pharmacie Acacias', 'Biyem-Assi Centre', '699 61 96 54', 'Yaoundé', 'Centre',
     ST_SetSRID(ST_MakePoint(11.4850, 3.8350), 4326), 'manual'),
    ('Pharmacie d''Odza', 'Odza', '222 30 51 33', 'Yaoundé', 'Centre',
     ST_SetSRID(ST_MakePoint(11.5350, 3.8250), 4326), 'manual'),
    ('Pharmacie de la Gare', 'Quartier Gare', '233 42 56 78', 'Douala', 'Littoral',
     ST_SetSRID(ST_MakePoint(9.7043, 4.0511), 4326), 'manual'),
    ('Pharmacie Akwa', 'Boulevard de la Liberté', '233 42 89 01', 'Douala', 'Littoral',
     ST_SetSRID(ST_MakePoint(9.6966, 4.0476), 4326), 'manual')
ON CONFLICT DO NOTHING;

-- Insert sample garde schedules for today and tomorrow
INSERT INTO :resolved_schema.gardes (pharmacie_id, date_garde)
SELECT id, CURRENT_DATE FROM :resolved_schema.pharmacies WHERE nom = 'Pharmacie Palais'
ON CONFLICT DO NOTHING;

INSERT INTO :resolved_schema.gardes (pharmacie_id, date_garde)
SELECT id, CURRENT_DATE FROM :resolved_schema.pharmacies WHERE nom = 'Pharmacie Acacias'
ON CONFLICT DO NOTHING;

INSERT INTO :resolved_schema.gardes (pharmacie_id, date_garde)
SELECT id, CURRENT_DATE FROM :resolved_schema.pharmacies WHERE nom = 'Pharmacie Akwa'
ON CONFLICT DO NOTHING;

INSERT INTO :resolved_schema.gardes (pharmacie_id, date_garde)
SELECT id, CURRENT_DATE + 1 FROM :resolved_schema.pharmacies WHERE nom = 'Pharmacie du Centre'
ON CONFLICT DO NOTHING;

INSERT INTO :resolved_schema.gardes (pharmacie_id, date_garde)
SELECT id, CURRENT_DATE + 1 FROM :resolved_schema.pharmacies WHERE nom = 'Pharmacie de la Gare'
ON CONFLICT DO NOTHING;

-- ============================================
-- VERIFY SETUP
-- ============================================
SELECT 'PostGIS Version: ' || PostGIS_Version() AS info;
SELECT 'Total Pharmacies: ' || COUNT(*) FROM :resolved_schema.pharmacies;
SELECT 'Total Gardes: ' || COUNT(*) FROM :resolved_schema.gardes;
SELECT 'Gardes Today: ' || COUNT(*) FROM :resolved_schema.gardes WHERE date_garde = CURRENT_DATE;

-- Show sample data
SELECT 
    p.nom, 
    p.ville, 
    ST_AsText(p.geom) AS coordinates,
    g.date_garde
FROM :resolved_schema.pharmacies p
LEFT JOIN :resolved_schema.gardes g ON p.id = g.pharmacie_id
ORDER BY p.ville, p.nom;
