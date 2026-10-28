# SAGA 3D Phase 4 — Godot world adapter + grab/move/release demo

A SEPARATE workspace that wires the Phase 1-3 SAGA 3D host (read-only, imported — never
edited) to a Godot 4.3 world: real hand tracking drives a grab/move/release interaction
through a validated WebSocket bridge. `INTERACTION_EVENT 1.0` end to end.

```
             Phases 1-3 repo (READ-ONLY)
        FastAPI host + sensor WS + fusion + gesture agent
                        |   (imported by Phase 4, monkey-patched wiring)
                        v
         saga4_world adapter (this repo, adapter/)
        /ws/world — one Godot client per session, validated wire,
        one rig->Godot transform, bounded queues, ack discipline
                        |   ws://127.0.0.1:8765/ws/world?session=<id>
                        v
         godot/ — Godot 4.3 project: hand marker, grabbable cube, status UI
```

## Quick start

```bat
cd "D:\collega active\phases\saga-3d-phase-4"
copy .env.example .env                       (adjust SAGA3_ROOT if needed)
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python scripts\run_host.py --session demo1

cd godot
"C:\path\to\Godot_v4.3-stable_win64.exe" --path . -- --session=demo1
```

Full details: `docs/setup.md`. Wire contract: `docs/world_protocol.md`.
Coordinates: `docs/coordinates.md`. Demo walkthrough: `docs/demo_script.md`.
Architecture: `docs/architecture.md`. Tests: `docs/testing.md` (54 passing).

## Layout

```
adapter/saga4_world/   bridge+protocol+transform+status+attach (the whole adapter)
config/world.yaml      thresholds, transform, constraints (tunable, documented)
godot/                 Godot 4.3 project (world_client is the validation gate)
tests/                 54 tests (unit + REAL-server e2e)
scripts/run_host.py    launcher
docs/                  protocol/coordinates/setup/testing/demo/architecture
logs/ calibration/     runtime output (stays OUT of the Phase 1-3 repo)
```

## Hard rules (checked, not aspirational)

* Phase 1-3 repository stays byte-for-byte read-only; runtime writes never land there.
* Runtime wiring happens on live instances, not via source edits.
* Everything crossing the wire is validated in BOTH directions against protocol.py.
* Everything is honest about hardware: nothing here has been validated on physical
  cameras yet (see PHASE4_IMPLEMENTATION_REPORT.md).
