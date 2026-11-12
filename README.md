# SAGA 3D Phase 4 — Godot world adapter + grab/move/release demo
#
# This is the CONSOLIDATED main development workspace for all of SAGA 3D:
#   Phase 1  sensor acquisition      -> sensor-client/ + host/app (sensor, registry, protocol)
#   Phase 2  calibration + 3D fusion -> host/app/spatial/ + scripts/calibrate.py
#   Phase 3  coordination + gesture  -> host/app/coordination/ + host/app/gesture/
#   Phase 4  Godot world adapter     -> adapter/ + godot/
# Everything runs in ONE process (FastAPI): /ws/sensor (browser sensors) and /ws/world (Godot).

```
     sensor-client/  (browser: camera + MediaPipe landmarks, served by the host at /client/)
                    |   ws://.../ws/sensor   (sensor protocol 1.0, unchanged)
                    v
     host/           FastAPI host: registry, sessions, calibration, 3D fusion (Phases 1-2),
                     coordination + gesture agent (Phase 3)
                    |   (world adapter attaches per session at runtime)
                    v
     adapter/        /ws/world for Godot — one client per session, validated wire,
                     one rig->Godot transform, bounded queues, ack discipline
                    |   ws://127.0.0.1:8765/ws/world?session=<id>
                    v
     godot/          Godot 4.3 project: hand marker, grabbable cube, status UI
```

## Quick start

```bat
cd "D:\collega active\phases\saga-3d-phase-4"
copy .env.example .env
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python scripts\run_host.py --session demo1

(then open http://127.0.0.1:8765/client/ in the browser(s) acting as cameras)
```

```bat
cd godot
"C:\path\to\Godot_v4.3-stable_win64.exe" --path . -- --session=demo1
```

Full details: `docs/setup.md`. Wire contract: `docs/world_protocol.md`.
Coordinates: `docs/coordinates.md`. Demo walkthrough: `docs/demo_script.md`.
Architecture: `docs/architecture.md`. Tests: `docs/testing.md`.
Phase 1-3 host documentation (from the original phase repos): `docs/host/`.

## Layout

```
host/                  consolidated Phases 1-3 implementation (app + its own test suite)
  host/app/spatial/        Phase 2: calibration, geometry, triangulation, fusion
  host/app/coordination/   Phase 3: multi-sensor coordination
  host/app/gesture/        Phase 3: gesture agent, pinch, INTERACTION_EVENT 1.0
sensor-client/         Phase 1: browser sensor client (vendor/ fetched by scripts/fetch_assets.sh)
adapter/saga4_world/   Phase 4: bridge+protocol+transform+status+attach (the whole adapter)
config/                host configs (app/camera/thresholds/fusion/gesture/coordination.yaml)
                       + world.yaml (thresholds, transform, constraints; tunable, documented)
godot/                 Godot 4.3 project (world_client is the validation gate)
tests/                 54 adapter tests (unit + REAL-server e2e)
host/tests/            357 host tests (protocol, registration, fusion, calibration, gesture, coordination)
scripts/               run_host.py (Windows launcher), calibrate.py, fetch_assets.sh, smoke_consolidated.py, ...
calibration/           calibration outputs (real data git-ignored; synthetic example committed)
docs/                  protocol/coordinates/setup/testing/demo/architecture + host/ (phase 1-3 docs)
```

## Hard rules (checked, not aspirational)

* One authoritative implementation of every component lives in THIS repository; the old
  phase repositories are historical references only and are NOT needed at runtime.
* Everything crossing the wire is validated in BOTH directions against protocol.py.
* Everything is honest about hardware: the calibration/fusion/gesture pipeline is fully
  synthetic-validated, but nothing has been validated on physical cameras yet
  (see docs/PHASE4_MAIN_WORKSPACE_MIGRATION_REPORT.md and PHASE4_IMPLEMENTATION_REPORT.md).
