"""
Extract park names/addresses from three sources:
  - Seattle: the city's open-data API (the same endpoint
    https://www.seattle.gov/parks/parks#/1 loads its map data from).
  - Shoreline: the city's public ArcGIS Server (the same Feature Service
    behind https://www.shorelinewa.gov 's "Shoreline Parks & Trails" map;
    shorelinewa.gov itself blocks automated fetches, but its GIS server on a
    different host does not). Park addresses come straight from that layer's
    ADDRESS field; since it stores polygons, not points, each park's map
    location is the polygon's area-weighted centroid.
  - Edmonds: scraped live from the city's own "Visit A Park" webpage (its
    GIS layers have no usable address field), then geocoded via the free US
    Census geocoder since the page has no coordinates. A plain default
    User-Agent gets a 403 from this site, so requests use a descriptive
    custom one instead.
  - Bellevue: scraped live from the city's own parks directory page and each
    linked individual park page (~80 of them). Each park page embeds clean
    <meta property="latitude/longitude"> tags and a structured address (the
    Drupal Address field's address-line1/locality/administrative-area/
    postal-code markup) directly — no geocoding needed. A few linked pages
    (e.g. "Beach Parks with Lifeguards") are informational, not actual parks,
    and are skipped since they have no coordinates.
  - Mercer Island: names and coordinates come from a Drupal.settings JSON
    blob embedded in the listing page's <script> tag (feeding an OpenLayers
    map widget) — no geocoding needed there either. That blob has no address
    field, so each park's own page is fetched too, for its schema.org
    PostalAddress microdata (streetAddress/addressLocality/postalCode).
  - Kirkland: kirklandwa.gov itself is blocked by the same kind of WAF as
    shorelinewa.gov (domain-wide, not just this page), so — same fallback as
    Shoreline — its public ArcGIS Server is used instead. That Parks
    FeatureServer mixes named parks with raw open-space parcels (cryptic
    codes like "JU2" as their only name) and a cemetery/pool, so it's
    filtered to CATEGORY='PARKS'. Addresses come straight from the SITEADDR
    field (recased from its all-caps source casing); coordinates are each
    polygon's area-weighted centroid, as with Shoreline.
  - Redmond: its public ArcGIS Server (found directly, without checking the
    city's own webpage first, since a GIS source this clean rarely needs a
    webpage fallback). Its "Parks" layer's d_Status field distinguishes real
    parks (ExD/ExU = Existing Developed/Undeveloped) from ones that don't
    exist yet (Planned/Proposed/Concept), though only the "existing" codes
    appear in the current data. One name ("Redmond Central Connector", a
    trail) repeats across multiple blank-address segments, so — unlike the
    other sources — this one also dedups within its own fetch, not just
    against already-known parks.
  - Medina: same CivicPlus-family CMS as Mercer Island (same embedded
    Drupal.settings map JSON for names/coordinates, same schema.org
    PostalAddress microdata per park page for addresses), so it reuses those
    same parsing helpers rather than duplicating them.

Writes everything to a CSV with a Visited (Y/N) column and a Visited Date
(YYYY-MM-DD) column, then plots it on an interactive map, titled "Seattle
Parks Project" in both the on-map overlay and the browser tab, with the
Seattle city logo (seattle_favicon.png, embedded as a base64 data URI so the
map stays a single self-contained HTML file) as the tab's favicon.

Usage:
    pip install requests folium beautifulsoup4 lxml

    # First run: fetch parks from the API, write the CSV, plot the map.
    python3 seattle_parks_map.py

    # Re-running later: if the CSV already exists, its rows (and your Visited
    # edits) are left untouched in place — only parks not already in the file
    # get appended.
    python3 seattle_parks_map.py

    # Edit the "visited" (Y/N) and "visited_date" (YYYY-MM-DD) columns in
    # seattle_parks.csv by hand, then:
    python3 seattle_parks_map.py --from-csv
    # ^ re-reads the CSV as-is (no API call) and regenerates the map with
    #   visited parks marked green.
"""
from __future__ import annotations

import argparse
import base64
import csv
import html
import json
import re
import sys
import time
from datetime import datetime

import requests

