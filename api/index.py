from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory
from chat import RECIPES, reply_to

# Double underscores __ are required here!
BASE = Path(__file__).resolve().parent
# This goes up one folder to find index.html
ROOT_DIR = BASE.parent 

# Double underscores __ are required here!
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10_000 

@app.route("/")
def index():
    # We use ROOT_DIR here because index.html is outside the api folder
    return send_from_directory(ROOT_DIR, "index.html")

@app.route("/style.css")
def stylesheet():
    # We use ROOT_DIR here because style.css is outside the api folder
    return send_from_directory(ROOT_DIR, "style.css")

@app.get("/api/health")
def health():
    return jsonify(ok=True, recipes=len(RECIPES))

@app.post("/api/chat")
@app.post("/chat.py")
def chat():
    message = (request.get_json(silent=True) or {}).get("message", "")
    return jsonify(reply_to(str(message).strip()[:300]))