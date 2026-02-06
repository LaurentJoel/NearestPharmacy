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
├── app/                    # Flask application
│   ├── __init__.py
│   ├── config.py
│   ├── database.py
│   └── routes.py
├── scripts/                # Data collection & setup
│   ├── setup_db.sql
│   ├── scrape_gardes.py
│   └── import_osm_pharmacies.py
├── data/                   # Data files
├── flutter_test_app/       # Flutter test client
├── requirements.txt
└── run.py
```

## License

MIT