API_URL = "https://data.seattle.gov/resource/ajyh-m2d3.json"
SHORELINE_URL = "https://gis.shorelinewa.gov/server/rest/services/PublicFacing/Parks/MapServer/5/query"
EDMONDS_PAGE_URL = "https://www.edmondswa.gov/government/departments/parks_and_recreation/parks"
CENSUS_GEOCODE_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
MERCER_ISLAND_BASE_URL = "https://www.mercerisland.gov"
MERCER_ISLAND_LIST_URL = "https://www.mercerisland.gov/parksites"
KIRKLAND_URL = "https://maps.kirklandwa.gov/host/rest/services/Parks/FeatureServer/0/query"
KIRKLAND_DIRECTIONALS = {"N", "S", "E", "W", "NE", "NW", "SE", "SW"}
REDMOND_URL = "https://gis.redmond.gov/arcgis/rest/services/PV/Cadastral/MapServer/2/query"
MEDINA_BASE_URL = "https://www.medina-wa.gov"
MEDINA_LIST_URL = "https://www.medina-wa.gov/publicworks/page/city-parks"
BELLEVUE_BASE_URL = "https://bellevuewa.gov"
BELLEVUE_LIST_URL = "https://bellevuewa.gov/city-government/departments/parks/parks-and-trails/parks"
USER_AGENT = "seattle-parks-map-script/1.0 (personal park-tracking project)"
CSV_PATH = "seattle_parks.csv"
MAP_PATH = "seattle_parks_map.html"
MAP_TITLE = "Seattle Parks Project"
FAVICON_PATH = "seattle_favicon.png"
CSV_FIELDS = ["name", "address", "city", "zip_code", "latitude", "longitude", "visited", "visited_date"]
DEFAULT_CITY = "Seattle"

# Visited is a state, not an identity, so it uses the dataviz status palette
# ("good") rather than a categorical hue; not-visited keeps the default
# single-hue blue (palette slot 1) from the original single-category map.
VISITED_COLOR = "#0ca30c"
UNVISITED_COLOR = "#2a78d6"
MARKER_RADIUS = 6  # px


def _is_visited(value: str) -> bool:
    return str(value).strip().upper() == "Y"


def _latest_visited_park(parks: list[dict]) -> dict | None:
    """Return the park with the most recent visited_date, or None if no park has one."""
    dated = [p for p in parks if str(p.get("visited_date", "")).strip()]
    if not dated:
        return None
    return max(dated, key=lambda p: p["visited_date"])


def _format_visited_date(value: str) -> str | None:
    """Parse a CSV visited_date value (YYYY-MM-DD) into "Month D, YYYY" for the
    popup. Returns None if the value is blank."""
    value = str(value).strip()
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").strftime("%B %-d, %Y")


def load_parks_from_csv() -> list[dict]:
    """Read parks back from an existing CSV (e.g. after hand-editing the Visited column)."""
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        return [
            {
                "name": row["name"],
                "address": row["address"],
                "city": row.get("city") or DEFAULT_CITY,
                "zip_code": row["zip_code"],
                "latitude": float(row["latitude"]),
                "longitude": float(row["longitude"]),
                "visited": row.get("visited", "N"),
                "visited_date": row.get("visited_date", ""),
            }
            for row in csv.DictReader(f)
        ]


def _load_existing_parks() -> list[dict]:
    """Same as load_parks_from_csv(), but an absent file just means "no existing rows"."""
    try:
        return load_parks_from_csv()
    except FileNotFoundError:
        return []


def fetch_new_parks(existing_keys: set[tuple[str, str]]) -> list[dict]:
    """Pull parks from the Socrata API, returning only ones not already in existing_keys."""
    resp = requests.get(API_URL, params={"$limit": 1000}, timeout=30)
    resp.raise_for_status()
    rows = resp.json()

    new_parks = []
    skipped = 0
    for row in rows:
        name = row.get("name", "").strip()
        address = row.get("address", "").strip()
        lat, lon = row.get("y_coord"), row.get("x_coord")
        if not name or not lat or not lon:
            skipped += 1
            continue
        if (name, address) in existing_keys:
            continue
        new_parks.append(
            {
                "name": name,
                "address": address,
                "city": DEFAULT_CITY,
                "zip_code": row.get("zip_code", ""),
                "latitude": float(lat),
                "longitude": float(lon),
                "visited": "N",
                "visited_date": "",
            },
        )
    if skipped:
        print(f"Skipped {skipped} row(s) missing a name or coordinates.", file=sys.stderr)
    return new_parks


