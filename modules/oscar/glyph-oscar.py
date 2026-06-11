#!/usr/bin/env python3
"""
Glyph OSCAR / AMSAT Pass Assist

Field-portable amateur satellite pass predictor for Glyph ecosystem.

Author: W4XEN

Install:
    pip install skyfield pyserial
    sudo apt install python3-pil fbi

Compass image:
    /home/YOUR_HOME_DIR_NAME/images/glyph-compass.png
"""

import json
import math
import os
import re
import select
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

try:
    from skyfield.api import EarthSatellite, load, wgs84
except Exception:
    EarthSatellite = None
    load = None
    wgs84 = None

try:
    from PIL import Image, ImageDraw, ImageFont
except Exception:
    Image = None
    ImageDraw = None
    ImageFont = None

# ---------- GLYPH THEME ----------

USE_COLOR = os.isatty(1)
RESET = "\033[0m" if USE_COLOR else ""
BOLD = "\033[1m" if USE_COLOR else ""
BORDER = "\033[1;37m" if USE_COLOR else ""
TITLE = "\033[1;32m" if USE_COLOR else ""
BLUE = "\033[1;34m" if USE_COLOR else ""
ACCENT = "\033[1;32m" if USE_COLOR else ""
WARN = "\033[38;5;220m" if USE_COLOR else ""
BAD = "\033[38;5;196m" if USE_COLOR else ""
HEADER_WIDTH = 58
TEXT_WIDTH = 58

# ---------- CONFIG ----------

APP_DIR = Path.home() / ".config" / "glyph-amsat"
CONFIG_PATH = APP_DIR / "config.json"
CACHE_DIR = Path("/tmp/glyph-amsat")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

TLE_URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP=amateur&FORMAT=tle"
GPS_PORT = "/dev/ttyACM0"
GPS_BAUD = 9600
FB_DEVICE = "/dev/fb1"
FB_TTY = "1"
COMPASS_PATH = Path.home() / "images" / "glyph-compass.png"
PASS_IMAGE = str(CACHE_DIR / "glyph_amsat_pass.png")
TLE_CACHE = CACHE_DIR / "amateur.tle"
HEADERS = {"User-Agent": "w4xen-glyph-amsat"}

SAT_NOTES = {
    "ISS": {"mode": "FM/APRS/Voice varies", "rx": "145.800 MHz varies", "tx": "145.990 MHz APRS; voice varies", "notes": "Check current ARISS mode before a pass."},
    "SO-50": {"mode": "FM V/u", "rx": "436.795 MHz", "tx": "145.850 MHz PL 67.0", "notes": "Use 74.4 Hz tone briefly to arm; 67.0 Hz for access. Adjust UHF down for Doppler."},
    "AO-91": {"mode": "FM U/v", "rx": "145.960 MHz", "tx": "435.250 MHz PL 67.0", "notes": "Check AMSAT status before use; battery condition has varied."},
    "PO-101": {"mode": "FM V/u", "rx": "437.500 MHz", "tx": "145.900 MHz PL 141.3", "notes": "Schedule/activity varies."},
    "AO-7": {"mode": "Linear", "rx": "145.950-145.800 MHz", "tx": "432.125-432.175 MHz", "notes": "Old bird; modes/usability vary with illumination."},
    "RS-44": {"mode": "Linear", "rx": "435.640-435.610 MHz", "tx": "145.965-145.995 MHz", "notes": "Inverting linear transponder; long passes."},
    "FO-29": {"mode": "Linear", "rx": "435.900-435.800 MHz", "tx": "145.900-146.000 MHz", "notes": "Inverting linear transponder; status varies."},
    "CAS-4A": {"mode": "Linear", "rx": "145.870-145.925 MHz", "tx": "435.220-435.280 MHz", "notes": "Check current status and passband."},
    "CAS-4B": {"mode": "Linear", "rx": "145.925-145.980 MHz", "tx": "435.280-435.340 MHz", "notes": "Check current status and passband."},
}

# ---------- TUI ----------

def clear(): os.system("clear")

def print_header(title):
    title = " ".join(str(title).replace("=", "").replace("—", "").split())
    if len(title) > HEADER_WIDTH:
        title = title[:HEADER_WIDTH - 1].rstrip() + "…"
    print(f"{BORDER}{'—' * HEADER_WIDTH}{RESET}")
    print(f"{TITLE}{title.center(HEADER_WIDTH)}{RESET}")
    print(f"{BORDER}{'—' * HEADER_WIDTH}{RESET}\n")

