#!/usr/bin/env python3
"""SAGA 3D Phase 4 launcher: host (Phases 1-3, READ-ONLY) + world adapter + /ws/world for Godot.

Usage:
    .venv/Scripts/python scripts/run_host.py [--host HOST] [--port PORT]
                                             [--session SESSION_ID]
                                             [--skip-generate-session]

Environment (see .env.example):
    SAGA3_ROOT          path of the Phases 1-3 repository (default: ../saga-3d phase 3)
    SAGA_LOG_DIR        runtime log output (default: <phase4>/logs; NEVER defaults into Phase 1-3)
    SAGA_CALIBRATION_DIR calibration files (default: <phase4>/calibration; NEVER defaults into Phase 1-3)

After startup:
    * REST   http://127.0.0.1:8765/api/health, /api/sessions, ...
    * WS     ws://127.0.0.1:8765/ws/sensor  (Phases 1-3 sensor protocol, unchanged)
    * WS     ws://127.0.0.1:8765/ws/world   (Godot: WORLD_HELLO -> events, see docs/world_protocol.md)
Godot is started separately (see docs/setup.md); it connects as a world client per session.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="SAGA 3D Phase 4 world host")
    parser.add_argument("--host", default=None, help="bind address (default: config/world.yaml endpoint.host)")
    parser.add_argument("--port", type=int, default=None, help="bind port (default: config/world.yaml endpoint.port)")
    parser.add_argument("--session", default="", help="auto-create this session id at startup")
    parser.add_argument("--skip-generate-session", action="store_true",
                        help="do NOT auto-create any session; sessions are made via POST /api/sessions")
    args = parser.parse_args()

    sys.path.insert(0, str(REPO_ROOT / "adapter"))
    from saga4_world.attach import create_phase4_app     # noqa: E402 (path set above)
    from saga4_world.config import load_world_config     # noqa: E402

    cfg = load_world_config()
    host = args.host or cfg.endpoint.get("host", "127.0.0.1")
    port = args.port or int(cfg.endpoint.get("port", 8765))

    app = create_phase4_app()

    if args.session:
        session = app.state.manager.create_session()
        print(f"[saga4] created session {session.session_id}")

    import uvicorn                                       # noqa: E402 (after env defaults are applied inside create_phase4_app)
    print(f"[saga4] host+world adapter on http://{host}:{port}  (ws: /ws/sensor, /ws/world)")
    if not args.session and not args.skip_generate_session:
        print("[saga4] no --session given: create one with POST /api/sessions or rerun with --session <id>")
    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
