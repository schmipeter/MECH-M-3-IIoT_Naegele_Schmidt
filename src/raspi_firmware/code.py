# code.py

# ===================================================================
# Haupt-Anwendung für das yourmuesli.at IoT Environmental Monitoring
#
# Autor: Peter Schmidt, Simon Nägele
# Datum: 02.09.2025
#
# Hardware: Raspberry Pi Pico W
# Sensor: DHT22 (Temperatur & Luftfeuchtigkeit)
# Software: CircuitPython
# ===================================================================

# ----------- Bibliotheken importieren -----------
# Hier werden später alle benötigten CircuitPython-Bibliotheken importiert
# z.B. import board, time, wifi, adafruit_dht, etc.
import time
import board
import wifi
import socketpool
import adafruit_dht
import digitalio
import supervisor
import json
import os
import microcontroller
import adafruit_minimqtt.adafruit_minimqtt as MQTT
import socketpool
import adafruit_ntp
import rtc





# ===================================================================
# KLASSE: ConfigManager
# ===================================================================
class ConfigManager:
    """
    Verwaltet das Laden und Speichern der Konfiguration aus der 'settings.toml'.
    """

    def __init__(self, filepath: str):
        """
        Initialisiert den ConfigManager.

        :param filepath: Der Pfad zur Konfigurationsdatei (z.B. "settings.toml").
        """
        self.filepath = filepath
        self.settings = {}

    def load_settings(self) -> dict:
        """
        Lädt die Einstellungen aus der TOML-Datei.

        :return: Ein Dictionary mit allen geladenen Einstellungen.
        """
        try:
            # CircuitPython settings.toml wird automatisch als os.getenv gelesen
            self.settings = {
                'device_id': os.getenv('device_id', 'Sensor-TempHumid1'),
                'names': os.getenv('names'),
                'location': os.getenv('location'),
                'CIRCUITPY_WIFI_SSID': os.getenv('CIRCUITPY_WIFI_SSID'),
                'CIRCUITPY_WIFI_PASSWORD': os.getenv('CIRCUITPY_WIFI_PASSWORD'),
                'MQTT_BROKER': os.getenv('MQTT_BROKER'),
                'MQTT_PORT': int(os.getenv('MQTT_PORT', '1883')),
                'MQTT_USER': os.getenv('MQTT_USER'),
                'MQTT_PASSWORD': os.getenv('MQTT_PASSWORD'),
                'MQTT_CLIENT_ID': os.getenv('MQTT_CLIENT_ID', 'pico_w_client'),
                'telemetry_topic_temperature': os.getenv('telemetry_topic_temperature'),
                'telemetry_topic_humidity': os.getenv('telemetry_topic_humidity'),
                'status_topic': os.getenv('status_topic'),
                'reading_interval_seconds': int(os.getenv('reading_interval_seconds', '60')),
                'sensor_pin': int(os.getenv('sensor_pin', '15'))
            }
            print(f"Konfiguration geladen: {self.settings['device_id']}")
            return self.settings
        except Exception as e:
            print(f"Fehler beim Laden der Konfiguration: {e}")
            return {}

    def save_settings(self, settings: dict):
        """
        Speichert Änderungen zurück in die TOML-Datei und startet den
        Mikrocontroller neu, um die neuen Einstellungen zu übernehmen.

        :param settings: Das Dictionary mit den zu speichernden Einstellungen.
        """
        try:
            # TOML-Datei schreiben
            with open(self.filepath, 'w') as f:
                f.write("# settings.toml - Automatisch gespeichert\n\n")
                for key, value in settings.items():
                    if isinstance(value, str):
                        f.write(f'{key} = "{value}"\n')
                    else:
                        f.write(f'{key} = {value}\n')
            
            print("Konfiguration gespeichert. Neustart in 3 Sekunden...")
            time.sleep(3)
            microcontroller.reset()
        except Exception as e:
            print(f"Fehler beim Speichern der Konfiguration: {e}")


