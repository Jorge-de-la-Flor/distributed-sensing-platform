[English](README.md) | Español

# Distributed Sensing Platform

Un sistema de sensado cyber-físico que implementa fusión probabilística de sensores, control mediante máquina de estados finitos y persistencia distribuida de datos en nodos heterogéneos.

## Descripción general

Este proyecto demuestra una arquitectura de sensado distribuida completa de extremo a extremo: un nodo de sensado basado en microcontrolador adquiere y procesa datos multi-modal en tiempo real, transmite telemetría estructurada a un gateway MQTT inalámbrico, y la entrega a un nodo de cómputo edge para persistencia y exposición mediante REST API.

```bash
Arduino Uno R3             Pico W               Pi Zero 2W
┌──────────────┐         ┌──────────┐         ┌────────────────┐
│ HC-SR04      │         │          │  MQTT   │ Suscriptor MQTT│
│ Sensor PIR   │─UART───▶│  WiFi   │────────▶│ Base SQLite    │
│ Filtro Kalman│         │  gateway │         │ REST API       │
│ FSM + servo  │         │          │         │                │
│ Buzzer       │         │          │         │                │
└──────────────┘         └──────────┘         └────────────────┘
   Lógica 5V     HW-221   Lógica 3.3V          <edge-ip>:5000
```

## Conceptos técnicos clave

**Estimación probabilística de estado** — Un filtro de Kalman 1D corre directamente en el Arduino para reducir el ruido de medición del sensor ultrasónico antes de la clasificación de estado. Las distancias crudas y filtradas se publican por separado, permitiendo comparar la calidad de estimación aguas abajo.

**Arquitectura de máquina de estados finitos** — El comportamiento del sistema se estructura como una FSM explícita con cuatro estados (`LIBRE`, `MONITOREANDO`, `CERCA`, `PELIGRO`). Las transiciones están determinadas por la fusión de las entradas PIR y ultrasónico filtrado, produciendo lógica de control determinista e inspeccionable.

**Fusión de sensores multi-modal** — Las modalidades de sensado PIR (infrarrojo pasivo) y ultrasónico se combinan: el PIR activa el pipeline de monitoreo, el ultrasónico cuantifica la proximidad. Este patrón de detección en dos etapas reduce los falsos positivos.

**Arquitectura edge distribuida** — La telemetría fluye a través de tres nodos físicamente distintos sobre dos capas de transporte (UART → MQTT/WiFi), con traducción de nivel lógico (5V ↔ 3.3V) gestionada por un shifter bidireccional HW-221.

**Persistencia edge y exposición REST** — El Pi Zero 2W mantiene un almacén de series temporales SQLite local y expone la telemetría mediante una REST API Flask, desacoplando el pipeline de sensado de cualquier consumidor aguas abajo.

## Hardware

| Componente           | Función                                           |
| -------------------- | ------------------------------------------------- |
| Arduino Uno R3       | Sensado, filtro Kalman, FSM, actuación            |
| HC-SR04              | Medición de distancia ultrasónica                 |
| Sensor PIR           | Detección de movimiento por infrarrojo pasivo     |
| Servo (180°)         | Actuador físico controlado por estado             |
| Buzzer activo        | Alerta de proximidad                              |
| Shifter HW-221       | Traducción de nivel lógico 5V ↔ 3.3V              |
| Raspberry Pi Pico W  | Receptor UART, gateway MQTT WiFi                  |
| Raspberry Pi Zero 2W | Nodo edge: suscriptor MQTT, SQLite, REST API      |

## Mapeo de pines

### Arduino Uno R3

| Pin    | Función                          |
| ------ | -------------------------------- |
| 8      | HC-SR04 TRIG                     |
| 7      | HC-SR04 ECHO                     |
| 4      | Señal PIR                        |
| 3      | PWM servo                        |
| 2      | Buzzer                           |
| TX (1) | UART al Pico W via HW-221        |

