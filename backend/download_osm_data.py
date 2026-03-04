"""
Download Midwest OSM PBF data for OSRM.
- Cook County (Chicago area): small, used for immediate OSRM processing
- Illinois + surrounding Midwest states: raw PBF only, for future production server use

Run: python download_osm_data.py
"""
import os
import urllib.request
import sys

DEST = os.path.join(os.path.dirname(__file__), "osrm-data")
os.makedirs(DEST, exist_ok=True)

# (filename, url, notes)
DOWNLOADS = [
    # --- Immediate OSRM use (small, fits in Docker Desktop) ---
    (
        "chicago.osm.pbf",
        "https://download.bbbike.org/osm/bbbike/Chicago/Chicago.osm.pbf",
        "Chicago city area      [OSRM-ready, ~50 MB]"
    ),
    # --- Full Midwest raw PBFs (for future production server) ---
    (
        "illinois.osm.pbf",
        "https://download.geofabrik.de/north-america/us/illinois-latest.osm.pbf",
        "Illinois full state    [~343 MB]"
    ),
    (
        "wisconsin.osm.pbf",
        "https://download.geofabrik.de/north-america/us/wisconsin-latest.osm.pbf",
        "Wisconsin              [~170 MB]"
    ),
    (
        "indiana.osm.pbf",
        "https://download.geofabrik.de/north-america/us/indiana-latest.osm.pbf",
        "Indiana                [~120 MB]"
    ),
    (
        "michigan.osm.pbf",
        "https://download.geofabrik.de/north-america/us/michigan-latest.osm.pbf",
        "Michigan               [~350 MB]"
    ),
    (
        "iowa.osm.pbf",
        "https://download.geofabrik.de/north-america/us/iowa-latest.osm.pbf",
        "Iowa                   [~130 MB]"
    ),
    (
        "missouri.osm.pbf",
        "https://download.geofabrik.de/north-america/us/missouri-latest.osm.pbf",
        "Missouri               [~200 MB]"
    ),
    (
        "minnesota.osm.pbf",
        "https://download.geofabrik.de/north-america/us/minnesota-latest.osm.pbf",
        "Minnesota              [~210 MB]"
    ),
    (
        "ohio.osm.pbf",
        "https://download.geofabrik.de/north-america/us/ohio-latest.osm.pbf",
        "Ohio                   [~250 MB]"
    ),
]

def progress(block_num, block_size, total_size):
    downloaded = block_num * block_size
    pct = min(100, downloaded * 100 // total_size) if total_size > 0 else 0
    mb = downloaded / (1024 * 1024)
    sys.stdout.write(f"\r  {mb:.1f} MB  ({pct}%)    ")
    sys.stdout.flush()

def main():
    print("=" * 60)
    print("  Kin — Midwest OSM PBF Downloader")
    print("=" * 60)
    for filename, url, label in DOWNLOADS:
        dest_path = os.path.join(DEST, filename)
        if os.path.exists(dest_path):
            size_mb = os.path.getsize(dest_path) / (1024 * 1024)
            print(f"\n[SKIP] {label}")
            print(f"       Already exists: {filename} ({size_mb:.1f} MB)")
            continue
        print(f"\n[DL]   {label}")
        print(f"       {url}")
        urllib.request.urlretrieve(url, dest_path, reporthook=progress)
        size_mb = os.path.getsize(dest_path) / (1024 * 1024)
        print(f"\n       ✅ Saved: {filename} ({size_mb:.1f} MB)")

    print("\n\n✅ All downloads complete.")
    print("\nNote: chicago.osm.pbf is ready for OSRM processing now.")
    print("      All other .pbf files are stored for future production server use.")

if __name__ == "__main__":
    main()
