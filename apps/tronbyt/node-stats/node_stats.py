import os
import socket
import time
from datetime import datetime, timezone

import psutil
from flask import Flask, jsonify

app = Flask(__name__)

HOST_ROOT = "/host-root"
HOST_SYS = "/host-sys"
TEMP_PATH = f"{HOST_SYS}/class/thermal/thermal_zone0/temp"
TEMP_MAX_C = 85.0


def get_temperature():
    try:
        with open(TEMP_PATH, "r") as f:
            return round(int(f.read().strip()) / 1000.0, 1)
    except (OSError, ValueError):
        return None


def collect_metrics():
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage(HOST_ROOT)
    temperature = get_temperature()

    return {
        "hostname": "rp5-master",
        "cpu_pct": round(psutil.cpu_percent(interval=0.2), 1),
        "ram_pct": round(memory.percent, 1),
        "ram_used_mb": round(memory.used / (1024 ** 2)),
        "ram_total_mb": round(memory.total / (1024 ** 2)),
        "temp_c": temperature,
        "temp_pct": (
            round(temperature / TEMP_MAX_C * 100, 1)
            if temperature is not None else None
        ),
        "disk_pct": round(disk.percent, 1),
        "disk_used_gb": round(disk.used / (1024 ** 3), 1),
        "disk_total_gb": round(disk.total / (1024 ** 3), 1),
        "online": True,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }


@app.route("/health")
def health():
    return jsonify({"status": "healthy", "hostname": socket.gethostname()})


@app.route("/metrics")
def metrics():
    try:
        return jsonify(collect_metrics())
    except Exception as exc:
        app.logger.exception("Failed to collect host metrics")
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