def styled_prompt(text): return input(f"{BLUE}{text}{RESET}")
def pause(): input(f"\n{BLUE}Press Enter to continue...{RESET}")

def wrap_line(line, width=TEXT_WIDTH):
    if not str(line).strip(): return [""]
    out, cur = [], ""
    for w in str(line).split():
        if not cur: cur = w
        elif len(cur) + 1 + len(w) <= width: cur += " " + w
        else: out.append(cur); cur = w
    if cur: out.append(cur)
    return out

def paginate(title, text_or_lines, body_lines=12):
    src = text_or_lines.splitlines() if isinstance(text_or_lines, str) else list(text_or_lines)
    lines = []
    for line in src: lines.extend(wrap_line(line))
    if not lines: lines = ["No content."]
    pages = max(1, (len(lines) + body_lines - 1) // body_lines)
    page = 0
    while True:
        clear(); print_header(title)
        chunk = lines[page*body_lines:page*body_lines+body_lines]
        for line in chunk: print(line)
        for _ in range(body_lines - len(chunk)): print()
        if pages == 1:
            pause(); return
        print(f"{ACCENT}Page {page+1}/{pages}{RESET}  {BLUE}n){RESET} Next  {BLUE}p){RESET} Prev  {BLUE}b){RESET} Back")
        c = styled_prompt("Select: ").strip().lower()
        if c in {"", "n"} and page < pages - 1: page += 1
        elif c == "p" and page > 0: page -= 1
        elif c in {"b", "q"}: return

def load_config():
    if CONFIG_PATH.exists():
        try: return json.loads(CONFIG_PATH.read_text())
        except Exception: pass
    return {"lat": None, "lon": None, "elev_m": 0, "location_name": "Unknown", "location_source": "Not set", "selected_sat": None, "pass_window_hours": 24, "min_elevation": 5, "live_update_seconds": 5}

def save_config(config):
    APP_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2))

# ---------- GPS ----------

