# 🗺️ How to Get All Pharmacies in Cameroon for Google Earth Pro

## ⚠️ Understanding the Challenge

**Google Earth Pro does NOT have a pharmacy database.**

When you search "pharmacies Cameroon" in Google Earth Pro, it shows results from Google Places - but you **cannot bulk export** these results. Google Earth Pro only allows you to:
- View locations on the map
- Create placemarks **one by one** manually

This would take WEEKS to do manually for all pharmacies in Cameroon!

---

## ✅ SOLUTION: Get Data from OpenStreetMap → Import to Google Earth Pro

OpenStreetMap has pharmacies already mapped with GPS coordinates. We can:
1. **Download pharmacy data** from OpenStreetMap (FREE!)
2. **Convert it to KML/KMZ** format
3. **Open in Google Earth Pro** to visualize/edit
4. **Import to PostGIS** for your API

---

## Step-by-Step Guide

### STEP 1: Download Cameroon Pharmacies from OpenStreetMap

**Option A: Use Overpass Turbo (Web Interface)**

1. Go to: https://overpass-turbo.eu/
2. Paste this query:

```
[out:json][timeout:120];
area["ISO3166-1"="CM"][admin_level=2]->.cameroon;
(
  node["amenity"="pharmacy"](area.cameroon);
  way["amenity"="pharmacy"](area.cameroon);
);
out center;
```

3. Click **"Run"** (top left)
4. Wait for results (may take 30-60 seconds)
5. Click **"Export"** → Select **"KML"**
6. Save the file as `pharmacies_cameroon.kml`

**Option B: Use the Script I Created**

```bash
cd NearestPharmacy
python scripts/import_osm_pharmacies.py
```

This creates `data/osm_pharmacies_cameroon.json` with all pharmacies.

---

### STEP 2: Open in Google Earth Pro

1. Open **Google Earth Pro**
2. Go to **File → Open**
3. Select your `pharmacies_cameroon.kml` file
4. All pharmacies will appear as placemarks!

Now you can:
- View all pharmacies on the map
- Edit/delete incorrect entries
- Add new pharmacies manually
- Save as **KMZ** (compressed KML)

---

### STEP 3: Export as KMZ

1. In Google Earth Pro, right-click on your **Pharmacies** folder
2. Select **"Save Place As..."**
3. Choose **KMZ** format
4. Save to `NearestPharmacy/data/pharmacies_cameroon.kmz`

---

### STEP 4: Import KMZ to PostGIS

Use the script I've created:

```bash
python scripts/import_kmz.py data/pharmacies_cameroon.kmz --import
```

---

## 📋 Alternative: Manual Data Collection

If you prefer to manually verify each pharmacy:

### Method 1: Use Google Maps + Export

1. Go to https://www.google.com/maps
2. Search "pharmacy near Yaoundé, Cameroon"
3. For each pharmacy, note:
   - Name
   - Address  
   - GPS coordinates (right-click → "What's here?")
4. Create placemarks in Google Earth Pro
5. Export as KMZ

### Method 2: Field Survey

If data accuracy is critical:
1. Use a GPS app on your phone
2. Visit each pharmacy
3. Record: Name, Address, GPS, Phone
4. Enter data into a spreadsheet
5. Import spreadsheet to Google Earth Pro

---

## Quick Comparison

| Method | Time | Data Quality | GPS Accuracy |
|--------|------|--------------|--------------|
| OpenStreetMap Export | 5 minutes | Good | High |
| Manual Google Earth | Weeks | Excellent | High |
| Field Survey | Months | Perfect | Very High |

**Recommendation**: Start with OpenStreetMap data, then refine in Google Earth Pro!
