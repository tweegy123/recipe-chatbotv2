import json
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory
from chat import RECIPES, reply_to

BASE = Path(__file__).resolve().parent
ROOT_DIR = BASE.parent 

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10_000 

@app.route("/")
def index():
    return send_from_directory(ROOT_DIR, "index.html")

@app.route("/style.css")
def stylesheet():
    return send_from_directory(ROOT_DIR, "style.css")

@app.get("/api/health")
def health():
    return jsonify(ok=True, recipes=len(RECIPES))

# --- FIXED ROUTE ---
@app.get("/api/recipes")
def get_all_recipes():
    # Read the raw JSON file directly so Flask doesn't crash on Python sets
    raw_data = json.loads((BASE / "database.json").read_text(encoding="utf-8"))
    return jsonify(raw_data)
# -------------------

@app.post("/api/chat")
@app.post("/chat.py")
def chat():
    message = (request.get_json(silent=True) or {}).get("message", "")
    return jsonify(reply_to(str(message).strip()[:300]))