"""
Pi-hole Top Domains
Shows the top 3 DNS domains queried through Pi-hole.
"""

load("render.star", "render")
load("http.star", "http")

PI_IP   = "192.168.4.29"
API_URL = "http://" + PI_IP + ":5000/pihole"

HEADER_COLOR = "#AA80FF"
DOMAIN_COLOR = "#EDF0D6"
COUNT_COLOR  = "#00E676"
RANK_COLOR   = "#7788AA"
DIVIDER_COLOR = "#1E2540"

def err(msg):
    return render.Root(
        child = render.Padding(
            pad = 2,
            child = render.Column(
                children = [
                    render.Text("PI-HOLE", color = "#FF5252", font = "tom-thumb"),
                    render.Text(msg, color = "#888888", font = "tom-thumb"),
                ],
            ),
        ),
    )

def domain_row(rank, domain, count):
    return render.Row(
        children = [
            render.Text(str(rank), color = RANK_COLOR, font = "tom-thumb"),
            render.Text(" ", color = "#000000", font = "tom-thumb"),
            render.Text(domain, color = DOMAIN_COLOR, font = "tom-thumb"),
            render.Text(" ", color = "#000000", font = "tom-thumb"),
            render.Text(str(count), color = COUNT_COLOR, font = "tom-thumb"),
        ],
    )

def main():
    rep = http.get(API_URL, ttl_seconds = 10)

    if rep.status_code != 200:
        return err("HTTP " + str(rep.status_code))

    d = rep.json()
    domains = d["top_domains"]

    if len(domains) == 0:
        return err("NO DNS DATA")

    children = [
        render.Row(
            children = [
                render.Text("PI-HOLE", color = HEADER_COLOR, font = "tom-thumb"),
                render.Text(" TOP DNS", color = "#445566", font = "tom-thumb"),
            ],
        ),
        render.Box(width = 62, height = 1, color = DIVIDER_COLOR),
        render.Box(width = 1, height = 1, color = "#000000"),
    ]

    max_domains = 3

    if len(domains) < max_domains:
        max_domains = len(domains)

    for i in range(max_domains):
        item = domains[i]

        # API already provides the simplified domain.
        domain = item["domain"]

        children.append(
            domain_row(
                i + 1,
                domain,
                item["count"],
            )
        )

        if i < max_domains - 1:
            children.append(
                render.Box(width = 1, height = 2, color = "#000000")
            )

    return render.Root(
        child = render.Padding(
            pad = 1,
            child = render.Column(
                children = children,
            ),
        ),
    )
