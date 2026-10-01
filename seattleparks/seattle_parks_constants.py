"""Constants shared by seattle_parks_fetch.py, seattle_parks_helpers.py, and
seattle_parks_map.py: Per-source URLs/regexes, exclusion rules, and file paths."""
import re

# HTTP fetch behavior
USER_AGENT = "seattle-parks-map-script/1.0 (personal park-tracking project)"
MAX_FETCH_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 5

# Shared geocoding endpoint (Tukwila, Federal Way, Bothell, Woodinville addresses
# with no coordinates of their own)
CENSUS_GEOCODE_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
# Census TIGERweb layer of current ZIP Code Tabulation Areas, for point-in-polygon zip lookups
CENSUS_ZCTA_URL = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/PUMA_TAD_TAZ_UGA_ZCTA/MapServer/11/query"

# Per-source URLs, in the same city order as the module docstring above
API_URL = "https://data.seattle.gov/resource/ajyh-m2d3.json"
SHORELINE_URL = "https://gis.shorelinewa.gov/server/rest/services/PublicFacing/Parks/MapServer/5/query"
BELLEVUE_BASE_URL = "https://bellevuewa.gov"
BELLEVUE_LIST_URL = "https://bellevuewa.gov/city-government/departments/parks/parks-and-trails/parks"
MERCER_ISLAND_BASE_URL = "https://www.mercerisland.gov"
MERCER_ISLAND_LIST_URL = "https://www.mercerisland.gov/parksites"
# The /parksites map widget only covers a curated subset of parks; this full
# directory page lists several more (e.g. Aubrey Davis Park) that never appear
# in that widget at all.
MERCER_ISLAND_DIRECTORY_URL = "https://www.mercerisland.gov/parksrec/page/parks"
KIRKLAND_URL = "https://maps.kirklandwa.gov/host/rest/services/Parks/FeatureServer/0/query"
REDMOND_URL = "https://gis.redmond.gov/arcgis/rest/services/PV/Cadastral/MapServer/2/query"
MEDINA_BASE_URL = "https://www.medina-wa.gov"
MEDINA_LIST_URL = "https://www.medina-wa.gov/publicworks/page/city-parks"
# Clyde Hill and Yarrow Point publish only a prose list of parks (no map data,
# no coordinates), so their few parks are listed here by hand: (name, address,
# latitude, longitude). Source pages: CLYDE_HILL_PARKS_URL, YARROW_POINT_PARKS_URL.
CLYDE_HILL_PARKS_URL = "https://clydehill.org/government/departments/public_works/parks.php"
CLYDE_HILL_PARKS = (
    # OSM's "Clyde Hill City Park" polygon centre (way 422278031)
    ("Clyde Hill Park", "Near 9605 NE 24th St", 47.6299295, -122.2133213),
    # The next three: Census geocoder, at the cross streets the city gives
    ("Muromoto Memorial Park", "92nd Ave NE & NE 26th St", 47.633766, -122.217803),
    ("NE 97th & NE 14th St Park", "97th Ave NE & NE 14th St", 47.622924, -122.211586),
    ("Rogerson Corner Park", "NE 24th St & 98th Ave NE", 47.631982, -122.209724),
)
# Algona: the city's seven parks (comprehensive plan inventory), with addresses or
# cross streets from King County's South King County Parks Guide. Coordinates are
# OSM park polygon centres, except Waffle Park (Census geocoder at its address)
# and 3rd Avenue Pocket Park (approximate: where 3rd Ave N meets the Interurban
# Trail; no address or map data is published for it).
ALGONA_PARKS_URL = "https://www.algonawa.gov/services/public_works/parks.php"
ALGONA_PARKS = (
    ("John Matchett Memorial Park", "400 Warde St", 47.2776597, -122.2483127),
    ("David E. Hill Wetland Preserve", "Pacific Ave N & Ellingson Rd", 47.2700421, -122.2415588),
    ("7th Avenue Park", "7th Ave N & Main St", 47.2875415, -122.2570722),
    ("Stanley Avenue Park", "Stanley Ave & Pullman Ave", 47.2808699, -122.2479254),
    ("Stanley Tot Lot", "Stanley Ave & Iron Ave", 47.2813432, -122.2475381),
    ("Waffle Park", "290 1st Ave N", 47.279042, -122.252306),
    ("3rd Avenue Pocket Park", "3rd Ave N", 47.2815, -122.2492),
)
HUNTS_POINT_PARKS_URL = "https://huntspoint-wa.gov/wetherillnaturepreserve"
HUNTS_POINT_PARKS = (
    # Next to Town Hall (3000 Hunts Point Rd); OSM way 422278032. Wetherill Nature
    # Preserve, which Hunts Point shares with Yarrow Point, is listed once, under
    # Yarrow Point, below.
    ("D. K. McDonald Park", "3000 Hunts Point Rd", 47.63708, -122.2271792),
)
# King County Parks natural areas in unincorporated North Highline (the Census's
# "Boulevard Park" area, the remains of the old Riverton-Boulevard Park CDP), which
# have no city source. Glendale Forest: King County Parks page; OSM park way centre.
# Hamm Creek Natural Area: OSM nature reserve centre (King County strategic
# acquisitions map). Labelled Burien, the mailing city King County itself gives.
BOULEVARD_PARK_PARKS_URL = "https://kingcounty.gov/en/dept/dnrp/nature-recreation/parks-recreation/king-county-parks/natural-working-lands/glendale-forest"
BOULEVARD_PARK_PARKS = (
    ("Glendale Forest", "8th Ave S & S 104th St", 47.5109909, -122.3225427),
    ("Hamm Creek Natural Area", "", 47.511591, -122.3104671),
)
YARROW_POINT_PARKS_URL = "https://yarrowpointwa.gov/public-spaces/"
YARROW_POINT_PARKS = (
    # Morningside Park keeps the Town Hall address, so Kirkland's layer (which also
    # lists it) dedups against it by (name, address); OSM way 922988438
    ("Morningside Park", "4030 95th Ave NE", 47.6470909, -122.2130823),
    ("Road End Beach", "9000 NE 47th St", 47.6518672, -122.2180739),  # OSM way 449744782
    ("42nd Street Launch Area", "NE 42nd St & 91st Ave NE", 47.647439, -122.218895),  # Census geocoder
    ("Sally's Alley", "Between 94th & 95th Ave NE", 47.6446083, -122.214422),  # OSM way 925741916
    ("Wetherill Nature Preserve", "", 47.6394891, -122.2229699),  # OSM relation 6278123
)
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
NEWCASTLE_URL = "https://services6.arcgis.com/kvG4x0h4KLP0c8nr/arcgis/rest/services/City_Park_Areas/FeatureServer/0/query"
NORMANDY_PARK_URL = "https://services7.arcgis.com/5d703jjhemO6FlIW/arcgis/rest/services/NP_Parks/FeatureServer/0/query"
KENMORE_URL = "https://gwa.kenmorewa.gov/arcgis/rest/services/Parks/FeatureServer/20/query"
BOTHELL_BASE_URL = "https://www.bothellwa.gov"
BOTHELL_LIST_URL = "https://www.bothellwa.gov/250/Parks"
WOODINVILLE_DETAIL_URL = "https://www.woodinville.gov/Facilities/Facility/Details/{}"
WOODINVILLE_PARK_IDS = (4, 5, 6, 7, 14, 15, 16, 17)
KING_COUNTY_URL = "https://gismaps.kingcounty.gov/arcgis/rest/services/Parks/KingCo_ParksAndTrails/MapServer/0/query"

