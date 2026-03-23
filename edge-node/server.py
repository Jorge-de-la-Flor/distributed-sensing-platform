"""
distributed-sensing-platform
Edge Node — Raspberry Pi Zero 2 W

Responsibilities:
  - Subscribe to all MQTT topics published by the Pico W gateway
  - Persist each telemetry frame to a local SQLite database
  - Expose a REST API (Flask) for downstream consumption or visualisation

REST endpoints:
  GET /estado      — most recent telemetry frame
  GET /lecturas    — last 100 telemetry frames (newest first)
  GET /health      — service liveness check

Run:
  python3 server.py
  or with uv:
  uv run server.py
"""

import sqlite3
import threading
import time
from datetime import datetime

import paho.mqtt.client as mqtt
from flask import Flask, jsonify

# ── Configuration ────────────────────────────────────────────────────────────
MQTT_SERVER = "YOUR_SSID_HERE"
MQTT_PORT   = 1883
DB_PATH     = "YOUR_DB_PATH_HERE"  # My DB_PATH was: /home/jorge/dsplatform.db
API_HOST    = "0.0.0.0"
API_PORT    = 5000

TOPICS = [
    "dsplatform/sensor/distancia/raw",
    "dsplatform/sensor/distancia/filtrada",
    "dsplatform/sensor/pir",
    "dsplatform/sensor/estado",
]

app = Flask(__name__)

# ── Database ─────────────────────────────────────────────────────────────────
def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS readings (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp     TEXT    NOT NULL,
                dist_raw      REAL    NOT NULL,
                dist_filtered REAL    NOT NULL,
                pir           INTEGER NOT NULL,
                state         TEXT    NOT NULL
            )
        """)

def persist(dist_raw: float, dist_filtered: float, pir: int, state: str) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO readings (timestamp, dist_raw, dist_filtered, pir, state) "
            "VALUES (?, ?, ?, ?, ?)",
            (datetime.utcnow().isoformat(), dist_raw, dist_filtered, pir, state),
        )

# ── MQTT ─────────────────────────────────────────────────────────────────────
_frame: dict[str, str] = {}
_frame_lock = threading.Lock()


def on_message(client, userdata, msg: mqtt.MQTTMessage) -> None:
    topic = msg.topic
    value = msg.payload.decode("utf-8", errors="ignore").strip()

    with _frame_lock:
        _frame[topic] = value

        if all(t in _frame for t in TOPICS):
            try:
                persist(
                    dist_raw      = float(_frame[TOPICS[0]]),
                    dist_filtered = float(_frame[TOPICS[1]]),
                    pir           = int(_frame[TOPICS[2]]),
                    state         = _frame[TOPICS[3]],
                )
                print(
                    f"[DB] {_frame[TOPICS[3]]:12s} | "
                    f"raw={float(_frame[TOPICS[0]]):6.2f} cm | "
                    f"filtered={float(_frame[TOPICS[1]]):6.2f} cm | "
                    f"PIR={_frame[TOPICS[2]]}"
                )
            except (ValueError, KeyError) as exc:
                print(f"[WARN] parse error: {exc}")


def mqtt_worker() -> None:
    while True:
        try:
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            client.on_message = on_message
            client.connect(MQTT_SERVER, MQTT_PORT)
            client.subscribe("dsplatform/#")
            print("[MQTT] connected and subscribed to dsplatform/#")
            client.loop_forever()
        except Exception as exc:
            print(f"[MQTT] error: {exc} — retrying in 5 s")
            time.sleep(5)

# ── REST API ─────────────────────────────────────────────────────────────────
def _row_to_dict(row: tuple) -> dict:
    return {
        "id":            row[0],
        "timestamp":     row[1],
        "dist_raw":      row[2],
        "dist_filtered": row[3],
        "pir":           row[4],
        "state":         row[5],
    }


@app.get("/estado")
def get_estado():
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT * FROM readings ORDER BY id DESC LIMIT 1"
        ).fetchone()
    if row is None:
        return jsonify({"error": "no data yet"}), 404
    return jsonify(_row_to_dict(row))


@app.get("/lecturas")
def get_lecturas():
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT * FROM readings ORDER BY id DESC LIMIT 100"
        ).fetchall()
    return jsonify([_row_to_dict(r) for r in rows])


@app.get("/health")
def health():
    return jsonify({"status": "ok", "timestamp": datetime.utcnow().isoformat()})


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    t = threading.Thread(target=mqtt_worker, daemon=True)
    t.start()
    print(f"[API] listening on http://{API_HOST}:{API_PORT}")
    app.run(host=API_HOST, port=API_PORT)
