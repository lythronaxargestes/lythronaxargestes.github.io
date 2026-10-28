"""Render a short video of seattle_parks_map.html for one park.

The video opens centered on the given park's marker with its pop-up open, holds
for a moment, fades the pop-up out, then zooms out smoothly (continuous
fractional zoom, not Leaflet's discrete zoom levels) until every marker is on
screen, and holds on that final view. The map's overlays (title/progress box,
visited legend, zoom and location buttons) are hidden; the OpenStreetMap
attribution is kept, since the tile license requires it.

The park is looked up as a (name, city) pair in the same park list the map is
rendered from (seattle_parks.csv + the missing-data backup CSV). Same-name,
same-city entries within DUPLICATE_DISTANCE_M of each other are one park (the
same rule the fetch pipeline uses) and are collapsed; if distinct parks still
share the pair, pass --address to pick one.

Frames are captured one at a time from headless Chrome (so timing is exact, not
real-time) and piped to ffmpeg. Run via uv, like the rest of this project:

    uv run --with playwright --with imageio-ffmpeg --with requests --with tqdm \\
        seattle_parks_video.py "Gas Works Park" Seattle

Needs Google Chrome installed (else run `uv run --with playwright playwright
install chromium` once) and network access for the OSM tiles and CDN scripts.
"""
from __future__ import annotations

import argparse
import difflib
import os
import shutil
import subprocess
import sys
from pathlib import Path
from tqdm import tqdm

from seattle_parks_constants import DUPLICATE_DISTANCE_M, MAP_PATH
from seattle_parks_helpers import apply_backup_data, distance_m, load_parks_from_csv, normalize_name

START_ZOOM = 19  # capped at the map's max zoom (19) in SETUP_JS
FIT_PADDING_PX = 60  # margin around the outermost markers in the final view
TILE_TIMEOUT_MS = 20000

# Hide the overlays (every position:fixed box, plus Leaflet's top-left zoom and
# locate controls) and kill CSS transitions so each captured frame is exact.
PAGE_CSS = """
body > div[style*="fixed"], .leaflet-top.leaflet-left { display: none !important; }
* { transition: none !important; animation: none !important; }
"""

SETUP_JS = """
({lat, lon, startZoom, padding, css}) => {
    const style = document.createElement("style");
    style.textContent = css;
    document.head.appendChild(style);

    const mapKey = Object.keys(window).find((k) => k.startsWith("map_") && window[k] instanceof L.Map);
    const map = window[mapKey];
    map.options.zoomSnap = 0;
    map._fadeAnimated = false;

    const markers = [];
    map.eachLayer((layer) => {
        if (layer instanceof L.CircleMarker) markers.push(layer);
    });
    const target = markers.find((m) => {
        const ll = m.getLatLng();
        return Math.abs(ll.lat - lat) < 1e-7 && Math.abs(ll.lng - lon) < 1e-7;
    });
    if (!target) return {error: "no marker at the park's coordinates; regenerate the map first"};

    const bounds = L.latLngBounds(markers.map((m) => m.getLatLng()));
    const endZoom = map.getBoundsZoom(bounds, false, L.point(padding, padding));
    const endCenter = bounds.getCenter();

    // Leaflet silently clamps setView to the map's max zoom, so a higher start
    // would leave the camera frozen at the max until the zoom drops below it.
    const effectiveStartZoom = Math.min(startZoom, map.getMaxZoom());
    target.getPopup().options.autoPan = false;
    map.setView(target.getLatLng(), effectiveStartZoom, {animate: false});
    target.openPopup();

    window.__video = {
        map, target, startZoom: effectiveStartZoom, endZoom,
        startPx: map.project(target.getLatLng(), 0),
        endPx: map.project(endCenter, 0),
    };
    return {markerCount: markers.length, endZoom};
}
"""

