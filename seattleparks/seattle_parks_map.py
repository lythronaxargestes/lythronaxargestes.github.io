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
  - Mercer Island: names and coordinates for most parks come from a
    Drupal.settings JSON blob embedded in the listing page's <script> tag
    (feeding an OpenLayers map widget) — no geocoding needed there either.
    That blob has no address field, so each park's own page is fetched too,
    for its schema.org PostalAddress microdata (streetAddress/
    addressLocality/postalCode). That map widget only covers a curated
    subset of parks though, so the city's full parks directory page is also
    scraped for its /parksrec/page/<slug> links to catch the rest (e.g.
    Aubrey Davis Park); a linked page only counts as a real park page if it
    has that same address microdata (filtering out the directory's
    informational pages — Trails, Off-Leash Dog Areas, event announcements —
    without a hardcoded exclude list), and since those extra pages have no
    coordinates of their own, each is geocoded via the free US Census
    geocoder from its address instead.
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
  - King County: county-owned/managed parks, rather than a per-city source, so
    it spans every city in the county (plus unincorporated areas) instead of
    just one. Found via the "Backyard Fun Finder" ArcGIS Experience Builder
    app (experience.arcgis.com/experience/26b4c16e5df04456a588454b2b5bc0ee)'s
    underlying web map, whose operational layer is a joined park-label-point /
    facilities-table layer on the county's own ArcGIS Server (not ArcGIS
    Online) -- the join makes every field name fully-qualified (e.g.
    "plibrary.recreatn.park_label_point.SiteName"). Only kept for cities
    already covered by one of the other sources above (TRACKED_CITIES) --
    e.g. a Renton or Auburn county park is kept, a Vashon or Sammamish one is
    dropped, since this project doesn't otherwise track those cities. Direct
    point geometry; address comes from the joined facilities table's
    A_Street/A_City/A_Zip fields (A_Zip has trailing whitespace in the source
    data, stripped like every other source's zip).

Dog parks, cemeteries, gyms, and "complex"-named facilities (e.g. sports
complexes) are excluded from every source (by a name-keyword check applied
after fetching, not per-source) — this project tracks parks in the
traditional sense, not off-leash areas, burial grounds, standalone fitness
facilities, or multi-use athletic complexes. Any "center" (community center,
rec center, senior center, etc.) is excluded the same way, since those are
recreation facilities rather than parkland, unless "Park" also appears in the
name (e.g. a park that happens to house a community center building). None of
these rules apply to the city of Seattle (e.g. its Grand Army of the Republic
Cemetery and Amy Yee Tennis Center are kept regardless).

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
    pip install requests folium beautifulsoup4 lxml tqdm

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
import json
import sys
from datetime import date

import folium
from folium.plugins import LocateControl

from seattle_parks_constants import (
    CSV_FIELDS,
    CSV_PATH,
    FAVICON_PATH,
    MAP_PATH,
    MAP_TITLE,
    MARKER_RADIUS,
    UNVISITED_COLOR,
    VISITED_COLOR,
)
from seattle_parks_fetch import FETCH_FUNCTIONS
from seattle_parks_helpers import (
    _apply_backup_data,
    _format_visited_date,
    _is_excluded_name,
    _is_visited,
    _load_existing_parks,
    _normalize_name,
    _parks_visited_since,
    _read_last_updated_date,
    load_parks_from_csv,
)


def sync_parks() -> list[dict]:
    """Fetch from all sources. Existing CSV rows are kept exactly as-is (order and
    edits untouched); only parks not already present are appended."""
    existing = _load_existing_parks()
    existing_keys = {(p["name"], p["address"]) for p in existing}
    new_parks = []
    for fetch in FETCH_FUNCTIONS:
        found = fetch(existing_keys)
        for p in found:
            p["name"] = _normalize_name(p["name"])
        existing_keys |= {(p["name"], p["address"]) for p in found}
        new_parks += found
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


def plot_map(parks: list[dict], last_updated: str, since_date: str | None) -> None:
    avg_lat = sum(p["latitude"] for p in parks) / len(parks)
    avg_lon = sum(p["longitude"] for p in parks) / len(parks)

    m = folium.Map(location=[avg_lat, avg_lon], zoom_start=11, tiles="cartodbpositron")
    m.get_root().title = MAP_TITLE
    LocateControl(position="topleft", strings={"title": "Find my location"}).add_to(m)
    try:
        with open(FAVICON_PATH, "rb") as f:
            favicon_b64 = base64.b64encode(f.read()).decode()
        m.get_root().header.add_child(
            folium.Element(f'<link rel="icon" type="image/png" href="data:image/png;base64,{favicon_b64}">'),
        )
    except FileNotFoundError:
        pass
    latest_parks = _parks_visited_since(parks, since_date)
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
    last_updated_html = (
        f'<div id="lastUpdated" data-date="{last_updated}" '
        f'style="font-size: 12px; font-weight: 400; margin-top: 8px; color: #5a5a52;">'
        f"Last updated: {_format_visited_date(last_updated)}</div>"
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
      {last_updated_html}
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

    since_date = _read_last_updated_date()
    last_updated = date.today().isoformat()

    if args.from_csv:
        try:
            parks = load_parks_from_csv()
        except FileNotFoundError:
            print(f"{CSV_PATH} not found — run without --from-csv first.", file=sys.stderr)
            sys.exit(1)
        plot_map(_apply_backup_data(parks), last_updated, since_date)
    else:
        parks = sync_parks()
        if not parks:
            print("No park data retrieved — aborting.", file=sys.stderr)
            sys.exit(1)
        write_csv(parks)
        plot_map(_apply_backup_data(parks), last_updated, since_date)


if __name__ == "__main__":
    main()
