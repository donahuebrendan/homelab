#!/usr/bin/env python3
"""
Pi Stats API
Background thread updates all slow stats every 5 seconds.
Flask routes return cached values instantly — no blocking.
"""

from flask import Flask, jsonify
import psutil
import socket
import time
import threading
import urllib.request
import json
import unicodedata
import os
from datetime import datetime
from zoneinfo import ZoneInfo

# ── DHT22 setup ────────────────────────────────────────────────────
_dht_sensor = None
try:
    import adafruit_dht
    import board
    _dht_sensor = adafruit_dht.DHT22(board.D4)
    print("DHT22 sensor initialized on GPIO D4")
except Exception as e:
    print(f"DHT22 not available: {e}")

# ── Shared stats cache (updated by background thread) ──────────────
_stats_cache = {
    "cpu_pct":      0.0,
    "ram_pct":      0.0,
    "ram_used_mb":  0,
    "ram_total_mb": 0,
    "temp_c":       0.0,
    "temp_pct":     0.0,
    "disk_pct":     0.0,
    "disk_used_gb": 0.0,
    "disk_total_gb":0.0,
    "rx_str":       "0B",
    "tx_str":       "0B",
    "ip":           "0.0.0.0",
    "hostname":     "raspberrypi",
    "uptime":       "0m",
    "dht_temp_f":   None,
    "dht_humidity": None,
}
_stats_lock = threading.Lock()

# ── Background thread helpers ──────────────────────────────────────
_last_net_bytes = None
_last_net_time  = None
_last_dht_read  = 0
_dht_temp_f     = None
_dht_humidity   = None

def _format_speed(bps):
    if bps < 1024:
        return str(int(bps)) + "B"
    elif bps < 1024 * 1024:
        return str(round(bps / 1024, 1)) + "K"
    else:
        return str(round(bps / (1024 * 1024), 1)) + "M"

def _get_cpu_temp():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return round(int(f.read()) / 1000.0, 1)
    except:
        return 0.0

def _get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "No IP"

def _read_dht():
    """Read DHT22 — called from background thread, never blocks a request."""
    global _dht_temp_f, _dht_humidity, _last_dht_read
    if _dht_sensor is None:
        return
    now = time.time()
    if now - _last_dht_read < 10:
        return
    try:
        temp_c   = _dht_sensor.temperature
        humidity = _dht_sensor.humidity
        if temp_c is not None and humidity is not None:
            _dht_temp_f   = round(temp_c * 9 / 5 + 32, 1)
            _dht_humidity = round(humidity, 1)
            _last_dht_read = now
    except RuntimeError:
        pass  # DHT22 occasionally glitches — keep last good value

def _update_stats():
    """Background thread — updates cache every 5 seconds."""
    global _last_net_bytes, _last_net_time

    # Warm up CPU measurement
    psutil.cpu_percent(interval=None)

    while True:
        try:
            # CPU
            cpu = psutil.cpu_percent(interval=1)  # blocks 1s in thread — that's fine

            # RAM
            ram = psutil.virtual_memory()

            # CPU temp
            cpu_temp = _get_cpu_temp()
            temp_pct = round(min(100, (cpu_temp / 85) * 100), 1)

            # Disk
            disk = psutil.disk_usage("/")

            # Network speeds
            net_now = psutil.net_io_counters()
            now     = time.time()
            if _last_net_bytes is None:
                rx_str = "0B"
                tx_str = "0B"
            else:
                dt     = max(now - _last_net_time, 0.001)
                rx_str = _format_speed((net_now.bytes_recv - _last_net_bytes.bytes_recv) / dt)
                tx_str = _format_speed((net_now.bytes_sent - _last_net_bytes.bytes_sent) / dt)
            _last_net_bytes = net_now
            _last_net_time  = now

            # Uptime
            secs = int(time.time() - psutil.boot_time())
            h, rem = divmod(secs, 3600)
            m, _   = divmod(rem, 60)
            uptime = f"{h}h{m}m" if h > 0 else f"{m}m"

            # DHT22 (non-blocking — uses cached value)
            _read_dht()

            # Update shared cache atomically
            with _stats_lock:
                _stats_cache.update({
                    "cpu_pct":       round(cpu, 1),
                    "ram_pct":       round(ram.percent, 1),
                    "ram_used_mb":   ram.used // (1024 ** 2),
                    "ram_total_mb":  ram.total // (1024 ** 2),
                    "temp_c":        cpu_temp,
                    "temp_pct":      temp_pct,
                    "disk_pct":      round(disk.percent, 1),
                    "disk_used_gb":  round(disk.used / (1024 ** 3), 1),
                    "disk_total_gb": round(disk.total / (1024 ** 3), 1),
                    "rx_str":        rx_str,
                    "tx_str":        tx_str,
                    "ip":            _get_ip(),
                    "hostname":      socket.gethostname(),
                    "uptime":        uptime,
                    "dht_temp_f":    _dht_temp_f,
                    "dht_humidity":  _dht_humidity,
                })

        except Exception as e:
            print(f"Stats update error: {e}")

        time.sleep(4)  # update every 4s (1s is used by cpu_percent interval above)