def _polygon_centroid(rings: list[list[list[float]]]) -> tuple[float, float]:
    """Area-weighted centroid of a polygon's largest ring. Returns (latitude, longitude)."""
    ring = max(rings, key=len)
    area = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(ring, ring[1:]):
        cross = x0 * y1 - x1 * y0
        area += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    area /= 2
    if area == 0:
        lons = [p[0] for p in ring]
        lats = [p[1] for p in ring]
        return sum(lats) / len(lats), sum(lons) / len(lons)
    return cy / (6 * area), cx / (6 * area)


def fetch_new_shoreline_parks(existing_keys: set[tuple[str, str]]) -> list[dict]:
    """Pull named park polygons from Shoreline's public ArcGIS Server, returning only
    ones not already in existing_keys. Each park's location is its polygon centroid,
    since this layer stores boundaries, not points."""
    resp = requests.get(
        SHORELINE_URL,
        params={
            "where": "NAME IS NOT NULL",
            "outFields": "NAME,ADDRESS",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "json",
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    new_parks = []
    skipped = 0
    for feature in data.get("features", []):
        attrs = feature["attributes"]
        name = (attrs.get("NAME") or "").strip()
        address = (attrs.get("ADDRESS") or "").strip()
        rings = feature.get("geometry", {}).get("rings")
        if not name or not rings:
            skipped += 1
            continue
        if (name, address) in existing_keys:
            continue
        lat, lon = _polygon_centroid(rings)
        new_parks.append(
            {
                "name": name,
                "address": address,
                "city": "Shoreline",
                "zip_code": "",
                "latitude": lat,
                "longitude": lon,
                "visited": "N",
                "visited_date": "",
            },
        )
    if skipped:
        print(f"Skipped {skipped} Shoreline row(s) missing a name or geometry.", file=sys.stderr)
    return new_parks


def _parse_edmonds_page(html: str) -> list[tuple[str, str]]:
    """Extract (name, address) pairs from the "Visit A Park" page. Each park is an
    <h3>Name</h3> followed by inline "Address: ..." text (sometimes split across
    nested tags, so this walks sibling nodes rather than relying on a single regex
    match)."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    results = []
    for h3 in soup.find_all("h3"):
        name = h3.get_text(strip=True)
        if not name:
            continue
        addr_parts = []
        found_label = False
        for sib in h3.next_siblings:
            if getattr(sib, "name", None) == "div":
                break
            text = sib.get_text() if hasattr(sib, "get_text") else str(sib)
            if not found_label:
                if "Address:" not in text:
                    continue
                found_label = True
                text = text.split("Address:", 1)[1]
            addr_parts.append(text)
        if not found_label:
            continue
        address = " ".join("".join(addr_parts).replace("\xa0", " ").split())
        results.append((name, address))
    return results


def _geocode_census(address: str, city: str, state: str = "WA") -> tuple[float, float, str] | None:
    """Look up (latitude, longitude, zip) for a one-line address via the free US
    Census geocoder. Returns None if it can't find a match (e.g. an address with
    no house number or an unrecognized cross-street)."""
    resp = requests.get(
        CENSUS_GEOCODE_URL,
        params={"address": f"{address}, {city}, {state}", "benchmark": "Public_AR_Current", "format": "json"},
        timeout=15,
    )
    resp.raise_for_status()
    matches = resp.json()["result"]["addressMatches"]
    if not matches:
        return None
    match = matches[0]
    return match["coordinates"]["y"], match["coordinates"]["x"], match["addressComponents"].get("zip", "")


def fetch_new_edmonds_parks(existing_keys: set[tuple[str, str]]) -> list[dict]:
    """Scrape name/address pairs from Edmonds's own "Visit A Park" page (its GIS
    layers have no usable address field) and geocode each via the free Census
    geocoder, returning only ones not already in existing_keys."""
    resp = requests.get(EDMONDS_PAGE_URL, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()

    new_parks = []
    skipped = 0
    for name, address in _parse_edmonds_page(resp.text):
        if (name, address) in existing_keys:
            continue
        geocoded = _geocode_census(address, "Edmonds")
        if geocoded is None:
            skipped += 1
            continue
        lat, lon, zip_code = geocoded
        new_parks.append(
            {
                "name": name,
                "address": address,
                "city": "Edmonds",
                "zip_code": zip_code,
                "latitude": lat,
                "longitude": lon,
                "visited": "N",
                "visited_date": "",
            },
        )
    if skipped:
        print(f"Skipped {skipped} Edmonds park(s) that couldn't be geocoded.", file=sys.stderr)
    return new_parks


def _bellevue_park_links(html: str) -> list[str]:
    """Extract unique individual park page URLs from the directory listing page."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    pattern = re.compile(r"^/city-government/departments/parks/parks-and-trails/parks/[a-z0-9-]+$")
    hrefs = {a["href"] for a in soup.find_all("a", href=pattern)}
    return [BELLEVUE_BASE_URL + href for href in sorted(hrefs)]


