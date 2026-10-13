"""
Pi System Monitor v5
Top bar: Network speeds + Uptime
Three bars: RAM %, CPU Temp, Disk Usage
"""

load("render.star", "render")
load("http.star", "http")

# ── Config ─────────────────────────────────────────────────────────
PI_IP   = "192.168.4.29"
API_URL = "http://" + PI_IP + ":5000/stats"

# ── Bar dimensions ─────────────────────────────────────────────────
BAR_W = 56
BAR_H = 3

# ── Color logic ────────────────────────────────────────────────────
def ram_color(pct):
    if pct < 25:
        return "#00E676"
    elif pct < 75:
        return "#FFD740"
    else:
        return "#FF5252"

def temp_color(pct):
    if pct < 50:
        return "#00E676"
    elif pct < 75:
        return "#FFD740"
    else:
        return "#FF5252"

def disk_color(pct):
    if pct < 50:
        return "#AA80FF"
    elif pct < 75:
        return "#FFD740"
    else:
        return "#FF5252"

# ── Single stat row + bar ──────────────────────────────────────────
def stat_row(label, value_str, pct, color):
    filled = int(BAR_W * pct / 100)
    if filled < 1:
        filled = 1
    if filled > BAR_W:
        filled = BAR_W
    empty = BAR_W - filled

    return render.Column(
        children = [
            render.Row(
                children = [
                    render.Text(label,     color = "#7788AA", font = "tom-thumb"),
                    render.Text(" ",       color = "#000000", font = "tom-thumb"),
                    render.Text(value_str, color = color,     font = "tom-thumb"),
                ],
            ),
            render.Box(width = 1, height = 1, color = "#000000"),
            render.Row(
                children = [
                    render.Box(width = filled, height = BAR_H, color = color),
                    render.Box(width = empty,  height = BAR_H, color = "#151B2E"),
                ],
            ),
        ],
    )

# ── Error screen ───────────────────────────────────────────────────
def err(msg):
    return render.Root(
        child = render.Padding(
            pad = 2,
            child = render.Column(
                children = [
                    render.Text("PI STATS", color = "#FF5252", font = "tom-thumb"),
                    render.Text(msg,        color = "#888888", font = "tom-thumb"),
                ],
            ),
        ),
    )

# ── Main ───────────────────────────────────────────────────────────
def main():
    rep = http.get(API_URL, ttl_seconds = 10)
    if rep.status_code != 200:
        return err("HTTP " + str(rep.status_code))

    d = rep.json()

    ram_pct  = d["ram_pct"]
    ram_used = d["ram_used_mb"]
    temp_c   = d["temp_c"]
    temp_pct = d["temp_pct"]
    disk_pct = d["disk_pct"]
    disk_gb  = d["disk_used_gb"]
    rx_str   = d["rx_str"]
    tx_str   = d["tx_str"]
    uptime   = d["uptime"]

    c_ram  = ram_color(ram_pct)
    c_temp = temp_color(temp_pct)
    c_disk = disk_color(disk_pct)

    return render.Root(
        child = render.Padding(
            pad = 1,
            child = render.Column(
                children = [

                    # ── Header: net speeds + uptime ───────────────
                    render.Row(
                        children = [
                            render.Text("▼",     color = "#00E676", font = "tom-thumb"),
                            render.Text(rx_str,  color = "#00E676", font = "tom-thumb"),
                            render.Text(" ",     color = "#000000", font = "tom-thumb"),
                            render.Text("▲",     color = "#FF5252", font = "tom-thumb"),
                            render.Text(tx_str,  color = "#FF5252", font = "tom-thumb"),
                            render.Text(" ",     color = "#000000", font = "tom-thumb"),
                            render.Text(uptime,  color = "#445566", font = "tom-thumb"),
                        ],
                    ),

                    # Divider
                    render.Box(width = 62, height = 1, color = "#1E2540"),
                    render.Box(width = 1,  height = 1, color = "#000000"),

                    # ── RAM ──────────────────────────────────────
                    stat_row("RAM", str(ram_used) + "M", ram_pct, c_ram),

                    render.Box(width = 1, height = 2, color = "#000000"),

                    # ── Temp ─────────────────────────────────────
                    stat_row("TMP", str(temp_c) + "C", temp_pct, c_temp),

                    render.Box(width = 1, height = 2, color = "#000000"),

                    # ── Disk ─────────────────────────────────────
                    stat_row("DSK", str(disk_gb) + "G", disk_pct, c_disk),

                ],
            ),
        ),
    )