# Address-parsing/recasing helpers
ALLCAPS_ADDRESS_DIRECTIONALS = {"N", "S", "E", "W", "NE", "NW", "SE", "SW"}
FEDERAL_WAY_ADDRESS_RE = re.compile(r"^(.*?),\s*Federal Way,\s*WA\s*(\d{5})$")
FEDERAL_WAY_COORD_RE = re.compile(r"cp=([\-0-9.]+)~([\-0-9.]+)")
LAKE_FOREST_PARK_ADDRESS_RE = re.compile(r"^(.*?),\s*Lake Forest Park,\s*WA\s*(\d{5})$")
BOTHELL_ADDRESS_RE = re.compile(r"^(.*?),\s*Bothell,\s*WA\s*(\d{5})$")

# Name-exclusion and geographic-scope rules
# Whole-word match (plural allowed), so e.g. "Dogwood Park" isn't excluded
EXCLUDED_NAME_RE = re.compile(r"\b(?:dog|off-leash|cemetery|cemetary|gym|complex)(?:e?s)?\b", re.IGNORECASE)
# Mean Earth radius in meters, for distance between coordinates
EARTH_RADIUS_M = 6371000
# Same-city, same-name parks this close together are treated as one park
DUPLICATE_DISTANCE_M = 100
# Parks at the same address this close together are one park, whatever their names
SAME_SPOT_DISTANCE_M = 5
TRACKED_CITIES = (
    "Seattle",
    "Shoreline",
    "Bellevue",
    "Mercer Island",
    "Kirkland",
    "Redmond",
    "Medina",
    "Clyde Hill",
    "Yarrow Point",
    "Hunts Point",
    "Burien",
    "Tukwila",
    "Renton",
    "SeaTac",
    "Kent",
    "Des Moines",
    "Federal Way",
    "Auburn",
    "Lake Forest Park",
    "Kenmore",
    "Newcastle",
    "Algona",
    "Normandy Park",
    "Bothell",
    "Woodinville",
)

# File paths
CSV_PATH = "seattle_parks.csv"
BACKUP_CSV_PATH = "seattle_parks_missing_data_backup.csv"
MAP_PATH = "seattle_parks_map.html"
FAVICON_PATH = "seattle_parks_favicon.png"

# Matches the data-date attribute plot_map() stamps into its own "Last updated"
# element, so the next run can read the previous run's date straight out of the
# map HTML it's about to overwrite -- no separate state file needed.
LAST_UPDATED_RE = re.compile(r'id="lastUpdated" data-date="(\d{4}-\d{2}-\d{2})"')

# CSV schema
CSV_FIELDS = ["name", "address", "city", "zip_code", "latitude", "longitude", "visited", "visited_date"]
DEFAULT_CITY = "Seattle"

# Map display
MAP_TITLE = "Seattle Parks Project"
# Visited is a state, not an identity, so it uses the dataviz status palette
# ("good") rather than a categorical hue. Not-visited was originally the
# default single-hue blue (palette slot 1) from the original single-category
# map, but that's the same blue Leaflet's LocateControl uses for the user's
# own "you are here" marker, so it's red instead to avoid the visual clash.
VISITED_COLOR = "#0ca30c"
UNVISITED_COLOR = "#d62a2a"
MARKER_RADIUS = 6  # px