def _parse_bellevue_park_page(html: str) -> dict | None:
    """Extract name/address/coordinates from an individual park page. Returns None
    for non-park informational pages (e.g. "Beach Parks with Lifeguards"), which
    have no latitude/longitude meta tags."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    lat_tag = soup.find("meta", attrs={"property": "latitude"})
    lon_tag = soup.find("meta", attrs={"property": "longitude"})
    if not lat_tag or not lon_tag:
        return None

    title = soup.find("title")
    name = title.get_text().split("|")[0].strip() if title else ""
    if not name:
        return None

    def _field(cls: str) -> str:
        tag = soup.find("span", class_=cls)
        return tag.get_text(strip=True) if tag else ""

    return {
        "name": name,
        "address": _field("address-line1"),
        "city": _field("locality") or "Bellevue",
        "zip_code": _field("postal-code"),
        "latitude": float(lat_tag["content"]),
        "longitude": float(lon_tag["content"]),
    }


def fetch_new_bellevue_parks(existing_keys: set[tuple[str, str]]) -> list[dict]:
    """Scrape Bellevue's parks directory page plus each individual park page it
    links to (~80 of them), returning only ones not already in existing_keys."""
    resp = requests.get(BELLEVUE_LIST_URL, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()
    links = _bellevue_park_links(resp.text)

    new_parks = []
    skipped = 0
    for url in links:
        page = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        page.raise_for_status()
        time.sleep(0.2)
        park = _parse_bellevue_park_page(page.text)
        if park is None:
            skipped += 1
            continue
        if (park["name"], park["address"]) in existing_keys:
            continue
        new_parks.append(
            {
                "name": park["name"],
                "address": park["address"],
                "city": park["city"],
                "zip_code": park["zip_code"],
                "latitude": park["latitude"],
                "longitude": park["longitude"],
                "visited": "N",
                "visited_date": "",
            },
        )
    if skipped:
        print(f"Skipped {skipped} Bellevue page(s) with no park coordinates.", file=sys.stderr)
    return new_parks


def _find_geo_feature_list(obj: object) -> list[dict] | None:
    """Recursively search a decoded Drupal.settings blob for the first list of
    OpenLayers-style features (each with an attributes dict containing
    "field_google_map"), regardless of which layer/view key it's nested under."""
    if isinstance(obj, list) and obj and isinstance(obj[0], dict):
        attrs = obj[0].get("attributes")
        if isinstance(attrs, dict) and "field_google_map" in attrs:
            return obj
    if isinstance(obj, dict):
        values = obj.values()
    elif isinstance(obj, list):
        values = obj
    else:
        return None
    for v in values:
        result = _find_geo_feature_list(v)
        if result is not None:
            return result
    return None