def nmea_to_decimal(value, hemi):
    try:
        raw = float(value); deg = int(raw // 100); mins = raw - deg * 100
        dec = deg + mins / 60.0
        return -dec if hemi in ("S", "W") else dec
    except Exception:
        return None

def parse_nmea(line):
    line = line.strip()
    if not line.startswith("$"): return None
    p = line.split(","); kind = p[0][-3:]
    if kind == "GGA" and len(p) >= 10:
        lat = nmea_to_decimal(p[2], p[3]); lon = nmea_to_decimal(p[4], p[5])
        if lat is not None and lon is not None and p[6] not in ("0", ""):
            try: elev = float(p[9]) if p[9] else 0.0
            except Exception: elev = 0.0
            return {"lat": lat, "lon": lon, "elev_m": elev, "sats": p[7] or "?", "source": "GPS GGA"}
    if kind == "RMC" and len(p) >= 7:
        lat = nmea_to_decimal(p[3], p[4]); lon = nmea_to_decimal(p[5], p[6])
        if p[2] == "A" and lat is not None and lon is not None:
            return {"lat": lat, "lon": lon, "elev_m": 0.0, "sats": "?", "source": "GPS RMC"}
    return None


# ---------- MAIDENHEAD GRID ----------

def maidenhead_to_latlon(grid):
    """Return approximate center lat/lon for a 4- or 6-character Maidenhead grid."""
    raw = str(grid or "").strip()
    g = raw.upper()
    if not re.fullmatch(r"[A-R]{2}[0-9]{2}([A-X]{2})?", g):
        raise ValueError("Use a 4- or 6-character grid, like DN13 or DN13RO.")

    lon = -180.0
    lat = -90.0

    # Field: A-R, 20 deg lon by 10 deg lat
    lon += (ord(g[0]) - ord("A")) * 20.0
    lat += (ord(g[1]) - ord("A")) * 10.0

    # Square: 0-9, 2 deg lon by 1 deg lat
    lon += int(g[2]) * 2.0
    lat += int(g[3]) * 1.0

    if len(g) == 6:
        # Subsquare: A-X, 5 min lon by 2.5 min lat
        lon_size = 2.0 / 24.0
        lat_size = 1.0 / 24.0
        lon += (ord(g[4]) - ord("A")) * lon_size
        lat += (ord(g[5]) - ord("A")) * lat_size
        lon += lon_size / 2.0
        lat += lat_size / 2.0
    else:
        # Center of 4-char square
        lon += 1.0
        lat += 0.5

    # Preserve common ham style: DN13ro instead of DN13RO
    pretty = g[:4] + (g[4:].lower() if len(g) == 6 else "")
    return lat, lon, pretty

def set_grid_location(config):
    clear(); print_header("Maidenhead Location")
    print("Enter a 4- or 6-character Maidenhead grid.")
    print("Example: DN13ro")
    print()
    grid = styled_prompt("Grid: ").strip()
    try:
        lat, lon, pretty = maidenhead_to_latlon(grid)
    except Exception as e:
        print(f"\n{BAD}Invalid grid:{RESET} {str(e)[:TEXT_WIDTH]}")
        pause(); return config

    elev_text = styled_prompt("Elev m [0]: ").strip()
    try:
        elev = float(elev_text) if elev_text else 0.0
    except Exception:
        elev = 0.0

    config.update({
        "lat": lat,
        "lon": lon,
        "elev_m": elev,
        "location_name": pretty,
        "location_source": "Maidenhead grid",
        "maidenhead": pretty,
    })
    save_config(config)

    clear(); print_header("Location Saved")
    print(f"Grid : {ACCENT}{pretty}{RESET}")
    print(f"Lat  : {ACCENT}{lat:.5f}{RESET}")
    print(f"Lon  : {ACCENT}{lon:.5f}{RESET}")
    print(f"Elev : {ACCENT}{elev:.0f} m{RESET}")
    print()
    print("Grid location is approximate, but plenty useful for handheld satellite work.")
    pause(); return config

def get_gps_fix(timeout=30):
    try: import serial
    except Exception: raise RuntimeError("pyserial is not installed. Run: pip install pyserial")
    start, last = time.time(), ""
    with serial.Serial(GPS_PORT, GPS_BAUD, timeout=1) as ser:
        while time.time() - start < timeout:
            raw = ser.readline().decode("ascii", errors="ignore").strip()
            if raw: last = raw
            fix = parse_nmea(raw)
            if fix: return fix
    raise RuntimeError(f"No GPS fix from {GPS_PORT}. Last: {last[:40]}")

def set_manual_location(config):
    clear(); print_header("Manual Location")
    print("Enter decimal coordinates. Example: 43.615, -116.203\n")
    try:
        lat = float(styled_prompt("Latitude : ").strip())
        lon = float(styled_prompt("Longitude: ").strip())
        elev = float(styled_prompt("Elev m   : ").strip() or "0")
    except Exception:
        print(f"\n{BAD}Invalid coordinates.{RESET}"); pause(); return config
    name = styled_prompt("Name     : ").strip() or "Manual Location"
    config.update({"lat": lat, "lon": lon, "elev_m": elev, "location_name": name, "location_source": "Manual coordinates"})
    save_config(config); print(f"\nSaved: {ACCENT}{name}{RESET}"); pause(); return config

def gps_screen(config):
    clear(); print_header("GPS Fix")
    print(f"Port: {ACCENT}{GPS_PORT}{RESET}\nBaud: {ACCENT}{GPS_BAUD}{RESET}\n\nWaiting for GPS fix...\n")
    try:
        fix = get_gps_fix(30); name = f"{fix['lat']:.4f}, {fix['lon']:.4f}"
        config.update({"lat": fix["lat"], "lon": fix["lon"], "elev_m": fix.get("elev_m", 0), "location_name": name, "location_source": fix.get("source", "GPS")})
        save_config(config)
        print(f"Fix : {ACCENT}{name}{RESET}\nElev: {ACCENT}{fix.get('elev_m',0):.0f} m{RESET}\nSats: {ACCENT}{fix.get('sats','?')}{RESET}")
    except Exception as e:
        print(f"{BAD}GPS failed:{RESET} {str(e)[:TEXT_WIDTH]}\n")
        print(f"{BLUE}g){RESET} Maidenhead grid")
        print(f"{BLUE}m){RESET} Manual coordinates")
        print(f"{BLUE}b){RESET} Back")
        choice = styled_prompt("Select: ").strip().lower()
        if choice == "g": return set_grid_location(config)
        if choice == "m": return set_manual_location(config)
    pause(); return config

# ---------- TLE / SATELLITES ----------

def require_skyfield():
    if EarthSatellite is None or load is None or wgs84 is None:
        raise RuntimeError("Skyfield is not installed. Run: pip install skyfield")

def fetch_tles(force=False):
    if TLE_CACHE.exists() and not force and time.time() - TLE_CACHE.stat().st_mtime < 24*3600:
        return TLE_CACHE.read_text()
    r = requests.get(TLE_URL, headers=HEADERS, timeout=20); r.raise_for_status()
    text = r.text.strip() + "\n"
    if len(text.splitlines()) < 6: raise RuntimeError("Downloaded TLE list was too small.")
    TLE_CACHE.write_text(text); return text

def parse_tles(text):
    lines = [l.rstrip() for l in text.splitlines() if l.strip()]
    sats, i = [], 0
    while i + 2 < len(lines):
        name, l1, l2 = lines[i].strip(), lines[i+1].strip(), lines[i+2].strip()
        if l1.startswith("1 ") and l2.startswith("2 "):
            sats.append({"name": name, "line1": l1, "line2": l2}); i += 3
        else: i += 1
    return sats

def note_for_sat(name):
    n = re.sub(r"\s*\(.*?\)\s*", " ", name.upper()).strip()
    for key, val in SAT_NOTES.items():
        if key in n: return val
    return {"mode": "Unknown/check AMSAT", "rx": "N/A", "tx": "N/A", "notes": "No local note. Check AMSAT status before transmitting."}

def pick_satellite(config):
    clear(); print_header("Pick Satellite")
    print("Fetching fresh amateur TLE list...\n")
    try: sats = parse_tles(fetch_tles(False))
    except Exception as e:
        print(f"{BAD}TLE fetch failed:{RESET} {str(e)[:TEXT_WIDTH]}"); pause(); return config
    print(f"Loaded: {ACCENT}{len(sats)} satellites{RESET}\n")
    q = styled_prompt("Search sat name/call: ").strip().upper()
    if q: matches = [s for s in sats if q in s["name"].upper()]
    else:
        preferred = ("ISS", "SO-50", "AO-7", "RS-44", "FO-29", "CAS-4", "PO-101", "TEVEL")
        matches = [s for s in sats if any(p in s["name"].upper() for p in preferred)] or sats[:20]
    if not matches:
        print("No matches."); pause(); return config
    page, size = 0, 10
    while True:
        clear(); print_header("Pick Satellite")
        chunk = matches[page*size:page*size+size]
        for idx, sat in enumerate(chunk, 1): print(f"{BLUE}{idx}){RESET} {sat['name'][:50]}")
        print(f"\n{BLUE}n){RESET} Next  {BLUE}p){RESET} Prev  {BLUE}b){RESET} Back")
        c = styled_prompt("\nSelect: ").strip().lower()
        if c in {"", "n"} and (page+1)*size < len(matches): page += 1
        elif c == "p" and page > 0: page -= 1
        elif c == "b": return config
        else:
            try:
                sel = int(c)
                if 1 <= sel <= len(chunk):
                    sat = chunk[sel-1]; config["selected_sat"] = sat; save_config(config)
                    clear(); print_header("Satellite Saved")
                    note = note_for_sat(sat["name"])
                    print(f"Selected: {ACCENT}{sat['name']}{RESET}\n")
                    print(f"Mode: {ACCENT}{note['mode']}{RESET}\nRX  : {ACCENT}{note['rx']}{RESET}\nTX  : {ACCENT}{note['tx']}{RESET}")
                    pause(); return config
            except Exception: pass

# ---------- PASS CALCULATION ----------

def make_satellite(satdict):
    require_skyfield(); return EarthSatellite(satdict["line1"], satdict["line2"], satdict["name"], load.timescale())

def observer_from_config(config):
    require_skyfield()
    if config.get("lat") is None or config.get("lon") is None: raise RuntimeError("No location set. Run GPS Fix or Manual Location first.")
    return wgs84.latlon(float(config["lat"]), float(config["lon"]), elevation_m=float(config.get("elev_m", 0) or 0))

def altaz_at(satellite, observer, dt_utc):
    t = load.timescale().from_datetime(dt_utc.astimezone(timezone.utc))
    alt, az, dist = (satellite - observer).at(t).altaz()
    return alt.degrees, az.degrees, dist.km

def cardinal(az):
    dirs = ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"]
    return dirs[int((az + 11.25) // 22.5) % 16]

def find_passes(config, hours=None, min_elev=None):
    require_skyfield()
    if not config.get("selected_sat"): raise RuntimeError("No satellite selected.")
    hours = hours if hours is not None else int(config.get("pass_window_hours", 24))
    min_elev = min_elev if min_elev is not None else float(config.get("min_elevation", 5))
    sat = make_satellite(config["selected_sat"]); obs = observer_from_config(config); ts = load.timescale()
    now = datetime.now(timezone.utc)
    times, events = sat.find_events(obs, ts.from_datetime(now), ts.from_datetime(now + timedelta(hours=hours)), altitude_degrees=min_elev)
    passes, cur = [], {}
    for t, event in zip(times, events):
        dt = t.utc_datetime().replace(tzinfo=timezone.utc)
        if event == 0: cur = {"aos": dt}
        elif event == 1 and cur: cur["max"] = dt
        elif event == 2 and cur:
            cur["los"] = dt
            if "aos" in cur and "max" in cur:
                alt, az, dist = altaz_at(sat, obs, cur["max"]); cur["max_alt"] = alt; cur["max_az"] = az; passes.append(cur)
            cur = {}
    return passes

def fmt_time(dt): return dt.astimezone().strftime("%H:%M")
def fmt_utc(dt): return dt.astimezone(timezone.utc).strftime("%H:%M UTC")

def pass_points(config, pass_info, step_minutes=5):
    sat = make_satellite(config["selected_sat"]); obs = observer_from_config(config)
    pts, t = [], pass_info["aos"]
    while t <= pass_info["los"]:
        alt, az, dist = altaz_at(sat, obs, t)
        if alt >= 0: pts.append({"time": t, "alt": alt, "az": az, "dist": dist})
        t += timedelta(minutes=step_minutes)
    if not pts or pts[-1]["time"] < pass_info["los"]:
        alt, az, dist = altaz_at(sat, obs, pass_info["los"])
        pts.append({"time": pass_info["los"], "alt": max(0, alt), "az": az, "dist": dist})
    return pts

def show_pass_list(config):
    clear(); print_header("Next Passes")
    if not config.get("selected_sat"):
        print("No satellite selected."); pause(); return None
    try: passes = find_passes(config, int(config.get("pass_window_hours", 24)))
    except Exception as e:
        print(f"{BAD}Pass calculation failed:{RESET}\n{str(e)[:TEXT_WIDTH]}"); pause(); return None
    if not passes:
        print("No passes in selected window."); pause(); return None
    while True:
        clear(); print_header("Next Passes")
        print(f"Sat: {ACCENT}{config['selected_sat']['name'][:40]}{RESET}")
        print(f"Loc: {ACCENT}{config.get('location_name','Unknown')}{RESET}\n")
        for i, p in enumerate(passes[:9], 1):
            dur = int((p["los"] - p["aos"]).total_seconds() // 60)
            print(f"{BLUE}{i}){RESET} AOS {fmt_time(p['aos'])}  Max {fmt_time(p['max'])} {p['max_alt']:.0f}° {cardinal(p['max_az'])}  LOS {fmt_time(p['los'])}  {dur}m")
        print(f"\n{BLUE}b){RESET} Back")
        c = styled_prompt("\nSelect pass: ").strip().lower()
        if c == "b": return None
        try:
            idx = int(c)
            if 1 <= idx <= min(9, len(passes)): return passes[idx-1]
        except Exception: pass

def pass_details_screen(config, pass_info):
    note = note_for_sat(config["selected_sat"]["name"])
    lines = [f"Sat: {config['selected_sat']['name']}", f"Loc: {config.get('location_name','Unknown')}", "", f"AOS: {fmt_time(pass_info['aos'])} / {fmt_utc(pass_info['aos'])}", f"Max: {fmt_time(pass_info['max'])} / {fmt_utc(pass_info['max'])}", f"LOS: {fmt_time(pass_info['los'])} / {fmt_utc(pass_info['los'])}", f"Peak: {pass_info['max_alt']:.0f}° {cardinal(pass_info['max_az'])} ({pass_info['max_az']:.0f}°)", "", f"Mode: {note['mode']}", f"RX  : {note['rx']}", f"TX  : {note['tx']}", f"Note: {note['notes']}", "", "Aiming table:"]
    for p in pass_points(config, pass_info, 5): lines.append(f"{fmt_time(p['time'])}  Az {p['az']:>3.0f}° {cardinal(p['az']):<3}  El {p['alt']:>2.0f}°")
    paginate("Pass Details", lines)

# ---------- GRAPHICS ----------

def fbi_available(): return shutil.which("fbi") is not None
def pil_available(): return Image is not None and ImageDraw is not None and ImageFont is not None

def clear_glyph_framebuffer():
    subprocess.run(["sudo", "dd", "if=/dev/zero", f"of={FB_DEVICE}", "bs=1M", "count=4"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)

def launch_fbi(image_path): subprocess.run(["sudo", "fbi", "-d", FB_DEVICE, "-T", FB_TTY, "-a", "--noverbose", image_path], check=False)

def load_font(size=24, bold=False):
    try: return ImageFont.truetype("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf", size)
    except Exception: return ImageFont.load_default()

def processed_compass(size=620):
    if not os.path.exists(COMPASS_PATH):
        img = Image.new("RGBA", (size, size), (0,0,0,255)); d = ImageDraw.Draw(img); green=(70,255,120,255); c=size//2; r=int(size*.43)
        d.ellipse((c-r,c-r,c+r,c+r), outline=green, width=4)
        for deg, lab in [(0,"N"),(90,"E"),(180,"S"),(270,"W")]:
            a=math.radians(deg-90); x=c+int((r-45)*math.cos(a)); y=c+int((r-45)*math.sin(a)); d.text((x-12,y-16), lab, fill=green, font=load_font(34, True))
        return img
    src = Image.open(COMPASS_PATH).convert("RGB")
    w,h=src.size; side=min(w,h); src=src.crop(((w-side)//2,(h-side)//2,(w+side)//2,(h+side)//2)).resize((size,size), Image.LANCZOS)
    gray=src.convert("L"); out=Image.new("RGBA", (size,size), (0,0,0,255)); pix=out.load(); gp=gray.load()
    for y in range(size):
        for x in range(size):
            lum=gp[x,y]
            if lum < 235:
                strength=int((235-lum)/235*255); g=max(55,strength); pix[x,y]=(30,min(255,120+g),70,255)
    return out

def sky_xy(cx, cy, max_r, az_deg, alt_deg):
    r=max_r*(1.0-max(0,min(90,alt_deg))/90.0); a=math.radians(az_deg-90.0)
    return cx+r*math.cos(a), cy+r*math.sin(a)

def current_point_for_pass(config, pass_info, now):
    sat=make_satellite(config["selected_sat"]); obs=observer_from_config(config)
    if now < pass_info["aos"]: dt=pass_info["aos"]; state="WAIT"
    elif now > pass_info["los"]: dt=pass_info["los"]; state="DONE"
    else: dt=now; state="LIVE"
    alt, az, dist = altaz_at(sat, obs, dt)
    return {"time": dt, "alt": max(0,alt), "az": az, "dist": dist, "state": state}

def build_pass_assist_image(config, pass_info):
    W,H=1000,660; comp_size=620; left=25; top=10; cx=left+comp_size//2; cy=top+comp_size//2; max_r=int(comp_size*.405)
    img=Image.new("RGBA", (W,H), (0,0,0,255)); img.alpha_composite(processed_compass(comp_size), (left,top)); draw=ImageDraw.Draw(img)
    green=(70,255,120,255); white=(238,238,238,255); yellow=(255,225,40,255); orange=(255,120,20,255); dim=(150,150,150,255); red=(255,80,80,255)
    title_f=load_font(30, True); med=load_font(24, True); small=load_font(20); tiny=load_font(18)
    pts=[]
    for p in pass_points(config, pass_info, 1): pts.append(sky_xy(cx, cy, max_r, p["az"], p["alt"]))
    if len(pts)>=2: draw.line(pts, fill=yellow, width=6, joint="curve")
    sat=make_satellite(config["selected_sat"]); obs=observer_from_config(config)
    for lab, dt in [("AOS", pass_info["aos"]),("MAX", pass_info["max"]),("LOS", pass_info["los"])]:
        alt,az,dist=altaz_at(sat, obs, dt); x,y=sky_xy(cx,cy,max_r,az,max(0,alt)); color=green if lab=="MAX" else white
        draw.ellipse((x-7,y-7,x+7,y+7), fill=color); draw.text((x+9,y-11), lab, fill=color, font=tiny)
    now=datetime.now(timezone.utc); cur=current_point_for_pass(config, pass_info, now); bx,by=sky_xy(cx,cy,max_r,cur["az"],cur["alt"])
    draw.ellipse((bx-17,by-17,bx+17,by+17), fill=orange, outline=white, width=3); draw.text((bx+21,by-14), "SAT", fill=orange, font=small)
    x=675; y=24; note=note_for_sat(config["selected_sat"]["name"]); satname=config["selected_sat"]["name"][:24]
    draw.text((x,y), satname, fill=green, font=title_f); y+=44
    draw.text((x,y), f"{cur['state']}  {now.strftime('%H:%M:%S')} UTC", fill=white, font=med); y+=42
    draw.text((x,y), f"Az {cur['az']:.0f}° {cardinal(cur['az'])}", fill=yellow, font=title_f); y+=42
    draw.text((x,y), f"El {cur['alt']:.0f}°", fill=yellow, font=title_f); y+=42
    if cur["state"]=="WAIT": draw.text((x,y), f"AOS in {max(0,int((pass_info['aos']-now).total_seconds()//60))} min", fill=green, font=med)
    elif cur["state"]=="LIVE": draw.text((x,y), f"LOS in {max(0,int((pass_info['los']-now).total_seconds()//60))} min", fill=green, font=med)
    else: draw.text((x,y), "Pass ended", fill=red, font=med)
    y+=42
    draw.text((x,y), f"Peak {pass_info['max_alt']:.0f}° {cardinal(pass_info['max_az'])}", fill=white, font=med); y+=40
    draw.text((x,y), f"AOS {fmt_utc(pass_info['aos'])}", fill=dim, font=small); y+=30
    draw.text((x,y), f"MAX {fmt_utc(pass_info['max'])}", fill=dim, font=small); y+=30
    draw.text((x,y), f"LOS {fmt_utc(pass_info['los'])}", fill=dim, font=small); y+=44
    draw.text((x,y), "FREQ", fill=green, font=med); y+=34
    draw.text((x,y), f"Mode: {note['mode'][:24]}", fill=white, font=small); y+=29
    draw.text((x,y), f"RX: {note['rx'][:25]}", fill=white, font=small); y+=29
    draw.text((x,y), f"TX: {note['tx'][:25]}", fill=white, font=small)
    fy = H - 25

    # No footer rectangle. Keep the compass visible.
    draw.text(
        (10, fy),
        config.get("location_name", "Saved Location")[:18],
        fill=green,
        font=med,
    )

    # Compact controls, tucked lower-right.
    controls = "Enter=Refresh  a=Auto  d=Details  b=Back"
    tw = draw.textlength(controls, font=small)
    draw.text(
        (W - int(tw) - 18, fy + 4),
        controls,
        fill=white,
        font=small,
    )
    img.convert("RGB").save(PASS_IMAGE, quality=95); return PASS_IMAGE

def live_pass_assist(config, pass_info):
    if not pil_available(): clear(); print_header("Live Pass Assist"); print("Install Pillow: sudo apt install python3-pil"); pause(); return
    if not fbi_available(): clear(); print_header("Live Pass Assist"); print("Install fbi: sudo apt install fbi"); pause(); return
    auto=True
    while True:
        clear(); print_header("Live Pass Assist")
        print(f"Sat: {ACCENT}{config['selected_sat']['name'][:40]}{RESET}\nLoc: {ACCENT}{config.get('location_name','Unknown')}{RESET}")
        print(f"Update: {ACCENT}{config.get('live_update_seconds',5)} sec{RESET}  Auto: {ACCENT}{'ON' if auto else 'OFF'}{RESET}\n")
        print("Building pass graphic...")
        try: path=build_pass_assist_image(config, pass_info); print("Opening on Glyph screen."); launch_fbi(path)
        except Exception as e:
            clear_glyph_framebuffer(); print(f"{BAD}Graphic failed:{RESET} {str(e)[:TEXT_WIDTH]}"); pause(); return
        if auto:
            wait=int(config.get("live_update_seconds",5)); print(f"{BLUE}Enter){RESET} Refresh  {BLUE}a){RESET} Auto Off  {BLUE}d){RESET} Details  {BLUE}b){RESET} Back")
            r,_,_=select.select([sys.stdin], [], [], wait); c=sys.stdin.readline().strip().lower() if r else ""
        else: c=styled_prompt("Enter=Refresh, a=Auto, d=Details, b=Back: ").strip().lower()
        clear_glyph_framebuffer()
        if c=="b": clear(); return
        if c=="a": auto=not auto
        elif c=="d": pass_details_screen(config, pass_info)

# ---------- SETTINGS / HELP ----------

def location_screen(config):
    while True:
        clear(); print_header("Set Location")
        print(f"Current: {ACCENT}{config.get('location_name','Unknown')}{RESET}")
        if config.get("lat") is not None:
            print(f"Lat/Lon: {ACCENT}{float(config['lat']):.5f}, {float(config['lon']):.5f}{RESET}")
        print(f"Source : {ACCENT}{config.get('location_source','Unknown')}{RESET}")
        print()
        print(f"{BLUE}1){RESET} Get GPS Fix")
        print(f"{BLUE}2){RESET} Enter Maidenhead Grid")
        print(f"{BLUE}3){RESET} Enter Manual Coordinates")
        print()
        print(f"{BLUE}b){RESET} Back")
        c = styled_prompt("\nSelect: ").strip().lower()
        if c == "1": config = gps_screen(config)
        elif c == "2": config = set_grid_location(config)
        elif c == "3": config = set_manual_location(config)
        elif c == "b": return config

def help_screen():
    paginate("Help / Install", ["Glyph OSCAR / AMSAT Pass Assist", "", "Predicts amateur satellite passes from fresh CelesTrak amateur TLEs and GPS/manual/grid location.", "", "Install:", "pip install skyfield pyserial", "sudo apt install python3-pil fbi", "", "GPS:", f"Port: {GPS_PORT}", f"Baud: {GPS_BAUD}", "", "Location fallback:", "Use a 4- or 6-character Maidenhead grid like DN13ro if GPS is unavailable.", "", "Live Pass Assist draws to /dev/fb1 with fbi. It will not appear in Termius.", "", "Sky plot: azimuth is compass direction. Altitude is distance from center: horizon near outer ring, overhead near center.", "", "Controls: Enter refreshes, a toggles auto, d details, b back.", "", "Always check current AMSAT status before transmitting."])

def settings_screen(config):
    while True:
        clear(); print_header("Settings")
        print(f"Window Hours : {ACCENT}{config.get('pass_window_hours',24)}{RESET}")
        print(f"Min Elevation: {ACCENT}{config.get('min_elevation',5)}°{RESET}")
        print(f"Live Update  : {ACCENT}{config.get('live_update_seconds',5)} sec{RESET}\n")
        print(f"{BLUE}1){RESET} Set Pass Window\n{BLUE}2){RESET} Set Min Elevation\n{BLUE}3){RESET} Set Live Update Seconds\n{BLUE}4){RESET} Set Location\n{BLUE}5){RESET} Force TLE Refresh\n{BLUE}6){RESET} Help / Install\n\n{BLUE}b){RESET} Back")
        c=styled_prompt("\nSelect: ").strip().lower()
        if c=="1":
            try: config["pass_window_hours"]=max(1,min(168,int(styled_prompt("Hours: ").strip()))); save_config(config)
            except Exception: pass
        elif c=="2":
            try: config["min_elevation"]=max(0,min(45,float(styled_prompt("Min elevation degrees: ").strip()))); save_config(config)
            except Exception: pass
        elif c=="3":
            try: config["live_update_seconds"]=max(1,min(60,int(styled_prompt("Live update seconds: ").strip()))); save_config(config)
            except Exception: pass
        elif c=="4": config=location_screen(config)
        elif c=="5":
            clear(); print_header("TLE Refresh")
            try: print(f"Downloaded {ACCENT}{len(parse_tles(fetch_tles(True)))}{RESET} satellites.")
            except Exception as e: print(f"{BAD}Failed:{RESET} {str(e)[:TEXT_WIDTH]}")
            pause()
        elif c=="6": help_screen()
        elif c=="b": return config

# ---------- MAIN ----------

def main():
    config=load_config(); selected_pass=None
    while True:
        clear(); print_header("Glyph OSCAR Tracker")
        loc=config.get("location_name") or "No location"; sat=config.get("selected_sat",{}).get("name") if config.get("selected_sat") else "No satellite"
        print(f"Loc: {ACCENT}{loc}{RESET}")
        if config.get("lat") is not None: print(f"GPS: {ACCENT}{float(config['lat']):.4f}, {float(config['lon']):.4f}{RESET}")
        else: print(f"GPS: {WARN}Not set{RESET}")
        print(f"Sat: {ACCENT}{sat[:42]}{RESET}")
        if selected_pass: print(f"Pass: {ACCENT}{fmt_time(selected_pass['aos'])} → {fmt_time(selected_pass['los'])} Peak {selected_pass['max_alt']:.0f}°{RESET}")
        print(f"\n{BLUE}1){RESET} Set Location\n{BLUE}2){RESET} Pick Satellite\n{BLUE}3){RESET} Next Passes\n{BLUE}4){RESET} Pass Details\n{BLUE}5){RESET} Live Pass Assist\n{BLUE}6){RESET} Settings\n\n{BLUE}q){RESET} Quit")
        c=styled_prompt("\nSelect: ").strip().lower()
        if c=="1": config=location_screen(config)
        elif c=="2": config=pick_satellite(config); selected_pass=None
        elif c=="3":
            p=show_pass_list(config)
            if p: selected_pass=p; pass_details_screen(config, selected_pass)
        elif c=="4":
            if not selected_pass: selected_pass=show_pass_list(config)
            if selected_pass: pass_details_screen(config, selected_pass)
        elif c=="5":
            if not selected_pass: selected_pass=show_pass_list(config)
            if selected_pass: live_pass_assist(config, selected_pass)
        elif c=="6": config=settings_screen(config)
        elif c=="q": clear(); break

if __name__ == "__main__": main()