# ===================================================================
# KLASSE: NetworkManager
# ===================================================================
class NetworkManager:
    """
    Kümmert sich um die Verbindung zum WLAN-Netzwerk.
    """

    def __init__(self, ssid: str, password: str):
        """
        Initialisiert den NetworkManager mit den WLAN-Zugangsdaten.

        :param ssid: Der Name des WLAN-Netzwerks (SSID).
        :param password: Das Passwort für das WLAN-Netzwerk.
        """
        self.ssid = ssid
        self.password = password
        self.max_retries = 5
        self.retry_delay = 5

    def connect(self) -> bool:
        """
        Stellt die Verbindung zum WLAN her. Versucht es bei einem Fehler
        mehrfach, bevor aufgegeben wird.

        :return: True bei erfolgreicher Verbindung, ansonsten False.
        """
        print(f"Verbinde mit WLAN: {self.ssid}")
        
        for attempt in range(self.max_retries):
            try:
                wifi.radio.connect(self.ssid, self.password)
                print(f"WLAN verbunden! IP: {self.get_ip()}")
                return True
            except Exception as e:
                print(f"Versuch {attempt + 1}/{self.max_retries} fehlgeschlagen: {e}")
                if attempt < self.max_retries - 1:
                    print(f"  Warte {self.retry_delay}s vor erneutem Versuch...")
                    time.sleep(self.retry_delay)
        
        print("WLAN-Verbindung nach allen Versuchen fehlgeschlagen!")
        return False

    def is_connected(self) -> bool:
        """
        Prüft den aktuellen Verbindungsstatus.

        :return: True, wenn eine WLAN-Verbindung besteht, ansonsten False.
        """
        return wifi.radio.connected

    def get_ip(self) -> str:
        """
        Gibt die aktuell zugewiesene IP-Adresse des Geräts zurück.

        :return: Die IP-Adresse als String (z.B. "192.168.1.100").
        """
        if wifi.radio.connected:
            return str(wifi.radio.ipv4_address)
        return "Nicht verbunden"
    
    def set_ntp_time(self, timezone_offset=0):
        """
        Synchronisiert die Systemzeit mit einem NTP-Server.

        :param timezone_offset: Offset in Stunden zur UTC-Zeit.
        """
        try:
            ntp = adafruit_ntp.NTP(
                socketpool.SocketPool(wifi.radio),
                server="pool.ntp.org",
                tz_offset=timezone_offset
            )
            current_time = ntp.datetime
            clock = rtc.RTC()
            clock.datetime = current_time
            #print aktuelle zeit
            print(f"Aktuelle NTP-Zeit: {current_time}")
            print("Systemzeit mit NTP synchronisiert. " )
        except Exception as e:
            print(f"Fehler bei NTP-Synchronisation: {e}")


# ===================================================================
# KLASSE: Sensor
# ===================================================================
class Sensor:
    """
    Kapselt die Logik zum Auslesen des DHT22-Sensors.
    """

    def __init__(self, pin_number: int):
        """
        Initialisiert den Sensor am angegebenen GPIO-Pin.

        :param pin_number: Die Nummer des GPIO-Pins (z.B. 15 für GP15).
        """
        try:
            # Dynamisch den Pin aus board-Modul holen
            pin_name = f"GP{pin_number}"
            self.pin = getattr(board, pin_name)
            print(self.pin)
            print(f"Pin {pin_name} gefunden")
        except AttributeError:
            print(f"Pin GP{pin_number} existiert nicht, verwende GP22 als Fallback")
            self.pin = board.GP22
        
        try:
            self.dht = adafruit_dht.DHT11(self.pin)
            print(f"DHT11-Sensor initialisiert an GP{pin_number}")
        except Exception as e:
            print(f"Fehler bei Sensor-Initialisierung: {e}")
            self.dht = None


    def read_data(self) -> dict | None:
        """
        Liest Temperatur und Luftfeuchtigkeit vom Sensor.

        :return: Ein Dictionary wie {'temperature': 22.5, 'humidity': 45.8}
                 oder None, falls das Auslesen fehlschlägt.
        """
        if self.dht is None:
            return None
        
        try:
            temperature = self.dht.temperature
            humidity = self.dht.humidity
            
            if temperature is not None and humidity is not None:
                return {
                    'temperature': float(temperature),
                    'humidity': float(humidity)
                }
            else:
                print("Sensor lieferte None-Werte")
                return None
                
        except RuntimeError as e:
            # Bei DHT normal – Timing/Checksumme nicht gepasst
            print(f"Sensor-Warnung: {e}")
            return None
        except Exception as e:
            print(f"Sensor-Fehler: {e}")
            return None


