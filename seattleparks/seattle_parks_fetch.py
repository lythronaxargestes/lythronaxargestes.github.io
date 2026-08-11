"""Per-city (and King County) fetch functions: pull new parks from each source's
live API/page, returning only ones not already in existing_keys. Orchestrated by
sync_parks() in seattle_parks_map.py via FETCH_FUNCTIONS below. Each city-specific
parsing helper lives right next to the fetch function that uses it; only
generic, city-agnostic helpers (retries, geocoding, centroids, recasing) live in
seattle_parks_helpers.py."""
from __future__ import annotations

import html
import json
import re
import sys
import time

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

from seattle_parks_constants import (
    API_URL,
    AUBURN_URL,
    BELLEVUE_BASE_URL,
    BELLEVUE_LIST_URL,
    BOTHELL_ADDRESS_RE,
    BOTHELL_BASE_URL,
    BOTHELL_LIST_URL,
    BURIEN_BASE_URL,
    BURIEN_LIST_URL,
    DEFAULT_CITY,
    DES_MOINES_ADDRESS_URL,
    DES_MOINES_PARKS_URL,
    FEDERAL_WAY_ADDRESS_RE,
    FEDERAL_WAY_COORD_RE,
    FEDERAL_WAY_URL,
    KENMORE_URL,
    KENT_URL,
    KING_COUNTY_URL,
    KIRKLAND_URL,
    LAKE_FOREST_PARK_ADDRESS_RE,
    LAKE_FOREST_PARK_URL,
    MEDINA_BASE_URL,
    MEDINA_LIST_URL,
    MERCER_ISLAND_BASE_URL,
    MERCER_ISLAND_DIRECTORY_URL,
    MERCER_ISLAND_LIST_URL,
    REDMOND_URL,
    RENTON_URL,
    SEATAC_URL,
    SHORELINE_URL,
    TRACKED_CITIES,
    TUKWILA_LIST_URL,
    USER_AGENT,
    WOODINVILLE_DETAIL_URL,
    WOODINVILLE_PARK_IDS,
)
from seattle_parks_helpers import _geocode_census, _get_with_retries, _normalize_allcaps_text, _polygon_centroid


def fetch_new_parks(existing_keys: set[tuple[str, str]]) -> list[dict]:
    """Pull parks from the Socrata API, returning only ones not already in existing_keys."""
    resp = _get_with_retries(API_URL, params={"$limit": 1000}, timeout=30)
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
    print("Finished fetching Seattle.")
    return new_parks


