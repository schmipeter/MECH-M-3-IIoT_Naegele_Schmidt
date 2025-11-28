# app.py - MQTT Collector für Sensor-Daten mit PostgreSQL
import paho.mqtt.client as mqtt
import psycopg2
import json
from datetime import datetime
import os
import time
import sys

# PostgreSQL-Verbindungsparameter
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
POSTGRES_DB = os.getenv("POSTGRES_DB", "sensors_db")
POSTGRES_USER = os.getenv("POSTGRES_USER", "admin")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "admin123")

# MQTT-Parameter
MQTT_HOST = os.getenv("MQTT_HOST", "158.180.44.197")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "bobm")
MQTT_PASS = os.getenv("MQTT_PASS", "letmein")

print("="*60)
print("MQTT to PostgreSQL Collector")
print("="*60)
print(f"MQTT Broker: {MQTT_HOST}:{MQTT_PORT}")
print(f"PostgreSQL: {POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}")
print("="*60)

# PostgreSQL-Verbindung
print("\n[1/3] Verbinde zu PostgreSQL...")
max_retries = 30
retry_count = 0

while retry_count < max_retries:
    try:
        conn = psycopg2.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            database=POSTGRES_DB,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD
        )
        print("PostgreSQL verbunden!")
        break
    except psycopg2.OperationalError as e:
        retry_count += 1
        print(f"Versuch {retry_count}/{max_retries} - PostgreSQL noch nicht bereit...")
        time.sleep(2)

if retry_count >= max_retries:
    print("PostgreSQL-Verbindung fehlgeschlagen!")
    sys.exit(1)

cursor = conn.cursor()

# Tabellen erstellen (optimiert für Zeitreihen)
print("\n[2/3] Erstelle Datenbank-Schema...")

cursor.execute("""
CREATE TABLE IF NOT EXISTS temperature (
    id SERIAL PRIMARY KEY,
    device_id TEXT NOT NULL,
    value REAL NOT NULL,
    unit TEXT DEFAULT '°C',
    timestamp TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS humidity (
    id SERIAL PRIMARY KEY,
    device_id TEXT NOT NULL,
    value REAL NOT NULL,
    unit TEXT DEFAULT '%',
    timestamp TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS sensor_status (
    device_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    last_seen TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
""")

# Indizes für bessere Performance
cursor.execute("""
CREATE INDEX IF NOT EXISTS idx_temperature_device_time 
ON temperature(device_id, timestamp DESC);
""")

cursor.execute("""
CREATE INDEX IF NOT EXISTS idx_humidity_device_time 
ON humidity(device_id, timestamp DESC);
""")

conn.commit()
print("Datenbank-Schema bereit!")

# Status-Tracking
sensor_status = {}
message_count = 0

# MQTT Callbacks
def on_connect(client, userdata, flags, reason_code, properties):
    """Wird aufgerufen wenn MQTT-Verbindung hergestellt ist"""
    print(f"\n[3/3] MQTT Verbindung: {mqtt.connack_string(reason_code)}")
    
    if reason_code == 0:
        print("MQTT verbunden!")
        # Auf alle Topics unter iiot/# subscriben
        client.subscribe("iiot/#", qos=1)
        print("  Subscribed: iiot/#")
        print("\n" + "="*60)
        print("System bereit - Warte auf Nachrichten...")
        print("="*60 + "\n")
    else:
        print(f"MQTT-Verbindungsfehler: {mqtt.connack_string(reason_code)}")

