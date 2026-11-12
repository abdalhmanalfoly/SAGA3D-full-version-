"""Smoke test for the CONSOLIDATED workspace (no external repos).

Starts the real combined app via scripts/run_host.py's entry point (create_phase4_app),
then checks REST health, session creation, /api/client-config (served from config/*.yaml),
the browser client static mount, the calibration status path (synthetic example rig), and
both WebSocket endpoints at the wire level.
"""
import os
import sys
import threading
import time
from pathlib import Path

import httpx
import uvicorn

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "adapter"))

os.environ["SAGA_LOG_DIR"] = str(REPO / "logs")
# Use the SYNTHETIC example rig shipped in this repository (no physical cameras involved):
os.environ["SAGA_CALIBRATION_DIR"] = str(REPO / "calibration" / "example_synthetic")
os.environ["SAGA_ALLOW_SYNTHETIC_CALIBRATION"] = "1"

from saga4_world.attach import create_phase4_app  # noqa: E402
from saga4_world.config import load_world_config  # noqa: E402

cfg = load_world_config()
PORT = 8799
app = create_phase4_app()
session = app.state.manager.create_session()
print(f"[smoke] session created: {session.session_id}")

server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="warning"))
thread = threading.Thread(target=server.run, daemon=True)
thread.start()
for _ in range(100):
    if server.started:
        break
    time.sleep(0.1)
assert server.started, "uvicorn did not start"

base = f"http://127.0.0.1:{PORT}"
results = {}
with httpx.Client(timeout=5.0) as c:
    r = c.get(f"{base}/api/health")
    results["GET /api/health"] = (r.status_code, r.json().get("ok", r.json()))
    r = c.get(f"{base}/api/sessions")
    results["GET /api/sessions"] = (r.status_code, session.session_id in r.text)
    r = c.get(f"{base}/api/client-config")
    ok = r.status_code == 200 and r.json()["model"]["bundle_path"].startswith("/client/vendor/")
    results["GET /api/client-config (vendor paths local)"] = (r.status_code, ok)
    r = c.get(f"{base}/client/index.html")
    results["GET /client/index.html (sensor page)"] = (r.status_code, "sensor" in r.text.lower() or r.status_code == 200)
    r = c.get(f"{base}/client/vendor/mediapipe/vision_bundle.mjs")
    results["GET MediaPipe bundle from local vendor/"] = (r.status_code, len(r.content) > 10000)
    r = c.get(f"{base}/client/vendor/models/hand_landmarker.task")
    results["GET MediaPipe model from local vendor/"] = (r.status_code, len(r.content) > 100000)

# WebSocket checks on both routes
import websockets  # noqa: E402
import asyncio  # noqa: E402


async def ws_checks():
    out = {}
    uri = f"ws://127.0.0.1:{PORT}/ws/world?session={session.session_id}"
    async with websockets.connect(uri) as ws:
        hello = {"protocol_version": "1.0", "message_type": "WORLD_HELLO", "session_id": session.session_id,
                 "sequence_number": 1, "timestamp_ms": int(time.time() * 1000), "client_id": "godot", "objects": []}
        await ws.send(__import__("json").dumps(hello))
        first = __import__("json").loads(await asyncio.wait_for(ws.recv(), 5))
        out["WS /ws/world handshake"] = (200, first.get("message_type") in ("WORLD_READY", "HOST_STATUS"))
    # sensor route: invalid hello must be rejected with a protocol ERROR (route alive, validation intact)
    uri = f"ws://127.0.0.1:{PORT}/ws/sensor"
    async with websockets.connect(uri) as ws:
        await ws.send(__import__("json").dumps({"garbage": True}))
        reply = __import__("json").loads(await asyncio.wait_for(ws.recv(), 5))
        out["WS /ws/sensor validation alive"] = (200, reply.get("message_type") == "ERROR")
    return out


ws_results = asyncio.run(ws_checks())
server.should_exit = True
thread.join(timeout=5)

fails = [k for k, v in {**results, **ws_results}.items() if not v[1]]
for k, (code, ok) in {**results, **ws_results}.items():
    print(f"[smoke] {'PASS' if ok else 'FAIL'}  {k}  (status {code})")
print(f"[smoke] RESULT: {'ALL PASS' if not fails else 'FAILURES: ' + str(fails)}")
sys.exit(0 if not fails else 1)