def fetch_new_shoreline_parks(existing_keys: set[tuple[str, str]]) -> list[dict]:
    """Pull named park polygons from Shoreline's public ArcGIS Server, returning only
    ones not already in existing_keys. Each park's location is its polygon centroid,
    since this layer stores boundaries, not points."""
    resp = _get_with_retries(
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
    print("Finished fetching Shoreline.")
    return new_parks


def _bellevue_park_links(html: str) -> list[str]:
    """Extract unique individual park page URLs from the directory listing page."""
    soup = BeautifulSoup(html, "html.parser")
    pattern = re.compile(r"^/city-government/departments/parks/parks-and-trails/parks/[a-z0-9-]+$")
    hrefs = {a["href"] for a in soup.find_all("a", href=pattern)}
    return [BELLEVUE_BASE_URL + href for href in sorted(hrefs)]


def _parse_bellevue_park_page(html: str) -> dict | None:
    """Extract name/address/coordinates from an individual park page. Returns None
    for non-park informational pages (e.g. "Beach Parks with Lifeguards"), which
    have no latitude/longitude meta tags."""
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
    resp = _get_with_retries(BELLEVUE_LIST_URL, headers={"User-Agent": USER_AGENT}, timeout=30)
    links = _bellevue_park_links(resp.text)

    new_parks = []
    skipped = 0
    for url in tqdm(links, desc="Bellevue pages"):
        page = _get_with_retries(url, headers={"User-Agent": USER_AGENT}, timeout=30)
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
    print("Finished fetching Bellevue.")
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
    resp = _get_with_retries(list_url, headers={"User-Agent": USER_AGENT}, timeout=30)

    new_parks = []
    parks = _parse_civicplus_map_listing(resp.text, base_url)
    for park in tqdm(parks, desc=f"{default_city} pages"):
        page = _get_with_retries(park["url"], headers={"User-Agent": USER_AGENT}, timeout=30)
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
    """Fetch Mercer Island's parks. Most come from the /parksites listing page's
    embedded map widget (precise point coordinates, no geocoding needed, via
    _fetch_new_civicplus_parks), but that widget only covers a curated subset --
    its full parks directory page lists several more (e.g. Aubrey Davis Park)
    that never appear in the widget at all. Those extras are found from the
    directory page's own /parksrec/page/<slug> links and geocoded from their
    address instead; a linked page only counts as a real park page if it
    actually has park-page address microdata, which cleanly filters out the
    directory's informational pages (Trails, Off-Leash Dog Areas, event
    announcements, etc.) without a hardcoded exclude list."""
    widget_resp = _get_with_retries(MERCER_ISLAND_LIST_URL, headers={"User-Agent": USER_AGENT}, timeout=30)
    widget_urls = {park["url"] for park in _parse_civicplus_map_listing(widget_resp.text, MERCER_ISLAND_BASE_URL)}

    new_parks = _fetch_new_civicplus_parks(existing_keys, MERCER_ISLAND_LIST_URL, MERCER_ISLAND_BASE_URL, "Mercer Island")

    dir_resp = _get_with_retries(MERCER_ISLAND_DIRECTORY_URL, headers={"User-Agent": USER_AGENT}, timeout=30)
    slugs = dict.fromkeys(re.findall(r'href="(/parksrec/page/[a-z0-9-]+)"', dir_resp.text))
    extra_urls = [MERCER_ISLAND_BASE_URL + slug for slug in slugs if MERCER_ISLAND_BASE_URL + slug not in widget_urls]

    for url in tqdm(extra_urls, desc="Mercer Island directory-only pages"):
        try:
            page = _get_with_retries(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        except requests.exceptions.HTTPError:
            # A few directory links (e.g. "provide-feedback") redirect off-site to
            # a CivicPlus form host that 403s a plain GET -- not a park page anyway.
            continue
        time.sleep(0.2)
        soup = BeautifulSoup(page.text, "html.parser")
        title_tag = soup.find(id="page-title")
        name = html.unescape(title_tag.get_text(strip=True)) if title_tag else ""
        details = _parse_civicplus_park_page(page.text, "Mercer Island")
        if not name or not details["address"] or (name, details["address"]) in existing_keys:
            continue
        geocoded = _geocode_census(details["address"], "Mercer Island")
        if geocoded is None:
            continue
        lat, lon, census_zip = geocoded
        new_parks.append(
            {
                "name": name,
                "address": details["address"],
                "city": details["city"],
                "zip_code": details["zip_code"] or census_zip,
                "latitude": lat,
                "longitude": lon,
                "visited": "N",
                "visited_date": "",
            },
        )

    print("Finished fetching Mercer Island.")
    return new_parks


def fetch_new_medina_parks(existing_keys: set[tuple[str, str]]) -> list[dict]:
    """Fetch Medina's parks listing page and each linked park page."""
    new_parks = _fetch_new_civicplus_parks(existing_keys, MEDINA_LIST_URL, MEDINA_BASE_URL, "Medina")
    print("Finished fetching Medina.")
    return new_parks


def fetch_new_kirkland_parks(existing_keys: set[tuple[str, str]]) -> list[dict]:
    """Pull named park polygons from Kirkland's public ArcGIS Server (kirklandwa.gov
    itself is WAF-blocked, same as shorelinewa.gov), filtered to CATEGORY='PARKS'
    to exclude raw open-space parcels, a cemetery, and a pool. Returns only ones
    not already in existing_keys. Each park's location is its polygon centroid."""
    resp = _get_with_retries(
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
    print("Finished fetching Kirkland.")
    return new_parks


def fetch_new_redmond_parks(existing_keys: set[tuple[str, str]]) -> list[dict]:
    """Pull park polygons from Redmond's public ArcGIS Server, returning only ones
    not already in existing_keys. One name ("Redmond Central Connector") repeats
    across multiple blank-address segments, so this also dedups within its own
    batch, not just against existing_keys. Each park's location is its polygon
    centroid."""
    resp = _get_with_retries(
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
    print("Finished fetching Redmond.")
    return new_parks


def _burien_park_links(page_html: str) -> list[str]:
    """Extract unique individual park page URLs from the directory listing page's
    sidebar navigation."""
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
    resp = _get_with_retries(BURIEN_LIST_URL, headers={"User-Agent": USER_AGENT}, timeout=30)

    new_parks = []
    skipped = 0
    for url in tqdm(_burien_park_links(resp.text), desc="Burien pages"):
        page = _get_with_retries(url, headers={"User-Agent": USER_AGENT}, timeout=30)
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
    print("Finished fetching Burien.")
    return new_parks


def _tukwila_park_links(page_html: str) -> list[str]:
    """Extract unique individual park page URLs from the directory listing page."""
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
    resp = _get_with_retries(TUKWILA_LIST_URL, headers={"User-Agent": USER_AGENT}, timeout=30)

    new_parks = []
    skipped = 0
    for url in tqdm(_tukwila_park_links(resp.text), desc="Tukwila pages"):
        page = _get_with_retries(url, headers={"User-Agent": USER_AGENT}, timeout=30)
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
    print("Finished fetching Tukwila.")
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
    resp = _get_with_retries(
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
    print("Finished fetching Renton.")
    return new_parks


def fetch_new_seatac_parks(existing_keys: set[tuple[str, str]]) -> list[dict]:
    """Pull parks from SeaTac's public ArcGIS Server (seatacwa.gov itself is
    WAF-blocked, same as Shoreline/Kirkland). Has direct point geometry and
    separate Name/Address/City/Zipcode fields, all owned by "City of SeaTac"
    (no regional-dataset filtering needed). Addresses are recased from the
    same all-caps style as Kirkland's layer."""
    resp = _get_with_retries(
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
    print("Finished fetching SeaTac.")
    return new_parks


def fetch_new_kent_parks(existing_keys: set[tuple[str, str]]) -> list[dict]:
    """Pull parks from Kent's public ArcGIS Server. Has direct point geometry and
    a clean parkname/address field pair; addresses are recased from the same
    all-caps style as Kirkland/SeaTac's layers. Both developed and undeveloped
    status parks are included — both are real, currently-existing properties."""
    resp = _get_with_retries(
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
    print("Finished fetching Kent.")
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
    address_resp = _get_with_retries(
        DES_MOINES_ADDRESS_URL,
        params={"where": "1=1", "outFields": "ParkName,SiteAddress", "returnGeometry": "false", "f": "json"},
        timeout=30,
    )
    address_by_key = {}
    for feature in address_resp.json().get("features", []):
        attrs = feature["attributes"]
        raw_name = (attrs.get("ParkName") or "").strip()
        raw_address = (attrs.get("SiteAddress") or "").strip()
        if not raw_name or not raw_address:
            continue
        address_by_key[_des_moines_name_key(raw_name)] = _normalize_allcaps_text(re.sub(r"\s+", " ", raw_address))

    resp = _get_with_retries(
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
    print("Finished fetching Des Moines.")
    return new_parks


def _parse_federal_way_accordion(page_html: str) -> list[dict]:
    """Extract (name, address, zip_code, latitude, longitude) for each park listed
    as an accordion item on the "Our Parks" page. Most items' embedded Bing map
    link encodes direct point coordinates (cp=<lat>~<lon>); for the rest, only the
    plain "Location:" address text is returned (latitude/longitude left as None),
    for the caller to geocode."""
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
    resp = _get_with_retries(FEDERAL_WAY_URL, headers={"User-Agent": USER_AGENT}, timeout=30)

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
    print("Finished fetching Federal Way.")
    return new_parks


def fetch_new_auburn_parks(existing_keys: set[tuple[str, str]]) -> list[dict]:
    """Pull named park polygons from Auburn's public ArcGIS Server (found via its
    Experience Builder parks app's underlying web map, not a direct GIS search).
    All owned by "COA" (no regional-dataset filtering needed). Name and address
    are recased from the same all-caps style as Kirkland/SeaTac/Kent's layers.
    Each park's location is its polygon centroid, as with Kirkland/Shoreline."""
    resp = _get_with_retries(
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
    print("Finished fetching Auburn.")
    return new_parks


def fetch_new_lake_forest_park_parks(existing_keys: set[tuple[str, str]]) -> list[dict]:
    """Pull the small "Park_Boundary" polygon layer from Lake Forest Park's ArcGIS
    Online organization (found via its Hub site's dataset metadata, same discovery
    path as Kent/SeaTac). Only 7 named parks, all clean. Each address already
    includes a ", Lake Forest Park, WA <zip>" suffix that's split off; each park's
    location is its polygon centroid, as with Kirkland/Shoreline/Auburn."""
    resp = _get_with_retries(
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
    print("Finished fetching Lake Forest Park.")
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
    resp = _get_with_retries(
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
    print("Finished fetching Kenmore.")
    return new_parks


def _bothell_park_links(page_html: str) -> list[tuple[str, str]]:
    """Extract (name, url) for each park listed in the Parks page's own left-nav
    accordion, scoped to that page's child pages specifically (data-parent="250")
    so it can't pick up unrelated site links."""
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
    resp = _get_with_retries(BOTHELL_LIST_URL, headers={"User-Agent": USER_AGENT}, timeout=30)

    new_parks = []
    skipped = 0
    for name, url in tqdm(_bothell_park_links(resp.text), desc="Bothell pages"):
        page = _get_with_retries(url, headers={"User-Agent": USER_AGENT}, timeout=30)
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
    print("Finished fetching Bothell.")
    return new_parks


def _parse_woodinville_park_page(page_html: str) -> tuple[str, str, str]:
    """Extract (name, address, zip_code) from a facility detail page: the name is
    the page's first <h2>; the address is the schema.org/hCard street-address and
    postal-code spans."""
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
    for facility_id in tqdm(WOODINVILLE_PARK_IDS, desc="Woodinville pages"):
        page = _get_with_retries(
            WOODINVILLE_DETAIL_URL.format(facility_id),
            headers={"User-Agent": USER_AGENT},
            timeout=30,
        )
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
    print("Finished fetching Woodinville.")
    return new_parks


def fetch_new_king_county_parks(existing_keys: set[tuple[str, str]]) -> list[dict]:
    """Pull point parks from King County's public ArcGIS Server (surfaced by the
    "Backyard Fun Finder" ArcGIS Experience Builder app's underlying web map, not
    a direct GIS search). This layer is county-wide, spanning cities this project
    doesn't otherwise track (Vashon, Sammamish, Black Diamond, ...), so it's
    filtered to TRACKED_CITIES to keep only parks in cities already covered by
    another source. The joined park-label-point / facilities-table layer returns
    fully-qualified field names; address comes from the facilities table's
    A_Street/A_City/A_Zip, whose A_Zip has trailing whitespace in the source
    data, stripped like every other source's zip."""
    name_field = "plibrary.recreatn.park_label_point.SiteName"
    street_field = "plibrary.recreatn.park_and_trail_facilities_table.A_Street"
    city_field = "plibrary.recreatn.park_and_trail_facilities_table.A_City"
    zip_field = "plibrary.recreatn.park_and_trail_facilities_table.A_Zip"
    resp = _get_with_retries(
        KING_COUNTY_URL,
        params={
            "where": "1=1",
            "outFields": f"{name_field},{street_field},{city_field},{zip_field}",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "json",
        },
        timeout=30,
    )
    data = resp.json()

    new_parks = []
    skipped = 0
    out_of_scope = 0
    for feature in data.get("features", []):
        attrs = feature["attributes"]
        name = (attrs.get(name_field) or "").strip()
        geometry = feature.get("geometry")
        if not name or not geometry:
            skipped += 1
            continue
        city = (attrs.get(city_field) or "").strip()
        if city not in TRACKED_CITIES:
            out_of_scope += 1
            continue
        address = (attrs.get(street_field) or "").strip()
        if (name, address) in existing_keys:
            continue
        new_parks.append(
            {
                "name": name,
                "address": address,
                "city": city,
                "zip_code": (attrs.get(zip_field) or "").strip(),
                "latitude": geometry["y"],
                "longitude": geometry["x"],
                "visited": "N",
                "visited_date": "",
            },
        )
    if skipped:
        print(f"Skipped {skipped} King County row(s) missing a name or geometry.", file=sys.stderr)
    if out_of_scope:
        print(f"Filtered out {out_of_scope} King County park(s) outside existing cities.", file=sys.stderr)
    print("Finished fetching King County.")
    return new_parks


FETCH_FUNCTIONS = (
    fetch_new_parks,
    fetch_new_shoreline_parks,
    fetch_new_bellevue_parks,
    fetch_new_mercer_island_parks,
    fetch_new_kirkland_parks,
    fetch_new_redmond_parks,
    fetch_new_medina_parks,
    fetch_new_burien_parks,
    fetch_new_tukwila_parks,
    fetch_new_renton_parks,
    fetch_new_seatac_parks,
    fetch_new_kent_parks,
    fetch_new_des_moines_parks,
    fetch_new_federal_way_parks,
    fetch_new_auburn_parks,
    fetch_new_lake_forest_park_parks,
    fetch_new_kenmore_parks,
    fetch_new_bothell_parks,
    fetch_new_woodinville_parks,
    fetch_new_king_county_parks,
)