# ===================================================================
# KLASSE: MqttClient
# ===================================================================
class MqttClient:
    """
    Verwaltet die Kommunikation mit dem zentralen MQTT-Broker.
    """

    def __init__(self, config: dict):
        """
        Initialisiert den MQTT-Client mit den Broker-Details aus der Konfiguration.

        :param config: Ein Dictionary mit den MQTT-Einstellungen.
        """
        self.config = config
        self.pool = socketpool.SocketPool(wifi.radio)
        
        # MQTT-Client erstellen
        self.mqtt = MQTT.MQTT(
            broker=config['MQTT_BROKER'],
            port=config['MQTT_PORT'],
            username=config['MQTT_USER'],
            password=config['MQTT_PASSWORD'],
            client_id=config['MQTT_CLIENT_ID'],
            socket_pool=self.pool,
            keep_alive=60,
            is_ssl=False
        )
        iso_time_struct= time.localtime()
        iso_time = (
                    f"{iso_time_struct.tm_year:04d}-{iso_time_struct.tm_mon:02d}-{iso_time_struct.tm_mday:02d}T"
                    f"{iso_time_struct.tm_hour:02d}:{iso_time_struct.tm_min:02d}:{iso_time_struct.tm_sec:02d}Z"
                )
        last_will_topic = config['status_topic']
        last_will_payload ={
            "device_id": config['device_id'],
            "status": "offline",
            "timestamp": iso_time
        }
        self.mqtt.will_set(last_will_topic, json.dumps(last_will_payload), qos=1, retain=True)

        
        
        print(f"MQTT-Client konfiguriert für {config['MQTT_BROKER']}")

    def connect(self):
        """
        Verbindet sich mit dem MQTT-Broker und setzt eine "Last Will and Testament"
        Nachricht, die gesendet wird, falls das Gerät unerwartet die Verbindung verliert.
        """
        try:
            print(f"Verbinde mit MQTT-Broker: {self.config['MQTT_BROKER']}:{self.config['MQTT_PORT']}")
            self.mqtt.connect()
            print("MQTT verbunden!")
            return True
        except Exception as e:
            print(f"MQTT-Verbindung fehlgeschlagen: {e}")
            return False
        
        

    def publish_telemetry(self, data: dict):
        """
        Formatiert die Sensordaten in ein JSON-Payload und sendet sie
        an das definierte Telemetrie-Topic.

        :param data: Das Dictionary mit den Sensordaten.
        """
        try:
            # ISO8601 UTC Timestamp
            
            iso_time_struct= time.localtime()
            iso_time = (
                        f"{iso_time_struct.tm_year:04d}-{iso_time_struct.tm_mon:02d}-{iso_time_struct.tm_mday:02d}T"
                        f"{iso_time_struct.tm_hour:02d}:{iso_time_struct.tm_min:02d}:{iso_time_struct.tm_sec:02d}Z"
                    )
            # Temperatur-Payload
            temp_payload = {
                "device_id": self.config['device_id'],
                "unit": "°C",
                "value": data['temperature'],
                "timestamp": iso_time
            }
            
            # Luftfeuchtigkeit-Payload
            humidity_payload = {
                "device_id": self.config['device_id'],
                "unit": "%",
                "value": data['humidity'],
                "timestamp": iso_time
            }
            
            # Topics
            temp_topic = self.config['telemetry_topic_temperature']
            humidity_topic = self.config['telemetry_topic_humidity']
            
            # Senden
            self.mqtt.publish(temp_topic, json.dumps(temp_payload), qos=1)
            self.mqtt.publish(humidity_topic, json.dumps(humidity_payload), qos=1)
            
            print(f"Telemetrie gesendet: T={data['temperature']:.1f}°C, H={data['humidity']:.1f}%")
            
        except Exception as e:
            print(f"Fehler beim Senden der Telemetrie: {e}")

    def publish_status(self, status: str):
        """
        Sendet eine einfache Statusnachricht (z.B. "online", "rebooting")
        an das definierte Status-Topic.

        :param status: Die zu sendende Statusnachricht.
        """
        iso_time_struct= time.localtime()
        iso_time = (
                    f"{iso_time_struct.tm_year:04d}-{iso_time_struct.tm_mon:02d}-{iso_time_struct.tm_mday:02d}T"
                    f"{iso_time_struct.tm_hour:02d}:{iso_time_struct.tm_min:02d}:{iso_time_struct.tm_sec:02d}Z"
                )
        status_payload = {
            "device_id": self.config['device_id'],
            "status": status,
            "timestamp": iso_time
            }
        try:
            self.mqtt.publish(self.config['status_topic'], json.dumps(status_payload), qos=1, retain=True)
            print(f"Status gesendet: {status}")
        except Exception as e:
            print(f"Fehler beim Senden des Status: {e}")

    def loop(self):
        """
        Hält die MQTT-Verbindung aktiv. Muss regelmäßig in der Hauptschleife
        aufgerufen werden.
        """
        try:
            self.mqtt.loop(timeout=1)
        except Exception as e:
            print(f"MQTT Loop-Fehler: {e}")

