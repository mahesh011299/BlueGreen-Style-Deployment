import os
import socket
from flask import Flask, jsonify

app = Flask(__name__)

VERSION = os.getenv("APP_VERSION", "7.8")
COMMIT_SHA = os.getenv("GIT_COMMIT", "unknown")
DB_HOST = os.getenv("DB_HOST", "orders-db")

@app.route("/")
def home():
    return jsonify({
        "status": "online",
        "service": "orders-api",
        "version": VERSION,
        "commit": COMMIT_SHA,
        "container": socket.gethostname()
    }), 200

@app.route("/health")
def health():
    return jsonify({"status": "UP", "version": VERSION}), 200

@app.route("/db-check")
def db_check():
    try:
        # Check internal DNS and reachability
        socket.gethostbyname(DB_HOST)
        return jsonify({"status": "CONNECTED", "database": DB_HOST}), 200
    except Exception as e:
        return jsonify({"status": "ERROR", "error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)