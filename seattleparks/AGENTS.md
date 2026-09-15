# seattleparks

A Folium map of every park across Seattle and ~20 neighboring King County cities,
tracking which ones have been visited. Static output (`seattle_parks_map.html`) is
served directly by this GitHub Pages site — there's no build step beyond running
the script below.

## Files

- `seattle_parks.csv` — the source of truth. One row per park: `name, address,
  city, zip_code, latitude, longitude, visited, visited_date`. Generated only by
  `seattle_parks_map.py`; never hand-edit it (see "Correcting data" below).
  Hand-edited `visited`/`visited_date` values are preserved across re-fetches
  (see `sync_parks()` in `seattle_parks_map.py`).
- `seattle_parks_missing_data_backup.csv` — hand-researched corrections/
  additions, applied on top of the main CSV at render time only (see
  "Correcting data" below).
- `seattle_parks_fetch.py` — one `fetch_new_*` function per city/source
  (Socrata API, ArcGIS FeatureServers, scraped directory pages, CivicPlus map
  widgets, ...). City-specific HTML/JSON parsing helpers live next to the fetch
  function that uses them.
- `seattle_parks_helpers.py` — generic, city-agnostic helpers shared by the
  above: HTTP retries, Census geocoding, polygon centroids, all-caps recasing,
  CSV load/exclusion, backup-CSV enrichment.
- `seattle_parks_constants.py` — URLs, regexes, file paths, excluded-name
  keywords.
- `seattle_parks_map.py` — orchestrates fetch → write CSV → render map
  (`main()`); read this file's module docstring first, it documents exactly how
  each city's data is sourced and why.
- `seattle_parks_update.sh` — the actual entry point (`uv run --with folium
  --with beautifulsoup4 --with requests --with tqdm seattle_parks_map.py
  --from-csv`).

## Common commands

```bash
bash seattle_parks_update.sh              # regenerate the map from the existing CSV (no re-fetch)
uv run --with folium --with beautifulsoup4 --with requests --with tqdm \
  seattle_parks_map.py                    # full re-fetch from every city source, then regenerate
```

Use `--from-csv` (i.e. `seattle_parks_update.sh`) whenever only the CSVs
changed — a full fetch is only needed to pick up new parks from the live
sources. Always run through `uv run --with <deps>`, never a bare `python3` or
`pip3 install` (Homebrew's Python blocks bare `pip install` anyway) — folium/
bs4/requests/tqdm aren't installed system-wide, and this project has no
committed venv.

## Correcting data

`seattle_parks.csv` is generated-only — never fix a park's coordinates or
address there by hand. All manual corrections go in
`seattle_parks_missing_data_backup.csv` instead, then regenerate the map via
`seattle_parks_update.sh` to confirm the fix rendered.

To append a correction, add a row with: `in_main_csv=Y`, the original (wrong)
`existing_*` values, the corrected `found_latitude`/`found_longitude` (and
`found_address`/`found_zip` if those changed too, otherwise leave them blank),
a `source_url` used to verify, and a `confidence_note` explaining why the new
value is trusted — cite user confirmation when the user pointed out the
error. Match the file's existing quoting/CRLF style; write with Python's
`csv` module rather than a raw string append.

When verifying a coordinate:

- Check OSM/Nominatim first, matching by exact park name rather than fuzzy/
  nearest-match — fuzzy name matching has produced confidently-wrong pairings
  (e.g. matched a park to another one 17km away).
- A large raw lat/lon distance to a park's OSM point isn't proof of an error:
  check the park's actual OSM way/relation polygon (point-in-polygon, or
  distance to the polygon edge) before flagging, especially for large/
  irregular parks. Several "500m+ discrepancies" turned out to be correct
  once checked against real polygon geometry instead of a centroid.
- Google Maps place pages (`google.com/maps/place/...`) are pure client-side
  JS — fetching the page gets no usable content, not even embedded
  coordinates. If a Google Maps URL surfaces via search with a
  `!3d<lat>!4d<lon>` segment, that's the real pin and is usable; the
  `@lat,lon` segment in the same URL is just the map viewport center, not the
  place location. Prefer OSM Nominatim (name lookup, not bare address),
  Wikipedia infoboxes, or Apple Maps links when Google Maps can't be scraped.
- Don't treat a second source as independent confirmation if it's just
  another mirror of the same underlying open-data export (several Seattle
  "corroborating" sources trace back to the same `data.seattle.gov` feed).
- The city's own dataset can be stale on both coordinates and names — a few
  Seattle parks have been officially renamed since it was last generated
  (e.g. International Children's Park → Donnie Chin International Children's
  Park); don't assume a name mismatch alone means bad data.
- Mercer Island's Mercerdale Park is a known fetch-pipeline gap: the free
  Census geocoder mismatches its address to a street in Ephrata, WA (~150mi
  away), which the fetch script's own city-mismatch check correctly rejects —
  so it's silently skipped on every live fetch and must be carried entirely
  via the backup CSV (`in_main_csv=N`), not fixed in the fetch logic.

## Notes

- Never hand-edit `seattle_parks_map.html`; it's fully regenerated each run.
- New parks are appended, never reordered/rewritten, on top of existing rows —
  a live re-fetch only adds `(name, address)` keys not already present.
- Some cities' addresses are geocoded (US Census geocoder); others come
  straight from ArcGIS point/polygon geometry or embedded map widgets — see
  the module docstring in `seattle_parks_map.py` for which is which per city.
- Base tiles are deliberately plain OpenStreetMap (`folium.TileLayer(
  "OpenStreetMap", opacity=0.7)` added to a `tiles=None` map), not Carto's
  `cartodbpositron` — Carto locked its free tile CDN behind an API key, and
  the user chose OSM specifically to avoid managing one for a personal
  project.