# Start background thread
_thread = threading.Thread(target=_update_stats, daemon=True)
_thread.start()

# ── Flask app ──────────────────────────────────────────────────────
app = Flask(__name__)

# ── Tide data ──────────────────────────────────────────────────────
NOAA_STATION  = "9410230"
NOAA_BASE_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"

_tide_cache = {"data": None, "date_str": None}

def fetch_tides():
    today = datetime.now().strftime("%Y%m%d")
    if _tide_cache["date_str"] == today and _tide_cache["data"] is not None:
        return _tide_cache["data"]
    url = (
        f"{NOAA_BASE_URL}?begin_date={today}&end_date={today}"
        f"&station={NOAA_STATION}&product=predictions&datum=MLLW"
        f"&time_zone=lst_ldt&interval=hilo&units=english"
        f"&application=tronbyt_pi&format=json"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "tronbyt-pi/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = json.loads(resp.read().decode())
        tides = []
        for p in raw.get("predictions", []):
            t_str    = p["t"]
            height   = round(float(p["v"]), 1)
            tide_type = p["type"]
            time_part = t_str.split(" ")[1]
            hour      = int(time_part.split(":")[0])
            minute    = int(time_part.split(":")[1])
            ampm      = "AM" if hour < 12 else "PM"
            hour12    = hour % 12 or 12
            tides.append({
                "time":   f"{hour12}:{minute:02d}{ampm}",
                "mins":   hour * 60 + minute,
                "height": height,
                "type":   tide_type,
            })
        _tide_cache["data"]     = tides
        _tide_cache["date_str"] = today
        return tides
    except Exception as e:
        print(f"Tide fetch error: {e}")
        return _tide_cache["data"]

def get_next_tide_index(tides):
    now = datetime.now()
    current_mins = now.hour * 60 + now.minute
    for i, t in enumerate(tides):
        if t["mins"] > current_mins:
            return i
    return 0

# ── National Debt ──────────────────────────────────────────────────
DEBT_URL = (
    "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"
    "/v2/accounting/od/debt_to_penny?sort=-record_date&page%5Bsize%5D=1"
)
_debt_cache = {"data": None, "date_str": None}

def fetch_debt():
    today = datetime.now().strftime("%Y-%m-%d")
    if _debt_cache["date_str"] == today and _debt_cache["data"] is not None:
        return _debt_cache["data"]
    try:
        req = urllib.request.Request(DEBT_URL, headers={"User-Agent": "tronbyt-pi/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = json.loads(resp.read().decode())
        record = raw["data"][0]
        total  = float(record["tot_pub_debt_out_amt"])
        def to_T(n): return round(n / 1_000_000_000_000, 2)
        data = {
            "total_T":     to_T(total),
            "public_T":    to_T(float(record["debt_held_public_amt"])),
            "intra_T":     to_T(float(record["intragov_hold_amt"])),
            "record_date": record["record_date"],
            "per_citizen": int(total / 335_000_000),
        }
        _debt_cache["data"]     = data
        _debt_cache["date_str"] = today
        return data
    except Exception as e:
        print(f"Debt fetch error: {e}")
        return _debt_cache["data"]

# ── Fantasy Football ───────────────────────────────────────────────
SLEEPER_LEAGUE_ID = "1339420703467773952"
SLEEPER_BASE_URL  = "https://api.sleeper.app/v1"

TEAM_TO_FRIEND = {
    "A plane hit the 2nd Bower": "Brendan",
    "Belichick's Goon Squad":    "Danny",
    "Embryogenesis":             "Hank",
    "Bag End Bagginses":         "Caleb",
    "Joe-ver the Rhine":         "Andrew",
    "Amon-Ra Speedwagon":        "Niles",
    "Stidham is #1":             "Justin",
    "Game of Throws":            "Megan",
}

def _normalize(name):
    if not name:
        return ""
    name = name.strip()
    name = unicodedata.normalize("NFKC", name)
    name = name.replace("\u2019", "'").replace("\u2018", "'").replace("\uff07", "'")
    return name

NORM_TEAM_MAP = {_normalize(k): v for k, v in TEAM_TO_FRIEND.items()}
_fantasy_cache = {"data": None, "date_str": None}

def fetch_fantasy():
    today = datetime.now().strftime("%Y-%m-%d")
    if _fantasy_cache["date_str"] == today and _fantasy_cache["data"] is not None:
        return _fantasy_cache["data"]
    try:
        def sleeper_get(url):
            req = urllib.request.Request(url, headers={"User-Agent": "tronbyt-pi/1.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                return json.loads(r.read().decode())
        rosters = sleeper_get(f"{SLEEPER_BASE_URL}/league/{SLEEPER_LEAGUE_ID}/rosters")
        users   = sleeper_get(f"{SLEEPER_BASE_URL}/league/{SLEEPER_LEAGUE_ID}/users")
        owner_to_team = {
            u["user_id"]: u.get("metadata", {}).get("team_name") or u.get("display_name")
            for u in users
        }
        standings = []
        for roster in rosters:
            s        = roster.get("settings", {})
            team     = owner_to_team.get(roster.get("owner_id"), "Unknown")
            friend   = NORM_TEAM_MAP.get(_normalize(team), team)
            pts      = s.get("fpts", 0) + s.get("fpts_decimal", 0) / 100
            standings.append({
                "name":   friend,
                "wins":   s.get("wins", 0),
                "losses": s.get("losses", 0),
                "ties":   s.get("ties", 0),
                "pts":    round(pts, 2),
            })
        standings.sort(key=lambda x: (x["wins"], x["pts"]), reverse=True)
        _fantasy_cache["data"]     = standings
        _fantasy_cache["date_str"] = today
        return standings
    except Exception as e:
        print(f"Fantasy fetch error: {e}")
        return _fantasy_cache["data"]

# ── Pi-hole ────────────────────────────────────────────────────────
PIHOLE_URL      = "http://192.168.4.35:8080"
PIHOLE_PASSWORD = os.environ["PIHOLE_PASSWORD"]

_pihole_sid         = None
_pihole_sid_expiry  = 0
_pihole_cache       = {"data": None, "last_fetch": 0}
PIHOLE_CACHE_SECS   = 60   # refresh top domains every 60 seconds

def _pihole_auth():
    """Authenticate with Pi-hole and return a session ID. Caches until ~5min before expiry."""
    global _pihole_sid, _pihole_sid_expiry
    now = time.time()
    if _pihole_sid and now < _pihole_sid_expiry:
        return _pihole_sid
    try:
        data = json.dumps({"password": PIHOLE_PASSWORD}).encode()
        req  = urllib.request.Request(
            f"{PIHOLE_URL}/api/auth",
            data    = data,
            headers = {"Content-Type": "application/json"},
            method  = "POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode())
        sid      = body["session"]["sid"]
        validity = body["session"].get("validity", 1800)
        _pihole_sid        = sid
        _pihole_sid_expiry = now + validity - 300   # renew 5 min early
        print(f"Pi-hole auth OK, SID valid for {validity}s")
        return sid
    except Exception as e:
        print(f"Pi-hole auth error: {e}")
        return None

def fetch_pihole_top(count=3):
    """Fetch top queried domains from Pi-hole. Cached for 60 seconds."""
    now = time.time()
    if _pihole_cache["data"] and now - _pihole_cache["last_fetch"] < PIHOLE_CACHE_SECS:
        return _pihole_cache["data"]
    sid = _pihole_auth()
    if not sid:
        return _pihole_cache["data"]
    try:
        req = urllib.request.Request(
            f"{PIHOLE_URL}/api/stats/top_domains?count={count}",
            headers = {"X-FTL-SID": sid},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode())

        domains = body.get("domains", [])

        # Strip subdomain prefix for cleaner display
        # e.g. "mtalk.google.com" -> "google.com"
        def clean_domain(d):
            parts = d.split(".")
            if len(parts) > 2:
                return ".".join(parts[-2:])
            return d

        data = {
            "top_domains":    [{"domain": clean_domain(d["domain"]), "full": d["domain"], "count": d["count"]} for d in domains],
            "total_queries":  body.get("total_queries", 0),
            "blocked_queries": body.get("blocked_queries", 0),
        }
        _pihole_cache["data"]       = data
        _pihole_cache["last_fetch"] = now
        return data
    except Exception as e:
        print(f"Pi-hole top domains error: {e}")
        return _pihole_cache["data"]

# ── Flight Tracker ─────────────────────────────────────────────────
import math
import sqlite3
import os
import base64

# Home coordinates — South Oceanside, CA
HOME_LAT = 33.1886
HOME_LON = -117.3800

# Bounding box (~20 mile radius)
BOX_DEG  = 0.29   # ~20 miles in degrees
LAMIN    = HOME_LAT - BOX_DEG
LAMAX    = HOME_LAT + BOX_DEG
LOMIN    = HOME_LON - BOX_DEG
LOMAX    = HOME_LON + BOX_DEG

# OpenSky credentials
OPENSKY_CLIENT_ID = os.environ["OPENSKY_CLIENT_ID"]
OPENSKY_CLIENT_SECRET = os.environ["OPENSKY_CLIENT_SECRET"]
OPENSKY_TOKEN_URL     = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"
OPENSKY_API_URL       = "https://opensky-network.org/api/states/all"

# Aircraft DB path (populated on first run)
AIRCRAFT_DB_PATH = "/persistent/aircraft/aircraft.db"
AIRCRAFT_CSV_URL = "https://opensky-network.org/datasets/metadata/aircraftDatabase.csv"

# Operating hours
OPERATING_START = 8   # 8 AM
OPERATING_END   = 20  # 8 PM

# Flight cache — updated by background thread
_flight_cache      = None
_flight_cache_lock = threading.Lock()

# OpenSky token cache
_opensky_token        = None
_opensky_token_expiry = 0

def _is_operating_hours():
    """Returns True between 7 AM and 9 PM Pacific time."""
    hour = datetime.now(ZoneInfo("America/Los_Angeles")).hour
    return 7 <= hour < 21

def _opensky_get_token():
    """Fetch OAuth2 bearer token from OpenSky. Cached until 2 min before expiry."""
    global _opensky_token, _opensky_token_expiry
    now = time.time()
    if _opensky_token and now < _opensky_token_expiry:
        return _opensky_token
    try:
        data = (
            f"grant_type=client_credentials"
            f"&client_id={OPENSKY_CLIENT_ID}"
            f"&client_secret={OPENSKY_CLIENT_SECRET}"
        ).encode()
        req = urllib.request.Request(
            OPENSKY_TOKEN_URL,
            data    = data,
            headers = {"Content-Type": "application/x-www-form-urlencoded"},
            method  = "POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode())
        token      = body["access_token"]
        expires_in = body.get("expires_in", 1800)
        _opensky_token        = token
        _opensky_token_expiry = now + expires_in - 120
        print(f"OpenSky token acquired, valid for {expires_in}s")
        return token
    except Exception as e:
        print(f"OpenSky auth error: {e}")
        return None

def _haversine_miles(lat1, lon1, lat2, lon2):
    """Calculate distance in miles between two coordinates."""
    R    = 3958.8   # Earth radius in miles
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a    = (math.sin(dlat / 2) ** 2 +
            math.cos(math.radians(lat1)) *
            math.cos(math.radians(lat2)) *
            math.sin(dlon / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))

def _lookup_aircraft(icao24):
    """Look up aircraft type from local SQLite DB."""
    if not os.path.exists(AIRCRAFT_DB_PATH):
        return "Unknown"
    try:
        conn = sqlite3.connect(AIRCRAFT_DB_PATH)
        c    = conn.cursor()
        c.execute("SELECT manufacturer, model FROM aircraft WHERE icao24=?", (icao24.lower(),))
        row = c.fetchone()
        conn.close()
        if row and (row[0] or row[1]):
            mfr   = row[0].strip() if row[0] else ""
            model = row[1].strip() if row[1] else ""
            if mfr and model:
                return f"{mfr} {model}"
            return mfr or model or "Unknown"
        return "Unknown Jet"
    except Exception as e:
        return "Unknown"

def _fetch_flights():
    """Poll OpenSky API and update flight cache. Called from background thread."""
    global _flight_cache

    if not _is_operating_hours():
        with _flight_cache_lock:
            _flight_cache = {
                "status":        "sleeping",
                "callsign":      "ZZZ",
                "altitude_ft":   0,
                "airspeed_mph":  0,
                "aircraft_type": "Radar Off",
                "distance_miles": 0.0,
                "last_updated":  datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        return

    token = _opensky_get_token()
    if not token:
        return   # keep last cache on auth failure

    url = (
        f"{OPENSKY_API_URL}"
        f"?lamin={LAMIN}&lomin={LOMIN}&lamax={LAMAX}&lomax={LOMAX}"
    )
    try:
        req = urllib.request.Request(
            url,
            headers = {
                "Authorization": f"Bearer {token}",
                "User-Agent":    "tronbyt-pi/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode())

        states = body.get("states") or []
        now_ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

        if not states:
            with _flight_cache_lock:
                _flight_cache = {
                    "status":        "empty",
                    "callsign":      "---",
                    "altitude_ft":   0,
                    "airspeed_mph":  0,
                    "aircraft_type": "Clear Skies",
                    "distance_miles": 0.0,
                    "last_updated":  now_ts,
                }
            return

        # Find closest aircraft using Haversine
        closest     = None
        closest_dist = float("inf")

        for s in states:
            # OpenSky state vector indices:
            # 0=icao24, 1=callsign, 5=lon, 6=lat, 7=baro_alt, 9=velocity
            lat = s[6]
            lon = s[5]
            if lat is None or lon is None:
                continue
            dist = _haversine_miles(HOME_LAT, HOME_LON, lat, lon)
            if dist < closest_dist:
                closest_dist = dist
                closest      = s

        if not closest:
            with _flight_cache_lock:
                _flight_cache = {
                    "status":        "empty",
                    "callsign":      "---",
                    "altitude_ft":   0,
                    "airspeed_mph":  0,
                    "aircraft_type": "Clear Skies",
                    "distance_miles": 0.0,
                    "last_updated":  now_ts,
                }
            return

        icao24       = (closest[0] or "").strip()
        callsign     = (closest[1] or "").strip() or "UNKNOWN"
        baro_alt_m   = closest[7] or 0
        velocity_ms  = closest[9] or 0

        alt_ft   = int(baro_alt_m * 3.28084)
        speed_mph = int(velocity_ms * 2.23694)
        ac_type  = _lookup_aircraft(icao24)

        with _flight_cache_lock:
            _flight_cache = {
                "status":        "active",
                "callsign":      callsign,
                "altitude_ft":   alt_ft,
                "airspeed_mph":  speed_mph,
                "aircraft_type": ac_type,
                "distance_miles": round(closest_dist, 1),
                "last_updated":  now_ts,
                "stale":         False,
            }
        print(f"Flight update: {callsign} {ac_type} {alt_ft}ft {speed_mph}mph {round(closest_dist,1)}mi")

    except Exception as e:
        print(f"OpenSky fetch error: {e}")
        # Mark cache stale but keep last known data
        with _flight_cache_lock:
            if _flight_cache:
                _flight_cache["stale"] = True

def _flight_poller():
    """Background thread — polls OpenSky every 30 seconds during operating hours."""
    while True:
        try:
            _fetch_flights()
        except Exception as e:
            print(f"Flight poller error: {e}")
        time.sleep(30)

# Start flight poller thread
_flight_thread = threading.Thread(target=_flight_poller, daemon=True)
_flight_thread.start()

# ── Routes ─────────────────────────────────────────────────────────
@app.route("/stats")
def stats():
    with _stats_lock:
        return jsonify(dict(_stats_cache))

@app.route("/tides")
def tides():
    tide_list = fetch_tides()
    if tide_list is None:
        return jsonify({"error": "Could not fetch tide data"}), 503
    return jsonify({
        "tides":    tide_list,
        "next_idx": get_next_tide_index(tide_list),
        "station":  NOAA_STATION,
        "location": "Oceanside, CA",
    })

@app.route("/debt")
def debt():
    data = fetch_debt()
    if data is None:
        return jsonify({"error": "Could not fetch debt data"}), 503
    return jsonify(data)

@app.route("/fantasy")
def fantasy():
    data = fetch_fantasy()
    if data is None:
        return jsonify({"error": "Could not fetch fantasy data"}), 503
    return jsonify(data)

@app.route("/pihole")
def pihole():
    data = fetch_pihole_top(count=3)
    if data is None:
        return jsonify({"error": "Could not fetch Pi-hole data"}), 503
    return jsonify(data)

@app.route("/flights")
def flights():
    with _flight_cache_lock:
        data = dict(_flight_cache) if _flight_cache else None
    if data is None:
        return jsonify({
            "status":        "empty",
            "callsign":      "---",
            "altitude_ft":   0,
            "airspeed_mph":  0,
            "aircraft_type": "Initializing",
            "distance_miles": 0.0,
            "last_updated":  datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
    return jsonify(data)

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
