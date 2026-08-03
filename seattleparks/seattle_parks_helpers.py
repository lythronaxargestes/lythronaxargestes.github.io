"""Generic, city-agnostic helpers shared by seattle_parks_fetch.py and
seattle_parks_map.py: HTTP retries, geocoding, polygon centroids, all-caps
recasing, CSV load/exclusion, and visited-date formatting. Parsing helpers tied
to one specific city's page/API markup live in seattle_parks_fetch.py instead,
next to the fetch function that uses them."""
from __future__ import annotations

import csv
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
    EXCLUDED_NAME_KEYWORDS,
    MAX_FETCH_ATTEMPTS,
    RETRY_BACKOFF_SECONDS,
)


def _normalize_name(name: str) -> str:
    """Normalize to Unicode NFC so cosmetically-identical park names compare
    equal even if their combining-character sequences differ byte-for-byte
    (e.g. an accented/Indigenous name copied from two different sources) --
    a raw string mismatch here silently breaks dedup and backup-CSV lookups
    without raising any error, since both spellings render the same on screen."""
    return unicodedata.normalize("NFC", name)


def _is_excluded_name(name: str, city: str) -> bool:
    """True if this park should be dropped: a blanket-excluded keyword (dog
    parks, cemeteries, gyms), or a standalone center -- e.g. a community/rec/
    senior center, a recreation facility rather than parkland -- unless "park"
    also appears in the name. None of these rules apply to Seattle (e.g. its
    Grand Army of the Republic Cemetery and Amy Yee Tennis Center are kept
    regardless)."""
    if city == "Seattle":
        return False
    lower = name.lower()
    if any(kw in lower for kw in EXCLUDED_NAME_KEYWORDS):
        return True
    return "center" in lower and "park" not in lower


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
                "name": _normalize_name(row["name"]),
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
        key = (_normalize_name(row["name"]), row["city"])
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
                "name": _normalize_name(row["name"]),
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


def _get_with_retries(url: str, **kwargs) -> requests.Response:
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


def _geocode_census(address: str, city: str, state: str = "WA") -> tuple[float, float, str] | None:
    """Look up (latitude, longitude, zip) for a one-line address via the free US
    Census geocoder. Returns None if it can't find a match (e.g. an address with
    no house number or an unrecognized cross-street), or if its best match lands
    in a different city than expected -- the geocoder doesn't always reject a bad
    address outright; it can instead return a confident-looking match in some
    other, same-named-street city (e.g. it once matched a Tukwila intersection
    address to a street in Bellingham, ~90 miles north)."""
    resp = _get_with_retries(
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
