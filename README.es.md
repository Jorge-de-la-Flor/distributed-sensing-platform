[English](README.md) | Español

# Plataforma de Detección Distribuida

Sistema de detección ciberfísico en el borde que implementa fusión probabilística de sensores, control mediante máquina de estados finitos y persistencia distribuida de datos en el borde a través de nodos de hardware heterogéneos.

## Descripción general

Este proyecto demuestra una arquitectura completa de detección distribuida de extremo a extremo: un nodo de detección basado en microcontrolador adquiere y procesa datos de sensores multimodales en tiempo real, transmite telemetría estructurada a una puerta de enlace inalámbrica y la entrega a un nodo de computación en el borde para su persistencia y exposición a la API REST.

```bash
Arduino Uno R3             Pico W               Pi Zero 2W
┌──────────────┐         ┌──────────┐         ┌────────────────┐
│ HC-SR04      │         │  Puerta  │  MQTT   │ Suscriptor MQTT│
│ Sensor PIR   │─UART──▶│   de     │────────▶│ Almacenamiento │
│ Filtro Kalman│         │  enlace  │         │ SQLite         │
│ FSM + servo  │         │  WiFi    │         │ API REST       │
│ Buzzer       │         │          │         │                │
└──────────────┘         └──────────┘         └────────────────┘
  Lógica de 5V   HW-221  Lógica de 3.3V        192.168.x.x:5000
```

## Conceptos técnicos clave

**Estimación de estado probabilística** — Un filtro de Kalman 1D se ejecuta en Arduino para reducir el ruido de medición ultrasónica antes de la clasificación del estado. Se publican tanto las distancias sin procesar como las filtradas, lo que permite comparar posteriormente la calidad de la estimación.

**Arquitectura de máquina de estados finitos** — El comportamiento del sistema se estructura como una máquina de estados finitos explícita con cuatro estados (`LIBRE`, `MONITOREANDO`, `CERCA`, `PELIGRO`). Las transiciones se controlan mediante la fusión de señales PIR y ultrasónicas filtradas, lo que produce una lógica de control determinista e inspeccionable.

**Fusión de sensores multimodales** — Se combinan las modalidades de detección PIR (infrarrojo pasivo) y ultrasónica: el PIR activa el sistema de monitorización y el ultrasónico cuantifica la proximidad. Este patrón de detección en dos etapas reduce los falsos positivos.

**Arquitectura distribuida en el borde** — La telemetría fluye a través de tres nodos físicamente distintos mediante dos capas de transporte (UART → MQTT/WiFi), con la conversión de nivel lógico (5 V ↔ 3,3 V) gestionada por un convertidor bidireccional HW-221.

**Persistencia en el borde y exposición REST** — La Raspberry Pi Zero 2W mantiene un almacenamiento local de series temporales SQLite y expone la telemetría a través de una API REST de Flask, desacoplando el sistema de detección de cualquier consumidor posterior.

## Hardware

| Componente           | Rol                                                                        |
| -------------------- | -------------------------------------------------------------------------- |
| Arduino Uno R3       | Detección, filtrado de Kalman, máquina de estados finitos (FSM), actuación |
| HC-SR04              | Medición de distancia por ultrasonido                                      |
| Sensor PIR           | Detección de movimiento por infrarrojos pasivos                            |
| Servo (180°)         | Actuador físico controlado por estado                                      |
| Buzzer activo        | Alerta de proximidad                                                       |
| HW-221 shifter       | Conversión de nivel lógico de 5V ↔ 3.3V                                    |
| Raspberry Pi Pico W  | Receptor UART, puerta de enlace WiFi MQTT                                  |
| Raspberry Pi Zero 2W | Nodo perimetral: suscriptor MQTT, SQLite, API REST                         |

## Asignación de pines

### Arduino Uno R3

| Pin    | Function                |
| ------ | ----------------------- |
| 8      | HC-SR04 TRIG            |
| 7      | HC-SR04 ECHO            |
| 4      | Señal PIR               |
| 3      | Servo PWM               |
| 2      | Buzzer                  |
| TX (1) | UARTa Pico W via HW-221 |

### Raspberry Pi Pico W

| Pin      | Function                      |
| -------- | ----------------------------- |
| GP0 (RX) | UART desde Arduino via HW-221 |
| GP1 (TX) | UART a Arduino (referencia)   |

## Temas MQTT

| Topic                                  | Type  | Description                                           |
| -------------------------------------- | ----- | ----------------------------------------------------- |
| `dsplatform/sensor/distancia/raw`      | float | Lectura ultrasónica sin filtrar (cm)                  |
| `dsplatform/sensor/distancia/filtrada` | float | Estimación filtrada mediante el método de Kalman (cm) |
| `dsplatform/sensor/pir`                | int   | Detección de movimiento PIR (0 \| 1)                  |
| `dsplatform/sensor/estado`             | str   | Etiqueta del estado FSM                               |

## Transiciones de estado del FSM

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

## API REST

URL base: `http://192.168.1.43:5000`

```bash
GET /estado → trama de telemetría más reciente
GET /lecturas → últimas 100 tramas (de la más reciente a la más antigua)
GET /health → estado de actividad del servicio
```

Ejemplo de respuesta (`/estado`):

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

## Estructura del repositorio

```bash
distributed-sensing-platform/
├── firmware/
│   ├── arduino/
│   │   └── sensing_node/
│   │       └── sensing_node.ino     # # Firmware de Arduino en C++
│   └── pico/
│       └── main.py                  # Puerta de enlace MicroPython para Pico W
├── edge-node/
│   ├── .python-version              # Selección del python-version
│   ├── pyproject.toml               # Definición del proyecto UV
│   └── server.py                    # # API REST de Flask + suscriptor MQTT
├── docs/
│   └── architecture.mermaid         # Diagrama de arquitectura del sistema
├── README.md
└── README.es.md
```

## Configuración

### Arduino

Abre `firmware/arduino/sensing_node/sensing_node.ino` en el IDE de Arduino. Instala la librería `Servo` (incluida). Selecciona la placa `Arduino Uno` y cárgala.

### Pico W

Flashea MicroPython v1.27 (variante Raspberry Pi Pico W) mediante Thonny. Instala `micropython-umqtt.simple` desde el gestor de paquetes de Thonny. Copia `firmware/pico/main.py` a la raíz de Pico. Actualiza las constantes `WIFI_SSID`, `WIFI_PASSWORD` y `MQTT_SERVER`.

### Nodo Edge (Pi Zero 2W)

```bash
# Instalar uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Instalar dependencias
cd edge-node
uv sync

# Ejecutar
uv run server.py
```

### Broker MQTT (PC — Mosquitto)

Crear `mosquitto.conf`:

```bash
listener 1883
allow_anonymous true
```

Ejecutar: `mosquitto -c mosquitto.conf -v`

Asegúrese de que el puerto 1883 esté abierto en el firewall del host.

## Notas de diseño

Los parámetros del filtro de Kalman (`Q=0.1`, `R=1.0`) se ajustaron empíricamente para el HC-SR04 en interiores. Aumentar `R` produce estimaciones más suaves a costa de una mayor latencia de seguimiento; Disminuir el valor de `Q` reduce la capacidad de respuesta a cambios rápidos de distancia.

Los límites de estado de la máquina de estados finitos (20 cm / 50 cm) y el patrón de detección PIR+ultrasónica de dos etapas están diseñados para equilibrar la sensibilidad con la tasa de falsos positivos en un entorno interior estático.

## Licencia

MIT
