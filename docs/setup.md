# Setup: running the Phase 4 world demo (Windows instructions, generalises elsewhere)

## Prerequisites

* Python 3.12 (the venv used during development was 3.12; Phase 1-3 host requirements apply).
* The READ-ONLY Phases 1-3 repository next to this one: `../saga-3d phase 3/` (do not
  modify it; the adapter only ever reads/imports from it).
* Godot 4.3 (opened the project under `godot/` at least once with the standard editor).
* A second machine is fine (the host binds `127.0.0.1` by default; relax
  `config/world.yaml endpoint.host` deliberately if you really want LAN).

## 1. Install the Python venv

```bat
cd "D:\collega active\phases\saga-3d-phase-4"
.venv\Scripts\python -m pip install -r requirements.txt
```

(If `.venv` does not exist yet, create it first: `python -m venv .venv`.)

## 2. Configure

Copy `.env.example` to `.env` and adjust `SAGA3_ROOT` if your Phases 1-3 checkout lives
somewhere else. All thresholds live in `config/world.yaml`; the coordinate transform is
documented in `docs/coordinates.md`.

## 3. Start the combined host

```bat
.venv\Scripts\python scripts\run_host.py --session demo1
```

Now serving on http://127.0.0.1:8765:
* `/api/health`, `/api/sessions`, ... (Phase 1-3 REST, unchanged)
* `/ws/sensor` — sensor protocol for real WebSpace Python cameras (Phase 1-3, unchanged)
* `/ws/world` — the Godot world socket (this phase, unit per-world docs/world_protocol.md)

Runtime outputs (logs, calibration) are written under `logs/` and `calibration/` **inside
the Phase 4 tree** — never inside the read-only repository.

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
(see PHASE4_IMPLEMENTATION_REPORT.md).

## 6. Heartbeat and reconnection

The Godot client sends `HEARTBEAT` (idle > ~1 s without traffic), the host answers
`HEARTBEAT_ACK`. Godot reconnects automatically (exponential backoff capped, bounded
attempts) if the socket drops; a disconnect mid-grab releases the held object locally and
notifies the host on the next successful HELLO handshake (OBJECT_STATE re-declaration).

## 7. One client per session

Starting a second Godot against the same session gives
`ERROR(WORLD_CLIENT_EXISTS, fatal)` and closes that socket. The session is free again once
the first Godot disconnects.
