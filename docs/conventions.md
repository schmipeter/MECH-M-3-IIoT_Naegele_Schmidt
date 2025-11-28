# MQTT & Daten-Konventionen

## Server
- Name: `mqttBroker`
- URL: `mqtt://158.180.44.197:1883`
- Protokoll: `mqtt`
- Beschreibung: Zentraler MQTT-Broker für die Gerätekommunikation

## Topics
- Temperatur:
  - Struktur: `iiot/group/Schmidt-Naegele/sensor/temperatur`
  - Publish: `TemperatureMessage`
- Luftfeuchtigkeit:
  - Struktur: `iiot/group/Schmidt-Naegele/sensor/humidity`
  - Publish: `HumidityMessage`
- Status:
  - Struktur: `iiot/group/Schmidt-Naegele/sensor/status`
  - Publish: `StatusMessage`
- Nur Kleinbuchstaben und `/` als Trenner
- Beispiele:
  - Temperatur: `iiot/group/Schmidt-Naegele/sensor/temperatur`
  - Luftfeuchtigkeit: `iiot/group/Schmidt-Naegele/sensor/humidity`
  - Status: `iiot/group/Schmidt-Naegele/sensor/status`

## Payloads
- Standardformat: **JSON**
- Temperatur / Luftfeuchtigkeit:
  - Zeitstempel: ISO8601 UTC (`2025-08-28T10:00:00Z`)
  - Einheit als String (z. B. `"°C"`, `"%"`)
  - Statuswerte: `ok`, `error`, `offline`
  - Beispiel Temperatur:
    ```json
    {
      "device_id": "device-001",
      "timestamp": "2025-08-28T10:00:00Z",
      "value": 22.5,
      "unit": "°C",
      "status": "ok"
    }
    ```
- Status:
  - Zeitstempel: Unix-Timestamp (`1698489600`)
  - Statuswerte: `online`, `offline`
  - Beispiel Status:
    ```json
    {
      "device_id": "device-001",
      "status": "online",
      "timestamp": 1698489600
    }
    ```

## Endpunkt
- Port: **1883**
- Username: `bobm`
- Password: In Vorlesung erfragen
- SSL/TLS: **False**
- Client-ID: `pico_w_client`
- MQTT-Version: **5.0**

# REST-API Konventionen

- Endpunkte sind **unverschlüsselt (HTTP)** erreichbar.
- Standard-Port: `80`
- Basis-URL: `http://<192.168.178.192>/`

## Endpunkte

### `/config`

## Endpunkte

### `/config`

#### GET – Konfiguration abrufen
- Beschreibung: Gibt die aktuelle Gerätekonfiguration zurück
- Request-Body: **nicht erforderlich**
- Response 200 OK:
```json
{
  "device_id": "sensor-01",
  "names": "Raum 1 Sensor",
  "location": "Innsbruck",
  "mqtt_broker": "broker.local",
  "mqtt_port": 1883,
  "mqtt_user": "bobm",
  "reading_interval_seconds": 60,
  "sensor_pin": 15
}
```
- Response 500 Internal Server Error:
```json
{
  "error": "Internal Server Error",
  "status_code": 500
}
```

POST – Konfiguration aktualisieren

- Beschreibung: Aktualisiert die Gerätekonfiguration

- Request-Body: JSON, alle Felder optional, keine zusätzlichen Keys erlaubt
```json
{
  "device_id": "sensor-01",
  "names": "Raum 1 Sensor",
  "location": "Innsbruck",
  "mqtt_broker": "broker.local",
  "mqtt_port": 1883,
  "mqtt_user": "bobm",
  "mqtt_password": "geheim",
  "reading_interval_seconds": 60,
  "sensor_pin": 15
}
```
- Response 200 OK:
```json
{
  "message": "Configuration updated successfully. Device will reboot in 3 seconds.",
  "updated_fields": ["location", "mqtt_broker"],
  "reboot": true
}
```
- Response 400 Bad Request:
```json
{
  "error": "Empty request body",
  "status_code": 400
}
```

- Response 404 Not Found:
```json
{
  "error": "Not Found",
  "status_code": 404
}
```
- Response 500 Internal Server Error:
```json
{
  "error": "Internal Server Error",
  "status_code": 500
}
```

### `/status`
#### GET – Gerätestatus abrufen

- Beschreibung: Gibt den aktuellen Status des Geräts zurück, inkl. Sensorwerte und MQTT/WiFi-Status
- Request-Body: nicht erforderlich
- Response 200 OK:
```json
{
  "device_id": "sensor-01",
  "wifi_connected": true,
  "wifi_ssid": "MyWiFi",
  "ip_address": "192.168.178.192",
  "mqtt_connected": true,
  "mqtt_broker": "broker.local",
  "uptime_seconds": 3600,
  "last_temperature": 22.5,
  "last_humidity": 55.2,
  "last_reading_timestamp": "2025-08-28T10:00:00Z",
  "firmware_version": "1.0.0"
}
```
- Response 500 Internal Server Error:
```json
{
  "error": "Internal Server Error",
  "status_code": 500
}
```