# ===================================================================
# KLASSE: WebServer
# ===================================================================

class WebServer:
    """
    HTTP-Server für Raspberry Pi Pico W (CircuitPython).
    Implementiert die standardisierte HTTP-API gemäß OpenAPI-Spezifikation.
    
    Unterstützte Endpunkte:
      - GET /config       - Konfiguration abrufen
      - POST /config      - Konfiguration setzen
      - GET /status       - Gerätestatus abrufen
    """

    def __init__(self, config_manager, mqtt_client=None, sensor=None, network_manager=None, port=80):
        """
        Initialisiert den WebServer.
        
        :param config_manager: ConfigManager-Instanz für Konfigurationszugriff
        :param mqtt_client: MqttClient-Instanz für MQTT-Status
        :param sensor: Sensor-Instanz für Sensordaten
        :param network_manager: NetworkManager-Instanz für Netzwerkstatus
        :param port: Port, auf dem der Server läuft (Standard: 80)
        """
        self.config_manager = config_manager
        self.mqtt_client = mqtt_client
        self.sensor = sensor
        self.network_manager = network_manager
        self.port = port
        self.start_time = time.monotonic()
        self.pool = socketpool.SocketPool(wifi.radio)
        self.server_socket = None
        self.last_sensor_data = None  # Speichert letzte erfolgreiche Messung

    # -------------------------------------------------------------------
    def start(self):
        """Startet den Webserver (non-blocking)."""
        try:
            self.server_socket = self.pool.socket(self.pool.AF_INET, self.pool.SOCK_STREAM)
            self.server_socket.settimeout(0.1)  # Kurzes Timeout für non-blocking
            self.server_socket.setsockopt(self.pool.SOL_SOCKET, self.pool.SO_REUSEADDR, 1)
            self.server_socket.bind(("0.0.0.0", self.port))
            self.server_socket.listen(2)
            print(f"✓ Webserver gestartet auf http://{wifi.radio.ipv4_address}:{self.port}")
            print(f"  Verfügbare Endpunkte:")
            print(f"    - GET  http://{wifi.radio.ipv4_address}:{self.port}/config")
            print(f"    - POST http://{wifi.radio.ipv4_address}:{self.port}/config")
            print(f"    - GET  http://{wifi.radio.ipv4_address}:{self.port}/status")
        except Exception as e:
            print(f"✗ Fehler beim Starten des Webservers: {e}")
            self.server_socket = None

    def poll(self):
        """
        Prüft auf eingehende HTTP-Anfragen (nicht blockierend).
        Sollte regelmäßig in der Hauptschleife aufgerufen werden.
        """
        if not self.server_socket:
            return

        try:
            client, addr = self.server_socket.accept()
        except OSError:
            # Kein Client wartet - normal bei non-blocking
            return

        print(f"\n→ HTTP-Anfrage von {addr[0]}:{addr[1]}")

        try:
            # HTTP-Request empfangen (max 4KB)
            request = b""
            client.settimeout(2.0)

            buf = bytearray(512)

            while len(request) < 4096:
                try:
                    n = client.recv_into(buf)
                    print(f"  Empfange {n} Bytes,")
                    if n == 0:
                        break
                    request += buf[:n]

                    if b"\r\n\r\n" in request:
                        break
                except OSError:
                    break

            if not request:
                client.close()
                return

            request_str = request.decode("utf-8")

            # Request-Line parsen
            lines = request_str.split("\r\n")
            request_line = lines[0]
            parts = request_line.split()

            if len(parts) < 2:
                response = self._http_error(400, "Bad Request")
                client.send(response)
                return

            method, path = parts[0], parts[1]
            print(f"  {method} {path}")

            # Header-Teil extrahieren und Body korrekt lesen
            header_end = request_str.find("\r\n\r\n")
            headers = request_str[:header_end].split("\r\n")[1:]  
            body = request_str[header_end + 4:] if header_end != -1 else ""
            # Content-Length prüfen
            content_length = 0
            for header in headers:
                if header.lower().startswith("content-length:"):
                    content_length = int(header.split(":")[1].strip())
                    break

            # Body vervollständigen, falls noch nicht vollständig gelesen
            while len(body.encode("utf-8")) < content_length:
                body += client.recv(512).decode("utf-8")

            # Request verarbeiten
            if method == "GET":
                response = self._handle_get_request(path)
            elif method == "POST":
                response = self._handle_post_request(path, body)
            else:
                response = self._http_error(405, "Method Not Allowed",
                                            {"Allow": "GET, POST"})

            client.send(response)
            print(f"← {method} {path} - Antwort gesendet")

        except Exception as e:
            print(f"✗ WebServer-Fehler: {e}")
            try:
                response = self._http_error(500, "Internal Server Error")
                client.send(response)
            except:
                pass

        finally:
            try:
                client.close()
            except:
                pass

    # -------------------------------------------------------------------
    def _handle_get_request(self, path):
        """
        Bearbeitet GET-Anfragen gemäß OpenAPI-Spezifikation.
        
        :param path: Request-Pfad
        :return: HTTP-Response als bytes
        """
        print(f"→ GET-Anfrage für {path}")
        if path == "/config":
            return self._get_config()
        elif path == "/status":
            return self._get_status()
        else:
            return self._http_error(404, "Not Found")

    # -------------------------------------------------------------------
    def _handle_post_request(self, path, body):
        """
        Bearbeitet POST-Anfragen gemäß OpenAPI-Spezifikation.
        
        :param path: Request-Pfad
        :param body: Request-Body
        :return: HTTP-Response als bytes
        """
        print(f"→ post-Anfrage für {path}")
        if path == "/config":
            return self._post_config(body)
        else:
            return self._http_error(404, "Not Found")

    # -------------------------------------------------------------------
    def _get_config(self):
        """
        GET /config - Gibt aktuelle Konfiguration zurück.
        
        Response-Format (JSON):
        {
            "device_id": "string",
            "names": "string",
            "location": "string",
            "mqtt_broker": "string",
            "mqtt_port": integer,
            "mqtt_user": "string",
            "reading_interval_seconds": integer,
            "sensor_pin": integer
        }
        """
        print("→ GET /config angefordert")
        try:
            config = {
                "device_id": self.config_manager.settings.get("device_id", ""),
                "names": self.config_manager.settings.get("names", ""),
                "location": self.config_manager.settings.get("location", ""),
                "mqtt_broker": self.config_manager.settings.get("MQTT_BROKER", ""),
                "mqtt_port": self.config_manager.settings.get("MQTT_PORT", 1883),
                "mqtt_user": self.config_manager.settings.get("MQTT_USER", ""),
                "reading_interval_seconds": self.config_manager.settings.get("reading_interval_seconds", 60),
                "sensor_pin": self.config_manager.settings.get("sensor_pin", 15)
            }
            
            return self._http_response(200, json.dumps(config), "application/json")
            
        except Exception as e:
            print(f"✗ Fehler bei GET /config: {e}")
            return self._http_error(500, "Internal Server Error")

    # -------------------------------------------------------------------
    def _post_config(self, body):
        """
        POST /config - Aktualisiert Konfiguration.
        
        Request-Format (JSON):
        {
            "device_id": "string" (optional),
            "names": "string" (optional),
            "location": "string" (optional),
            "mqtt_broker": "string" (optional),
            "mqtt_port": integer (optional),
            "mqtt_user": "string" (optional),
            "mqtt_password": "string" (optional),
            "reading_interval_seconds": integer (optional),
            "sensor_pin": integer (optional)
        }
        
        Response: 200 OK mit Bestätigung und Neustart-Hinweis
        """
        print("→ POST /config angefordert")
        try:
            if not body or not body.strip():
                return self._http_error(400, "Empty request body")
            
            # JSON parsen
            try:
                new_config = json.loads(body)
            except ValueError as e:
                return self._http_error(400, f"Invalid JSON: {str(e)}")
            
            # Validierung
            valid_keys = {
                "device_id", "names", "location", 
                "mqtt_broker", "mqtt_port", "mqtt_user", "mqtt_password",
                "reading_interval_seconds", "sensor_pin"
            }
            
            invalid_keys = set(new_config.keys()) - valid_keys
            if invalid_keys:
                return self._http_error(400, f"Invalid configuration keys: {', '.join(invalid_keys)}")
            
            # Typ-Validierung
            if "mqtt_port" in new_config:
                if not isinstance(new_config["mqtt_port"], int) or not (1 <= new_config["mqtt_port"] <= 65535):
                    return self._http_error(400, "mqtt_port must be integer between 1-65535")
            
            if "reading_interval_seconds" in new_config:
                if not isinstance(new_config["reading_interval_seconds"], int) or new_config["reading_interval_seconds"] < 1:
                    return self._http_error(400, "reading_interval_seconds must be positive integer")
            
            if "sensor_pin" in new_config:
                if not isinstance(new_config["sensor_pin"], int) or not (0 <= new_config["sensor_pin"] <= 28):
                    return self._http_error(400, "sensor_pin must be integer between 0-28")
            
            # Konfiguration aktualisieren und speichern
            # Mapping zu internen Schlüsseln
            key_mapping = {
                "mqtt_broker": "MQTT_BROKER",
                "mqtt_port": "MQTT_PORT",
                "mqtt_user": "MQTT_USER",
                "mqtt_password": "MQTT_PASSWORD"
            }
            
            updated_settings = self.config_manager.settings.copy()
            for key, value in new_config.items():
                internal_key = key_mapping.get(key, key)
                updated_settings[internal_key] = value
            
            # Erfolgsantwort senden BEVOR Neustart
            response_data = {
                "message": "Configuration updated successfully. Device will reboot in 3 seconds.",
                "updated_fields": list(new_config.keys()),
                "reboot": True
            }
            response = self._http_response(200, json.dumps(response_data), "application/json")
            
            # Antwort senden
            print("  Sende Bestätigung und bereite Neustart vor...")
            
            # Konfiguration speichern (löst Neustart aus)
            self.config_manager.save_settings(updated_settings)
            
            return response
            
        except Exception as e:
            print(f"✗ Fehler bei POST /config: {e}")
            return self._http_error(500, f"Internal Server Error: {str(e)}")

    # -------------------------------------------------------------------
    def _get_status(self):
        """
        GET /status - Gibt Gerätestatus zurück.
        
        Response-Format (JSON):
        {
            "device_id": "string",
            "wifi_connected": boolean,
            "wifi_ssid": "string",
            "ip_address": "string",
            "mqtt_connected": boolean,
            "mqtt_broker": "string",
            "uptime_seconds": integer,
            "last_temperature": float or null,
            "last_humidity": float or null,
            "last_reading_timestamp": "string" (ISO8601) or null,
            "firmware_version": "string"
        }
        """
        print("→ GET /status angefordert")
        try:
            # Aktuellen Sensor-Wert holen (falls verfügbar)
            current_temp = None
            current_humidity = None
            
            if self.last_sensor_data:
                current_temp = self.last_sensor_data.get('temperature')
                current_humidity = self.last_sensor_data.get('humidity')
            
            # Timestamp der letzten Messung
            last_reading_time = None
            if self.last_sensor_data and 'timestamp' in self.last_sensor_data:
                last_reading_time = self.last_sensor_data['timestamp']
            
            # MQTT-Status
            mqtt_connected = False
            try:
                if self.mqtt_client and hasattr(self.mqtt_client.mqtt, '_sock'):
                    mqtt_connected = self.mqtt_client.mqtt._sock is not None
            except:
                pass
            
            status = {
                "device_id": self.config_manager.settings.get("device_id", "unknown"),
                "wifi_connected": wifi.radio.connected,
                "wifi_ssid": self.config_manager.settings.get("CIRCUITPY_WIFI_SSID", ""),
                "ip_address": str(wifi.radio.ipv4_address) if wifi.radio.connected else None,
                "mqtt_connected": mqtt_connected,
                "mqtt_broker": self.config_manager.settings.get("MQTT_BROKER", ""),
                "uptime_seconds": int(time.monotonic() - self.start_time),
                "last_temperature": current_temp,
                "last_humidity": current_humidity,
                "last_reading_timestamp": last_reading_time,
                "firmware_version": "1.0.0"
            }
            
            return self._http_response(200, json.dumps(status), "application/json")
            
        except Exception as e:
            print(f"✗ Fehler bei GET /status: {e}")
            return self._http_error(500, "Internal Server Error")

    # -------------------------------------------------------------------
    def update_sensor_data(self, sensor_data):
        """
        Aktualisiert die gespeicherten Sensordaten mit Timestamp.
        Sollte nach jeder erfolgreichen Messung aufgerufen werden.
        
        :param sensor_data: Dictionary mit temperature und humidity
        """
        if sensor_data:
            timestamp = time.localtime()
            iso_time = "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}Z".format(
                timestamp[0], timestamp[1], timestamp[2],
                timestamp[3], timestamp[4], timestamp[5]
            )
            self.last_sensor_data = {
                'temperature': sensor_data.get('temperature'),
                'humidity': sensor_data.get('humidity'),
                'timestamp': iso_time
            }

    # -------------------------------------------------------------------
    def _http_response(self, status_code, body, content_type="text/plain", extra_headers=None):
        """
        Erzeugt eine HTTP-Response.
        
        :param status_code: HTTP-Statuscode
        :param body: Response-Body (String)
        :param content_type: Content-Type Header
        :param extra_headers: Dictionary mit zusätzlichen Headern
        :return: Response als bytes
        """
        status_messages = {
            200: "OK",
            400: "Bad Request",
            404: "Not Found",
            405: "Method Not Allowed",
            500: "Internal Server Error"
        }
        
        reason = status_messages.get(status_code, "Unknown")
        
        headers = (
            f"HTTP/1.1 {status_code} {reason}\r\n"
            f"Content-Type: {content_type}\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Connection: close\r\n"
            f"Server: Pico-W/CircuitPython\r\n"
        )
        
        if extra_headers:
            for key, value in extra_headers.items():
                headers += f"{key}: {value}\r\n"
        
        headers += "\r\n"
        
        return (headers + body).encode("utf-8")

    # -------------------------------------------------------------------
    def _http_error(self, status_code, message, extra_headers=None):
        """
        Erzeugt eine JSON-formatierte Fehlerantwort.
        
        :param status_code: HTTP-Statuscode
        :param message: Fehlermeldung
        :param extra_headers: Dictionary mit zusätzlichen Headern
        :return: Response als bytes
        """
        error_body = json.dumps({
            "error": message,
            "status_code": status_code
        })
        
        return self._http_response(status_code, error_body, "application/json", extra_headers)


