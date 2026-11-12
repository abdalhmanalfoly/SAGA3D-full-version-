# PHASE 1 — COMPLETION AUDIT: Sensor Acquisition

**Date:** 2026-11-12 · **Repo:** `saga-3d-phase-4` @ `bd01443` (`consolidation/main-workspace`) · **Audit type:** read-only, evidence-based

**Phase gate status: IMPLEMENTATION COMPLETE — NOT OPERATIONALLY VERIFIED**
(highest achieved verification level = 4, "real application/service execution" with *simulated* sensors over the real wire; level 5 "real hardware execution" has never happened)

---

## 1. Phase ownership (actual code dependencies, not folders)

| Component | Path | Role |
|---|---|---|
| Browser sensor client | `sensor-client/` (`index.html`, `operator.html`, `src/{camera,landmark_detector,websocket_client,protocol,sensor_state,app,operator}.js`, `styles.css`, `tests/`) | camera access + MediaPipe landmarks + WS client |
| MediaPipe assets (local) | `sensor-client/vendor/` (git-ignored, present; re-fetch: `scripts/fetch_assets.sh`) | WASM + `hand_landmarker.task` 1.1.1, served at `/client/vendor` |
| Protocol/registry/sessions | `host/app/schemas/`, `host/app/services/`, `sensor_registry.py`, `websocket_handler.py`, `session_manager.py` | protocol 1.0 validation, sensor identity/lifecycle, session mgmt |
| FastAPI app + routes | `host/app/main.py`, `config.py` | `/ws/sensor`, `/client` static mount, REST |
| Config | `config/camera.yaml`, `config/app.yaml`, `config/thresholds.yaml` | camera/facing/resolution, server bind, limits |
| Client tests | `sensor-client/tests/*.test.mjs` (16) | browser-logic unit tests (Node) |
| Host tests | `host/tests/test_protocol_validation.py`, `test_registration.py`, `test_sessions.py`, `test_observations.py`, `test_health.py`, `test_privacy_and_logging.py`, `test_js_contract.py` | protocol/registration contracts |

**Shared with other phases:** `main.py` (factory also mounts Phase 2 fusion + Phase 3 wiring), `session_manager.py`, `logs/`. Phase 2 consumes Phase 1's `LANDMARK_OBSERVATION` stream; Phase 4 attaches to Phase 1 sessions.

## 2. Implementation audit

**IMPLEMENTED (verified by inspection + tests):**
- Camera access: `camera.js` `getUserMedia` with `facingMode/width/height/frameRate` ideals from `config/camera.yaml` (640×480@30); error mapping `NotAllowedError/SecurityError`, `NotFoundError/DevicesNotFoundError`; `isSecureContext` guard (HTTPS required for phones) surfaced in `index.html` secure-warning.
- MediaPipe: `landmark_detector.js` loads **local** `vision_bundle.mjs` + WASM + model (no CDN); hand landmarks, float16; `flip_handedness: true` convention documented in `config/camera.yaml`.
- Sensor page flow (`app.js`): session code entry, start/stop, status lines, **"Save calibration frame"** button (`app.js:180–197`) downloading the un-mirrored frame at exact stream resolution (used by Phase 2).
- Operator page (`operator.js`): session create/stop/join link; per-sensor state/permission/rate/ages/gaps/reconnects/last-error table.
- WS client: `websocket_client.js` — bounded exponential backoff + jitter, reconnect states, `maxBufferedBytes` backpressure (droppable messages refused when full).
- Host: strict protocol 1.0 validation both directions (`schemas/`), sensor registration/lifecycle (`online/degraded/disconnected`), HELLO timeout, duplicate/late rejection, `max_message_bytes`, observation recorder, event logging, sweep.

**PARTIALLY IMPLEMENTED:** none material.
**MISSING:** body/pose landmarks (only `hand_landmarker`; `config/fusion.yaml targets: [wrist]` — body tracking is out of current pipeline scope); explicit per-device camera picker (facing-mode only).
**Present but not operationally verified:** everything above on *real* cameras — no browser has ever streamed through this host.
**No duplicated/obsolete/placeholder components found.**
**Hidden dependency on earlier phases:** none — Phase 1 is the root phase.

## 3. Real-world operational audit (what a human needs)

