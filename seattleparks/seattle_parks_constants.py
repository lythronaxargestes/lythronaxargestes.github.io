"""Constants shared by seattle_parks_fetch.py, seattle_parks_helpers.py, and
seattle_parks_map.py: per-source URLs/regexes, exclusion rules, and file paths."""
import re

# HTTP fetch behavior
USER_AGENT = "seattle-parks-map-script/1.0 (personal park-tracking project)"
MAX_FETCH_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 5

# Shared geocoding endpoint (Tukwila, Federal Way, Bothell, Woodinville addresses
# with no coordinates of their own)
CENSUS_GEOCODE_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"

# Per-source URLs, in the same city order as the module docstring above
API_URL = "https://data.seattle.gov/resource/ajyh-m2d3.json"
SHORELINE_URL = "https://gis.shorelinewa.gov/server/rest/services/PublicFacing/Parks/MapServer/5/query"
BELLEVUE_BASE_URL = "https://bellevuewa.gov"
BELLEVUE_LIST_URL = "https://bellevuewa.gov/city-government/departments/parks/parks-and-trails/parks"
MERCER_ISLAND_BASE_URL = "https://www.mercerisland.gov"
MERCER_ISLAND_LIST_URL = "https://www.mercerisland.gov/parksites"
KIRKLAND_URL = "https://maps.kirklandwa.gov/host/rest/services/Parks/FeatureServer/0/query"
REDMOND_URL = "https://gis.redmond.gov/arcgis/rest/services/PV/Cadastral/MapServer/2/query"
MEDINA_BASE_URL = "https://www.medina-wa.gov"
MEDINA_LIST_URL = "https://www.medina-wa.gov/publicworks/page/city-parks"
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
KING_COUNTY_URL = "https://gismaps.kingcounty.gov/arcgis/rest/services/Parks/KingCo_ParksAndTrails/MapServer/0/query"

# Address-parsing/recasing helpers
ALLCAPS_ADDRESS_DIRECTIONALS = {"N", "S", "E", "W", "NE", "NW", "SE", "SW"}
FEDERAL_WAY_ADDRESS_RE = re.compile(r"^(.*?),\s*Federal Way,\s*WA\s*(\d{5})$")
FEDERAL_WAY_COORD_RE = re.compile(r"cp=([\-0-9.]+)~([\-0-9.]+)")
LAKE_FOREST_PARK_ADDRESS_RE = re.compile(r"^(.*?),\s*Lake Forest Park,\s*WA\s*(\d{5})$")
BOTHELL_ADDRESS_RE = re.compile(r"^(.*?),\s*Bothell,\s*WA\s*(\d{5})$")

# Name-exclusion and geographic-scope rules
EXCLUDED_NAME_KEYWORDS = ("dog park", "cemetery", "cemetary", "gym", "complex")
TRACKED_CITIES = (
    "Seattle",
    "Shoreline",
    "Bellevue",
    "Mercer Island",
    "Kirkland",
    "Redmond",
    "Medina",
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
    "Bothell",
    "Woodinville",
)

# File paths
CSV_PATH = "seattle_parks.csv"
BACKUP_CSV_PATH = "seattle_parks_missing_data_backup.csv"
MAP_PATH = "seattle_parks_map.html"
FAVICON_PATH = "seattle_favicon.png"

# CSV schema
CSV_FIELDS = ["name", "address", "city", "zip_code", "latitude", "longitude", "visited", "visited_date"]
DEFAULT_CITY = "Seattle"

# Map display
MAP_TITLE = "Seattle Parks Project"
# Visited is a state, not an identity, so it uses the dataviz status palette
# ("good") rather than a categorical hue; not-visited keeps the default
# single-hue blue (palette slot 1) from the original single-category map.
VISITED_COLOR = "#0ca30c"
UNVISITED_COLOR = "#2a78d6"
MARKER_RADIUS = 6  # px
