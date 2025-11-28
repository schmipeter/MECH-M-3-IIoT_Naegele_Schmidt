# Dockerfile für MQTT Collector
FROM python:3.11-slim

WORKDIR /app

# Dependencies installieren
RUN pip install --no-cache-dir \
    paho-mqtt==2.1.0 \
    psycopg2-binary==2.9.9

# App-Code kopieren
COPY app.py .

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import psycopg2; import os; psycopg2.connect(host=os.getenv('POSTGRES_HOST'), port=os.getenv('POSTGRES_PORT'), database=os.getenv('POSTGRES_DB'), user=os.getenv('POSTGRES_USER'), password=os.getenv('POSTGRES_PASSWORD')).close()" || exit 1

# App starten
CMD ["python", "-u", "app.py"]