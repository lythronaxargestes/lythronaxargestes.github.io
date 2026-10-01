"""Parks that none of the live sources list, so they're written down here by hand and
added to the CSV by fetch_new_extra_parks (seattle_parks_fetch.py), like any other
source's parks (they can be marked visited in the CSV afterward). That covers:

  - Parks in towns without usable map data (Clyde Hill, Yarrow Point, Hunts Point,
    Algona, Pacific, and Milton), plus King County's natural areas in unincorporated Boulevard Park
    (Glendale Forest and Hamm Creek, labelled Burien).
  - Parks that a source's data misses, such as Walker Preserve and Brittany Park in
    Normandy Park, three Newcastle parks, and several Bothell, Federal Way, Tukwila,
    and Woodinville parks.

Each park's comment gives its source and how sure the location is. Where the
sources disagree or only give a rough position, the coordinates are approximate.
"""
from __future__ import annotations

from seattle_parks_helpers import ListedPark

EXTRA_PARKS: tuple[ListedPark, ...] = (
    # Bothell
    # Doug Allen Sportsfields - Approximate - address confirmed by city site/Yelp/Zillow, but
    # not directly in Census TIGER ranges; lat/lon interpolated between neighboring geocoded
    # addresses on the same street. Source:
    # https://www.bothellwa.gov/1665/Doug-Allen-Sportsfields
    ListedPark(
        name="Doug Allen Sportsfields",
        address="19417 88th Ave NE",
        latitude=47.7696,
        longitude=-122.2233,
        city="Bothell",
        zip_code="98011",
    ),
    # Former Wayne Golf Course - High confidence - clubhouse/main access address from official
    # city page, lat/lon exact-matched by Census Bureau geocoder. Source:
    # https://www.bothellwa.gov/1184/Former-Wayne-Golf-Course
    ListedPark(
        name="Former Wayne Golf Course",
        address="16721 96th Ave NE",
        latitude=47.74912,
        longitude=-122.21341,
        city="Bothell",
        zip_code="98011",
    ),
    # North Creek Sportsfields - Medium confidence - multi-field complex with several addresses
    # (also 11902/11905 North Creek Pkwy, 19113 120th Ave NE); Field #1 address used as
    # representative, may not be true centroid. Source:
    # https://www.bothellwa.gov/1669/North-Creek-Sportsfields
    ListedPark(
        name="North Creek Sportsfields",
        address="19016 North Creek Pkwy",
        latitude=47.76863,
        longitude=-122.18484,
        city="Bothell",
        zip_code="98011",
    ),
    # Volunteer Park - High confidence - street address confirmed on official city page; lat/lon
    # derived from the same corner parcel's other frontage address, corroborated by RecPlanet.
    # Source: https://www.bothellwa.gov/1663/Volunteer-Park
    ListedPark(
        name="Volunteer Park",
        address="9621 Main St",
        latitude=47.75994,
        longitude=-122.21167,
        city="Bothell",
        zip_code="98011",
    ),
    # William Penn Park - Medium confidence - address not on official city page, from a
    # third-party park directory, confirmed by exact Census geocoder match. Source:
    # https://www.mypacer.com/parks/123275/william-penn-park-bothell
    ListedPark(
        name="William Penn Park",
        address="19900 100th Ave NE",
        latitude=47.77239,
        longitude=-122.20689,
        city="Bothell",
        zip_code="98011",
    ),
    # Burien
    # Walker Creek Wetland - Approximate - no official park coordinate published; estimated from
    # OSM street-segment intersection, medium confidence. Source:
    # https://nominatim.openstreetmap.org
    ListedPark(
        name="Walker Creek Wetland",
        address="South 176th Street and Des Moines Memorial Drive South",
        latitude=47.4445,
        longitude=-122.3275,
        city="Burien",
        zip_code="98148",
    ),
    # Glendale Forest - Medium-high confidence - King County Parks natural area in
    # unincorporated North Highline (Boulevard Park), labelled Burien, the mailing city King
    # County gives; there is no city source. The coordinates are the center of OSM's park
    # polygon. Source:
    # https://kingcounty.gov/en/dept/dnrp/nature-recreation/parks-recreation/king-county-parks/natural-working-lands/glendale-forest
    ListedPark(
        name="Glendale Forest",
        address="8th Ave S & S 104th St",
        latitude=47.5109909,
        longitude=-122.3225427,
        city="Burien",
        zip_code="98168",
    ),
    # Hamm Creek Natural Area - Medium confidence - King County Parks natural area in
    # unincorporated North Highline (Boulevard Park), labelled Burien, the mailing city King
    # County gives; there is no city source. The coordinates are the center of OSM's nature
    # reserve (it appears on King County's strategic acquisitions map; ownership not confirmed).
    # Source:
    # https://kingcounty.gov/en/dept/dnrp/nature-recreation/parks-recreation/king-county-parks/natural-working-lands/glendale-forest
    ListedPark(
        name="Hamm Creek Natural Area",
        address="",
        latitude=47.511591,
        longitude=-122.3104671,
        city="Burien",
        zip_code="98168",
    ),
    # Federal Way
    # BPA Trail - Approximate - trail spans ~3.8 mi from Celebration Park to Madrona Park (508
    # SW 356th St); representative point is the documented north trailhead. Source:
    # https://www.wta.org/go-hiking/hikes/bpa-trail
    ListedPark(
        name="BPA Trail",
        address="1095 S 324th St (Celebration Park, north trailhead - no single address for the trail itself)",
        latitude=47.3078,
        longitude=-122.3197,
        city="Federal Way",
        zip_code="98003",
    ),
    # Hanwoori Korean Gardens & Panther Lake Trail - High confidence - house-level geocode
    # match, corroborated by a Yelp listing at the same address. Source:
    # https://nominatim.openstreetmap.org
    ListedPark(
        name="Hanwoori Korean Gardens & Panther Lake Trail",
        address="550 SW Campus Dr",
        latitude=47.29364,
        longitude=-122.34218,
        city="Federal Way",
        zip_code="98023",
    ),
    # Lakota Park - High confidence - direct OSM park polygon match confirms both address and
    # coordinates. Source: https://photon.komoot.io
    ListedPark(
        name="Lakota Park",
        address="31334 SW Dash Point Rd",
        latitude=47.3205,
        longitude=-122.35822,
        city="Federal Way",
        zip_code="98023",
    ),
    # Tukwila
    # 57th Avenue Mini Park - High confidence - official city page's map link resolves to a
    # Google-named place matching this exact park. Source:
    # https://www.tukwilawa.gov/departments/parks-and-recreation/parks-and-trails/57th-avenue-mini-park/
    ListedPark(
        name="57th Avenue Mini Park",
        address="13300 57th Avenue South",
        latitude=47.48422,
        longitude=-122.264333,
        city="Tukwila",
    ),
    # Bicentennial Park - High confidence - cross-confirmed by an independent search estimate
    # landing within meters of the official map-link pin. Source:
    # https://www.tukwilawa.gov/departments/parks-and-recreation/parks-and-trails/bicentennial-park/
    ListedPark(
        name="Bicentennial Park",
        address="7200 Strander Boulevard",
        latitude=47.45637,
        longitude=-122.247053,
        city="Tukwila",
    ),
    # Cecil Moses Park - Medium-high confidence - Google's place record cites a 27th Ave S
    # address (also seen independently as 11099 27th Ave S) rather than West Marginal Place
    # South; may have two associated addresses. Pin location for the park itself is confident.
    # Source:
    # https://www.tukwilawa.gov/departments/parks-and-recreation/parks-and-trails/cecil-moses-park/
    ListedPark(
        name="Cecil Moses Park",
        address="11013 West Marginal Place South",
        latitude=47.503673,
        longitude=-122.29831,
        city="Tukwila",
    ),
    # Duwamish Hill Preserve - High confidence - official city page's map link resolves to a
    # Google-named place with an exact name match corroborated independently. Source:
    # https://www.tukwilawa.gov/departments/parks-and-recreation/parks-and-trails/duwamish-hill-preserve/
    ListedPark(
        name="Duwamish Hill Preserve",
        address="3800 South 115th Street",
        latitude=47.501727,
        longitude=-122.285497,
        city="Tukwila",
    ),
    # Woodinville
    # Stonehill Meadows Park - Approximate - no park-specific coordinates found; lat/lon is a
    # proxy from Census TIGER geocoding of a neighboring residence described as directly across
    # from the park. Source:
    # https://www.woodinville.gov/facilities/facility/details/Stonehill-Meadows-Park-17
    ListedPark(
        name="Stonehill Meadows Park",
        address="134th Place NE (no house number found on official city page)",
        latitude=47.76229,
        longitude=-122.15942,
        city="Woodinville",
        zip_code="98072",
    ),
    # Tanglin Ridge Park - Approximate - no park-specific coordinates found; lat/lon is a proxy
    # from Census TIGER geocoding of three neighboring homes on the same block. Source:
    # https://www.woodinville.gov/facilities/facility/details/Tanglin-Ridge-Park-16
    ListedPark(
        name="Tanglin Ridge Park",
        address="NE 185th St (no house number found on official city page)",
        latitude=47.7617,
        longitude=-122.13901,
        city="Woodinville",
        zip_code="98072",
    ),
    # Woodin Creek Park - High confidence - city facilities page confirms address, coordinates
    # cross-validated by two independent sources within ~150m. Source:
    # https://www.atly.com/location/WoodinCreekPark
    ListedPark(
        name="Woodin Creek Park",
        address="13201 NE 171st Street",
        latitude=47.75092,
        longitude=-122.16393,
        city="Woodinville",
        zip_code="98072",
    ),
    # Mercer Island
    # Mercerdale Park - High confidence - OpenStreetMap has a direct named-polygon match for
    # this park; the free Census geocoder mismatches this address's cross-street format to a
    # street in Ephrata, WA (~150mi away) and is rejected by the fetch's own city-mismatch
    # safety check, so the main fetch skips this park entirely. Source:
    # https://www.mercerisland.gov/parksrec/page/mercerdale-park
    ListedPark(
        name="Mercerdale Park",
        address="77th Avenue SE & SE 32nd Street",
        latitude=47.580856,
        longitude=-122.2349175,
        city="Mercer Island",
        zip_code="98040",
    ),
    # Normandy Park
    # Walker Preserve - Medium-high confidence - missing from the city's GIS park layer; the
    # address is from the city's 2024 parks plan (27.73-acre open space along Walker Creek) and
    # the coordinates are the center of OSM's 'Walker Creek Preserve' polygon (way 703792747).
    # Source: https://www.openstreetmap.org/way/703792747;
    # https://normandyparkwa.gov/wp-content/uploads/NPPROST-Plan-Report-2024-FINAL.pdf
    ListedPark(
        name="Walker Preserve",
        address="168th St & SW 2nd Ave",
        latitude=47.4503045,
        longitude=-122.3432005,
        city="Normandy Park",
        zip_code="98166",
    ),
    # Brittany Park - Medium-high confidence - missing from the city's GIS park layer; the
    # address is from the city's 2024 parks plan (the first park established in Normandy Park,
    # 0.35 acres) and the coordinates are the center of OSM's 'Brittany Circle Park' polygon
    # (way 1536714190). Source: https://www.openstreetmap.org/way/1536714190;
    # https://normandyparkwa.gov/wp-content/uploads/NPPROST-Plan-Report-2024-FINAL.pdf
    ListedPark(
        name="Brittany Park",
        address="SW Normandy Terrace & Brittany Dr",
        latitude=47.4424886,
        longitude=-122.3515414,
        city="Normandy Park",
        zip_code="98166",
    ),
    # Newcastle
    # Hillside Park - Medium-high confidence - on the City of Newcastle's City Parks page
    # (neighborhood park, 5.5 acres) but missing from the city's GIS park layer; the coordinates
    # are the Census geocoder's match for the listed address. Source:
    # https://newcastlewa.gov/parks_and_trails/parks-trails/city-parks/
    ListedPark(
        name="Hillside Park",
        address="14356 SE 92nd St",
        latitude=47.518576,
        longitude=-122.148988,
        city="Newcastle",
        zip_code="98059",
    ),
    # Park at 95th - Medium-high confidence - on the City of Newcastle's City Parks page
    # (community park, 33.5 acres, undeveloped) but missing from the city's GIS park layer; the
    # coordinates are the Census geocoder's match for the listed address. Source:
    # https://newcastlewa.gov/parks_and_trails/parks-trails/city-parks/
    ListedPark(
        name="Park at 95th",
        address="12700 SE 95th Way",
        latitude=47.51778,
        longitude=-122.170814,
        city="Newcastle",
        zip_code="98056",
    ),
    # Newcastle Historical Park - Medium confidence - on the City of Newcastle's City Parks page
    # (0.25 acres, marked 'coming soon') but missing from the city's GIS park layer, so it may
    # not be open yet; the coordinates are the Census geocoder's match for the listed address.
    # Source: https://newcastlewa.gov/parks_and_trails/parks-trails/city-parks/
    ListedPark(
        name="Newcastle Historical Park",
        address="13600 SE 71st St",
        latitude=47.539629,
        longitude=-122.157204,
        city="Newcastle",
        zip_code="98059",
    ),
    # Clyde Hill
    # Clyde Hill Park - Medium-high confidence - Clyde Hill's parks page lists its parks in
    # prose only, with no map data. The coordinates are the center of OSM's 'Clyde Hill City
    # Park' polygon (way 422278031). Source:
    # https://clydehill.org/government/departments/public_works/parks.php
    ListedPark(
        name="Clyde Hill Park",
        address="Near 9605 NE 24th St",
        latitude=47.6299295,
        longitude=-122.2133213,
        city="Clyde Hill",
        zip_code="98004",
    ),
    # Muromoto Memorial Park - Medium-high confidence - Clyde Hill's parks page lists its parks
    # in prose only, with no map data. The coordinates are the Census geocoder at the cross
    # streets the city gives. Source:
    # https://clydehill.org/government/departments/public_works/parks.php
    ListedPark(
        name="Muromoto Memorial Park",
        address="92nd Ave NE & NE 26th St",
        latitude=47.633766,
        longitude=-122.217803,
        city="Clyde Hill",
        zip_code="98004",
    ),
    # NE 97th & NE 14th St Park - Medium-high confidence - Clyde Hill's parks page lists its
    # parks in prose only, with no map data. The coordinates are the Census geocoder at the
    # cross streets the city gives. Source:
    # https://clydehill.org/government/departments/public_works/parks.php
    ListedPark(
        name="NE 97th & NE 14th St Park",
        address="97th Ave NE & NE 14th St",
        latitude=47.622924,
        longitude=-122.211586,
        city="Clyde Hill",
        zip_code="98004",
    ),
    # Rogerson Corner Park - Medium-high confidence - Clyde Hill's parks page lists its parks in
    # prose only, with no map data. The coordinates are the Census geocoder at the cross streets
    # the city gives. Source:
    # https://clydehill.org/government/departments/public_works/parks.php
    ListedPark(
        name="Rogerson Corner Park",
        address="NE 24th St & 98th Ave NE",
        latitude=47.631982,
        longitude=-122.209724,
        city="Clyde Hill",
        zip_code="98004",
    ),
    # Algona
    # John Matchett Memorial Park - Medium-high confidence - One of Algona's seven parks in its
    # comprehensive plan inventory; addresses and cross streets are from King County's South
    # King County Parks Guide. The coordinates are the center of OSM's park polygon (way
    # 547150676). Source: https://www.algonawa.gov/services/public_works/parks.php;
    # https://cdn.kingcounty.gov/-/media/king-county/depts/council/vonreichbauer/documents/south-king-county-parks-guide_2025.pdf
    ListedPark(
        name="John Matchett Memorial Park",
        address="400 Warde St",
        latitude=47.2776597,
        longitude=-122.2483127,
        city="Algona",
        zip_code="98001",
    ),
    # David E. Hill Wetland Preserve - Medium-high confidence - One of Algona's seven parks in
    # its comprehensive plan inventory; addresses and cross streets are from King County's South
    # King County Parks Guide. The coordinates are the center of OSM's nature reserve polygon
    # (way 1317045624). Source: https://www.algonawa.gov/services/public_works/parks.php;
    # https://cdn.kingcounty.gov/-/media/king-county/depts/council/vonreichbauer/documents/south-king-county-parks-guide_2025.pdf
    ListedPark(
        name="David E. Hill Wetland Preserve",
        address="Pacific Ave N & Ellingson Rd",
        latitude=47.2700421,
        longitude=-122.2415588,
        city="Algona",
        zip_code="98001",
    ),
    # 7th Avenue Park - Medium-high confidence - One of Algona's seven parks in its
    # comprehensive plan inventory; addresses and cross streets are from King County's South
    # King County Parks Guide. The coordinates are the center of an unnamed OSM park (way
    # 1376377688) at the described spot. Source:
    # https://www.algonawa.gov/services/public_works/parks.php;
    # https://cdn.kingcounty.gov/-/media/king-county/depts/council/vonreichbauer/documents/south-king-county-parks-guide_2025.pdf
    ListedPark(
        name="7th Avenue Park",
        address="7th Ave N & Main St",
        latitude=47.2875415,
        longitude=-122.2570722,
        city="Algona",
        zip_code="98001",
    ),
    # Stanley Avenue Park - Medium-high confidence - One of Algona's seven parks in its
    # comprehensive plan inventory; addresses and cross streets are from King County's South
    # King County Parks Guide. The coordinates are the center of an unnamed OSM park (way
    # 1152803210) at the described spot. Source:
    # https://www.algonawa.gov/services/public_works/parks.php;
    # https://cdn.kingcounty.gov/-/media/king-county/depts/council/vonreichbauer/documents/south-king-county-parks-guide_2025.pdf
    ListedPark(
        name="Stanley Avenue Park",
        address="Stanley Ave & Pullman Ave",
        latitude=47.2808699,
        longitude=-122.2479254,
        city="Algona",
        zip_code="98001",
    ),
    # Stanley Tot Lot - Medium-high confidence - One of Algona's seven parks in its
    # comprehensive plan inventory; addresses and cross streets are from King County's South
    # King County Parks Guide. The coordinates are the center of an unnamed OSM park (way
    # 1116101448) at the described spot. Source:
    # https://www.algonawa.gov/services/public_works/parks.php;
    # https://cdn.kingcounty.gov/-/media/king-county/depts/council/vonreichbauer/documents/south-king-county-parks-guide_2025.pdf
    ListedPark(
        name="Stanley Tot Lot",
        address="Stanley Ave & Iron Ave",
        latitude=47.2813432,
        longitude=-122.2475381,
        city="Algona",
        zip_code="98001",
    ),
    # Waffle Park - Medium-high confidence - One of Algona's seven parks in its comprehensive
    # plan inventory; addresses and cross streets are from King County's South King County Parks
    # Guide. The coordinates are the Census geocoder at its address. Source:
    # https://www.algonawa.gov/services/public_works/parks.php;
    # https://cdn.kingcounty.gov/-/media/king-county/depts/council/vonreichbauer/documents/south-king-county-parks-guide_2025.pdf
    ListedPark(
        name="Waffle Park",
        address="290 1st Ave N",
        latitude=47.279042,
        longitude=-122.252306,
        city="Algona",
        zip_code="98001",
    ),
    # 3rd Avenue Pocket Park - Medium confidence - One of Algona's seven parks in its
    # comprehensive plan inventory; addresses and cross streets are from King County's South
    # King County Parks Guide. The coordinates are an approximation: where 3rd Ave N meets the
    # Interurban Trail; no address or map data is published for it, so the pin may be off.
    # Source: https://www.algonawa.gov/services/public_works/parks.php;
    # https://cdn.kingcounty.gov/-/media/king-county/depts/council/vonreichbauer/documents/south-king-county-parks-guide_2025.pdf
    ListedPark(
        name="3rd Avenue Pocket Park",
        address="3rd Ave N",
        latitude=47.2815,
        longitude=-122.2492,
        city="Algona",
        zip_code="98001",
    ),
    # Hunts Point
    # D. K. McDonald Park - Medium-high confidence - The town's own page names it but gives no
    # map data. The coordinates are the center of OSM's polygon (way 422278032). Source:
    # https://huntspoint-wa.gov/wetherillnaturepreserve
    ListedPark(
        name="D. K. McDonald Park",
        address="3000 Hunts Point Rd",
        latitude=47.63708,
        longitude=-122.2271792,
        city="Hunts Point",
        zip_code="98004",
    ),
    # Yarrow Point
    # Morningside Park - Medium-high confidence - Listed on the town's public spaces page, which
    # has no map data. The coordinates are the center of OSM's polygon (way 922988438); at Town
    # Hall's address, so a Kirkland layer entry for it is treated as a duplicate. Source:
    # https://yarrowpointwa.gov/public-spaces/
    ListedPark(
        name="Morningside Park",
        address="4030 95th Ave NE",
        latitude=47.6470909,
        longitude=-122.2130823,
        city="Yarrow Point",
        zip_code="98004",
    ),
    # Road End Beach - Medium-high confidence - Listed on the town's public spaces page, which
    # has no map data. The coordinates are the center of OSM's polygon (way 449744782). Source:
    # https://yarrowpointwa.gov/public-spaces/
    ListedPark(
        name="Road End Beach",
        address="9000 NE 47th St",
        latitude=47.6518672,
        longitude=-122.2180739,
        city="Yarrow Point",
        zip_code="98004",
    ),
    # 42nd Street Launch Area - Medium-high confidence - Listed on the town's public spaces
    # page, which has no map data. The coordinates are the Census geocoder at the cross streets.
    # Source: https://yarrowpointwa.gov/public-spaces/
    ListedPark(
        name="42nd Street Launch Area",
        address="NE 42nd St & 91st Ave NE",
        latitude=47.647439,
        longitude=-122.218895,
        city="Yarrow Point",
        zip_code="98004",
    ),
    # Sally's Alley - Medium-high confidence - Listed on the town's public spaces page, which
    # has no map data. The coordinates are the center of OSM's park (way 925741916). Source:
    # https://yarrowpointwa.gov/public-spaces/
    ListedPark(
        name="Sally's Alley",
        address="Between 94th & 95th Ave NE",
        latitude=47.6446083,
        longitude=-122.214422,
        city="Yarrow Point",
        zip_code="98004",
    ),
    # Wetherill Nature Preserve - Medium-high confidence - Listed on the town's public spaces
    # page, which has no map data. The coordinates are the center of OSM's relation 6278123;
    # shared with Hunts Point. Source: https://yarrowpointwa.gov/public-spaces/
    ListedPark(
        name="Wetherill Nature Preserve",
        address="",
        latitude=47.6394891,
        longitude=-122.2229699,
        city="Yarrow Point",
        zip_code="98004",
    ),
    # Pacific
    # Pacific City Park - Medium-high confidence - One of the City of Pacific's parks, listed
    # with its address in King County's South King County Parks Guide; Pacific has no parks map
    # data. The coordinates are the center of OSM's park polygon (way 25681090). Source:
    # https://www.pacificwa.gov/services/parks___recreation;
    # https://cdn.kingcounty.gov/-/media/king-county/depts/council/vonreichbauer/documents/south-king-county-parks-guide_2025.pdf
    ListedPark(
        name="Pacific City Park",
        address="600 3rd Ave SE",
        latitude=47.2630737,
        longitude=-122.236751,
        city="Pacific",
    ),
    # Clint Steiger Memorial Park - Medium-high confidence - One of the City of Pacific's parks,
    # listed with its address in King County's South King County Parks Guide; Pacific has no
    # parks map data. The coordinates are the center of OSM's park polygon (way 488860914); the
    # guide calls it 'Clint Steiger Memorial (Volunteer) Park'. Source:
    # https://www.pacificwa.gov/services/parks___recreation;
    # https://cdn.kingcounty.gov/-/media/king-county/depts/council/vonreichbauer/documents/south-king-county-parks-guide_2025.pdf
    ListedPark(
        name="Clint Steiger Memorial Park",
        address="100 3rd Ave SE",
        latitude=47.2640197,
        longitude=-122.2481631,
        city="Pacific",
    ),
    # Elise Park - Medium-high confidence - One of the City of Pacific's parks, listed with its
    # address in King County's South King County Parks Guide; Pacific has no parks map data. The
    # coordinates are the center of OSM's park polygon (way 505076794). Source:
    # https://www.pacificwa.gov/services/parks___recreation;
    # https://cdn.kingcounty.gov/-/media/king-county/depts/council/vonreichbauer/documents/south-king-county-parks-guide_2025.pdf
    ListedPark(
        name="Elise Park",
        address="225 Elise Lane",
        latitude=47.2685558,
        longitude=-122.25425,
        city="Pacific",
    ),
    # Aspen Park - Medium-high confidence - One of the City of Pacific's parks, listed with its
    # address in King County's South King County Parks Guide; Pacific has no parks map data. The
    # coordinates are the center of OSM's park polygon (way 1149789640). Source:
    # https://www.pacificwa.gov/services/parks___recreation;
    # https://cdn.kingcounty.gov/-/media/king-county/depts/council/vonreichbauer/documents/south-king-county-parks-guide_2025.pdf
    ListedPark(
        name="Aspen Park",
        address="101 Aspen Ln N",
        latitude=47.2686097,
        longitude=-122.2347128,
        city="Pacific",
    ),
    # Milwaukee Park - Medium-high confidence - One of the City of Pacific's parks, listed with
    # its address in King County's South King County Parks Guide; Pacific has no parks map data.
    # The coordinates are the center of OSM's park polygon (way 480155292). Source:
    # https://www.pacificwa.gov/services/parks___recreation;
    # https://cdn.kingcounty.gov/-/media/king-county/depts/council/vonreichbauer/documents/south-king-county-parks-guide_2025.pdf
    ListedPark(
        name="Milwaukee Park",
        address="522 Milwaukee Blvd S",
        latitude=47.2601422,
        longitude=-122.2506422,
        city="Pacific",
    ),
    # Beaver Park - Medium-high confidence - One of the City of Pacific's parks, listed with its
    # address in King County's South King County Parks Guide; Pacific has no parks map data. The
    # coordinates are the center of OSM's park polygon (way 480155324). Source:
    # https://www.pacificwa.gov/services/parks___recreation;
    # https://cdn.kingcounty.gov/-/media/king-county/depts/council/vonreichbauer/documents/south-king-county-parks-guide_2025.pdf
    ListedPark(
        name="Beaver Park",
        address="550 Beaver Blvd",
        latitude=47.260025,
        longitude=-122.2588408,
        city="Pacific",
    ),
    # Blueberry Park - Medium-high confidence - One of the City of Pacific's parks, listed with
    # its address in King County's South King County Parks Guide; Pacific has no parks map data.
    # The coordinates are the center of OSM's park polygon (way 1376352643). Source:
    # https://www.pacificwa.gov/services/parks___recreation;
    # https://cdn.kingcounty.gov/-/media/king-county/depts/council/vonreichbauer/documents/south-king-county-parks-guide_2025.pdf
    ListedPark(
        name="Blueberry Park",
        address="117 5th Ave SW",
        latitude=47.2608447,
        longitude=-122.2514609,
        city="Pacific",
    ),
    # Otter Park - Medium-high confidence - One of the City of Pacific's parks, listed with its
    # address in King County's South King County Parks Guide; Pacific has no parks map data. The
    # coordinates are the Census geocoder at its address. Source:
    # https://www.pacificwa.gov/services/parks___recreation;
    # https://cdn.kingcounty.gov/-/media/king-county/depts/council/vonreichbauer/documents/south-king-county-parks-guide_2025.pdf
    ListedPark(
        name="Otter Park",
        address="215 Otter Dr SW",
        latitude=47.259346,
        longitude=-122.256096,
        city="Pacific",
    ),
    # Strawberry Park - Medium-high confidence - One of the City of Pacific's parks, listed with
    # its address in King County's South King County Parks Guide; Pacific has no parks map data.
    # The coordinates are the Census geocoder, which matched the address as 132 Strawberry St
    # SW. Source: https://www.pacificwa.gov/services/parks___recreation;
    # https://cdn.kingcounty.gov/-/media/king-county/depts/council/vonreichbauer/documents/south-king-county-parks-guide_2025.pdf
    ListedPark(
        name="Strawberry Park",
        address="132 Strawberry Ct SW",
        latitude=47.259352,
        longitude=-122.250687,
        city="Pacific",
    ),
    # Sunset Park - Medium-high confidence - One of the City of Pacific's parks, listed with its
    # address in King County's South King County Parks Guide; Pacific has no parks map data. The
    # coordinates are the Census geocoder at its address. Source:
    # https://www.pacificwa.gov/services/parks___recreation;
    # https://cdn.kingcounty.gov/-/media/king-county/depts/council/vonreichbauer/documents/south-king-county-parks-guide_2025.pdf
    ListedPark(
        name="Sunset Park",
        address="244 Sunset Dr",
        latitude=47.265374,
        longitude=-122.244417,
        city="Pacific",
    ),
    # Rhubarb Park - Medium confidence - One of the City of Pacific's parks, listed with its
    # address in King County's South King County Parks Guide; Pacific has no parks map data. The
    # coordinates are an approximation: the Census geocoder doesn't know 215 Rhubarb Ave SW, so
    # this is its match for 200 Rhubarb Ave SW on the same street, and the pin may be a little
    # off. Source: https://www.pacificwa.gov/services/parks___recreation;
    # https://cdn.kingcounty.gov/-/media/king-county/depts/council/vonreichbauer/documents/south-king-county-parks-guide_2025.pdf
    ListedPark(
        name="Rhubarb Park",
        address="215 Rhubarb Ave SW",
        latitude=47.260472,
        longitude=-122.254301,
        city="Pacific",
    ),
    # Milton
    # Milton Community Park - Medium-high confidence - On the City of Milton's Parks & Trails
    # page, whose park pages give the address or cross streets; Milton has no parks map data.
    # The coordinates are the center of OSM's park polygon (way 467548589); the city also calls
    # it Triangle Park. Source: https://www.miltonwa.gov/177/Parks-Trails
    ListedPark(
        name="Milton Community Park",
        address="15th Ave & Milton Way",
        latitude=47.2475912,
        longitude=-122.3161775,
        city="Milton",
    ),
    # Hill Tower Park - Medium-high confidence - On the City of Milton's Parks & Trails page,
    # whose park pages give the address or cross streets; Milton has no parks map data. The
    # coordinates are the center of OSM's park polygon (way 540132151). Source:
    # https://www.miltonwa.gov/177/Parks-Trails
    ListedPark(
        name="Hill Tower Park",
        address="600 19th Ave",
        latitude=47.2521429,
        longitude=-122.3086957,
        city="Milton",
    ),
    # Milltown Commons Skatepark - Medium-high confidence - On the City of Milton's Parks &
    # Trails page, whose park pages give the address or cross streets; Milton has no parks map
    # data. The coordinates are the Census geocoder at the cross streets the city gives. Source:
    # https://www.miltonwa.gov/177/Parks-Trails
    ListedPark(
        name="Milltown Commons Skatepark",
        address="23rd Ave & Milton Way",
        latitude=47.250109,
        longitude=-122.304276,
        city="Milton",
    ),
    # West Milton Park - Medium-high confidence - On the City of Milton's Parks & Trails page,
    # whose park pages give the address or cross streets; Milton has no parks map data. The
    # coordinates are the Census geocoder at its address. Source:
    # https://www.miltonwa.gov/177/Parks-Trails
    ListedPark(
        name="West Milton Park",
        address="700 Kent St",
        latitude=47.249728,
        longitude=-122.324989,
        city="Milton",
    ),
    # West Milton Nature Preserve - Medium confidence - On the City of Milton's Parks & Trails
    # page, whose park pages give the address or cross streets; Milton has no parks map data.
    # The coordinates are the Census geocoder at its address; the preserve is larger than a
    # point, so this is only a representative spot. Source:
    # https://www.miltonwa.gov/177/Parks-Trails
    ListedPark(
        name="West Milton Nature Preserve",
        address="604 5th Ave",
        latitude=47.252144,
        longitude=-122.328167,
        city="Milton",
    ),
    # Olympic View Park - Medium-high confidence - On the City of Milton's Parks & Trails page,
    # whose park pages give the address or cross streets; Milton has no parks map data. The
    # coordinates are the center of OSM's park polygon (way 703797654). Source:
    # https://www.miltonwa.gov/177/Parks-Trails
    ListedPark(
        name="Olympic View Park",
        address="32 Hylebos Ave",
        latitude=47.2600024,
        longitude=-122.3072427,
        city="Milton",
    ),
)
