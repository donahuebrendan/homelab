"""
Argo CD Deployment Watch
Shows application sync/health and vertically scrolls through
deployment readiness across the home k3s cluster.
"""

load("render.star", "render")
load("http.star", "http")

PI_IP = "192.168.4.29"
API_URL = "http://" + PI_IP + ":5000/argocd"

GREEN  = "#00E676"
YELLOW = "#FFD740"
RED    = "#FF5252"
BLUE   = "#40C4FF"
WHITE  = "#FFFFFF"
GRAY   = "#888888"

NAMESPACE_ORDER = [
    "argocd",
    "kube-system",
    "pihole",
    "tronbyt",
]

NAMESPACE_LABELS = {
    "argocd": "ARGO CD",
    "kube-system": "KUBE SYSTEM",
    "pihole": "PI-HOLE",
    "tronbyt": "TRONBYT",
}

# Shorten longer names so rows fit Tidbyt's 64-pixel display.
SHORT_NAMES = {
    "argocd-applicationset-controller": "appset-ctrl",
    "argocd-notifications-controller": "notify-ctrl",
    "argocd-dex-server": "dex-server",
    "argocd-repo-server": "repo-server",
    "argocd-server": "argocd-server",
    "local-path-provisioner": "local-path",
    "metrics-server": "metrics",
    "tronbyt-server": "tronbyt-web",
    "stats-api": "stats-api",
    "coredns": "coredns",
    "traefik": "traefik",
    "pihole": "pihole",
    "argocd-redis": "redis",
}

def error_screen(message):
    return render.Root(
        child = render.Padding(
            pad = 2,
            child = render.Column(
                children = [
                    render.Text("ARGO CD", color = GREEN, font = "tom-thumb"),
                    render.Text(message, color = RED, font = "tom-thumb"),
                ],
            ),
        ),
    )

def deployment_row(deployment):
    name = deployment["name"]
    short_name = SHORT_NAMES.get(name, name)
    ready = deployment["ready"]
    desired = deployment["desired"]
    status = deployment["status"]

    if status == "healthy":
        color = GREEN
        marker = "OK"
    elif status == "progressing":
        color = YELLOW
        marker = "WAIT"
    else:
        color = RED
        marker = "DOWN"

    return render.Row(
        children = [
            render.Text(
                short_name + " ",
                color = WHITE,
                font = "tom-thumb",
            ),
            render.Text(
                str(int(ready)) + "/" + str(int(desired)) + " ",
                color = color,
                font = "tom-thumb",
            ),
            render.Text(
                marker,
                color = color,
                font = "tom-thumb",
            ),
        ],
    )

def main():
    rep = http.get(API_URL, ttl_seconds = 60)

    if rep.status_code != 200:
        return error_screen("HTTP " + str(rep.status_code))

    data = rep.json()

    if "error" in data:
        return error_screen("API ERROR")

    sync = data.get("sync", "Unknown")
    health = data.get("health", "Unknown")
    deployments = data.get("deployments", [])

    if len(deployments) == 0:
        return error_screen("NO DEPLOYMENTS")

    ready_count = 0
    for deployment in deployments:
        if deployment["status"] == "healthy":
            ready_count += 1

    total_count = len(deployments)

    sync_color = GREEN if sync == "Synced" else YELLOW
    health_color = GREEN if health == "Healthy" else RED

    rows = []

    for namespace in NAMESPACE_ORDER:
        namespace_deployments = []
        for deployment in deployments:
            if deployment["namespace"] == namespace:
                namespace_deployments.append(deployment)

        if len(namespace_deployments) == 0:
            continue

        # Namespace heading
        rows.append(
            render.Text(
                "-- " + NAMESPACE_LABELS.get(namespace, namespace) + " --",
                color = BLUE,
                font = "tom-thumb",
            )
        )

        for deployment in namespace_deployments:
            rows.append(deployment_row(deployment))

        # Small gap between namespace groups
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
                    render.Row(
                        children = [
                            render.Text(
                                "  ARGO CD ",
                                color = GREEN,
                                font = "tom-thumb",
                            ),
                            render.Text(
                                str(ready_count) + "/" + str(total_count),
                                color = GREEN if ready_count == total_count else YELLOW,
                                font = "tom-thumb",
                            ),
                        ],
                    ),

                    render.Row(
                        children = [
                            render.Text(sync.upper(), color = sync_color, font = "tom-thumb"),
                            render.Text("  ", color=WHITE, font="tom-thumb"),
                            render.Text(health.upper(), color = health_color, font = "tom-thumb"),
                        ],
                    ),

                    render.Box(
                        width = 62,
                        height = 1,
                        color = "#1A3520",
                    ),

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
