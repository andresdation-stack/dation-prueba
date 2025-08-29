import os
import time
from flask import Flask, request, jsonify, render_template


API_KEY = os.environ.get("API_KEY", "andres-123")

app = Flask(__name__)

# Estado en memoria (se pierde si se reinicia el servicio)
state = {"value": None, "device_id": None, "ts": None}


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/about")
def about():
    return render_template("about.html")


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

    try:
        state["value"] = float(v)
    except (TypeError, ValueError):
        return jsonify({"error": "invalid value"}), 400

    state["device_id"] = data.get("device_id", "esp32")
    state["ts"] = int(time.time())
    return jsonify({"ok": True}), 200


@app.context_processor
def inject_globals():
    return {"current_year": time.localtime().tm_year}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
