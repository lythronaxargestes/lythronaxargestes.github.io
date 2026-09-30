"""Generic, city-agnostic helpers shared by seattle_parks_fetch.py and
seattle_parks_map.py: HTTP retries, geocoding, polygon centroids, all-caps
recasing, CSV load/exclusion, and visited-date formatting. Parsing helpers tied
to one specific city's page/API markup live in seattle_parks_fetch.py instead,
next to the fetch function that uses them."""
from __future__ import annotations

import csv
import math
import re
import sys
import time
import unicodedata
from datetime import datetime

import requests

from seattle_parks_constants import (
    ALLCAPS_ADDRESS_DIRECTIONALS,
    BACKUP_CSV_PATH,
    CENSUS_GEOCODE_URL,
    CSV_PATH,
    DEFAULT_CITY,
    DUPLICATE_DISTANCE_M,
    EARTH_RADIUS_M,
    EXCLUDED_NAME_RE,
    LAST_UPDATED_RE,
    MAP_PATH,
    MAX_FETCH_ATTEMPTS,
    RETRY_BACKOFF_SECONDS,
    SAME_SPOT_DISTANCE_M,
)


def normalize_name(name: str) -> str:
    """Normalize to Unicode NFC so cosmetically-identical park names compare
    equal even if their combining-character sequences differ byte-for-byte
    (e.g. an accented/Indigenous name copied from two different sources) --
    a raw string mismatch here silently breaks dedup and backup-CSV lookups
    without raising any error, since both spellings render the same on screen."""
    return unicodedata.normalize("NFC", name)


def is_excluded_name(name: str, city: str) -> bool:
    """True if this park should be dropped: a blanket-excluded keyword (dog
    parks, cemeteries, gyms), or a standalone center -- e.g. a community/rec/
    senior center, a recreation facility rather than parkland -- unless "park"
    also appears in the name. None of these rules apply to Seattle (e.g. its
    Grand Army of the Republic Cemetery and Amy Yee Tennis Center are kept
    regardless)."""
    if city == "Seattle":
        return False
    lower = name.lower()
    if EXCLUDED_NAME_RE.search(lower):
        return True
    return "center" in lower and "park" not in lower


ADDRESS_ABBREVIATIONS = {
    "&": "and", "st": "street", "dr": "drive", "ave": "avenue", "blvd": "boulevard",
    "rd": "road", "pl": "place", "ln": "lane", "ct": "court", "pkwy": "parkway",
    "n": "north", "s": "south", "e": "east", "w": "west",
    "ne": "northeast", "nw": "northwest", "se": "southeast", "sw": "southwest",
}


def normalize_address(address: str) -> str:
    """Lowercase and expand common abbreviations so the same street address
    spelled two ways ("NE 138th St & Juanita Dr NE" vs "NE 138th St and Juanita
    Drive NE") compares equal."""
    tokens = re.findall(r"[a-z0-9]+|&", address.lower())
    return " ".join(ADDRESS_ABBREVIATIONS.get(t, t) for t in tokens)


def distance_m(a: dict, b: dict) -> float:
    """Approximate distance in meters between two parks (equirectangular; fine at
    the tens-of-meters scale this is used for)."""
    x = math.radians(b["longitude"] - a["longitude"]) * math.cos(math.radians(a["latitude"]))
    y = math.radians(b["latitude"] - a["latitude"])
    return EARTH_RADIUS_M * math.hypot(x, y)


def is_duplicate_park(park: dict, others: list[dict]) -> bool:
    """True if `park` is the same park as one in `others` but reported by a
    different source with a slightly different name/address spelling, which the
    exact (name, address) check in each fetch function can't catch. Same city
    required, plus either:
      - the same name (case-insensitive) and either the same normalized address
        or a location within DUPLICATE_DISTANCE_M ("Big Finn Hill Park" listed
        by two sources); or
      - the same normalized address and a location within SAME_SPOT_DISTANCE_M
        regardless of name ("Magnuson Park" vs "Warren G. Magnuson Park").
    Name alone isn't enough (many cities have their own "Rotary Park"), and
    neither is a shared address (city directory pages often list one address
    for several different parks). Fuzzy name matching (one name contained in
    the other) was tried and rejected: it merges many distinct neighbors, e.g.
    "Woodland Park Zoo" / "Woodland Park" or "Rotary Park" / "Rotary D"."""
    address = normalize_address(park["address"])
    for other in others:
        if other["city"] != park["city"]:
            continue
        same_address = bool(address) and address == normalize_address(other["address"])
        distance = distance_m(park, other)
        if same_address and distance <= SAME_SPOT_DISTANCE_M:
            return True
        if park["name"].casefold() == other["name"].casefold() and (
            same_address or distance <= DUPLICATE_DISTANCE_M
        ):
            return True
    return False


def is_visited(value: str) -> bool:
    return str(value).strip().upper() == "Y"


def parks_visited_since(parks: list[dict], since_date: str | None) -> list[dict]:
    """Return every park visited on or after `since_date` (the "Last updated" date
    stamped into the previous run's map -- see read_last_updated_date), earliest-
    visited first. This surfaces every visit logged since that map was last
    regenerated, not just the single latest day, since parks are often marked
    visited by hand across several different days between runs. Falls back to
    parks sharing the single latest visited_date if since_date is unknown (e.g.
    the very first run, before any map has ever been generated)."""
    dated = [p for p in parks if str(p.get("visited_date", "")).strip()]
    if not dated:
        return []
    if since_date is None:
        since_date = max(p["visited_date"] for p in dated)
    matches = [p for p in dated if p["visited_date"] >= since_date]
    matches.sort(key=lambda p: p["name"].lower())
    matches.sort(key=lambda p: p["visited_date"])
    return matches


