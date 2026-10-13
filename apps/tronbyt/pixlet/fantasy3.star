"""
Fantasy Football Leaderboard
Scrolls through all 8 teams showing name, record, and points.
"""

load("render.star", "render")
load("http.star", "http")

PI_IP   = "192.168.4.29"
API_URL = "http://" + PI_IP + ":5000/fantasy"

# ── Rank colors ────────────────────────────────────────────────────
RANK_COLORS = [
    "#FFD700",   # 1st - gold
    "#C0C0C0",   # 2nd - silver
    "#CD7F32",   # 3rd - bronze
    "#FFFFFF",   # 4th
    "#FFFFFF",   # 5th
    "#FFFFFF",   # 6th
    "#FFFFFF",   # 7th
    "#FFFFFF",   # 8th
]

# Brendan's highlight color
BRENDAN_COLOR = "#FF0000"

def err(msg):
    return render.Root(
        child = render.Padding(
            pad = 2,
            child = render.Column(
                children = [
                    render.Text("FANTASY", color = "#00E676", font = "tom-thumb"),
                    render.Text(msg,       color = "#888888", font = "tom-thumb"),
                ],
            ),
        ),
    )

def team_row(rank, team):
    c       = RANK_COLORS[rank] if rank < len(RANK_COLORS) else "#FFFFFF"
    wins    = str(int(team["wins"]))
    losses  = str(int(team["losses"]))
    record  = wins + "-" + losses
    pts     = str(team["pts"])
    name    = team["name"]

    # Highlight Brendan regardless of his position in the standings
    if name == "Brendan":
        name_color = BRENDAN_COLOR
    else:
        name_color = "#FFFFFF"

    return render.Row(
        children = [
            # Rank number
            render.Text(str(rank + 1) + " ", color = c,          font = "tom-thumb"),

            # Name
            render.Text(name + " ",          color = name_color, font = "tom-thumb"),

            # Record
            render.Text(record + " ",        color = c,          font = "tom-thumb"),

            # Points
            render.Text(pts,                 color = "#00E676",  font = "tom-thumb"),
        ],
    )

def main():
    rep = http.get(API_URL, ttl_seconds = 3600)

    if rep.status_code != 200:
        return err("HTTP " + str(rep.status_code))

    teams = rep.json()

    if len(teams) == 0:
        return err("NO DATA")

    # Build all team rows
    rows = []

    for i, team in enumerate(teams):
        rows.append(team_row(i, team))
        rows.append(
            render.Box(
                width = 1,
                height = 2,
                color = "#000000",
            )
        )

    return render.Root(
        child = render.Padding(
            pad = 1,
            child = render.Column(
                children = [

                    # ── Header ────────────────────────────────────
                    render.Row(
                        children = [
                            render.Text(
                                "Sleeper ",
                                color = "#00B4FF",
                                font = "tom-thumb",
                            ),
                            render.Text(
                                " 2026",
                                color = "#00B4FF",
                                font = "tom-thumb",
                            ),
                        ],
                    ),

                    render.Box(
                        width = 62,
                        height = 1,
                        color = "#1A3520",
                    ),

                    render.Box(
                        width = 1,
                        height = 1,
                        color = "#000000",
                    ),

                    # ── Scrolling leaderboard ─────────────────────
                    render.Marquee(
                        height = 22,
                        scroll_direction = "vertical",
                        offset_start = 22,
                        offset_end = 22,
                        child = render.Column(
                            children = rows,
                        ),
                    ),
                ],
            ),
        ),
    )