def _parse_civicplus_map_listing(page_html: str, base_url: str) -> list[dict]:
    """Extract deduplicated (name, url, latitude, longitude) entries from a
    Drupal.settings JSON blob embedded in a listing page (feeds an OpenLayers map
    widget; the same parks often appear twice, once per map/list view). Shared by
    Mercer Island and Medina, which run the same CivicPlus-family CMS."""
    marker = "jQuery.extend(Drupal.settings, "
    start = page_html.find(marker)
    if start < 0:
        return []
    data, _ = json.JSONDecoder().raw_decode(page_html, start + len(marker))
    features = _find_geo_feature_list(data) or []

    seen = set()
    parks = []
    for feature in features:
        attrs = feature["attributes"]
        name = html.unescape(attrs.get("title") or "")
        point = re.match(r"POINT \(([-\d.]+) ([-\d.]+)\)", attrs.get("field_google_map") or "")
        href = re.search(r'href="([^"]+)"', attrs.get("name") or "")
        if not name or not point or not href or name in seen:
            continue
        seen.add(name)
        parks.append(
            {
                "name": name,
                "url": base_url + href.group(1),
                "latitude": float(point.group(2)),
                "longitude": float(point.group(1)),
            },
        )
    return parks


def _parse_civicplus_park_page(page_html: str, default_city: str) -> dict:
    """Extract the schema.org PostalAddress microdata from an individual park page
    (same markup convention on both Mercer Island's and Medina's sites)."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(page_html, "html.parser")

    def _field(itemprop: str) -> str:
        tag = soup.find(attrs={"itemprop": itemprop})
        return tag.get_text(strip=True) if tag else ""

    return {
        "address": _field("streetAddress"),
        "city": _field("addressLocality").strip(", ") or default_city,
        "zip_code": _field("postalCode"),
    }


def _fetch_new_civicplus_parks(
    existing_keys: set[tuple[str, str]], list_url: str, base_url: str, default_city: str,
) -> list[dict]:
    """Shared fetch logic for CivicPlus-family sites (Mercer Island, Medina): pull
    names/coordinates from the listing page's embedded map JSON, then each park's
    own page for its address, returning only ones not already in existing_keys."""
    resp = requests.get(list_url, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()

    new_parks = []
    for park in _parse_civicplus_map_listing(resp.text, base_url):
        page = requests.get(park["url"], headers={"User-Agent": USER_AGENT}, timeout=30)
        page.raise_for_status()
        time.sleep(0.2)
        details = _parse_civicplus_park_page(page.text, default_city)
        if (park["name"], details["address"]) in existing_keys:
            continue
        new_parks.append(
            {
                "name": park["name"],
                "address": details["address"],
                "city": details["city"],
                "zip_code": details["zip_code"],
                "latitude": park["latitude"],
                "longitude": park["longitude"],
                "visited": "N",
                "visited_date": "",
            },
        )
    return new_parks


def fetch_new_mercer_island_parks(existing_keys: set[tuple[str, str]]) -> list[dict]:
    """Fetch Mercer Island's parks listing page and each linked park page."""
    return _fetch_new_civicplus_parks(existing_keys, MERCER_ISLAND_LIST_URL, MERCER_ISLAND_BASE_URL, "Mercer Island")


def fetch_new_medina_parks(existing_keys: set[tuple[str, str]]) -> list[dict]:
    """Fetch Medina's parks listing page and each linked park page."""
    return _fetch_new_civicplus_parks(existing_keys, MEDINA_LIST_URL, MEDINA_BASE_URL, "Medina")


def _normalize_kirkland_address(address: str) -> str:
    """Recase an all-caps SITEADDR value (e.g. "15305 119TH AVE NE") into normal
    title case, keeping directional abbreviations (NE, SW, ...) uppercase and
    ordinal suffixes (119TH -> 119th) lowercase."""
    words = []
    for word in address.split():
        if word.upper() in KIRKLAND_DIRECTIONALS:
            words.append(word.upper())
            continue
        ordinal = re.match(r"^(\d+)(ST|ND|RD|TH)$", word, re.IGNORECASE)
        words.append(ordinal.group(1) + ordinal.group(2).lower() if ordinal else word.capitalize())
    return " ".join(words)