def on_message(client, userdata, msg):
    """Wird aufgerufen wenn MQTT-Nachricht empfangen wird"""
    global message_count
    message_count += 1
    
    try:
        # Payload parsen
        payload = json.loads(msg.payload.decode())
        topic = msg.topic
        
        print(f"\n[{message_count}] Topic: {topic}")
        print(f" Payload: {payload}")
        
        # Device-ID extrahieren
        device_id = payload.get("device_id", "unknown")
        timestamp_str = payload.get("timestamp")
        
        # Timestamp konvertieren
        if timestamp_str:
            # ISO8601 Format parsen
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        else:
            timestamp = datetime.utcnow()
        
        # STATUS-Nachrichten verarbeiten
        if "status" in topic.lower():
            status = payload.get("status", "unknown")
            
            sensor_status[device_id] = {
                "status": status,
                "last_seen": timestamp_str
            }
            
            cursor.execute("""
                INSERT INTO sensor_status (device_id, status, last_seen, updated_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (device_id) 
                DO UPDATE SET 
                    status = EXCLUDED.status,
                    last_seen = EXCLUDED.last_seen,
                    updated_at = NOW();
            """, (device_id, status, timestamp))
            
            conn.commit()
            print(f" Status gespeichert: {device_id} = {status}")
            return
        
        # TEMPERATUR-Daten verarbeiten
        if "temperature" in topic.lower():
            value = float(payload.get("value", 0))
            unit = payload.get("unit", "°C")
            
            cursor.execute("""
                INSERT INTO temperature (device_id, value, unit, timestamp)
                VALUES (%s, %s, %s, %s);
            """, (device_id, value, unit, timestamp))
            
            conn.commit()
            print(f"Temperatur gespeichert: {device_id} = {value}{unit}")
        
        # LUFTFEUCHTIGKEIT-Daten verarbeiten
        elif "humidity" in topic.lower():
            value = float(payload.get("value", 0))
            unit = payload.get("unit", "%")
            
            cursor.execute("""
                INSERT INTO humidity (device_id, value, unit, timestamp)
                VALUES (%s, %s, %s, %s);
            """, (device_id, value, unit, timestamp))
            
            conn.commit()
            print(f" Luftfeuchtigkeit gespeichert: {device_id} = {value}{unit}")
        
        else:
            print(f" Unbekannter Topic-Typ: {topic}")
    
    except json.JSONDecodeError as e:
        print(f" JSON-Fehler: {e}")
    except Exception as e:
        print(f"  Verarbeitungsfehler: {e}")
        # Rollback bei Fehler
        conn.rollback()

def on_disconnect(client, userdata, flags, reason_code, properties):
    """Wird aufgerufen wenn MQTT-Verbindung getrennt wird"""
    print(f"\nMQTT getrennt: {mqtt.connack_string(reason_code)}")
    if reason_code != 0:
        print("  Versuche Wiederverbindung...")

def on_subscribe(client, userdata, mid, reason_code_list, properties):
    """Wird aufgerufen wenn Subscribe erfolgreich war"""
    print(f"  Subscribe bestätigt (mid={mid})")

# MQTT Client erstellen und konfigurieren
print("\n[3/3] Starte MQTT Client...")

client = mqtt.Client(
    client_id="mqtt_collector_pico",
    protocol=mqtt.MQTTv311,  # MQTTv311 statt v31 (stabiler)
    callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
    clean_session=True
)

# Callbacks registrieren
client.on_connect = on_connect
client.on_message = on_message
client.on_disconnect = on_disconnect
client.on_subscribe = on_subscribe

# Authentifizierung
client.username_pw_set(MQTT_USER, MQTT_PASS)

# Keepalive und Reconnect-Einstellungen
client.reconnect_delay_set(min_delay=1, max_delay=120)

try:
    # Verbindung herstellen
    print(f"Verbinde zu {MQTT_HOST}:{MQTT_PORT}...")
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    
    # Event-Loop starten (blockierend)
    client.loop_forever(retry_first_connection=True)

except KeyboardInterrupt:
    print("\n\n Programm durch Benutzer beendet")
    client.disconnect()
    cursor.close()
    conn.close()
    print(" Verbindungen geschlossen")
    sys.exit(0)

except Exception as e:
    print(f"\n Fataler Fehler: {e}")
    sys.exit(1)