FROM python:3.11-slim

# Install system deps for Adafruit DHT22 and GPIO
RUN apt-get update && apt-get install -y \
    gcc \
    libgpiod-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN mkdir -p /app/data

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY stats_api.py .
COPY build_aircraft_db.py .

EXPOSE 5000
CMD ["python3", "stats_api.py"]
