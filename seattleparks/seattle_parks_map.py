"""
Extract park names/addresses from these sources:
  - Seattle: the city's open-data API (the same endpoint
    https://www.seattle.gov/parks/parks#/1 loads its map data from).
  - Shoreline: the city's public ArcGIS Server (the same Feature Service
    behind https://www.shorelinewa.gov 's "Shoreline Parks & Trails" map;
    shorelinewa.gov itself blocks automated fetches, but its GIS server on a
    different host does not). Park addresses come straight from that layer's
    ADDRESS field; since it stores polygons, not points, each park's map
    location is the polygon's area-weighted centroid.
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
  - Burien: scraped live from the city's own parks directory page (CivicLive,
    same CMS family as Bellevue, but a different markup convention: no
    per-field classes at all — just the page's own <h2 class="pageTitle">
    for the name, the next plain <h2> for the address, and an embedded
    Google Maps iframe URL for coordinates (!2d<lon>!3d<lat>) — no geocoding
    needed.
  - Tukwila: its own ArcGIS Server (maps.tukwilawa.gov) is unreachable (TLS
    cert expired, and the Web Adaptor itself reports "Could not access any
    GIS Server machines" even bypassing that), likely a decommissioned
    "legacy" system, so scraped live from the city's own parks directory page
    instead. The park name is each page's plain <h1>; the address is plain
    text after a "Location:" label (no consistent class/tag — sometimes bare
    text, sometimes wrapped in a Google Maps link), bounded by the enclosing
    </p> and any trailing \xa0. No coordinates anywhere on the page, so each
    address is geocoded via the free US Census geocoder.
  - Renton: its public ArcGIS Server, found directly. The "Parks" layer has
    direct Latitude/Longitude fields (no centroid/geocoding needed), but it's
    a regional facilities dataset covering several neighboring jurisdictions
    too (Seattle, King County, Tukwila, Newcastle, Kent, SeaTac all appear in
    the OWNER field alongside Renton), so it's filtered to OWNER='Renton'.
    The LOCATION field is inconsistently formatted ("<name> - <address>" most
    of the time, but sometimes a different alias name, a bare description, or
    equal to NAME with no real address at all), so it's parsed leniently
    rather than dropped when imperfect. A couple of exact-duplicate records
    exist in the source data, so — like Redmond — this also dedups within
    its own batch, not just against existing_keys.
  - SeaTac: seatacwa.gov itself is blocked by the same Akamai WAF as
    Shoreline/Kirkland (domain-wide), so its public ArcGIS Server is used
    instead — found directly, cleanly split into Name/Address/City/Zipcode
    fields, all owned by "City of SeaTac" (no regional-dataset filtering
    needed, unlike Renton), with direct point geometry. Addresses are in the
    same all-caps SITEADDR style as Kirkland's layer, so it reuses that same
    recasing helper.
  - Kent: its public ArcGIS Server, found via its Open Data Hub's dataset
    metadata (the Hub catalog itself doesn't list a parks dataset, but one
    dataset's ArcGIS GeoService distribution URL revealed the underlying
    org's REST services directory, which does have a dedicated parks point
    layer). Direct point geometry and a clean parkname/address field pair;
    addresses are all-caps like Kirkland/SeaTac's, so this reuses the same
    recasing helper. Both "developed" and "undeveloped" status parks are
    included — both represent real, currently-existing park properties.
  - Des Moines: desmoineswa.gov's own "Parks" page is just a redirect to a
    static PDF map, no structured data, so its public ArcGIS Server is used
    instead. The "Des Moines Parks By Class" point layer has direct point
    geometry and clean names, filtered to ParkType='CITY' to drop schools/
    state/county land, but has no address field of its own; a separate "City
    Parks" polygon layer has a SiteAddress field but it's only populated on a
    handful of records, so addresses are a best-effort join between the two
    layers by name (with periods/whitespace stripped, since the layers don't
    always spell a park's name identically) — most parks end up with a blank
    address. One name ("Des Moines Creek Trail") repeats across two points,
    so this also dedups within its own batch.
  - Federal Way: scraped live from the city's own "Our Parks" page, which is
    fetchable (no WAF) and lists every park as an accordion item with a
    "Location:" line and Google/Bing map links. Most entries' Bing link
    encodes direct point coordinates (cp=<lat>~<lon>), used as-is with no
    geocoding; a handful lack that (e.g. Olympic View Park has coordinates but
    no clean street address, so its address is left blank) or lack coordinates
    entirely, in which case the Location address is geocoded via the free US
    Census geocoder instead. One park (BPA Trail) has neither a street address
    nor coordinates and is skipped.
  - Auburn: its own public ArcGIS Server, found indirectly — auburnwa.gov's
    parks page embeds an ArcGIS Experience Builder app, whose item metadata
    (via the ArcGIS Online sharing API) reveals a "City of Auburn Parks" web
    map, whose operational-layer URL is the city's own GIS server, not
    ArcGIS Online. That "Parks" layer stores polygons, not points (so each
    park's location is its polygon centroid, as with Kirkland/Shoreline), is
    entirely owned by "COA" (no regional-dataset filtering needed), and has
    both a short NAME and a fuller, more readable FULLNAME per park — FULLNAME
    is used since it's always populated and never abbreviated. Name and
    address are both in the same all-caps style as Kirkland/SeaTac/Kent, so
    this reuses that same recasing helper.
  - Lake Forest Park: its ArcGIS Online organization, found via its Hub open-
    data site's dataset metadata (the same discovery path as Kent/SeaTac);
    the org's full service catalog (browsed directly, since the Hub page
    itself doesn't list it) has a "Parks_Map_WFL1" service with a small,
    clean "Park_Boundary" polygon layer (only 7 named city parks — this is a
    small city — with clean SITENAME/Address fields, no jurisdiction or
    status field needed). A second layer in the same service is an exact
    duplicate of the first and is ignored. Addresses already include a
    ", Lake Forest Park, WA <zip>" suffix that's split off into the
    city/zip_code columns, same as Federal Way's page-scraped addresses.
    Each park's location is its polygon centroid, as with Kirkland/Shoreline/
    Auburn.
  - Kenmore: kenmorewa.gov itself is blocked by the same Akamai WAF as
    Shoreline/Kirkland/SeaTac, but its parks page embeds an ArcGIS Experience
    Builder "Parks Tour" app; that app's item metadata (via the ArcGIS Online
    sharing API) led to a web map, whose operational-layer URL is the city's
    own ArcGIS Server on a separate gwa.kenmorewa.gov host (not WAF-blocked).
    That "Parks" layer is a regional dataset (its own description says so)
    spanning multiple agencies — state parks, WDFW, King County, Seattle
    Public Utilities, and a private marina all appear in its OWNER field
    alongside the city itself — so it's filtered to OWNER='City of Kenmore'.
    Several names have embedded newlines from the source editor (e.g. "Jack
    Crawford \nSkate Park"), collapsed to single spaces. The layer has no
    address field at all, so address is left blank for every park here.
    Polygon geometry, so each park's location is its centroid, as with
    Kirkland/Shoreline/Auburn/Lake Forest Park.
  - Bothell: scraped live from the city's own parks directory page and each
    linked individual park page (~23 of them), rather than its ArcGIS Server
    (found, but its "BothellParks" layer is stale — last edited 2017 — and is
    missing 4 parks that are on the live site today, plus it has 2 garbage
    rows, a duplicate, and several blank addresses). The directory's own
    left-nav accordion (scoped to the Parks page's child pages specifically,
    so it can't pick up unrelated site links) gives the exact current list;
    each park's own page has a clean "Address" heading followed by a bullet
    list whose first item is the street address, geocoded via the free US
    Census geocoder (no coordinates anywhere on either the directory or
    individual pages).
  - Woodinville: its "Facilities" booking page (a CivicPlus widget) only
    renders 5 of the city's facilities by default (the rest are paginated
    behind a JS-driven AJAX search with no working plain-GET or query-string
    override found), and 2 of those 5 aren't parks at all (a community center
    and a plaza) — so rather than fight that pagination, this hits each
    facility's own detail page directly by ID (/Facilities/Facility/Details/
    {id}, which resolves fine without the name slug in the URL). The city
    states it has exactly "three community and five neighborhood parks," and
    those 8 IDs were found by direct enumeration and cross-checked against
    that count, so they're hardcoded rather than re-discovered by crawling a
    paginated listing every run. Each detail page has a clean name (the
    page's first <h2>) and a schema.org/hCard address (street-address/
    locality/postal-code spans); two parks' addresses are only a street name
    with no house number (Tanglin Ridge Park, Stonehill Meadows Park), so
    those are expected to fail Census geocoding and be skipped.

Dog parks, cemeteries, and gyms are excluded from every source (by a
name-keyword check applied after fetching, not per-source) — this project
tracks parks in the traditional sense, not off-leash areas, burial grounds,
or standalone fitness facilities. One exception: Seattle's Grand Army of the
Republic Cemetery is kept. Any "center" (community center, rec center, senior
center, etc.) is excluded the same way, since those are recreation facilities
rather than parkland, unless "Park" also appears in the name (e.g. a park
that happens to house a community center building) or the city is Seattle
(Seattle Parks & Recreation's own facilities, like Amy Yee Tennis Center, are
kept regardless).

seattle_parks_missing_data_backup.csv is a hand-researched (web search)
supplementary source for parks whose primary source had no address, or no
coordinates at all. At render time only -- never written back to
seattle_parks.csv -- it fills in blank addresses for parks already present
(matched by name+city) and adds parks missing entirely from the main CSV when
it found usable coordinates. Kept separate from the main CSV because each
city's live fetch dedups on (name, address); baking a backup-found address
into seattle_parks.csv would break that check on the next sync and cause the
live source to re-add the same park with its own (blank) address.

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
CENSUS_GEOCODE_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
MERCER_ISLAND_BASE_URL = "https://www.mercerisland.gov"
MERCER_ISLAND_LIST_URL = "https://www.mercerisland.gov/parksites"
KIRKLAND_URL = "https://maps.kirklandwa.gov/host/rest/services/Parks/FeatureServer/0/query"
ALLCAPS_ADDRESS_DIRECTIONALS = {"N", "S", "E", "W", "NE", "NW", "SE", "SW"}
REDMOND_URL = "https://gis.redmond.gov/arcgis/rest/services/PV/Cadastral/MapServer/2/query"
MEDINA_BASE_URL = "https://www.medina-wa.gov"
MEDINA_LIST_URL = "https://www.medina-wa.gov/publicworks/page/city-parks"
BELLEVUE_BASE_URL = "https://bellevuewa.gov"
BELLEVUE_LIST_URL = "https://bellevuewa.gov/city-government/departments/parks/parks-and-trails/parks"
BURIEN_BASE_URL = "https://www.burienwa.gov"
BURIEN_LIST_URL = "https://www.burienwa.gov/residents/parks_recreation_cultural_services/city_parks_trails_facilities"
TUKWILA_LIST_URL = "https://www.tukwilawa.gov/departments/parks-and-recreation/parks-and-trails/"
RENTON_URL = "https://gismaps.rentonwa.gov/as03/rest/services/Operational/ParksAndRecreation/MapServer/9/query"
SEATAC_URL = "https://services3.arcgis.com/DLryYCwhA8W7Jq7Q/ArcGIS/rest/services/Parks/FeatureServer/0/query"
KENT_URL = "https://services3.arcgis.com/AME2ELqJ7UG0JjrU/ArcGIS/rest/services/KentParkPoints_view/FeatureServer/0/query"
DES_MOINES_PARKS_URL = "https://maps.desmoineswa.gov/dmgis/rest/services/ParksAndRec/ParksMap/MapServer/1/query"
DES_MOINES_ADDRESS_URL = "https://maps.desmoineswa.gov/dmgis/rest/services/ParksAndRec/ParksMap/MapServer/2/query"
FEDERAL_WAY_URL = "https://www.federalwaywa.gov/page/our-parks"
AUBURN_URL = "https://gis.auburnwa.gov/hosting/rest/services/Administration/BoundariesB/MapServer/0/query"
LAKE_FOREST_PARK_URL = "https://services7.arcgis.com/LD3i16TenysvoOyS/arcgis/rest/services/Parks_Map_WFL1/FeatureServer/14/query"
KENMORE_URL = "https://gwa.kenmorewa.gov/arcgis/rest/services/Parks/FeatureServer/20/query"
BOTHELL_BASE_URL = "https://www.bothellwa.gov"
BOTHELL_LIST_URL = "https://www.bothellwa.gov/250/Parks"
WOODINVILLE_DETAIL_URL = "https://www.woodinville.gov/Facilities/Facility/Details/{}"
WOODINVILLE_PARK_IDS = (4, 5, 6, 7, 14, 15, 16, 17)
EXCLUDED_NAME_KEYWORDS = ("dog park", "cemetery", "cemetary", "gym")
EXCLUDED_NAME_EXCEPTIONS = {("Grand Army of the Republic Cemetery", "Seattle")}


def _is_excluded_name(name: str, city: str) -> bool:
    """True if this park should be dropped: a blanket-excluded keyword (dog
    parks, cemeteries), unless it's an explicit (name, city) exception, or a
    standalone center -- e.g. a community/rec/senior center, a recreation
    facility rather than parkland -- unless "park" also appears in the name
    or the city is Seattle (Seattle Parks & Recreation's own facilities, like
    Amy Yee Tennis Center, are kept regardless)."""
    if (name, city) in EXCLUDED_NAME_EXCEPTIONS:
        return False
    lower = name.lower()
    if any(kw in lower for kw in EXCLUDED_NAME_KEYWORDS):
        return True
    return "center" in lower and "park" not in lower and city != "Seattle"
USER_AGENT = "seattle-parks-map-script/1.0 (personal park-tracking project)"
CSV_PATH = "seattle_parks.csv"
BACKUP_CSV_PATH = "seattle_parks_missing_data_backup.csv"
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


def _latest_visited_parks(parks: list[dict]) -> list[dict]:
    """Return all parks sharing the most recent visited_date, or [] if no park has one."""
    dated = [p for p in parks if str(p.get("visited_date", "")).strip()]
    if not dated:
        return []
    latest_date = max(p["visited_date"] for p in dated)
    return [p for p in dated if p["visited_date"] == latest_date]


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


def _apply_backup_data(parks: list[dict]) -> list[dict]:
    """Enrich `parks` for display using seattle_parks_missing_data_backup.csv (hand
    researched via web search for parks whose primary source had no address, or
    no coordinates at all): fills in blank addresses for parks already present
    (matched by name+city) when the backup found one, and adds parks that are
    entirely missing from the main CSV (in_main_csv='N') when the backup found
    usable coordinates. This never writes back to seattle_parks.csv -- it's
    applied fresh at render time only, so the primary CSV's (name, address)
    dedup keys, which each city's live fetch depends on to avoid re-adding
    parks on the next sync, are never disturbed by backup-sourced values."""
    try:
        with open(BACKUP_CSV_PATH, newline="", encoding="utf-8") as f:
            backup_rows = list(csv.DictReader(f))
    except FileNotFoundError:
        return parks

    enriched = [dict(p) for p in parks]
    by_key = {(p["name"], p["city"]): p for p in enriched}

    for row in backup_rows:
        key = (row["name"], row["city"])
        found_address = (row.get("found_address") or "").strip()
        found_zip = (row.get("found_zip") or "").strip()
        found_lat = (row.get("found_latitude") or "").strip()
        found_lon = (row.get("found_longitude") or "").strip()

        if row.get("in_main_csv") == "Y":
            park = by_key.get(key)
            if park is not None and not park["address"] and found_address:
                park["address"] = found_address
                if found_zip:
                    park["zip_code"] = found_zip
        elif row.get("in_main_csv") == "N" and key not in by_key and found_lat and found_lon:
            new_park = {
                "name": row["name"],
                "address": found_address,
                "city": row["city"],
                "zip_code": found_zip,
                "latitude": float(found_lat),
                "longitude": float(found_lon),
                "visited": "N",
                "visited_date": "",
            }
            enriched.append(new_park)
            by_key[key] = new_park

    return [p for p in enriched if not _is_excluded_name(p["name"], p["city"])]


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


def _normalize_allcaps_text(text: str) -> str:
    """Recase an all-caps value (e.g. "15305 119TH AVE NE", "VAN DOREN'S LANDING")
    into normal title case: directional abbreviations (NE, SW, ...) stay uppercase,
    ordinal suffixes (119TH -> 119th) go lowercase, and (unlike str.title())
    apostrophes don't cause a following letter to capitalize ("DOREN'S" ->
    "Doren's", not "Doren'S"). Shared by Kirkland/SeaTac (addresses) and Kent
    (addresses and park names), whose ArcGIS layers all store text this way."""
    words = []
    for word in text.split():
        if word.upper() in ALLCAPS_ADDRESS_DIRECTIONALS:
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
        address = _normalize_allcaps_text((attrs.get("SITEADDR") or "").strip())
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


def _burien_park_links(page_html: str) -> list[str]:
    """Extract unique individual park page URLs from the directory listing page's
    sidebar navigation."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(page_html, "html.parser")
    pattern = re.compile(
        r"^/residents/parks_recreation_cultural_services/city_parks_trails_facilities/[a-z0-9_]+/$",
    )
    hrefs = {a["href"] for a in soup.find_all("a", href=pattern)}
    return [BURIEN_BASE_URL + href for href in sorted(hrefs)]


