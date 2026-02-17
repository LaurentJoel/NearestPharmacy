# Pharmacy Data Directory

This directory contains data files for the Nearest Pharmacy API.

## Files

| File                      | Description                                     |
| ------------------------- | ----------------------------------------------- |
| `pharmacies_UPDATED.json` | Main pharmacy dataset (merged from all sources) |

## Data Sources

### 1. OpenStreetMap

Run the import script to fetch all pharmacies from OpenStreetMap:

```bash
python scripts/import_osm_pharmacies.py
```

### 2. Google Earth Pro (Manual)

If you prefer to manually curate pharmacies:

1. Create placemarks in Google Earth Pro
2. Export as KML file
3. Place the KML file in this directory
4. Run: `python scripts/import_kml.py`
