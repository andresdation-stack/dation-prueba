import os, time
from flask import Flask, request, jsonify, render_template_string

API_KEY = os.environ.get("API_KEY", "andres-123")

# Estado en memoria (se pierde si se reinicia el servicio)
state = {"value": None, "device_id": None, "ts": None}

app = Flask(__name__)

# HTML hiper simple con auto-actualización cada 2s
HTML = """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>ESP32 · Último dato</title>
  <style>
    body { font-family: system-ui, Arial; margin: 2rem; }
    .card { border: 1px solid #ddd; border-radius: 12px; padding: 1.25rem; max-width: 420px; }
    h1 { margin: 0 0 .5rem 0; font-size: 1.25rem; }
    .v { font-size: 2.5rem; margin: .25rem 0; }
    .muted { color: #666; font-size: .9rem; }
  </style>
</head>
<body>
  <div class="card">
    <h1>Último dato del ESP32</h1>
    <div id="value" class="v">—</div>
    <div id="device" class="muted">—</div>
    <div id="time" class="muted">—</div>
  </div>

  <script>
    async function load() {
      try {
        const r = await fetch('/api/latest');
        const j = await r.json();
        document.getElementById('value').textContent = (j.value ?? '—');
        document.getElementById('device').textContent = j.device_id ? ('Dispositivo: ' + j.device_id) : '—';
        document.getElementById('time').textContent = j.ts ? ('Actualizado: ' + new Date(j.ts * 1000).toLocaleString()) : '—';
      } catch(e) {
        console.error(e);
      }
    }
    load();
    setInterval(load, 2000);
  </script>
</body>
</html>
"""

@app.get("/")
def home():
    return render_template_string(HTML)

@app.get("/health")
def health():
    return "ok", 200

@app.get("/api/latest")
def latest():
    return jsonify(state)

@app.post("/ingest")
def ingest():
    data = request.get_json(silent=True) or {}
    if data.get("api_key") != API_KEY:
        return jsonify({"error": "unauthorized"}), 401

    v = data.get("value")
    if v is None:
        return jsonify({"error": "missing value"}), 400

    state["value"] = float(v)
    state["device_id"] = data.get("device_id", "esp32")
    state["ts"] = int(time.time())
    return jsonify({"ok": True}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