# progress is the eased 0..1 zoom progress; popupOpacity < 0 leaves the pop-up alone.
FRAME_JS = """
async ({progress, popupOpacity}) => {
    const v = window.__video;
    const popup = v.target.getPopup();
    if (popupOpacity >= 0) {
        if (popupOpacity === 0) {
            v.map.closePopup();
        } else if (popup.getElement()) {
            popup.getElement().style.opacity = popupOpacity;
        }
    }
    if (progress >= 0) {
        // Zooming about a fixed screen point: the center moves along the line
        // from the park to the final center in proportion to 1/scale, so the
        // park drifts across the screen exactly as a real camera zoom would.
        const zoom = v.startZoom + (v.endZoom - v.startZoom) * progress;
        const inv0 = 1 / Math.pow(2, v.startZoom);
        const inv1 = 1 / Math.pow(2, v.endZoom);
        const inv = 1 / Math.pow(2, zoom);
        const k = inv0 === inv1 ? 1 : (inv0 - inv) / (inv0 - inv1);
        const x = v.startPx.x + (v.endPx.x - v.startPx.x) * k;
        const y = v.startPx.y + (v.endPx.y - v.startPx.y) * k;
        const center = v.map.unproject(L.point(x, y), 0);
        v.map.setView(center, zoom, {animate: false});
    }
    const raf = () => new Promise((resolve) => requestAnimationFrame(resolve));
    const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
    const start = performance.now();
    await raf();
    const pending = () => Array.from(document.querySelectorAll("img.leaflet-tile")).some((t) => !t.complete);
    while (pending() && performance.now() - start < __TIMEOUT__) await sleep(20);
    await raf();
    return !pending();
}
""".replace("__TIMEOUT__", str(TILE_TIMEOUT_MS))


def ease_in_out(t: float) -> float:
    return t * t * (3 - 2 * t)


def find_park(name: str, city: str, address: str | None) -> dict:
    """Look up the park among the parks the map renders, collapsing duplicates."""
    parks = apply_backup_data(load_parks_from_csv())
    want_name = normalize_name(name).casefold()
    want_city = city.casefold()
    matches = [p for p in parks if p["name"].casefold() == want_name and p["city"].casefold() == want_city]

    if not matches:
        city_parks = [p["name"] for p in parks if p["city"].casefold() == want_city]
        pool = city_parks or [p["name"] for p in parks]
        close = difflib.get_close_matches(normalize_name(name), pool, n=5, cutoff=0.5)
        hint = f" Did you mean: {', '.join(close)}?" if close else ""
        sys.exit(f"No park named {name!r} in {city!r}.{hint}")

    if address:
        needle = address.casefold()
        matches = [p for p in matches if needle in p["address"].casefold()]
        if not matches:
            sys.exit(f"No {name!r} in {city!r} has an address containing {address!r}")

    distinct: list[dict] = []
    for p in matches:
        if not any(distance_m(p, q) <= DUPLICATE_DISTANCE_M for q in distinct):
            distinct.append(p)
    if len(distinct) > 1:
        lines = "\n".join(f"  {p['address'] or '(no address)'}  ({p['latitude']}, {p['longitude']})" for p in distinct)
        sys.exit(f"{len(distinct)} different parks are named {name!r} in {city!r}; pick one with --address:\n{lines}")
    return distinct[0]


def start_encoder(output: Path, fps: int) -> subprocess.Popen:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        import imageio_ffmpeg

        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg, "-y", "-loglevel", "error",
        "-f", "image2pipe", "-framerate", str(fps), "-i", "-",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-movflags", "+faststart",
        str(output),
    ]  # fmt: skip
    return subprocess.Popen(cmd, stdin=subprocess.PIPE)


def launch_browser(playwright):
    try:
        return playwright.chromium.launch(channel="chrome", headless=True)
    except Exception as chrome_error:
        try:
            return playwright.chromium.launch(headless=True)
        except Exception:
            sys.exit(
                f"Could not launch Chrome ({chrome_error}).\n"
                "Install Google Chrome, or run: uv run --with playwright playwright install chromium"
            )