### Raspberry Pi Pico W

| Pin      | Función                             |
| -------- | ----------------------------------- |
| GP0 (RX) | UART desde Arduino via HW-221       |
| GP1 (TX) | UART al Arduino (solo referencia)   |

## Topics MQTT

| Topic                                  | Tipo  | Descripción                           |
| -------------------------------------- | ----- | ------------------------------------- |
| `dsplatform/sensor/distancia/raw`      | float | Lectura ultrasónica sin filtrar (cm)  |
| `dsplatform/sensor/distancia/filtrada` | float | Estimación filtrada por Kalman (cm)   |
| `dsplatform/sensor/pir`                | int   | Detección de movimiento PIR (0 \| 1)  |
| `dsplatform/sensor/estado`             | str   | Etiqueta de estado FSM                |

## Transiciones de estado FSM

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

URL base: `http://<edge-node-ip>:5000`

```bash
GET /estado     → trama de telemetría más reciente
GET /lecturas   → últimas 100 tramas (más recientes primero)
GET /health     → verificación de disponibilidad del servicio
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
│   │       └── sensing_node.ino     # Firmware Arduino C++
│   └── pico/
│       └── main.py                  # Gateway MicroPython Pico W
├── edge-node/
│   ├── .python-version              # Versión de Python fijada
│   ├── pyproject.toml               # Definición de proyecto uv
│   └── server.py                    # REST API Flask + suscriptor MQTT
├── docs/
│   └── architecture.mermaid         # Diagrama de arquitectura del sistema
├── README.md
└── README.es.md
```

## Configuración

### Arduino

Abrir `firmware/arduino/sensing_node/sensing_node.ino` en Arduino IDE. La librería `Servo` viene incluida con el IDE. Seleccionar placa `Arduino Uno` y subir el firmware.

### Pico W

Flashear MicroPython v1.27 (variante Raspberry Pi Pico W) via Thonny. Instalar `micropython-umqtt.simple` desde el gestor de paquetes de Thonny. Copiar `firmware/pico/main.py` a la raíz del Pico. Actualizar las constantes de configuración al inicio del archivo:

```python
WIFI_SSID     = "tu_red"
WIFI_PASSWORD = "tu_contraseña"
MQTT_SERVER   = "ip_del_broker"
```

### Nodo edge (Pi Zero 2W)

```bash
# Instalar uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Instalar dependencias y ejecutar
cd edge-node
uv sync
uv run server.py
```

Actualizar `MQTT_SERVER` y `DB_PATH` en `server.py` antes de ejecutar.

### Broker MQTT (Mosquitto)

Crear `mosquitto.conf`:

```bash
listener 1883
allow_anonymous true
```

```bash
mosquitto -c mosquitto.conf -v
```

Asegurarse de que el puerto 1883 sea accesible desde todos los nodos en la red local.

## Requisitos

- Arduino IDE 2.x
- Raspberry Pi Pico W con MicroPython v1.27+
- Python 3.11+ (nodo edge)
- uv
- Mosquitto 2.x (broker MQTT)

## Notas de diseño

Los parámetros del filtro de Kalman (`Q=0.1`, `R=1.0`) fueron ajustados empíricamente para el HC-SR04 en rangos interiores. Aumentar `R` produce estimaciones más suaves a costa de latencia de seguimiento; disminuir `Q` reduce la capacidad de respuesta ante cambios de distancia rápidos.

Los umbrales de estado de la FSM (20 cm / 50 cm) y el patrón de detección en dos etapas PIR + ultrasónico están diseñados para equilibrar sensibilidad frente a tasa de falsos positivos en un entorno interior estático.

## Referencias

- Welch, G., & Bishop, G. (2006).
  *An Introduction to the Kalman Filter.*
- Thrun, S., Burgard, W., & Fox, D. (2005).
  *Probabilistic Robotics.*
- HiveMQ. (2024).
  *MQTT Essentials.*

## Licencia

MIT