def read_last_updated_date() -> str | None:
    """Read the "Last updated" date stamped into the existing map HTML (the one
    this run is about to overwrite), or None if there's no existing map yet (the
    very first run) or it predates this feature."""
    try:
        with open(MAP_PATH, encoding="utf-8") as f:
            html = f.read()
    except FileNotFoundError:
        return None
    match = LAST_UPDATED_RE.search(html)
    return match.group(1) if match else None


def format_visited_date(value: str) -> str | None:
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
                "name": normalize_name(row["name"]),
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


def load_existing_parks() -> list[dict]:
    """Same as load_parks_from_csv(), but an absent file just means "no existing rows"."""
    try:
        return load_parks_from_csv()
    except FileNotFoundError:
        return []


def apply_backup_data(parks: list[dict]) -> list[dict]:
    """Enrich `parks` for display using seattle_parks_missing_data_backup.csv (hand
    researched via web search) -- backup data wins whenever it's present, falling
    back to the main CSV's own value for any field the backup left blank. This
    covers both parks already present (matched by name+city) whose primary-source
    address/coordinates were missing or wrong (e.g. a city's own directory page
    listing the same address for several different parks), and parks missing
    entirely from the main CSV (in_main_csv='N') when the backup found usable
    coordinates. This never writes back to seattle_parks.csv -- it's applied fresh
    at render time only, so the primary CSV's (name, address) dedup keys, which
    each city's live fetch depends on to avoid re-adding parks on the next sync,
    are never disturbed by backup-sourced values."""
    try:
        with open(BACKUP_CSV_PATH, newline="", encoding="utf-8") as f:
            backup_rows = list(csv.DictReader(f))
    except FileNotFoundError:
        return parks

    enriched = [dict(p) for p in parks]
    by_key = {(p["name"], p["city"]): p for p in enriched}

    for row in backup_rows:
        key = (normalize_name(row["name"]), row["city"])
        found_address = (row.get("found_address") or "").strip()
        found_zip = (row.get("found_zip") or "").strip()
        found_lat = (row.get("found_latitude") or "").strip()
        found_lon = (row.get("found_longitude") or "").strip()

        if row.get("in_main_csv") == "Y":
            park = by_key.get(key)
            if park is not None:
                if found_address:
                    park["address"] = found_address
                if found_zip:
                    park["zip_code"] = found_zip
                if found_lat and found_lon:
                    park["latitude"] = float(found_lat)
                    park["longitude"] = float(found_lon)
        elif row.get("in_main_csv") == "N" and key not in by_key and found_lat and found_lon:
            new_park = {
                "name": normalize_name(row["name"]),
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

    return [p for p in enriched if not is_excluded_name(p["name"], p["city"])]


def get_with_retries(url: str, **kwargs) -> requests.Response:
    """GET url, retrying up to MAX_FETCH_ATTEMPTS times (with a growing backoff)
    on timeouts/connection errors or 5xx server errors -- transient failures
    seen in practice (e.g. bellevuewa.gov intermittently stalling partway
    through its ~80 individual park pages). Raises immediately on a non-5xx
    HTTP error (e.g. 404), since retrying won't help, or on the final
    attempt's failure otherwise."""
    for attempt in range(1, MAX_FETCH_ATTEMPTS + 1):
        try:
            resp = requests.get(url, **kwargs)
            resp.raise_for_status()
            return resp
        except requests.exceptions.HTTPError:
            if resp.status_code < 500 or attempt == MAX_FETCH_ATTEMPTS:
                raise
        except requests.exceptions.RequestException:
            if attempt == MAX_FETCH_ATTEMPTS:
                raise
        print(f"Retrying {url} (attempt {attempt} failed)...", file=sys.stderr)
        time.sleep(RETRY_BACKOFF_SECONDS * attempt)
    raise AssertionError("unreachable: last attempt always returns or raises")


def polygon_centroid(rings: list[list[list[float]]]) -> tuple[float, float]:
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


def geocode_census(address: str, city: str, state: str = "WA") -> tuple[float, float, str] | None:
    """Look up (latitude, longitude, zip) for a one-line address via the free US
    Census geocoder. Returns None if it can't find a match (e.g. an address with
    no house number or an unrecognized cross-street), or if its best match lands
    in a different city than expected -- the geocoder doesn't always reject a bad
    address outright; it can instead return a confident-looking match in some
    other, same-named-street city (e.g. it once matched a Tukwila intersection
    address to a street in Bellingham, ~90 miles north)."""
    resp = get_with_retries(
        CENSUS_GEOCODE_URL,
        params={"address": f"{address}, {city}, {state}", "benchmark": "Public_AR_Current", "format": "json"},
        timeout=15,
    )
    matches = resp.json()["result"]["addressMatches"]
    if not matches:
        return None
    match = matches[0]
    matched_city = match["addressComponents"].get("city", "")
    if matched_city.strip().casefold() != city.strip().casefold():
        return None
    return match["coordinates"]["y"], match["coordinates"]["x"], match["addressComponents"].get("zip", "")


def normalize_allcaps_text(text: str) -> str:
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
