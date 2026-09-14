# Copyright 2026 NetApp Instaclustr contributors. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

#!/usr/bin/env python3
"""Keep the workshop container alive; expose readiness without serving files."""
from __future__ import annotations

import json
import os
import platform
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path != "/healthz":
            self.send_error(404)
            return
        repo = Path(os.environ.get("LAB_REPO_DIR", "/workspace/agentic-rag"))
        ready = all((repo / part / "Makefile").is_file() for part in
                    ("2-news-agent", "3-financials-agent", "4-orchestrator-agent"))
        body = json.dumps({"service": "agentic-lab", "status": "ok" if ready else "not_ready",
                           "python": platform.python_version(), "repository_ready": ready}).encode()
        self.send_response(200 if ready else 503)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        # Do not log paths, headers, environment variables, or health-check noise.
        return


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", 8088), Handler)
    print("Runtime readiness is listening on the private container network at port 8088.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
