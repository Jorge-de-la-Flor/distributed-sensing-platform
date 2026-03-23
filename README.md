English | [Español](README.es.md)

# Distributed Sensing Platform

A cyber-physical edge sensing system implementing probabilistic sensor fusion, finite-state machine control, and distributed edge data persistence across heterogeneous hardware nodes.

## Overview

This project demonstrates a complete end-to-end distributed sensing architecture: a microcontroller-based sensing node acquires and processes multi-modal sensor data in real time, transmits structured telemetry to a wireless MQTT gateway, and delivers it to an edge compute node for persistence, REST API exposure, and live dashboard visualisation.

```bash
Arduino Uno R3             Pico W               Pi Zero 2W
┌──────────────┐         ┌──────────┐         ┌────────────────┐
│ HC-SR04      │         │          │  MQTT   │ MQTT Subscriber│
│ PIR sensor   │─UART───▶│  WiFi   │────────▶│ SQLite store   │
│ Kalman filter│         │  gateway │         │ REST API       │
│ FSM + servo  │         │          │         │ SSE Dashboard  │
│ Buzzer       │         │          │         │                │
└──────────────┘         └──────────┘         └────────────────┘
   5V logic      HW-221    3.3V logic           <edge-ip>:5000
```

## Demo

[![Distributed Sensing Platform Demo](https://img.youtube.com/vi/wTfh7YRz6LQ/maxresdefault.jpg)](https://www.youtube.com/watch?v=wTfh7YRz6LQ)

## Key Technical Concepts

**Probabilistic state estimation** — A 1D Kalman filter runs directly on the Arduino to reduce ultrasonic measurement noise before state classification. Raw and filtered distances are both published, enabling downstream comparison of estimation quality.

**Finite state machine architecture** — System behaviour is structured as an explicit FSM with four states (`LIBRE`, `MONITOREANDO`, `CERCA`, `PELIGRO`). Transitions are driven by fused PIR and filtered ultrasonic inputs, producing deterministic and inspectable control logic.

**Multi-modal sensor fusion** — PIR (passive infrared) and ultrasonic sensing modalities are combined: PIR activates the monitoring pipeline, ultrasonic quantifies proximity. This two-stage detection pattern reduces false positives.

**Distributed edge architecture** — Telemetry flows across three physically distinct nodes over two transport layers (UART → MQTT/WiFi), with logic level translation (5V ↔ 3.3V) handled by a bidirectional HW-221 shifter.

**Edge persistence and REST exposure** — The Pi Zero 2W maintains a local SQLite time-series store and exposes telemetry via a Flask REST API, decoupling the sensing pipeline from any downstream consumer.

**Real-time dashboard via SSE** — A Server-Sent Events stream pushes each telemetry frame to a browser dashboard the moment it arrives, with FSM-state-aware colour coding and no polling required.

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

| Pin    | Function                         |
| ------ | -------------------------------- |
| 8      | HC-SR04 TRIG                     |
| 7      | HC-SR04 ECHO                     |
| 4      | PIR signal                       |
| 9      | Servo PWM                        |
| 2      | Buzzer                           |
| TX (1) | UART to Pico W via HW-221        |

### Raspberry Pi Pico W

| Pin      | Function                         |
| -------- | -------------------------------- |
| GP0 (RX) | UART from Arduino via HW-221     |
| GP1 (TX) | UART to Arduino (reference only) |

## MQTT Topics

| Topic                                  | Type  | Description                        |
| -------------------------------------- | ----- | ---------------------------------- |
| `dsplatform/sensor/distancia/raw`      | float | Unfiltered ultrasonic reading (cm) |
| `dsplatform/sensor/distancia/filtrada` | float | Kalman-filtered estimate (cm)      |
| `dsplatform/sensor/pir`                | int   | PIR motion detection (0 \| 1)      |
| `dsplatform/sensor/estado`             | str   | FSM state label                    |

## FSM State Transitions

```bash
                  PIR=0, dist > 50 cm
       ┌──────────────────────────────────┐
       │                                  ▼
  PELIGRO ◀── dist ≤ 20 cm ──── LIBRE ────────── MONITOREANDO
       │                           │  PIR=1, dist > 50 cm  │
       │                           │◀──────────────────────┘
       └──── dist > 20 cm ────▶ CERCA
                          20 cm < dist ≤ 50 cm
```

## REST API

Base URL: `http://<edge-node-ip>:5000`

```bash
GET /estado     → most recent telemetry frame
GET /lecturas   → last 100 frames (newest first)
GET /health     → service liveness check
GET /stream     → SSE stream of live telemetry
GET /dashboard  → real-time browser dashboard
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
│   ├── .python-version              # Python version pin
│   ├── pyproject.toml               # uv project definition
│   └── server.py                    # Flask REST API + MQTT subscriber + SSE dashboard
├── docs/
│   └── architecture.mermaid         # System architecture diagram
├── README.md
└── README.es.md
```

## Setup

### Arduino

Open `firmware/arduino/sensing_node/sensing_node.ino` in Arduino IDE. The `Servo` library is bundled with the IDE. Select board `Arduino Uno` and upload.

### Pico W

Flash MicroPython v1.27 (Raspberry Pi Pico W variant) via Thonny. Install `micropython-umqtt.simple` from Thonny's package manager. Copy `firmware/pico/main.py` to the Pico root. Update the configuration constants at the top of the file:

```python
WIFI_SSID     = "your_network"
WIFI_PASSWORD = "your_password"
MQTT_SERVER   = "broker_ip"
```

### Edge Node (Pi Zero 2W)

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies and run
cd edge-node
uv sync
uv run server.py
```

Update `MQTT_SERVER` and `DB_PATH` in `server.py` before running.

Open the live dashboard at `http://<edge-node-ip>:5000/dashboard`.

### MQTT Broker (Mosquitto)

Create `mosquitto.conf`:

```bash
listener 1883
allow_anonymous true
```

```bash
mosquitto -c mosquitto.conf -v
```

Ensure port 1883 is reachable from all nodes on the local network.

## Requirements

- Arduino IDE 2.x
- Raspberry Pi Pico W with MicroPython v1.27+
- Python 3.12+ (edge node)
- uv
- Mosquitto 2.x (MQTT broker)

## Design Notes

The Kalman filter parameters (`Q=0.1`, `R=1.0`) were tuned empirically for the HC-SR04 at indoor ranges. Increasing `R` produces smoother estimates at the cost of tracking latency; decreasing `Q` reduces responsiveness to rapid distance changes.

The FSM state boundaries (20 cm / 50 cm) and the two-stage PIR + ultrasonic detection pattern are designed to balance sensitivity against false-positive rate in a static indoor environment.

The SSE endpoint maintains a per-client queue and broadcasts each telemetry frame atomically. Disconnected clients are detected on the next broadcast and removed from the registry without blocking the MQTT worker thread.

## References

- Welch, G., & Bishop, G. (2006).
  *An Introduction to the Kalman Filter.*
- Thrun, S., Burgard, W., & Fox, D. (2005).
  *Probabilistic Robotics.*
- HiveMQ. (2024).
  *MQTT Essentials.*

## License

MIT
