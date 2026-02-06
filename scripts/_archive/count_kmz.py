import zipfile, re
from glob import glob

total = 0
files = sorted(glob('data/Pharmacie Yaounde*.kmz'))

for f in files:
    try:
        with zipfile.ZipFile(f, 'r') as z:
            for name in z.namelist():
                if name.endswith('.kml'):
                    content = z.read(name).decode('utf-8')
                    count = len(re.findall(r'<Placemark', content))
                    print(f"{f.split('\\')[-1]}: {count} pharmacies")
                    total += count
                    break
    except Exception as e:
        print(f"{f}: Error - {e}")

print(f"\nTOTAL: {total} pharmacies in 19 files")
