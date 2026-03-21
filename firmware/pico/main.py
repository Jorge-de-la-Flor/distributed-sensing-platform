"""
distributed-sensing-platform
MQTT Gateway Firmware — Raspberry Pi Pico W (MicroPython v1.27)

Responsibilities:
  - Receive structured telemetry from Arduino Uno via UART (GP0/GP1)
  - Parse CSV telemetry lines: dist_raw, dist_filtered, pir, state
  - Publish each field to dedicated MQTT topics via WiFi
  - Reconnect automatically on WiFi or broker failure

MQTT topics published:
  dsplatform/sensor/distancia/raw       float (cm)
  dsplatform/sensor/distancia/filtrada  float (cm)
  dsplatform/sensor/pir                 int   (0 | 1)
  dsplatform/sensor/estado              str   (LIBRE | MONITOREANDO | CERCA | PELIGRO)

Hardware:
  UART0 RX → GP0  (from Arduino TX via HW-221 logic level shifter)
  UART0 TX → GP1  (to Arduino RX — reference only, not used)
"""

import machine
import network
import time
from umqtt.simple import MQTTClient

# ── Configuration ────────────────────────────────────────────────────────────
WIFI_SSID     = "YOUR_SSID_HERE"
WIFI_PASSWORD = "YOUR_PASSWORD_HERE"

MQTT_SERVER   = "YOUR_MQTT_SERVER_IP_HERE"
MQTT_PORT     = 1883
MQTT_CLIENT   = "PicoW-DSP"

TOPIC_RAW      = b"dsplatform/sensor/distancia/raw"
TOPIC_FILTERED = b"dsplatform/sensor/distancia/filtrada"
TOPIC_PIR      = b"dsplatform/sensor/pir"
TOPIC_STATE    = b"dsplatform/sensor/estado"

# ── UART ─────────────────────────────────────────────────────────────────────
uart = machine.UART(0, baudrate=9600, tx=machine.Pin(0), rx=machine.Pin(1))

# ── WiFi ─────────────────────────────────────────────────────────────────────
def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(WIFI_SSID, WIFI_PASSWORD)
    print("Connecting to WiFi", end="")
    timeout = 20
    while not wlan.isconnected() and timeout > 0:
        print(".", end="")
        time.sleep(0.5)
        timeout -= 1
    if wlan.isconnected():
        print(f"\nWiFi connected — IP: {wlan.ifconfig()[0]}")
    else:
        print("\nWiFi timeout — rebooting")
        machine.reset()

# ── MQTT ─────────────────────────────────────────────────────────────────────
def connect_mqtt():
    client = MQTTClient(MQTT_CLIENT, MQTT_SERVER, port=MQTT_PORT, keepalive=60)
    client.connect()
    print("MQTT broker connected")
    return client

# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    connect_wifi()
    client = connect_mqtt()
    buffer = ""

    while True:
        try:
            if uart.any():
                raw = uart.read(uart.any())
                buffer += raw.decode("utf-8", errors="ignore")

                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line or line.count(",") != 3:
                        continue

                    parts = line.split(",")
                    dist_raw, dist_filtered, pir, state = parts

                    client.publish(TOPIC_RAW,      dist_raw.encode())
                    client.publish(TOPIC_FILTERED, dist_filtered.encode())
                    client.publish(TOPIC_PIR,      pir.encode())
                    client.publish(TOPIC_STATE,    state.encode())

                    print(f"[TX] {state} | raw={dist_raw} filtered={dist_filtered} pir={pir}")

            client.check_msg()
            time.sleep_ms(10)

        except OSError as e:
            print(f"Connection error: {e} — reconnecting in 5s")
            time.sleep(5)
            try:
                connect_wifi()
                client = connect_mqtt()
            except Exception as e2:
                print(f"Reconnect failed: {e2}")

main()
