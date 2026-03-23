"""
distributed-sensing-platform
Edge Node — Raspberry Pi Zero 2 W

Responsibilities:
  - Subscribe to all MQTT topics published by the Pico W gateway
  - Persist each telemetry frame to a local SQLite database
  - Expose a REST API (Flask) for downstream consumption or visualisation
  - Stream real-time telemetry via Server-Sent Events (SSE)

REST endpoints:
  GET /estado      — most recent telemetry frame
  GET /lecturas    — last 100 telemetry frames (newest first)
  GET /health      — service liveness check
  GET /stream      — SSE stream of live telemetry (text/event-stream)
  GET /dashboard   — minimal real-time dashboard (HTML)

Run:
  uv run server.py
"""

import json
import queue
import sqlite3
import threading
import time
from datetime import datetime

import paho.mqtt.client as mqtt
from flask import Flask, Response, jsonify

# ── Configuration ────────────────────────────────────────────────────────────
# Replace these with your real MQTT broker address and local DB path on the Pi
MQTT_SERVER = "YOUR_SSID_HERE"  # fake example: 192.168.1.100
MQTT_PORT   = 1883
DB_PATH     = "YOUR_DB_PATH_HERE"  # fake example: /home/user/app.db
API_HOST    = "0.0.0.0"
API_PORT    = 5000

TOPICS = [
    "dsplatform/sensor/distancia/raw",
    "dsplatform/sensor/distancia/filtrada",
    "dsplatform/sensor/pir",
    "dsplatform/sensor/estado",
]

app = Flask(__name__)

# ── SSE subscriber registry ──────────────────────────────────────────────────
_sse_clients: list[queue.Queue] = []
_sse_lock = threading.Lock()


def broadcast(data: dict) -> None:
    with _sse_lock:
        dead = []
        for q in _sse_clients:
            try:
                q.put_nowait(data)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _sse_clients.remove(q)

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
                dist_raw      = float(_frame[TOPICS[0]])
                dist_filtered = float(_frame[TOPICS[1]])
                pir           = int(_frame[TOPICS[2]])
                state         = _frame[TOPICS[3]]

                persist(dist_raw, dist_filtered, pir, state)

                frame = {
                    "timestamp":     datetime.utcnow().isoformat(),
                    "dist_raw":      dist_raw,
                    "dist_filtered": dist_filtered,
                    "pir":           pir,
                    "state":         state,
                }
                broadcast(frame)

                print(
                    f"[DB] {state:12s} | "
                    f"raw={dist_raw:6.2f} cm | "
                    f"filtered={dist_filtered:6.2f} cm | "
                    f"PIR={pir}"
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


# ── SSE stream ───────────────────────────────────────────────────────────────
@app.get("/stream")
def stream():
    q: queue.Queue = queue.Queue(maxsize=50)
    with _sse_lock:
        _sse_clients.append(q)

    def generate():
        try:
            while True:
                try:
                    data = q.get(timeout=30)
                    yield f"data: {json.dumps(data)}\n\n"
                except queue.Empty:
                    yield ": keepalive\n\n"
        except GeneratorExit:
            with _sse_lock:
                if q in _sse_clients:
                    _sse_clients.remove(q)

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache",
                             "X-Accel-Buffering": "no"})


# ── Dashboard ────────────────────────────────────────────────────────────────
DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Distributed Sensing Platform</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Courier New', monospace;
      background: #0d1117;
      color: #c9d1d9;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 2rem;
    }
    h1 { color: #58a6ff; font-size: 1.4rem; margin-bottom: 2rem; letter-spacing: 2px; }
    .grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 1rem; width: 100%; max-width: 700px; }
    .card {
      background: #161b22;
      border: 1px solid #30363d;
      border-radius: 8px;
      padding: 1.2rem;
    }
    .card .label { font-size: 0.75rem; color: #8b949e; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 0.4rem; }
    .card .value { font-size: 2rem; font-weight: bold; color: #e6edf3; }
    .card.state .value { font-size: 1.4rem; }
    .LIBRE        { border-color: #238636; }
    .MONITOREANDO { border-color: #9e6a03; }
    .CERCA        { border-color: #d29922; }
    .PELIGRO      { border-color: #da3633; }
    .LIBRE .value        { color: #3fb950; }
    .MONITOREANDO .value { color: #e3b341; }
    .CERCA .value        { color: #d29922; }
    .PELIGRO .value      { color: #f85149; }
    .timestamp { font-size: 0.75rem; color: #484f58; margin-top: 1.5rem; }
    .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #3fb950; margin-right: 6px; animation: pulse 1.5s infinite; }
    @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
  </style>
</head>
<body>
  <h1>⬡ DISTRIBUTED SENSING PLATFORM</h1>
  <div class="grid">
    <div class="card state" id="card-state">
      <div class="label">FSM State</div>
      <div class="value" id="state">—</div>
    </div>
    <div class="card">
      <div class="label">PIR Motion</div>
      <div class="value" id="pir">—</div>
    </div>
    <div class="card">
      <div class="label">Distance Raw (cm)</div>
      <div class="value" id="dist-raw">—</div>
    </div>
    <div class="card">
      <div class="label">Distance Filtered (cm)</div>
      <div class="value" id="dist-filtered">—</div>
    </div>
  </div>
  <p class="timestamp"><span class="dot"></span><span id="ts">connecting...</span></p>

  <script>
    const src = new EventSource('/stream');
    src.onmessage = e => {
      const d = JSON.parse(e.data);
      document.getElementById('state').textContent         = d.state;
      document.getElementById('pir').textContent           = d.pir ? 'DETECTED' : 'CLEAR';
      document.getElementById('dist-raw').textContent      = d.dist_raw.toFixed(2);
      document.getElementById('dist-filtered').textContent = d.dist_filtered.toFixed(2);
      document.getElementById('ts').textContent            = d.timestamp + ' UTC';
      document.getElementById('card-state').className      = 'card state ' + d.state;
    };
    src.onerror = () => {
      document.getElementById('ts').textContent = 'connection lost — retrying...';
    };
  </script>
</body>
</html>"""


@app.get("/dashboard")
def dashboard():
    return Response(DASHBOARD_HTML, mimetype="text/html")


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    t = threading.Thread(target=mqtt_worker, daemon=True)
    t.start()
    print(f"[API] listening on http://{API_HOST}:{API_PORT}")
    print(f"[API] dashboard → http://<edge-ip>:{API_PORT}/dashboard")
    app.run(host=API_HOST, port=API_PORT, threaded=True)