| Requirement | Where | Status |
|---|---|---|
| PC + Python venv | `.venv` (Python 3.12.4, pinned `requirements.txt`) | ready |
| LAN with PC + phones | same Wi-Fi | HUMAN ACTION |
| HTTPS cert for phone cameras | `bash scripts/make_dev_cert.sh <LAN-IP>` → `certs/dev.{crt,key}`; `SAGA_TLS_CERT/KEY` in `.env` | tool ready, not generated |
| Host start | `.venv\Scripts\python scripts\run_host.py --session demo1` | command verified (smoke + e2e) |
| Sensor page | `https://<LAN-IP>:8765/client/` | served locally (smoke-verified) |
| Camera permission grant | browser prompt per device | HUMAN ACTION |
| What you see when it works | operator page rows: online, rate > 0 Hz, small ages | defined |
| Failure diagnosis | operator page columns (gaps/reconnects/last error), host event log `logs/` | tooling exists |

## 4. Actual verification audit

| Level | Achieved? | Evidence |
|---|---|---|
| 1 Code inspection | ✔ | this audit |
| 2 Automated tests | ✔ | 16 node + ~70 host protocol/registration tests (within 411 pass) |
| 3 Synthetic execution | ✔ | simulated WS clients |
| 4 Real service execution | ✔ (simulated sensors) | `scripts/smoke_consolidated.py` 8/8; `e2e_fusion_live.py` 11/11 (registration, heartbeats, statuses) |
| 5 **Real hardware execution** | ✘ **never** | no camera/browser has ever streamed |
| 6 End-to-end operational demo | ✘ | depends on 5 |

## 5. Missing-work register

| ID | Class | Task | Files | Why | Action | Depends | P | Completion criteria | Evidence required |
|---|---|---|---|---|---|---|---|---|---|
| P1-H1 | HUMAN | LAN setup: PC + ≥2 cameras on same network | — | browsers reach host | connect devices | — | P0 | operator page loads on each device | screenshot/observation |
| P1-H2 | HUMAN | Generate HTTPS dev cert | `scripts/make_dev_cert.sh`, `.env` | phones need secure context | run script, set `SAGA_TLS_CERT/KEY` | P1-H1 | P0 | `https://<LAN-IP>:8765/client/` loads, no browser camera block | page loads |
| P1-H3 | HUMAN | Start host with session | `scripts/run_host.py` | server runtime | run command | P1-H2 | P0 | `host_started` in log; `/api/health` OK | log line |
| P1-H4 | HUMAN | Open sensor page per camera + grant permission | `sensor-client/` | acquire streams | per-device browser session | P1-H3 | P0 | live preview, sensor registered | operator page row online |
| P1-H5 | HUMAN | Verify handedness convention | `config/camera.yaml` | Phase 2/3 label correctness | raise right hand, check label | P1-H4 | P1 | label matches visual truth | recorded observation |
| P1-H6 | HUMAN | Record each camera's streaming WxH | operator page / PNG filename | Phase 2 resolution match | note values | P1-H4 | P0 | values recorded | note in handover |
| P1-H7 | HUMAN | Record real FPS/latency/CPU per device | operator page + browser DevTools | performance evidence | measure & record | P1-H4 | P2 | numbers recorded | measurement note |
| P1-V1 | VALIDATION | Real-camera 10-min stability run (no drop loops) | — | handover requires stable delivery | run session | P1-H4 | P0 | no unbounded reconnects; ages stay small | session log |
| P1-D1 | DEVELOPMENT | (optional) device picker UI | `sensor-client/src/camera.js`, `index.html` | convenience | implement later | — | P3 | user selects device | — |
| P1-D2 | DEVELOPMENT | (optional) body/pose landmarks | `landmark_detector.js`, model config | broader project goal | future feature | — | P3 | pose landmarks flow | — |
| P1-B1 | BLOCKER | none currently | — | — | — | — | — | — | — |

## 6. Definition of Done (Phase 1)

1. Host runs from this repo with zero external deps (`SAGA3_ROOT` absent).
2. ≥2 real cameras stream via browser: registered, stable ≥10 min, rate > 0, timestamps flowing.
3. Handedness convention verified; per-camera streaming resolution recorded.
4. Real performance numbers recorded (FPS, obs age, reconnect behaviour).
5. Evidence: session log + operator-page observations + measurement notes.

**Handover status: NOT READY until P1-H1..H7 and P1-V1 pass** (see `PHASE1_HANDOVER_CONTRACT.md`).
