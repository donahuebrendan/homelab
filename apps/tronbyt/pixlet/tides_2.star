"""
Oceanside Tide Chart v2
Compact layout - all 4 tides visible
tom-thumb font throughout
"""

load("render.star", "render")
load("http.star", "http")

PI_IP   = "192.168.4.29"
API_URL = "http://" + PI_IP + ":5000/tides"

def tide_row(tide, is_next):
    is_high  = tide["type"] == "H"
    c        = "#00B4FF" if is_high else "#FF9100"
    c_time   = "#FF69B4" if is_high else "#4488CC"
    c_height = "#FFFFFF" if is_next else "#445566"
    arrow    = "▲" if is_high else "▼"
    label    = "HI" if is_high else "LO"
    dot      = render.Box(width = 2, height = 7, color = c if is_next else "#111111")

    return render.Row(
        children = [
            dot,
            render.Box(width = 2, height = 1, color = "#000000"),
            render.Text(arrow,              color = c,        font = "tom-thumb"),
            render.Text(label + " ",        color = c,        font = "tom-thumb"),
            render.Text(tide["time"],       color = c_time,   font = "tom-thumb"),
            render.Text(" ",               color = "#000000", font = "tom-thumb"),
            render.Text(str(tide["height"]) + "ft", color = c_height, font = "tom-thumb"),
        ],
    )

def err(msg):
    return render.Root(
        child = render.Padding(
            pad = 2,
            child = render.Column(
                children = [
                    render.Text("TIDES", color = "#00B4FF", font = "tom-thumb"),
                    render.Text(msg,     color = "#888888", font = "tom-thumb"),
                ],
            ),
        ),
    )

def main():
    rep = http.get(API_URL, ttl_seconds = 3600)
    if rep.status_code != 200:
        return err("HTTP " + str(rep.status_code))

    d        = rep.json()
    tides    = d["tides"]
    next_idx = d["next_idx"]

    if len(tides) == 0:
        return err("NO DATA")

    rows = []
    for i, tide in enumerate(tides[:4]):
        rows.append(tide_row(tide, i == next_idx))
        if i < 3:
            rows.append(render.Box(width = 1, height = 1, color = "#000000"))

    return render.Root(
        child = render.Padding(
            pad = 1,
            child = render.Column(
                children = [

                    # ── Header ────────────────────────────────────
                    render.Row(
                        children = [
                            render.Text("~ ", color = "#00B4FF",  font = "tom-thumb"),
                            render.Text("OCEANSIDE", color = "#AA80FF", font = "tom-thumb"),
                            render.Text(" TIDES ~", color = "#00B4FF", font = "tom-thumb"),
                        ],
                    ),
                    render.Box(width = 62, height = 1, color = "#1A2535"),
                    render.Box(width = 1,  height = 1, color = "#000000"),

                ] + rows,
            ),
        ),
    )
