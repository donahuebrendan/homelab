#!/usr/bin/env python3

import csv
import os
import sqlite3
import urllib.request

DB_PATH = "/persistent/aircraft/aircraft.db"
CSV_URL = "https://opensky-network.org/datasets/metadata/aircraftDatabase.csv"


def main():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    # Build a temporary database first so a failed download never leaves
    # a partially built database at the final path.
    temp_path = DB_PATH + ".tmp"
    if os.path.exists(temp_path):
        os.remove(temp_path)

    conn = None
    try:
        print("Downloading aircraft database...", flush=True)
        request = urllib.request.Request(
            CSV_URL,
            headers={"User-Agent": "tronbyt-pi/1.0"},
        )

        with urllib.request.urlopen(request, timeout=120) as response:
            import io
            stream = io.TextIOWrapper(
                response, encoding="utf-8-sig", errors="replace", newline=""
            )
            reader = csv.DictReader(stream)
            if not reader.fieldnames:
                raise RuntimeError("Aircraft CSV has no header")

            # Normalize column names, including any surrounding whitespace.
            reader.fieldnames = [
                name.strip().strip('"').lower()
                for name in reader.fieldnames
            ]

            required = {"icao24", "manufacturername", "model"}
            if not required.issubset(set(reader.fieldnames)):
                raise RuntimeError(
                    f"Unexpected CSV columns: {reader.fieldnames}"
                )

            conn = sqlite3.connect(temp_path)
            conn.execute("""
                CREATE TABLE aircraft (
                    icao24 TEXT PRIMARY KEY,
                    manufacturer TEXT,
                    model TEXT
                )
            """)
            conn.execute(
                "CREATE INDEX idx_icao24 ON aircraft(icao24)"
            )

            batch = []
            total = 0

            # Process one CSV row at a time; never load the whole CSV in RAM.
            for row in reader:
                icao = (row.get("icao24") or "").strip().lower()
                if not icao:
                    continue

                manufacturer = (row.get("manufacturername") or "").strip()
                model = (row.get("model") or "").strip()
                batch.append((icao, manufacturer, model))

                if len(batch) >= 1000:
                    conn.executemany(
                        "INSERT OR REPLACE INTO aircraft VALUES (?, ?, ?)",
                        batch,
                    )
                    total += len(batch)
                    batch.clear()

            if batch:
                conn.executemany(
                    "INSERT OR REPLACE INTO aircraft VALUES (?, ?, ?)",
                    batch,
                )
                total += len(batch)

        if total == 0:
            raise RuntimeError("No aircraft records were imported")

        conn.commit()
        conn.close()
        conn = None

        # Atomic replacement: the final DB appears only after a successful build.
        os.replace(temp_path, DB_PATH)
        print(f"Aircraft database ready: {total:,} records", flush=True)

    except Exception:
        if conn is not None:
            conn.close()
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise


if __name__ == "__main__":
    main()