# ===================================================================
# ANGEPASSTE HAUPTSCHLEIFE
# ===================================================================

def main():
    """
    Hauptfunktion des IoT Environmental Monitoring Systems.
    """
    
    # Status-LED initialisieren
    led = digitalio.DigitalInOut(board.LED)
    led.direction = digitalio.Direction.OUTPUT
    
    print("\n" + "="*60)
    print("IoT Environmental Monitoring System")
    print("Raspberry Pi Pico W - DHT11 Sensor")
    print("="*60 + "\n")
    
    # 1. INITIALISIERUNG
    print("[ 1/5 ] Lade Konfiguration...")
    config_mgr = ConfigManager("/settings.toml")
    config = config_mgr.load_settings()
    
    if not config.get('CIRCUITPY_WIFI_SSID'):
        print("FEHLER: WLAN-SSID nicht konfiguriert!")
        while True:
            led.value = True
            time.sleep(0.2)
            led.value = False
            time.sleep(0.2)
    
    # 2. WLAN-VERBINDUNG
    print("\n[ 2/5 ] Verbinde mit WLAN...")
    network_mgr = NetworkManager(
        config['CIRCUITPY_WIFI_SSID'],
        config['CIRCUITPY_WIFI_PASSWORD']
    )
    
    led_blink_count = 0
    while not network_mgr.connect():
        led_blink_count += 1
        led.value = True
        time.sleep(0.5)
        led.value = False
        time.sleep(0.5)
        
        if led_blink_count > 10:
            print("WLAN-Verbindung fehlgeschlagen - Neustart...")
            time.sleep(5)
            microcontroller.reset()

    network_mgr.set_ntp_time(timezone_offset=0)
    print("Systemzeit gesetzt.",)
    # 3. SENSOR INITIALISIEREN
    print("\n[ 3/5 ] Initialisiere Sensor...")
    sensor = Sensor(config['sensor_pin'])
    
    # 4. MQTT-CLIENT INITIALISIEREN
    print("\n[ 4/5 ] Initialisiere MQTT-Client...")
    mqtt_client = MqttClient(config)
    
    if not mqtt_client.connect():
        print("MQTT-Verbindung fehlgeschlagen!")
        # Weiter ausführen - MQTT ist optional für HTTP-API
    else:
        mqtt_client.publish_status("online")
    
    # 5. WEBSERVER INITIALISIEREN
    print("\n[ 5/5 ] Starte Webserver...")
    web_server = WebServer(
        config_mgr, 
        mqtt_client=mqtt_client, 
        sensor=sensor,
        network_manager=network_mgr,
        port=80
    )
    web_server.start()
    
    print("\n✓ System bereit!")
    print(f"  Device ID: {config['device_id']}")
    print(f"  IP-Adresse: {network_mgr.get_ip()}")
    print(f"  Lese-Intervall: {config['reading_interval_seconds']}s\n")

    led.value = True
    
    # Timer für Sende-Intervall
    last_reading_time = time.monotonic()
    reading_interval = config['reading_interval_seconds']
    
    # 6. HAUPTSCHLEIFE
    print("Starte Hauptschleife...\n")
    
    while True:
        try:
            # MQTT-Verbindung aufrechterhalten
            if mqtt_client:
                mqtt_client.loop()
            
            # WebServer-Anfragen prüfen (WICHTIG: Regelmäßig aufrufen!)
            web_server.poll()
            
            # Prüfen, ob Lese-Intervall abgelaufen ist
            current_time = time.monotonic()
            if current_time - last_reading_time >= reading_interval:
                last_reading_time = current_time
                
                led.value = False
                
                print(f"[{int(time.monotonic())}s] Lese Sensordaten...")
                sensor_data = sensor.read_data()
                
                if sensor_data:
                    # Sensordaten im WebServer aktualisieren
                    web_server.update_sensor_data(sensor_data)
                    
                    # MQTT-Telemetrie senden (falls verbunden)
                    if mqtt_client:
                        mqtt_client.publish_telemetry(sensor_data)
                    
                    led.value = True
                else:
                    print("  Ungültige Sensordaten - überspringe Sendung")
                    for _ in range(3):
                        led.value = False
                        time.sleep(0.2)
                        led.value = True
                        time.sleep(0.2)
            
            # WLAN-Verbindung prüfen
            if not network_mgr.is_connected():
                print("⚠ WLAN-Verbindung verloren - versuche Wiederverbindung...")
                led.value = False
                if network_mgr.connect():
                    if mqtt_client:
                        mqtt_client.connect()
                        mqtt_client.publish_status("reconnected")
                    led.value = True
            
            # Kurze Pause (wichtig für WebServer-Reaktionszeit!)
            time.sleep(0.1)
            
        except KeyboardInterrupt:
            print("\n\nProgramm durch Benutzer beendet.")
            if mqtt_client:
                mqtt_client.publish_status("offline")
            led.value = False
            break
            
        except Exception as e:
            print(f"Fehler in Hauptschleife: {e}")
            for _ in range(5):
                led.value = not led.value
                time.sleep(0.1)
            time.sleep(5)

if __name__ == "__main__":
    main()