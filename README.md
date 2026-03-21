English | [Español](README.es.md)

# Distributed Sensing Platform

A cyber-physical edge sensing system implementing probabilistic sensor fusion, finite-state machine control, and distributed edge data persistence across heterogeneous hardware nodes.

## Overview

This project demonstrates a complete end-to-end distributed sensing architecture: a microcontroller-based sensing node acquires and processes multi-modal sensor data in real time, transmits structured telemetry to a wireless gateway, and delivers it to an edge compute node for persistence and REST API exposure.

```bash
Arduino Uno R3             Pico W               Pi Zero 2W
┌──────────────┐         ┌──────────┐         ┌────────────────┐
│ HC-SR04      │         │          │  MQTT   │ MQTT Subscriber│
│ PIR sensor   │─UART──▶│  WiFi    │────────▶│ SQLite store   │
│ Kalman filter│         │  gateway │         │ REST API       │
│ FSM + servo  │         │          │         │                │
│ Buzzer       │         │          │         │                │
└──────────────┘         └──────────┘         └────────────────┘
   5V logic      HW-221    3.3V logic         192.168.x.x:5000
```

## Key Technical Concepts

**Probabilistic state estimation** — A 1D Kalman filter runs on the Arduino to reduce ultrasonic measurement noise before state classification. Raw and filtered distances are both published, enabling downstream comparison of estimation quality.

**Finite state machine architecture** — System behaviour is structured as an explicit FSM with four states (`LIBRE`, `MONITOREANDO`, `CERCA`, `PELIGRO`). Transitions are driven by fused PIR and filtered ultrasonic inputs, producing deterministic and inspectable control logic.

**Multi-modal sensor fusion** — PIR (passive infrared) and ultrasonic sensing modalities are combined: PIR activates the monitoring pipeline, ultrasonic quantifies proximity. This two-stage detection pattern reduces false positives.

**Distributed edge architecture** — Telemetry flows across three physically distinct nodes over two transport layers (UART → MQTT/WiFi), with logic level translation (5V ↔ 3.3V) handled by a bidirectional HW-221 shifter.

**Edge persistence and REST exposure** — The Pi Zero 2W maintains a local SQLite time-series store and exposes telemetry via a Flask REST API, decoupling the sensing pipeline from any downstream consumers.

## Hardware

| Component            | Role                                         |
| -------------------- | -------------------------------------------- |
| Arduino Uno R3       | Sensing, Kalman filtering, FSM, actuation    |
| HC-SR04              | Ultrasonic distance measurement              |
| PIR sensor           | Passive infrared motion detection            |
| Servo (180°)         | State-driven physical actuator               |
| Active buzzer        | Proximity alert                              |
| HW-221 shifter       | 5V ↔ 3.3V logic level translation            |
| Raspberry Pi Pico W  | UART receiver, WiFi MQTT gateway             |
| Raspberry Pi Zero 2W | Edge node: MQTT subscriber, SQLite, REST API |

## Pin Mapping

### Arduino Uno R3

| Pin    | Function                  |
| ------ | ------------------------- |
| 8      | HC-SR04 TRIG              |
| 7      | HC-SR04 ECHO              |
| 4      | PIR signal                |
| 3      | Servo PWM                 |
| 2      | Buzzer                    |
| TX (1) | UART to Pico W via HW-221 |

### Raspberry Pi Pico W

| Pin      | Function                     |
| -------- | ---------------------------- |
| GP0 (RX) | UART from Arduino via HW-221 |
| GP1 (TX) | UART to Arduino (reference)  |

## MQTT Topics

| Topic                                  | Type  | Description                        |
| -------------------------------------- | ----- | ---------------------------------- |
| `dsplatform/sensor/distancia/raw`      | float | Unfiltered ultrasonic reading (cm) |
| `dsplatform/sensor/distancia/filtrada` | float | Kalman-filtered estimate (cm)      |
| `dsplatform/sensor/pir`                | int   | PIR motion detection (0 \| 1)      |
| `dsplatform/sensor/estado`             | str   | FSM state label                    |

## FSM State Transitions

```bash
              PIR=0, dist > 50
    ┌─────────────────────────────────┐
    │                                 ▼
PELIGRO ◀── dist ≤ 20 ──── LIBRE ──────────── MONITOREANDO
    │                        │   PIR=1, dist>50      │
    │                        │◀──────────────────────┘
    └─── dist > 20 ─────▶ CERCA
                      20 < dist ≤ 50
```

## REST API

Base URL: `http://192.168.1.43:5000`

```bash
GET /estado     → most recent telemetry frame
GET /lecturas   → last 100 frames (newest first)
GET /health     → service liveness
```

Example response (`/estado`):

```json
{
  "id": 1482,
  "timestamp": "2026-03-20T23:41:07.123456",
  "dist_raw": 34.21,
  "dist_filtered": 33.87,
  "pir": 1,
  "state": "CERCA"
}
```

## Repository Structure

```bash
distributed-sensing-platform/
├── firmware/
│   ├── arduino/
│   │   └── sensing_node/
│   │       └── sensing_node.ino     # Arduino C++ firmware
│   └── pico/
│       └── main.py                  # Pico W MicroPython gateway
├── edge-node/
│   ├── .python-version              # Selection of python-version
│   ├── pyproject.toml               # UV project definition
│   └── server.py                    # Flask REST API + MQTT subscriber
├── docs/
│   └── architecture.mermaid         # System architecture diagram
├── README.md
└── README.es.md
```

## Setup

### Arduino

Open `firmware/arduino/sensing_node/sensing_node.ino` in Arduino IDE. Install the `Servo` library (bundled). Select board `Arduino Uno` and upload.

### Pico W

Flash MicroPython v1.27 (Raspberry Pi Pico W variant) via Thonny. Install `micropython-umqtt.simple` from Thonny's package manager. Copy `firmware/pico/main.py` to the Pico root. Update `WIFI_SSID`, `WIFI_PASSWORD`, and `MQTT_SERVER` constants.

### Edge Node (Pi Zero 2W)

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
cd edge-node
uv sync

# Run
uv run server.py
```

### MQTT Broker (PC — Mosquitto)

Create `mosquitto.conf`:

```bash
listener 1883
allow_anonymous true
```

Run: `mosquitto -c mosquitto.conf -v`

Ensure port 1883 is open on the host firewall.

## Design Notes

The Kalman filter parameters (`Q=0.1`, `R=1.0`) were tuned empirically for the HC-SR04 at indoor ranges. Increasing `R` produces smoother estimates at the cost of tracking latency; decreasing `Q` reduces responsiveness to rapid distance changes.

The FSM state boundaries (20 cm / 50 cm) and the two-stage PIR+ultrasonic detection pattern are designed to balance sensitivity against false-positive rate in a static indoor environment.

## License

MIT
