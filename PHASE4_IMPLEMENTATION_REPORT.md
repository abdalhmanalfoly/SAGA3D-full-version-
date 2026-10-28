# Phase 4 implementation report

Date: 2026-10-28. Workspace: `D:\collega active\phases\saga-3d-phase-4\` (separate git
repo, sibling of the read-only `D:\collega active\phases\saga-3d phase 3\`).

## Goal

Integrate the Phase 1-3 SAGA 3D host (WebSpace cameras, fusion, gesture agent) with a
Godot 4.3 world: a hand marker that follows validated fusion output, a grabbable cube
driven ONLY by host interaction events, and an explicit grab-request/confirm handshake.

## Delivered

* **adapter/saga4_world/** — Python side: attach.py (one FastAPI process adds `/ws/world`
  and a 20 Hz tick task to the REAL Phase 1-3 app; runtime wiring monkey-patches live
  instances only), bridge.py (FusionResult → validated HandSample → REAL GestureAgent →
  queued events/pose slots), server.py (per-client socket session with hello timeout,
  heartbeat watchdog, fatal/close discipline), protocol.py (strict INTERACTION_EVENT 1.0
  validation BOTH directions: required/unknown fields, types, pattern of object ids,
  per-direction sequence checks), transform.py (the single rig→Godot mapping, validated
  orthonormal rotation + volume checks + fingerprint), status.py (derived host trust
  states), config.py, p3.py (all Phase 3 contract imports consolidated).
* **godot/** — Godot 4.3 project: `world_client.gd` (single validation gate),
  `main.gd` (signal wiring + ACK dispatch), `hand_marker.gd` (freeze on invalid, never
  dead-reckons), `grabbable_cube.gd` (plausibility screen), `status_ui.gd`.
* **tests/** — 54 passing (50 unit + 4 e2e against a REAL uvicorn server with a real
  websockets client; the grab-release path exercises the actual ack round-trip at wire
  level, incl. real Phase 3 gesture/pinch state machines).
* **docs/** — world_protocol, coordinates, setup, testing, demo_script, architecture.
* **scripts/run_host.py**, **.env.example**, **requirements.txt** (pinned, matching the
  Phase 1-3 lock for shared modules).

## Verified (this machine)

| check | result |
|---|---|
| pytest tests (unit) ref `df7335b` contract | 50 passed |
| pytest tests incl. e2e (real uvicorn + websockets client) | 54 passed, 0 failed |
| Godot 4.3 headless scene load + per-script `--check-only` | parse-clean |
| Phase 1-3 repository untouched after all runs | `git status` clean (start commit `df7335b`) |
| Launcher smoke run (`scripts/run_host.py`) | /api/health 200, session created, world socket accepted |

Key bug found and fixed during integration: FastAPI 0.143 requires the WebSocket
parameter to be ANNOTATED (`ws: WebSocket`); an untyped parameter is treated as a
required query field and the route 403s before `accept()` — this affected every
websocket handshake (found by ASGI-level send spying).

## NOT yet verified (needs physical hardware) — be honest in the demo

* **No physical WebSpace camera was available in this environment.** All e2e motion was
  synthetic: fusion results were injected directly through the REAL bridge entry point
  (`on_fusion_result`) with REAL timestamps, and in the grab e2e the real fusion ticker
  was disabled (`manager.fusion_tick = lambda: None`, test-file-documented) because the
  live engine would consume the synthetic observations and emit competing results; the
  calibration gate was stubbed (`_calibrated_sensor_count -> 2`) because a fresh session
  with no physical sensors correctly blocks interaction (that safe path itself IS
  unit-tested).
* The rig→Godot transform rotation is an intrinsically reasonable default (board-flat
  assumption, right-handed, verified numerically) but NOT verified against two physical
  reference points (docs/coordinates.md §5 describes the exact check an operator must do
  before any hardware session).
* Real-camera end-to-end latency, 30 Hz MOVE_TARGET under real frame pacing, sensor
  disconnect/reconnect while a grab is mid-handshake: unit-level verified, not
  hardware-measured.
* Godot was run headless for validation only; no human watched the demo scene.

## Contract compliance (Phase 3 handoff §6)

* Uses the REAL `GestureAgent`, `HandSample.from_fusion_result` mapping semantics,
  `InteractionObject`, `INTERACTION_EVENT 1.0` event types, `acknowledge()` — imported
  via adapter/saga4_world/p3.py from the read-only repo.
* One transform module (`transform.py`); all messages validated both directions; discrete
  events keep their own bounded FIFO (256) and never collapse into pose slots (2).
* Runtime writes capped to the Phase 4 tree (SAGA_LOG_DIR/SAGA_CALIBRATION_DIR default to
  `<phase4>/logs` and `<phase4>/calibration`, applied by attach.py env defaults).

## Risks / deferred

* SessionCoordination is attached per-session when the Phase 3 coordination adapter
  imports; its DEGRADED state gates the world's trust state through `_coordinator_source`.
  Wiring with REAL degraded coordination transitions was exercised only at unit level.
* Godot reconnect/backoff is bounded but not stress-tested against server restart loops.
* Single move rate cap (30 Hz) plus slot collapse bounded memory; saturating all queues
  simultaneously is untested (deliberately bounded, no unbounded channel exists).
