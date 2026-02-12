"""
Health Server - Lightweight HTTP endpoint proving 24/7 liveness.

Runs as a daemon thread inside the scheduler process.
GET /health returns JSON with zone, timestamp, vault status, and service health.

Usage (auto-started by scheduler):
    from utils.health_server import start_health_server
    start_health_server(port=8080)

Manual test:
    curl http://localhost:8080/health
"""

import os
import json
import logging
import threading
from pathlib import Path
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler

logger = logging.getLogger("HealthServer")

ZONE = os.getenv("ZONE", "local")
VAULT_PATH = Path(__file__).parent.parent / "AI_Employee_Vault"


class HealthHandler(BaseHTTPRequestHandler):
    """Serves GET /health with system status JSON."""

    def do_GET(self):
        if self.path != "/health":
            self.send_response(404)
            self.end_headers()
            return

        # Check vault existence
        vault_ok = VAULT_PATH.exists() and (VAULT_PATH / "Company_Handbook.md").exists()

        # Gather service health
        services = {}
        try:
            from utils.retry import health
            for svc, info in health.get_status().items():
                services[svc] = {
                    "healthy": info["healthy"],
                    "last_check": info["last_check"],
                }
                if info.get("last_error"):
                    services[svc]["last_error"] = info["last_error"]
        except Exception:
            pass

        body = {
            "status": "ok" if vault_ok else "degraded",
            "zone": ZONE,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "vault_ok": vault_ok,
            "services": services,
        }

        payload = json.dumps(body, indent=2).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):
        """Suppress default stderr logging — use our logger instead."""
        logger.debug("Health %s", format % args)


def start_health_server(port: int | None = None):
    """Launch the health HTTP server in a daemon thread."""
    port = port or int(os.getenv("HEALTH_PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logger.info(f"Health server listening on 0.0.0.0:{port}")
    return server
