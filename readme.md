# Raspberry Pi Pico W IoT Sensor – Dokumentation

## 1. Projektstruktur

- **`code.py`**  
  Enthält die vollständige Implementierung des Webservers und des MQTT-Clients für den Raspberry Pi Pico W.
  - HTTP-API (`GET /config`, `POST /config`, `GET /status`) gemäß OpenAPI/AsyncAPI-Spezifikation
  - MQTT-Kommunikation für Sensordaten (Temperatur, Luftfeuchtigkeit) und Statusmeldungen

- **`boot.py`**  
Setzt den den Pico auf write Acces so das der Http endpunkt die Config ändern kann.
Achtung wenn boot.py aktiv kann der Pico nicht mehr vom PC beschrieben werden.

- **`settings.toml`**  
  Enthält alle konfigurierbaren Parameter des Geräts:
  - Sensor-Pin
  - Messintervall (`reading_interval_seconds`)
  - MQTT-Broker, Port, Benutzer
  - Device-ID, Standort, Gerätename  
  Passwörter und WLAN-SSID sind **nicht enthalten** und müssen manuell ergänzt werden.
  Das settingsforGit.toml muss in settings.toml unbennant werde.

- **`conventions.md` & `asyncapi.yaml`**  
  Definieren die Konventionen für REST-API und MQTT (liegen in ./docs):
  - MQTT-Topics und Payload-Formate
  - REST-Endpunkte, Ports und Response-Strukturen
  - Zeitstempel-Formate 
  - Statuswerte und erlaubte Einheiten

---

## 2. REST-API

- Standard-Port: `80`
- Basis-URL: `http://192.168.178.192/`
- Endpunkte:
  - **`GET /config`** – liefert aktuelle Gerätekonfiguration zurück
  - **`POST /config`** – aktualisiert die Gerätekonfiguration (JSON-Body erforderlich)
  - **`GET /status`** – liefert aktuellen Gerätestatus inkl. Sensorwerte und MQTT/WiFi-Status


### Anleitung zur Nutzung des Docker-Setups zur API-Überprüfung

Mit dem bereitgestellten `docker-compose.yml` können Sie Ihre HTTP-API automatisch mit Dredd gegen die OpenAPI-Spezifikation testen. Zusätzlich stehen Swagger UI und Swagger Editor für manuelle Tests und zur Validierung der API zur Verfügung.

---

### Container starten
In das Projektverzeichniss des Dockerfiles wechseln.
```bash
cd ./docs/API_Tests
```
Das Docker Image bauen:
```bash
docker-compose up -d
```

 Nach dem Start stehen folgende Tools bereit:
 Swagger Editor : OpenAPI bearbeiten und validieren: http://localhost:8082  


Zum Testen muss das openapi.yml file importiert werden dann können die Endpukte getestet werden.

## 3. MQTT-Kommunikation

- Haupt-Topics:
  - `iiot/group/Schmidt-Naegele/sensor/temperatur` → Temperatur-Messages
  - `iiot/group/Schmidt-Naegele/sensor/humidity` → Luftfeuchtigkeits-Messages
  - `iiot/group/Schmidt-Naegele/sensor/status` → Status-Messages

- Payloads:
  - JSON-Format
  - Telemetrie: Zeitstempel **ISO8601 UTC**, Einheiten als String, Statuswerte `ok`, `error`, `offline`
  - Status: Unix-Timestamp, Statuswerte `online`, `offline`

- **Test**:  
  Mit **MQTT Explorer** überprüft, dass Daten korrekt publiziert und empfangen werden.

- Verbindung:
  - Port: 1883
  - Username/Password: müssen manuell gesetzt werden
  - SSL/TLS: false
  - Client-ID: konfigurierbar
  - MQTT-Version: 5.0

---

## 4. Hinweise zum Betrieb

- Das Gerät startet automatisch mit der Konfiguration aus `settings.toml`.
- WLAN-SSID und Passwörter müssen manuell gesetzt werden.
- Nach Änderungen an der Konfiguration per `POST /config` oder direkt in `settings.toml` erfolgt ein automatischer Neustart des Pico.
- Sensordaten werden regelmäßig gemessen und über MQTT publiziert.

## Netzwerk-Integration und IT-Hinweise

Damit die Raspberry Pi Pico W Geräte zuverlässig ihre Sensordaten an den zentralen MQTT-Broker senden können, muss die örtliche IT-Abteilung sicherstellen, dass das WLAN und die Firewall korrekt konfiguriert sind. Insbesondere sollten folgende Punkte beachtet werden:

- **Firewall-Whitelist:** Der MQTT-Broker-Port (Standard: 1883) und die IP-Adresse des Brokers müssen auf der Firewall freigegeben sein. Andernfalls können die Geräte keine Telemetriedaten senden.  
- **WLAN-Zugang:** Die Geräte benötigen ein stabiles WLAN mit ausreichender Signalstärke. Die WLAN-SSID und das Passwort müssen in `settings.toml` korrekt hinterlegt werden.  
- **DNS-Auflösung:** Falls der Broker über einen Hostnamen angesprochen wird, muss die lokale DNS-Auflösung funktionieren.  

Für die **ferngesteuerte Nutzung der HTTP-API** (`GET /config`, `POST /config`, `GET /status`) kann das Gerät über Port-Forwarding, VPN oder einen Reverse-Proxy zugänglich gemacht werden. Dabei bestehen jedoch folgende Risiken und Hindernisse:

- **Sicherheitsrisiken:** Unverschlüsselte HTTP-Zugriffe können abgefangen oder manipuliert werden. Passwörter und Konfigurationsdaten könnten kompromittiert werden.  
- **Firewall- und NAT-Hindernisse:** Externe Zugriffe müssen durch die Firewall erlaubt und korrekt weitergeleitet werden, was administrative Anpassungen erfordert.  
- **Zugriffskontrolle:** Ohne Authentifizierung könnten unautorisierte Benutzer die API aufrufen oder die Geräte neu konfigurieren.  

Empfohlen wird daher, den externen Zugriff nur über **sichere Kanäle (VPN, HTTPS-Proxy)** und mit **authentifizierten Benutzern** zu ermöglichen, um die Integrität der Daten und die Sicherheit der Geräte zu gewährleisten.

# 5. Anleitung zur Nutzung der Cloud Integration

## Passwort und für MQTT in Docker Image setzen
Im Docker-Compose File MQTT Passwort setzen.

## Das Docker Image Bauen
In das Projektverzeichniss des Dockerfiles wechseln.

```bash
cd ./src/Cloud
```

Das Docker Image bauen:

```bash
docker compose up -d --build
```

## Grafana mit Postgrass Datenbank Verbinden

1. **Öffnen:** http://localhost:4000
2. **Login:** admin / admin123
3. **Data Source hinzufügen:**
   - Configuration → Data Sources → Add data source
   - PostgreSQL wählen
   - **Wichtig:** Als UID eingeben: `sensor_db`
   - Host: `postgres:5432`
   - Database: `sensors_db`
   - User: `admin`
   - Password: `admin123`
   - SSL Mode: `disable`
   - Save & Test
## Importieren des Dashboards

   - Dashboards → New → Import
   - JSON aus Artifact `grafana-dashboard-json` kopieren
   - Import klicken
   

