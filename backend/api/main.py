
import os
import sys
import json
import logging
import time
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request, g
from flask_cors import CORS
from dotenv import load_dotenv

# Ensure backend root is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

load_dotenv()

# ─── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","module":"%(name)s","msg":"%(message)s"}',
    datefmt="%Y-%m-%dT%H:%M:%S"
)
logger = logging.getLogger("api")


# ─── App Factory ───────────────────────────────────────────────────────────────
def create_app() -> Flask:
    app = Flask(__name__)
    app.config["JSON_SORT_KEYS"] = False
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-me")

    CORS(app, resources={r"/*": {"origins": "*"}})

    # Request timing middleware
    @app.before_request
    def start_timer():
        g.start = time.time()

    @app.after_request
    def log_request(response):
        duration = round((time.time() - g.start) * 1000, 2)
        logger.info(f"{request.method} {request.path} → {response.status_code} ({duration}ms)")
        response.headers["X-Response-Time"] = f"{duration}ms"
        return response

    # ── Error Handlers ──
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "Bad request", "detail": str(e)}), 400

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(500)
    def internal_error(e):
        logger.error(f"Internal error: {e}")
        return jsonify({"error": "Internal server error"}), 500

    # ── Register blueprints ──
    from api.routes import bp
    app.register_blueprint(bp)

    # ── Auto-initialize Database ──
    try:
        from db.init_db import init_db
        init_db()
    except Exception as e:
        logger.error(f"Failed to auto-initialize db: {e}")

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_DEBUG", "1") == "1")