def _parse_burien_park_page(page_html: str) -> dict | None:
    """Extract name/address/coordinates from an individual park page. The markup has
    no per-field classes: the name is the page's <h2 class="pageTitle">, the address
    is the next plain <h2>, and coordinates come from an embedded Google Maps iframe
    URL (query params !2d<lon>!3d<lat>). Returns None if title or coordinates are
    missing."""
    title_match = re.search(r'<h2 class="pageTitle">([^<]+)</h2>', page_html)
    if not title_match:
        return None
    name = html.unescape(title_match.group(1)).strip()
    if not name:
        return None

    point_match = re.search(r"!2d(-?[\d.]+)!3d(-?[\d.]+)", page_html)
    if not point_match:
        return None

    address_match = re.search(r"<h2>([^<]+)</h2>", page_html)
    address = html.unescape(address_match.group(1)).strip() if address_match else ""

    return {
        "name": name,
        "address": address,
        "latitude": float(point_match.group(2)),
        "longitude": float(point_match.group(1)),
    }


def fetch_new_burien_parks(existing_keys: set[tuple[str, str]]) -> list[dict]:
    """Scrape Burien's parks directory page plus each individual park page it links
    to (~30 of them), returning only ones not already in existing_keys."""
    resp = requests.get(BURIEN_LIST_URL, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()

    new_parks = []
    skipped = 0
    for url in _burien_park_links(resp.text):
        page = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        page.raise_for_status()
        time.sleep(0.2)
        park = _parse_burien_park_page(page.text)
        if park is None:
            skipped += 1
            continue
        if (park["name"], park["address"]) in existing_keys:
            continue
        new_parks.append(
            {
                "name": park["name"],
                "address": park["address"],
                "city": "Burien",
                "zip_code": "",
                "latitude": park["latitude"],
                "longitude": park["longitude"],
                "visited": "N",
                "visited_date": "",
            },
        )
    if skipped:
        print(f"Skipped {skipped} Burien page(s) with no park coordinates.", file=sys.stderr)
    return new_parks


def _tukwila_park_links(page_html: str) -> list[str]:
    """Extract unique individual park page URLs from the directory listing page."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(page_html, "html.parser")
    pattern = re.compile(
        r"^https://www\.tukwilawa\.gov/departments/parks-and-recreation/parks-and-trails/[a-z0-9-]+/$",
    )
    hrefs = {a["href"] for a in soup.find_all("a", href=pattern)}
    return sorted(hrefs)


def _parse_tukwila_park_page(page_html: str) -> tuple[str, str] | None:
    """Extract (name, address) from an individual park page. The name is the plain
    <h1>; the address follows a "Location:" label in the body with no consistent
    markup (sometimes bare text, sometimes wrapped in a Google Maps link), so this
    scans raw HTML after the label, bounded by the enclosing </p> (a new paragraph
    always starts the park description) and any trailing \xa0 within it."""
    title_match = re.search(r"<h1>([^<]+)</h1>", page_html)
    if not title_match:
        return None
    name = html.unescape(title_match.group(1)).strip()
    if not name:
        return None

    body = page_html[title_match.end() :]
    location_idx = body.find("Location:")
    if location_idx < 0:
        return name, ""
    window = body[location_idx + len("Location:") : location_idx + len("Location:") + 600]
    p_end = window.find("</p>")
    if p_end >= 0:
        window = window[:p_end]
    window = re.sub(r"<[^>]+>", "", window)
    address = html.unescape(window).split("\xa0")[0].strip()
    return name, address


def fetch_new_tukwila_parks(existing_keys: set[tuple[str, str]]) -> list[dict]:
    """Scrape Tukwila's parks directory page plus each individual park page it links
    to (~18 of them), geocoding each address via the free Census geocoder (the page
    has no coordinates), returning only ones not already in existing_keys."""
    resp = requests.get(TUKWILA_LIST_URL, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()

    new_parks = []
    skipped = 0
    for url in _tukwila_park_links(resp.text):
        page = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        page.raise_for_status()
        time.sleep(0.2)
        parsed = _parse_tukwila_park_page(page.text)
        if parsed is None:
            skipped += 1
            continue
        name, address = parsed
        if (name, address) in existing_keys:
            continue
        geocoded = _geocode_census(address, "Tukwila") if address else None
        if geocoded is None:
            skipped += 1
            continue
        lat, lon, zip_code = geocoded
        new_parks.append(
            {
                "name": name,
                "address": address,
                "city": "Tukwila",
                "zip_code": zip_code,
                "latitude": lat,
                "longitude": lon,
                "visited": "N",
                "visited_date": "",
            },
        )
    if skipped:
        print(f"Skipped {skipped} Tukwila park(s) with no address or that couldn't be geocoded.", file=sys.stderr)
    return new_parks


def _parse_renton_location(name: str, location: str) -> str:
    """Best-effort address from the LOCATION field, which is inconsistently
    formatted: usually "<name> - <address>" (possibly a different alias for
    name), sometimes a bare description, sometimes just a repeat of NAME with
    no real address. Returns "" rather than a redundant/uninformative value."""
    location = (location or "").strip()
    if not location or location == name:
        return ""
    if " - " in location:
        location = location.split(" - ", 1)[1]
    return " ".join(location.split())


def fetch_new_renton_parks(existing_keys: set[tuple[str, str]]) -> list[dict]:
    """Pull parks from Renton's public ArcGIS Server, filtered to OWNER='Renton'
    since this layer is a regional facilities dataset covering several
    neighboring jurisdictions' parks too. Most records have direct Latitude/
    Longitude fields; a handful of real parks have those fields null but still
    have valid polygon boundary geometry, so those fall back to a polygon
    centroid (as with Kirkland/Shoreline/Auburn) rather than being skipped. A
    couple of exact-duplicate records exist in the source data, so this also
    dedups within its own batch, not just against existing_keys."""
    resp = requests.get(
        RENTON_URL,
        params={
            "where": "OWNER='Renton'",
            "outFields": "NAME,LOCATION,Latitude,Longitude",
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
        name = (attrs.get("NAME") or "").strip()
        lat, lon = attrs.get("Latitude"), attrs.get("Longitude")
        if lat is None or lon is None:
            rings = feature.get("geometry", {}).get("rings")
            if rings:
                lat, lon = _polygon_centroid(rings)
        if not name or lat is None or lon is None:
            skipped += 1
            continue
        address = _parse_renton_location(name, attrs.get("LOCATION") or "")
        key = (name, address)
        if key in existing_keys or key in seen:
            continue
        seen.add(key)
        new_parks.append(
            {
                "name": name,
                "address": address,
                "city": "Renton",
                "zip_code": "",
                "latitude": float(lat),
                "longitude": float(lon),
                "visited": "N",
                "visited_date": "",
            },
        )
    if skipped:
        print(f"Skipped {skipped} Renton row(s) missing a name or coordinates.", file=sys.stderr)
    return new_parks


def fetch_new_seatac_parks(existing_keys: set[tuple[str, str]]) -> list[dict]:
    """Pull parks from SeaTac's public ArcGIS Server (seatacwa.gov itself is
    WAF-blocked, same as Shoreline/Kirkland). Has direct point geometry and
    separate Name/Address/City/Zipcode fields, all owned by "City of SeaTac"
    (no regional-dataset filtering needed). Addresses are recased from the
    same all-caps style as Kirkland's layer."""
    resp = requests.get(
        SEATAC_URL,
        params={
            "where": "1=1",
            "outFields": "Name,Address,Zipcode",
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
        name = (attrs.get("Name") or "").strip()
        geometry = feature.get("geometry")
        if not name or not geometry:
            skipped += 1
            continue
        address = _normalize_allcaps_text((attrs.get("Address") or "").strip())
        if (name, address) in existing_keys:
            continue
        new_parks.append(
            {
                "name": name,
                "address": address,
                "city": "SeaTac",
                "zip_code": (attrs.get("Zipcode") or "").strip(),
                "latitude": geometry["y"],
                "longitude": geometry["x"],
                "visited": "N",
                "visited_date": "",
            },
        )
    if skipped:
        print(f"Skipped {skipped} SeaTac row(s) missing a name or geometry.", file=sys.stderr)
    return new_parks


def fetch_new_kent_parks(existing_keys: set[tuple[str, str]]) -> list[dict]:
    """Pull parks from Kent's public ArcGIS Server. Has direct point geometry and
    a clean parkname/address field pair; addresses are recased from the same
    all-caps style as Kirkland/SeaTac's layers. Both developed and undeveloped
    status parks are included — both are real, currently-existing properties."""
    resp = requests.get(
        KENT_URL,
        params={
            "where": "1=1",
            "outFields": "parkname,address",
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
        name = _normalize_allcaps_text((attrs.get("parkname") or "").strip())
        geometry = feature.get("geometry")
        if not name or not geometry:
            skipped += 1
            continue
        address = _normalize_allcaps_text((attrs.get("address") or "").strip())
        if (name, address) in existing_keys:
            continue
        new_parks.append(
            {
                "name": name,
                "address": address,
                "city": "Kent",
                "zip_code": "",
                "latitude": geometry["y"],
                "longitude": geometry["x"],
                "visited": "N",
                "visited_date": "",
            },
        )
    if skipped:
        print(f"Skipped {skipped} Kent row(s) missing a name or geometry.", file=sys.stderr)
    return new_parks


def _des_moines_name_key(name: str) -> str:
    return re.sub(r"\s+", " ", name.replace(".", "")).strip().casefold()


def fetch_new_des_moines_parks(existing_keys: set[tuple[str, str]]) -> list[dict]:
    """Pull parks from Des Moines' public ArcGIS Server (desmoineswa.gov's own
    "Parks" page just redirects to a static PDF map, no structured data). The
    point layer has no address field, so addresses come from a best-effort join
    against the separate polygon layer's sparse SiteAddress field, matched by
    name with periods/whitespace stripped (the two layers don't always spell a
    park's name identically, e.g. "Cecil Powell Park" vs. the polygon layer's
    misspelled "Cecil Powel Park" — mismatches like that are simply left with a
    blank address rather than force-matched)."""
    address_resp = requests.get(
        DES_MOINES_ADDRESS_URL,
        params={"where": "1=1", "outFields": "ParkName,SiteAddress", "returnGeometry": "false", "f": "json"},
        timeout=30,
    )
    address_resp.raise_for_status()
    address_by_key = {}
    for feature in address_resp.json().get("features", []):
        attrs = feature["attributes"]
        raw_name = (attrs.get("ParkName") or "").strip()
        raw_address = (attrs.get("SiteAddress") or "").strip()
        if not raw_name or not raw_address:
            continue
        address_by_key[_des_moines_name_key(raw_name)] = _normalize_allcaps_text(re.sub(r"\s+", " ", raw_address))

    resp = requests.get(
        DES_MOINES_PARKS_URL,
        params={
            "where": "ParkType='CITY' AND ActiveFlag=1",
            "outFields": "ParkName",
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
        geometry = feature.get("geometry")
        if not name or not geometry:
            skipped += 1
            continue
        address = address_by_key.get(_des_moines_name_key(name), "")
        key = (name, address)
        if key in existing_keys or key in seen:
            continue
        seen.add(key)
        new_parks.append(
            {
                "name": name,
                "address": address,
                "city": "Des Moines",
                "zip_code": "",
                "latitude": geometry["y"],
                "longitude": geometry["x"],
                "visited": "N",
                "visited_date": "",
            },
        )
    if skipped:
        print(f"Skipped {skipped} Des Moines row(s) missing a name or geometry.", file=sys.stderr)
    return new_parks


FEDERAL_WAY_ADDRESS_RE = re.compile(r"^(.*?),\s*Federal Way,\s*WA\s*(\d{5})$")
FEDERAL_WAY_COORD_RE = re.compile(r"cp=([\-0-9.]+)~([\-0-9.]+)")


def _parse_federal_way_accordion(page_html: str) -> list[dict]:
    """Extract (name, address, zip_code, latitude, longitude) for each park listed
    as an accordion item on the "Our Parks" page. Most items' embedded Bing map
    link encodes direct point coordinates (cp=<lat>~<lon>); for the rest, only the
    plain "Location:" address text is returned (latitude/longitude left as None),
    for the caller to geocode."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(page_html, "html.parser")
    parks = []
    for item in soup.select("div.accordion-item"):
        button = item.find("button", class_="accordion")
        panel = item.find("div", class_="panel-content")
        if not button or not panel:
            continue
        name = button.get_text(strip=True)
        if not name:
            continue
        text = panel.get_text("\n", strip=True)
        location_match = re.search(r"Location:\s*(.+)", text)
        location = location_match.group(1).split("\n")[0].strip() if location_match else ""
        address, zip_code = "", ""
        addr_match = FEDERAL_WAY_ADDRESS_RE.match(location)
        if addr_match:
            address, zip_code = addr_match.group(1), addr_match.group(2)
        latitude, longitude = None, None
        for a in panel.find_all("a", href=True):
            coord_match = FEDERAL_WAY_COORD_RE.search(a["href"])
            if coord_match:
                latitude, longitude = float(coord_match.group(1)), float(coord_match.group(2))
                break
        parks.append(
            {
                "name": name,
                "address": address,
                "zip_code": zip_code,
                "latitude": latitude,
                "longitude": longitude,
            },
        )
    return parks


def fetch_new_federal_way_parks(existing_keys: set[tuple[str, str]]) -> list[dict]:
    """Scrape Federal Way's "Our Parks" page (fetchable, unlike several
    neighboring cities' WAF-blocked sites). Most parks' coordinates come
    straight from an embedded Bing map link; the few without one are geocoded
    via the free Census geocoder from their Location address instead. A park
    with neither (BPA Trail, whose "location" is just descriptive text with no
    street address) is skipped."""
    resp = requests.get(FEDERAL_WAY_URL, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()

    new_parks = []
    skipped = 0
    for park in _parse_federal_way_accordion(resp.text):
        name, address = park["name"], park["address"]
        if (name, address) in existing_keys:
            continue
        latitude, longitude, zip_code = park["latitude"], park["longitude"], park["zip_code"]
        if latitude is None or longitude is None:
            if not address:
                skipped += 1
                continue
            geocoded = _geocode_census(address, "Federal Way")
            if geocoded is None:
                skipped += 1
                continue
            latitude, longitude, zip_code = geocoded
        new_parks.append(
            {
                "name": name,
                "address": address,
                "city": "Federal Way",
                "zip_code": zip_code,
                "latitude": latitude,
                "longitude": longitude,
                "visited": "N",
                "visited_date": "",
            },
        )
    if skipped:
        print(f"Skipped {skipped} Federal Way park(s) with no address or that couldn't be geocoded.", file=sys.stderr)
    return new_parks


def fetch_new_auburn_parks(existing_keys: set[tuple[str, str]]) -> list[dict]:
    """Pull named park polygons from Auburn's public ArcGIS Server (found via its
    Experience Builder parks app's underlying web map, not a direct GIS search).
    All owned by "COA" (no regional-dataset filtering needed). Name and address
    are recased from the same all-caps style as Kirkland/SeaTac/Kent's layers.
    Each park's location is its polygon centroid, as with Kirkland/Shoreline."""
    resp = requests.get(
        AUBURN_URL,
        params={
            "where": "1=1",
            "outFields": "FULLNAME,ADDRESS",
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
        name = _normalize_allcaps_text((attrs.get("FULLNAME") or "").strip())
        address = _normalize_allcaps_text((attrs.get("ADDRESS") or "").strip())
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
                "city": "Auburn",
                "zip_code": "",
                "latitude": lat,
                "longitude": lon,
                "visited": "N",
                "visited_date": "",
            },
        )
    if skipped:
        print(f"Skipped {skipped} Auburn row(s) missing a name or geometry.", file=sys.stderr)
    return new_parks


LAKE_FOREST_PARK_ADDRESS_RE = re.compile(r"^(.*?),\s*Lake Forest Park,\s*WA\s*(\d{5})$")


def fetch_new_lake_forest_park_parks(existing_keys: set[tuple[str, str]]) -> list[dict]:
    """Pull the small "Park_Boundary" polygon layer from Lake Forest Park's ArcGIS
    Online organization (found via its Hub site's dataset metadata, same discovery
    path as Kent/SeaTac). Only 7 named parks, all clean. Each address already
    includes a ", Lake Forest Park, WA <zip>" suffix that's split off; each park's
    location is its polygon centroid, as with Kirkland/Shoreline/Auburn."""
    resp = requests.get(
        LAKE_FOREST_PARK_URL,
        params={
            "where": "1=1",
            "outFields": "SITENAME,Address",
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
        name = (attrs.get("SITENAME") or "").strip()
        rings = feature.get("geometry", {}).get("rings")
        if not name or not rings:
            skipped += 1
            continue
        raw_address = (attrs.get("Address") or "").strip()
        addr_match = LAKE_FOREST_PARK_ADDRESS_RE.match(raw_address)
        address, zip_code = addr_match.groups() if addr_match else (raw_address, "")
        if (name, address) in existing_keys:
            continue
        lat, lon = _polygon_centroid(rings)
        new_parks.append(
            {
                "name": name,
                "address": address,
                "city": "Lake Forest Park",
                "zip_code": zip_code,
                "latitude": lat,
                "longitude": lon,
                "visited": "N",
                "visited_date": "",
            },
        )
    if skipped:
        print(f"Skipped {skipped} Lake Forest Park row(s) missing a name or geometry.", file=sys.stderr)
    return new_parks


def fetch_new_kenmore_parks(existing_keys: set[tuple[str, str]]) -> list[dict]:
    """Pull parks from Kenmore's own ArcGIS Server (found via an embedded
    Experience Builder app on kenmorewa.gov, which is itself WAF-blocked like
    Shoreline/Kirkland/SeaTac). The "Parks" layer is a regional dataset spanning
    several agencies, so it's filtered to OWNER='City of Kenmore'. Some names have
    embedded newlines from the source editor, collapsed to single spaces. No
    address field exists on this layer, so address is always blank. Each park's
    location is its polygon centroid, as with Kirkland/Shoreline/Auburn/Lake
    Forest Park."""
    resp = requests.get(
        KENMORE_URL,
        params={
            "where": "OWNER='City of Kenmore'",
            "outFields": "SITENAME",
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
        name = re.sub(r"\s+", " ", (attrs.get("SITENAME") or "").strip())
        rings = feature.get("geometry", {}).get("rings")
        if not name or not rings:
            skipped += 1
            continue
        if (name, "") in existing_keys:
            continue
        lat, lon = _polygon_centroid(rings)
        new_parks.append(
            {
                "name": name,
                "address": "",
                "city": "Kenmore",
                "zip_code": "",
                "latitude": lat,
                "longitude": lon,
                "visited": "N",
                "visited_date": "",
            },
        )
    if skipped:
        print(f"Skipped {skipped} Kenmore row(s) missing a name or geometry.", file=sys.stderr)
    return new_parks


def _bothell_park_links(page_html: str) -> list[tuple[str, str]]:
    """Extract (name, url) for each park listed in the Parks page's own left-nav
    accordion, scoped to that page's child pages specifically (data-parent="250")
    so it can't pick up unrelated site links."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(page_html, "html.parser")
    nav = soup.find("ol", attrs={"data-parent": "250"})
    if nav is None:
        return []
    links = []
    for a in nav.select('a.navMainItem[data-type="SecondaryMainItem"]'):
        name = a.get_text(strip=True)
        href = a.get("href")
        if name and href:
            links.append((name, BOTHELL_BASE_URL + href))
    return links


BOTHELL_ADDRESS_RE = re.compile(r"^(.*?),\s*Bothell,\s*WA\s*(\d{5})$")


def _parse_bothell_park_page(page_html: str) -> str:
    """Extract the street address from an individual park page: an "Address"
    heading (sometimes followed by a literal "&nbsp;" before the closing tag) is
    always followed by a bullet list whose first item is the address, including a
    ", Bothell, WA <zip>" suffix that the caller splits off separately."""
    match = re.search(
        r"<h2[^>]*>\s*Address(?:&nbsp;)?\s*</h2>\s*<ul[^>]*>\s*<li[^>]*>(.*?)</li>",
        page_html,
        re.DOTALL,
    )
    if not match:
        return ""
    return html.unescape(re.sub(r"<[^>]+>", "", match.group(1))).strip()


def fetch_new_bothell_parks(existing_keys: set[tuple[str, str]]) -> list[dict]:
    """Scrape Bothell's parks directory page plus each individual park page it
    links to (~23 of them), geocoding each address via the free Census geocoder
    (neither page has coordinates). Used instead of the city's ArcGIS Server,
    whose "BothellParks" layer is stale (last edited 2017), missing several
    current parks, and has garbage/duplicate rows."""
    resp = requests.get(BOTHELL_LIST_URL, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()

    new_parks = []
    skipped = 0
    for name, url in _bothell_park_links(resp.text):
        page = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        page.raise_for_status()
        time.sleep(0.2)
        raw_address = _parse_bothell_park_page(page.text)
        addr_match = BOTHELL_ADDRESS_RE.match(raw_address)
        address = addr_match.group(1) if addr_match else raw_address
        if (name, address) in existing_keys:
            continue
        geocoded = _geocode_census(address, "Bothell") if address else None
        if geocoded is None:
            skipped += 1
            continue
        lat, lon, zip_code = geocoded
        new_parks.append(
            {
                "name": name,
                "address": address,
                "city": "Bothell",
                "zip_code": zip_code,
                "latitude": lat,
                "longitude": lon,
                "visited": "N",
                "visited_date": "",
            },
        )
    if skipped:
        print(f"Skipped {skipped} Bothell park(s) with no address or that couldn't be geocoded.", file=sys.stderr)
    return new_parks


def _parse_woodinville_park_page(page_html: str) -> tuple[str, str, str]:
    """Extract (name, address, zip_code) from a facility detail page: the name is
    the page's first <h2>; the address is the schema.org/hCard street-address and
    postal-code spans."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(page_html, "html.parser")
    name_tag = soup.find("h2")
    name = name_tag.get_text(strip=True) if name_tag else ""
    street = soup.select_one(".street-address")
    postal = soup.select_one(".postal-code")
    address = street.get_text(strip=True) if street else ""
    zip_code = postal.get_text(strip=True) if postal else ""
    return name, address, zip_code


def fetch_new_woodinville_parks(existing_keys: set[tuple[str, str]]) -> list[dict]:
    """Fetch each of Woodinville's 8 parks directly by facility ID (its
    "Facilities" booking page only renders 5 facilities by default via a
    JS-paginated widget, 2 of which aren't parks, so the paginated listing isn't
    used at all). Geocodes each address via the free Census geocoder (no
    coordinates on any of these pages); 2 parks with no house number in their
    address are expected to fail geocoding and get skipped."""
    new_parks = []
    skipped = 0
    for facility_id in WOODINVILLE_PARK_IDS:
        page = requests.get(
            WOODINVILLE_DETAIL_URL.format(facility_id),
            headers={"User-Agent": USER_AGENT},
            timeout=30,
        )
        page.raise_for_status()
        time.sleep(0.2)
        name, address, _ = _parse_woodinville_park_page(page.text)
        if not name:
            skipped += 1
            continue
        if (name, address) in existing_keys:
            continue
        geocoded = _geocode_census(address, "Woodinville") if address else None
        if geocoded is None:
            skipped += 1
            continue
        lat, lon, zip_code = geocoded
        new_parks.append(
            {
                "name": name,
                "address": address,
                "city": "Woodinville",
                "zip_code": zip_code,
                "latitude": lat,
                "longitude": lon,
                "visited": "N",
                "visited_date": "",
            },
        )
    if skipped:
        print(f"Skipped {skipped} Woodinville park(s) with no address or that couldn't be geocoded.", file=sys.stderr)
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
    new_bellevue = fetch_new_bellevue_parks(existing_keys)
    existing_keys |= {(p["name"], p["address"]) for p in new_bellevue}
    new_mercer_island = fetch_new_mercer_island_parks(existing_keys)
    existing_keys |= {(p["name"], p["address"]) for p in new_mercer_island}
    new_kirkland = fetch_new_kirkland_parks(existing_keys)
    existing_keys |= {(p["name"], p["address"]) for p in new_kirkland}
    new_redmond = fetch_new_redmond_parks(existing_keys)
    existing_keys |= {(p["name"], p["address"]) for p in new_redmond}
    new_medina = fetch_new_medina_parks(existing_keys)
    existing_keys |= {(p["name"], p["address"]) for p in new_medina}
    new_burien = fetch_new_burien_parks(existing_keys)
    existing_keys |= {(p["name"], p["address"]) for p in new_burien}
    new_tukwila = fetch_new_tukwila_parks(existing_keys)
    existing_keys |= {(p["name"], p["address"]) for p in new_tukwila}
    new_renton = fetch_new_renton_parks(existing_keys)
    existing_keys |= {(p["name"], p["address"]) for p in new_renton}
    new_seatac = fetch_new_seatac_parks(existing_keys)
    existing_keys |= {(p["name"], p["address"]) for p in new_seatac}
    new_kent = fetch_new_kent_parks(existing_keys)
    existing_keys |= {(p["name"], p["address"]) for p in new_kent}
    new_des_moines = fetch_new_des_moines_parks(existing_keys)
    existing_keys |= {(p["name"], p["address"]) for p in new_des_moines}
    new_federal_way = fetch_new_federal_way_parks(existing_keys)
    existing_keys |= {(p["name"], p["address"]) for p in new_federal_way}
    new_auburn = fetch_new_auburn_parks(existing_keys)
    existing_keys |= {(p["name"], p["address"]) for p in new_auburn}
    new_lake_forest_park = fetch_new_lake_forest_park_parks(existing_keys)
    existing_keys |= {(p["name"], p["address"]) for p in new_lake_forest_park}
    new_kenmore = fetch_new_kenmore_parks(existing_keys)
    existing_keys |= {(p["name"], p["address"]) for p in new_kenmore}
    new_bothell = fetch_new_bothell_parks(existing_keys)
    existing_keys |= {(p["name"], p["address"]) for p in new_bothell}
    new_woodinville = fetch_new_woodinville_parks(existing_keys)
    new_parks = (
        new_seattle
        + new_shoreline
        + new_bellevue
        + new_mercer_island
        + new_kirkland
        + new_redmond
        + new_medina
        + new_burien
        + new_tukwila
        + new_renton
        + new_seatac
        + new_kent
        + new_des_moines
        + new_federal_way
        + new_auburn
        + new_lake_forest_park
        + new_kenmore
        + new_bothell
        + new_woodinville
    )
    new_parks = [p for p in new_parks if not _is_excluded_name(p["name"], p["city"])]
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
    latest_parks = _latest_visited_parks(parks)
    latest_ids = {id(p) for p in latest_parks}
    latest_markers = {}
    search_index = []
    for p in parks:
        color = VISITED_COLOR if _is_visited(p.get("visited", "N")) else UNVISITED_COLOR
        city_zip = " ".join(part for part in (p["city"], p["zip_code"]) if part)
        address_line = ", ".join(part for part in (p["address"], city_zip) if part)
        popup_html = f"<b>{p['name']}</b><br>{address_line}"
        visited_date = _format_visited_date(p.get("visited_date", ""))
        if visited_date:
            popup_html += f"<br><b>Visited:</b> {visited_date}"
        popup = folium.Popup(popup_html, max_width=250)
        marker = folium.CircleMarker(
            location=[p["latitude"], p["longitude"]],
            radius=MARKER_RADIUS,
            color="#ffffff",
            weight=1,
            fill=True,
            fill_color=color,
            fill_opacity=0.9,
            popup=popup,
        )
        marker.add_to(m)
        search_index.append(
            {"name": p["name"], "lat": p["latitude"], "lon": p["longitude"], "marker": marker.get_name()},
        )
        if id(p) in latest_ids:
            latest_markers[id(p)] = marker

    if latest_parks and latest_markers:
        links = []
        for lp in latest_parks:
            marker = latest_markers.get(id(lp))
            if not marker:
                continue
            goto_marker_js = (
                f"{m.get_name()}.setView([{lp['latitude']}, {lp['longitude']}], 16); "
                f"{marker.get_name()}.openPopup(); return false;"
            )
            links.append(f'<div><a href="#" onclick="{goto_marker_js}">{lp["name"]}</a></div>')
        label = "Latest parks visited:" if len(links) > 1 else "Latest park visited:"
        latest_html = (
            f'<div style="font-size: 14px; font-weight: 400; margin-top: 4px; display: flex;">'
            f'<b style="flex-shrink: 0;">{label}</b>'
            f'<div style="margin-left: 4px;">{"".join(links)}</div></div>'
        )
    else:
        latest_html = ""
    visited_count = sum(1 for p in parks if _is_visited(p.get("visited", "N")))
    seattle_parks = [p for p in parks if p["city"] == "Seattle"]
    seattle_visited_count = sum(1 for p in seattle_parks if _is_visited(p.get("visited", "N")))
    seattle_pct = (seattle_visited_count / len(seattle_parks) * 100) if seattle_parks else 0.0
    metro_pct = (visited_count / len(parks) * 100) if parks else 0.0
    progress_html = (
        f'<div style="font-size: 14px; font-weight: 400; margin-top: 4px;">'
        f"<b>Seattle progress:</b> {seattle_visited_count} / {len(seattle_parks)} ({seattle_pct:.1f}%)</div>"
        f'<div style="font-size: 14px; font-weight: 400;">'
        f"<b>Seattle Metro Area progress:</b> {visited_count} / {len(parks)} ({metro_pct:.1f}%)</div>"
    )
    search_html = """
    <div style="position: relative; margin-top: 8px;">
      <input id="parkSearchInput" type="text" placeholder="Search parks..." autocomplete="off"
             style="width: 100%; box-sizing: border-box; font-size: 14px; font-weight: 400;
                    padding: 6px 8px; border: 1px solid #c3c2b7; border-radius: 4px;
                    font-family: system-ui, -apple-system, sans-serif;">
      <div id="parkSearchResults"
           style="display: none; position: absolute; top: 100%; left: 0; right: 0; margin-top: -1px;
                  background: #fcfcfb; border: 1px solid #c3c2b7; border-radius: 0 0 4px 4px;
                  max-height: 220px; overflow-y: auto; z-index: 1001;">
      </div>
    </div>
    """
    title_html = f"""
    <div style="position: fixed; top: 16px; left: 60px; z-index: 1000;
                background: #fcfcfb; padding: 8px 22px; border: 1px solid #c3c2b7;
                border-radius: 4px; font-family: system-ui, -apple-system, sans-serif;
                font-size: 24px; font-weight: 700; color: #0b0b0b;">
      {MAP_TITLE}
      {latest_html}
      {progress_html}
      {search_html}
    </div>
    """
    m.get_root().html.add_child(folium.Element(title_html))

    search_index_json = json.dumps(search_index)
    search_script = f"""
    <script>
    (function() {{
        var parksSearchIndex = {search_index_json};
        var input = document.getElementById("parkSearchInput");
        var results = document.getElementById("parkSearchResults");
        input.addEventListener("input", function() {{
            var query = input.value.trim().toLowerCase();
            results.innerHTML = "";
            if (!query) {{
                results.style.display = "none";
                return;
            }}
            var matches = parksSearchIndex.filter(function(p) {{
                return p.name.toLowerCase().indexOf(query) !== -1;
            }}).slice(0, 8);
            if (matches.length === 0) {{
                results.style.display = "none";
                return;
            }}
            matches.forEach(function(p) {{
                var item = document.createElement("div");
                item.textContent = p.name;
                item.style.padding = "6px 8px";
                item.style.cursor = "pointer";
                item.style.fontSize = "14px";
                item.style.fontWeight = "400";
                item.style.fontFamily = "system-ui, -apple-system, sans-serif";
                item.addEventListener("mouseenter", function() {{ item.style.background = "#eeeeea"; }});
                item.addEventListener("mouseleave", function() {{ item.style.background = "transparent"; }});
                item.addEventListener("click", function() {{
                    {m.get_name()}.setView([p.lat, p.lon], 16);
                    window[p.marker].openPopup();
                    input.value = "";
                    results.innerHTML = "";
                    results.style.display = "none";
                }});
                results.appendChild(item);
            }});
            results.style.display = "block";
        }});
        document.addEventListener("click", function(e) {{
            if (e.target !== input) {{
                results.style.display = "none";
            }}
        }});
    }})();
    </script>
    """
    m.get_root().html.add_child(folium.Element(search_script))

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
        plot_map(_apply_backup_data(parks))
    else:
        parks = sync_parks()
        if not parks:
            print("No park data retrieved — aborting.", file=sys.stderr)
            sys.exit(1)
        write_csv(parks)
        plot_map(_apply_backup_data(parks))


if __name__ == "__main__":
    main()