def fetch_new_kirkland_parks(existing_keys: set[tuple[str, str]]) -> list[dict]:
    """Pull named park polygons from Kirkland's public ArcGIS Server (kirklandwa.gov
    itself is WAF-blocked, same as shorelinewa.gov), filtered to CATEGORY='PARKS'
    to exclude raw open-space parcels, a cemetery, and a pool. Returns only ones
    not already in existing_keys. Each park's location is its polygon centroid."""
    resp = requests.get(
        KIRKLAND_URL,
        params={
            "where": "CATEGORY='PARKS'",
            "outFields": "PROPNAME,SITEADDR",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "json",
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    new_parks = []
    skipped = 0
    for feature in data.get("features", []):
        attrs = feature["attributes"]
        name = (attrs.get("PROPNAME") or "").strip()
        address = _normalize_kirkland_address((attrs.get("SITEADDR") or "").strip())
        rings = feature.get("geometry", {}).get("rings")
        if not name or not rings:
            skipped += 1
            continue
        if (name, address) in existing_keys:
            continue
        lat, lon = _polygon_centroid(rings)
        new_parks.append(
            {
                "name": name,
                "address": address,
                "city": "Kirkland",
                "zip_code": "",
                "latitude": lat,
                "longitude": lon,
                "visited": "N",
                "visited_date": "",
            },
        )
    if skipped:
        print(f"Skipped {skipped} Kirkland row(s) missing a name or geometry.", file=sys.stderr)
    return new_parks


def fetch_new_redmond_parks(existing_keys: set[tuple[str, str]]) -> list[dict]:
    """Pull park polygons from Redmond's public ArcGIS Server, returning only ones
    not already in existing_keys. One name ("Redmond Central Connector") repeats
    across multiple blank-address segments, so this also dedups within its own
    batch, not just against existing_keys. Each park's location is its polygon
    centroid."""
    resp = requests.get(
        REDMOND_URL,
        params={
            "where": "1=1",
            "outFields": "ParkName,Address",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "json",
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()

    new_parks = []
    seen = set()
    skipped = 0
    for feature in data.get("features", []):
        attrs = feature["attributes"]
        name = (attrs.get("ParkName") or "").strip()
        address = (attrs.get("Address") or "").strip()
        rings = feature.get("geometry", {}).get("rings")
        if not name or not rings:
            skipped += 1
            continue
        key = (name, address)
        if key in existing_keys or key in seen:
            continue
        seen.add(key)
        lat, lon = _polygon_centroid(rings)
        new_parks.append(
            {
                "name": name,
                "address": address,
                "city": "Redmond",
                "zip_code": "",
                "latitude": lat,
                "longitude": lon,
                "visited": "N",
                "visited_date": "",
            },
        )
    if skipped:
        print(f"Skipped {skipped} Redmond row(s) missing a name or geometry.", file=sys.stderr)
    return new_parks


def sync_parks() -> list[dict]:
    """Fetch from all sources. Existing CSV rows are kept exactly as-is (order and
    edits untouched); only parks not already present are appended."""
    existing = _load_existing_parks()
    existing_keys = {(p["name"], p["address"]) for p in existing}
    new_seattle = fetch_new_parks(existing_keys)
    existing_keys |= {(p["name"], p["address"]) for p in new_seattle}
    new_shoreline = fetch_new_shoreline_parks(existing_keys)
    existing_keys |= {(p["name"], p["address"]) for p in new_shoreline}
    new_edmonds = fetch_new_edmonds_parks(existing_keys)
    existing_keys |= {(p["name"], p["address"]) for p in new_edmonds}
    new_bellevue = fetch_new_bellevue_parks(existing_keys)
    existing_keys |= {(p["name"], p["address"]) for p in new_bellevue}
    new_mercer_island = fetch_new_mercer_island_parks(existing_keys)
    existing_keys |= {(p["name"], p["address"]) for p in new_mercer_island}
    new_kirkland = fetch_new_kirkland_parks(existing_keys)
    existing_keys |= {(p["name"], p["address"]) for p in new_kirkland}
    new_redmond = fetch_new_redmond_parks(existing_keys)
    existing_keys |= {(p["name"], p["address"]) for p in new_redmond}
    new_medina = fetch_new_medina_parks(existing_keys)
    new_parks = (
        new_seattle
        + new_shoreline
        + new_edmonds
        + new_bellevue
        + new_mercer_island
        + new_kirkland
        + new_redmond
        + new_medina
    )
    if existing:
        print(f"Found {len(new_parks)} new park(s) to add to the existing {len(existing)}.")
    return existing + new_parks


def write_csv(parks: list[dict]) -> None:
    parks = sorted(parks, key=lambda p: p["name"].lower())
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(parks)
    print(f"Wrote {len(parks)} parks to {CSV_PATH}")


def plot_map(parks: list[dict]) -> None:
    import folium

    avg_lat = sum(p["latitude"] for p in parks) / len(parks)
    avg_lon = sum(p["longitude"] for p in parks) / len(parks)

    m = folium.Map(location=[avg_lat, avg_lon], zoom_start=11, tiles="cartodbpositron")
    m.get_root().title = MAP_TITLE
    try:
        with open(FAVICON_PATH, "rb") as f:
            favicon_b64 = base64.b64encode(f.read()).decode()
        m.get_root().header.add_child(
            folium.Element(f'<link rel="icon" type="image/png" href="data:image/png;base64,{favicon_b64}">'),
        )
    except FileNotFoundError:
        pass
    for p in parks:
        color = VISITED_COLOR if _is_visited(p.get("visited", "N")) else UNVISITED_COLOR
        city_zip = " ".join(part for part in (p["city"], p["zip_code"]) if part)
        address_line = ", ".join(part for part in (p["address"], city_zip) if part)
        popup_html = f"<b>{p['name']}</b><br>{address_line}"
        visited_date = _format_visited_date(p.get("visited_date", ""))
        if visited_date:
            popup_html += f"<br><b>Visited:</b> {visited_date}"
        popup = folium.Popup(popup_html, max_width=250)
        folium.CircleMarker(
            location=[p["latitude"], p["longitude"]],
            radius=MARKER_RADIUS,
            color="#ffffff",
            weight=1,
            fill=True,
            fill_color=color,
            fill_opacity=0.9,
            popup=popup,
        ).add_to(m)

    latest_park = _latest_visited_park(parks)
    latest_html = (
        f'<div style="font-size: 14px; font-weight: 400; margin-top: 4px;">'
        f"<b>Latest park visited:</b> {latest_park['name']}</div>"
        if latest_park
        else ""
    )
    title_html = f"""
    <div style="position: fixed; top: 16px; left: 60px; z-index: 1000;
                background: #fcfcfb; padding: 8px 22px; border: 1px solid #c3c2b7;
                border-radius: 4px; font-family: system-ui, -apple-system, sans-serif;
                font-size: 24px; font-weight: 700; color: #0b0b0b;">
      {MAP_TITLE}
      {latest_html}
    </div>
    """
    m.get_root().html.add_child(folium.Element(title_html))

    legend_html = f"""
    <div style="position: fixed; bottom: 30px; left: 30px; z-index: 1000;
                background: #fcfcfb; padding: 10px 14px; border: 1px solid #c3c2b7;
                border-radius: 4px; font-family: system-ui, -apple-system, sans-serif;
                font-size: 13px; color: #0b0b0b;">
      <div style="margin-bottom:4px;">
        <span style="display:inline-block;width:10px;height:10px;border-radius:50%;
                      background:{VISITED_COLOR};margin-right:6px;"></span>Visited
      </div>
      <div>
        <span style="display:inline-block;width:10px;height:10px;border-radius:50%;
                      background:{UNVISITED_COLOR};margin-right:6px;"></span>Not visited
      </div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    m.save(MAP_PATH)
    visited_count = sum(1 for p in parks if _is_visited(p.get("visited", "N")))
    print(f"Wrote map with {len(parks)} markers ({visited_count} visited) to {MAP_PATH}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--from-csv",
        action="store_true",
        help="Skip the API fetch; read the existing CSV (with your Visited edits) and regenerate the map only.",
    )
    args = parser.parse_args()

    if args.from_csv:
        try:
            parks = load_parks_from_csv()
        except FileNotFoundError:
            print(f"{CSV_PATH} not found — run without --from-csv first.", file=sys.stderr)
            sys.exit(1)
        plot_map(parks)
    else:
        parks = sync_parks()
        if not parks:
            print("No park data retrieved — aborting.", file=sys.stderr)
            sys.exit(1)
        write_csv(parks)
        plot_map(parks)


if __name__ == "__main__":
    main()
