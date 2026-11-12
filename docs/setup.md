# Setup: running the SAGA 3D consolidated workspace (Windows instructions, generalises elsewhere)

## Prerequisites

* Python 3.12 (the venv used during development was 3.12; host requirements apply).
* Node.js (any recent version; used ONLY to run the browser-logic unit tests — the sensor
  client itself has no build step and no npm dependencies).
* Godot 4.3 (opened the project under `godot/` at least once with the standard editor).
* A second machine is fine (the host binds `127.0.0.1` by default; relax
  `config/world.yaml endpoint.host` deliberately if you really want LAN).
* The whole implementation (sensor client, host, adapter) lives in THIS repository.
  The old phase repositories (`saga-3d phase 1/2/3`) are historical references only
  and are NOT needed at runtime.

## 1. Install the Python venv

```bat
cd "D:\collega active\phases\saga-3d-phase-4"
.venv\Scripts\python -m pip install -r requirements.txt
```

(If `.venv` does not exist yet, create it first: `python -m venv .venv`.)

## 1b. Fetch the MediaPipe browser assets (one-time)

The sensor client loads MediaPipe Tasks-Vision (WASM + hand-landmarker model) LOCALLY —
never from a CDN. The binaries are git-ignored (size + licensing) and fetched once by:

```bash
bash scripts/fetch_assets.sh        # requires node/npm + network access, pinned version 1.1.1
```

(The assets were consolidated from the Phase 1 checkout; if `sensor-client/vendor/` already
exists, the script verifies and keeps it. Verify the model hash: `sensor-client/vendor/models/hand_landmarker.task.sha256`.)

## 2. Configure

Copy `.env.example` to `.env`. There is NO `SAGA3_ROOT` anymore — the host tree is
`host/` inside this repository. All thresholds live in `config/world.yaml`; the coordinate
transform is documented in `docs/coordinates.md`.

## 3. Start the combined host

```bat
.venv\Scripts\python scripts\run_host.py --session demo1
```

Now serving on http://127.0.0.1:8765:
* `/client/` — the browser sensor client (camera + MediaPipe landmarks; served locally)
* `/api/health`, `/api/sessions`, `/api/client-config`, ... (host REST, unchanged)
* `/ws/sensor` — sensor protocol for real cameras (Phase 1, unchanged)
* `/ws/world` — the Godot world socket (see docs/world_protocol.md)

Runtime outputs (logs, calibration) are written under `logs/` and `calibration/` inside
this repository.

## 4. Start Godot

```bat
cd godot
"C:\path\to\Godot_v4.3-stable_win64.exe" --path . -- --session=demo1
```

(or open `godot/project.godot` in the Godot editor, set `main.tscn`, run F5 under the same
command line arg `--session=demo1`).

The scene connects to `ws://127.0.0.1:8765/ws/world?session=demo1`, greets with
`WORLD_HELLO` (declaring `cube_1`), expects `WORLD_READY`, then follows the world
protocol: `HOVER`/`GRAB`/`MOVE`/`RELEASE`, heartbeats and status panels.

## 5. Real sensor data

Sessions created through the REST API with NO registered sensors show
`WAITING_FOR_SENSORS`, then (correctly) `CALIBRATION_REQUIRED`; interaction stays inhibited
by design (tests/test_bridge.py covers this safe-stop). Real sensors plus a real calibration
move the state machine forward — that full path is NOT yet exercised on physical hardware
(see PHASE4_IMPLEMENTATION_REPORT.md and the migration report). A fully SYNTHETIC end-to-end
check of the fusion path runs from this repository with:
`SAGA_CALIBRATION_DIR=calibration/example_synthetic SAGA_ALLOW_SYNTHETIC_CALIBRATION=1` and
`scripts/e2e_fusion_live.py` (see docs/testing.md).

## 6. Heartbeat and reconnection

The Godot client sends `HEARTBEAT` (idle > ~1 s without traffic), the host answers
`HEARTBEAT_ACK`. Godot reconnects automatically (exponential backoff capped, bounded
attempts) if the socket drops; a disconnect mid-grab releases the held object locally and
notifies the host on the next successful HELLO handshake (OBJECT_STATE re-declaration).

## 7. One client per session

Starting a second Godot against the same session gives
`ERROR(WORLD_CLIENT_EXISTS, fatal)` and closes that socket. The session is free again once
the first Godot disconnects.
