"""
US National Debt Monitor
Clean centered layout, red/white/blue theme.
"""

load("render.star", "render")
load("http.star", "http")

PI_IP   = "192.168.4.29"
API_URL = "http://" + PI_IP + ":5000/debt"

def err(msg):
    return render.Root(
        child = render.Padding(
            pad = 2,
            child = render.Column(
                children = [
                    render.Text("US DEBT", color = "#FF4444", font = "tom-thumb"),
                    render.Text(msg,       color = "#888888", font = "tom-thumb"),
                ],
            ),
        ),
    )

def main():
    rep = http.get(API_URL, ttl_seconds = 3600)
    if rep.status_code != 200:
        return err("HTTP " + str(rep.status_code))

    d       = rep.json()
    total_T = str(d["total_T"])

    parts   = total_T.split(".")
    whole   = parts[0]
    decimal = "." + parts[1] if len(parts) > 1 else ""

    return render.Root(
        child = render.Padding(
            pad = 1,
            child = render.Column(
                children = [

                    # ── Title centered (~62px wide, "US DEBT" ~7chars * 4px = ~28px) ──
                    render.Row(
                        children = [
                            render.Box(width = 12, height = 1, color = "#000000"),
                            render.Text("US ", color = "#FFFFFF", font = "tom-thumb"),
                            render.Text("DEBT", color = "#4488FF", font = "tom-thumb"),
                        ],
                    ),

                    # Red/white/blue striped divider
                    render.Row(
                        children = [
                            render.Box(width = 20, height = 1, color = "#FF4444"),
                            render.Box(width = 22, height = 1, color = "#FFFFFF"),
                            render.Box(width = 20, height = 1, color = "#4488FF"),
                        ],
                    ),

                    render.Box(width = 1, height = 6, color = "#000000"),

                    # ── $ + number centered (~62px wide, "$40.05T" ~7chars * 6px = ~42px) ──
                    render.Row(
                        children = [
                            render.Box(width = 8, height = 1, color = "#000000"),
                            render.Text("$",      color = "#FFFFFF", font = "tb-8"),
                            render.Text(whole,    color = "#FF4444", font = "tb-8"),
                            render.Text(decimal,  color = "#FFFFFF", font = "tb-8"),
                            render.Text("T",      color = "#4488FF", font = "tb-8"),
                        ],
                    ),

                    render.Box(width = 1, height = 4, color = "#000000"),

                    # ── Date centered ─────────────────────────────
                    render.Row(
                        children = [
                            render.Box(width = 10, height = 1, color = "#000000"),
                            render.Text(d["record_date"], color = "#223355", font = "tom-thumb"),
                        ],
                    ),

                ],
            ),
        ),
    )
