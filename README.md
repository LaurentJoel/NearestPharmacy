# Nearest Pharmacy Cameroon API

A Flask-based REST API to find the nearest pharmacy on duty (de garde) in Cameroon based on user's GPS location.

## Features

- 🔍 Find nearest pharmacy on duty within a specified radius
- 📍 Uses PostGIS for efficient geospatial queries
- 📅 Daily updated pharmacy duty schedules from annuaire-medical.cm
- 🗺️ Pharmacy locations from OpenStreetMap/Google Earth Pro

## Architecture

```
User's GPS Position → API Request → PostGIS Query → Nearest Pharmacies de Garde
```

## Data Sources

| Data | Source | Update Frequency |
|------|--------|------------------|
| Pharmacy Locations | OpenStreetMap / Google Earth Pro | One-time + manual updates |
| Duty Schedules | annuaire-medical.cm scraping | Daily |
| User Position | Mobile app GPS | Real-time |

## Setup

### Prerequisites

- Python 3.9+
- PostgreSQL 13+ with PostGIS extension
- pip

### Installation

```bash
# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Setup database
psql -U postgres -f scripts/setup_db.sql

# Run the API
python run.py
```

## API Endpoints

### GET /api/pharmacies/nearby

Find pharmacies on duty near a location.

**Parameters:**
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| lat | float | Yes | Latitude |
| lon | float | Yes | Longitude |
| distance_m | int | No | Radius in meters (default: 5000) |
| date | string | No | Date YYYY-MM-DD (default: today) |

**Example:**
```bash
curl "http://localhost:5000/api/pharmacies/nearby?lat=3.848&lon=11.502&distance_m=10000"
```

## Project Structure

```
NearestPharmacy/
├── app/                    # Flask backend (Blueprint module)
│   ├── __init__.py         # Public API: init_pharmacy_module(), create_pharmacy_blueprint()
│   ├── config.py           # PharmacyConfig with schema support
│   ├── database.py         # DB pool & qualified_table() helper
│   └── routes.py           # API endpoints (pharmacy_api blueprint)
├── pharmacy_app/           # Flutter mobile frontend
│   └── lib/
│       ├── main.dart               # Standalone entry point
│       ├── pharmacy_feature.dart   # Barrel export for parent app
│       ├── models/pharmacy.dart    # Pharmacy data model
│       ├── services/pharmacy_service.dart  # API client
│       ├── screens/pharmacy_screen.dart    # Embeddable screen widget
│       └── widgets/pharmacy_card.dart      # Reusable UI components
├── scripts/                # Data collection & maintenance
│   ├── setup_db.sql        # Schema-aware DB setup
│   ├── auto_daily_scraper.py   # Daily duty schedule scraper
│   ├── import_kml.py       # KML data importer
│   ├── import_osm_pharmacies.py # OSM data importer
│   └── cleanup_database.py # DB maintenance
├── data/                   # Pharmacy data (JSON)
├── integration_example.py  # Parent app integration reference
├── requirements.txt
└── run.py                  # Standalone server entry point
```

## License

MIT