def render(park: dict, args: argparse.Namespace, output: Path) -> None:
    from playwright.sync_api import sync_playwright

    fps = args.fps
    hold_frames = round(args.hold * fps)
    zoom_frames = round(args.zoom_seconds * fps)
    # The fade runs during the first part of the zoom, so it can't outlast it.
    fade_frames = min(round(args.fade * fps), zoom_frames)
    end_hold_frames = round(args.end_hold * fps)
    total = hold_frames + zoom_frames + end_hold_frames
    map_url = Path(MAP_PATH).resolve().as_uri()

    encoder = start_encoder(output, fps)
    encoder_stdin = encoder.stdin
    assert encoder_stdin is not None  # start_encoder opens it with stdin=PIPE
    stale_frames = 0

    def capture(page, progress: float, popup_opacity: float, repeat: int = 1) -> None:
        nonlocal stale_frames
        settled = page.evaluate(FRAME_JS, {"progress": progress, "popupOpacity": popup_opacity})
        if not settled:
            stale_frames += 1
        png = page.screenshot(type="png")
        for _ in range(repeat):
            encoder_stdin.write(png)

    with sync_playwright() as pw:
        browser = launch_browser(pw)
        page = browser.new_page(viewport={"width": args.width, "height": args.height})
        page.goto(map_url, wait_until="load")
        page.wait_for_function("Object.keys(window).some(k => k.startsWith('map_') && window[k] instanceof L.Map)")
        info = page.evaluate(
            SETUP_JS,
            {"lat": park["latitude"], "lon": park["longitude"], "startZoom": START_ZOOM,
             "padding": FIT_PADDING_PX, "css": PAGE_CSS},
        )  # fmt: skip
        if "error" in info:
            browser.close()
            encoder.kill()
            sys.exit(info["error"])
        print(f"{info['markerCount']} markers; final zoom {info['endZoom']:.2f}; {total} frames at {fps} fps")

        # Opening hold: one capture, repeated.
        capture(page, 0, -1, repeat=hold_frames)
        # Zoom out, fading the pop-up over the first fade_frames of it.
        for i in tqdm(range(1, zoom_frames + 1)):
            progress = ease_in_out(i / zoom_frames)
            opacity = max(0.0, 1 - i / fade_frames) if fade_frames else 0.0
            capture(page, progress, opacity)
        # Closing hold: the final frame again.
        png = page.screenshot(type="png")
        for _ in tqdm(range(end_hold_frames)):
            encoder_stdin.write(png)
        browser.close()

    encoder_stdin.close()
    code = encoder.wait()
    if code != 0:
        sys.exit(f"ffmpeg failed with exit code {code}")
    if stale_frames:
        print(f"Warning: {stale_frames} frame(s) were captured before all map tiles finished loading", file=sys.stderr)
    print(f"Wrote {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("name", help="Park name, e.g. 'Gas Works Park' (case-insensitive)")
    parser.add_argument("city", help="City, e.g. Seattle (case-insensitive)")
    parser.add_argument("--address", help="Substring of the address, to pick between distinct same-named parks")
    parser.add_argument("-o", "--output", type=Path, help="Output .mp4 (default: parks.mp4)")
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--hold", type=float, default=2.0, help="Seconds the pop-up stays open at the start")
    parser.add_argument("--fade", type=float, default=1.0, help="Seconds for the pop-up to fade out, starting as the zoom-out begins (capped at --zoom-seconds)")
    parser.add_argument("--zoom-seconds", type=float, default=7.0, help="Seconds spent zooming out")
    parser.add_argument("--end-hold", type=float, default=1.0, help="Seconds to hold the final view")
    args = parser.parse_args()

    if args.width % 2 or args.height % 2:
        sys.exit("--width and --height must be even (required by yuv420p H.264)")

    # Resolve the output path before chdir-ing: the project's own paths are
    # relative to this script's directory, but the video belongs where the user ran it.
    launch_dir = Path.cwd()
    output = args.output.resolve() if args.output else None
    os.chdir(Path(__file__).resolve().parent)
    if not Path(MAP_PATH).exists():
        sys.exit(f"{MAP_PATH} not found; run seattle_parks_update.sh first")

    park = find_park(args.name, args.city, args.address)
    print(f"Park: {park['name']} - {park['address']}, {park['city']} ({park['latitude']}, {park['longitude']})")

    if output is None:
        output = launch_dir / "parks.mp4"
    render(park, args, output)


if __name__ == "__main__":
    main()
