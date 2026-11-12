# SAGA 3D — Complete Project Readiness Audit (Consolidated Phase 4 Workspace)

**Date:** 2026-11-12 · **Repository:** `D:\collega active\phases\saga-3d-phase-4\` · **Branch:** `consolidation/main-workspace` @ `bd01443` (working tree clean at audit start and end)
**Auditor:** independent read-only audit (no source/config/calibration changes; only report files were created)
**Scope:** Phases 1–4 operational readiness **for real hardware**, plus cross-phase integration.

**Companion deliverables:**
- `docs/SAGA3D_HUMAN_ACTION_CHECKLIST.md` — physical/manual actions only
- `docs/SAGA3D_REAL_WORLD_RUNBOOK.md` — 15-step operational startup runbook
- `docs/SAGA3D_REQUIRED_DEVELOPMENT_BACKLOG.md` — code tasks only (P0–P3)

---

## 1. Executive Summary

All four phases' **software foundations are consolidated in this repository and pass every runnable synthetic test** (independently re-executed during this audit — see §16). However, **the project has never run on real hardware end-to-end**, and the three decisive gaps are physical, not software:

1. **No real camera calibration exists.** `calibrate.py inspect` reports `NOT READY: need at least 2 valid, compatible calibrated cameras (have 0)`. Real cameras, a printed checkerboard, and physical capture work are required. This is the user's current phase.
2. **Godot is not installed on this machine.** Every Phase 4 Godot-side behaviour (scene load, WebSocket client, hand marker, grab interaction) is **UNVERIFIED** — scripts and signals were inspected and look correct, but nothing was ever launched.
3. **No real-camera session has ever been run.** Phase 1 works in code and was exercised with *simulated sensor clients* over the real wire (`e2e_fusion_live.py`, 11/11), but no browser camera has ever streamed through it.

**Verdict by phase (code / real-hardware readiness):**

| Phase | Software foundation | Real-hardware readiness |
|---|---|---|
| 1 Sensor acquisition | IMPLEMENTED (synthetic-verified) | HARDWARE REQUIRED — never run with a real camera |
| 2 Calibration + 3D fusion | IMPLEMENTED (synthetic-verified, quality gates enforced) | **BLOCKED on physical prerequisites** — board, cameras, mounting |
| 3 Coordination + gesture | IMPLEMENTED (synthetic-verified) | HARDWARE REQUIRED — thresholds untested on real gestures |
| 4 Bridge + Godot | Bridge IMPLEMENTED; Godot scripts exist | UNVERIFIED — Godot absent; transform unvalidated |

**The single next action for the human owner:** print/measure the checkerboard, set up two cameras, and run the documented capture → intrinsics → rig workflow (Stage 2 of the roadmap, §15). No code changes are required first.

---

## 2. Current Project Status

**Independently verified during this audit (exact commands and results in §16):**

| Check | Result | Nature |
|---|---|---|
| `.venv\Scripts\python.exe -m pytest` | **411 passed, 0 failed** (52.1 s) | synthetic |
| `cd sensor-client && node --test tests/*.test.mjs` | **16 pass, 0 fail** | synthetic |
| `scripts/calibrate.py selftest` | synthetic accuracy table (intrinsic RMS 0.05–0.09 px; triangulation errors grow with depth/noise as documented) | synthetic |
| `scripts/calibrate.py inspect` | `NOT READY ... (have 0)` — correct behaviour, **no real calibration present** | read-only |
| `where godot` | **NOT FOUND** | environment |
| Python 3.12.4 / Node v20.16.0 | present | environment |
| Git state | clean, `bd01443` | — |

**Previously verified in the consolidation session (recorded, not re-run here):** smoke 8/8, coordination demo 9/9, synthetic live-fusion e2e 11/11, independence test with old repos hidden.

**User's practical progress (do not confuse with code status):** the user is **at Phase 2, before physical camera calibration**. Phase 3 practical execution has **not** started. Code existing ≠ user completed the phase.

---

## 3. Repository Architecture

```
saga-3d-phase-4/
├── host/app/                 consolidated Phases 1–3
│   ├── main.py               FastAPI app factory; routes: /api/health, /api/sessions(+/stop,/fusion,/calibration
│   │                         +bindings|invalidate|reload), /api/client-config, /ws/sensor, /client static mount
│   ├── schemas/ services/    Phase 1: protocol 1.0 models, clock, logging, observation recorder
│   ├── sensor_registry.py    Phase 1: sensor identity/registration/lifecycle
│   ├── websocket_handler.py  Phase 1: /ws/sensor ingest → fusion + coordinator
│   ├── session_manager.py    Phase 1: sessions
│   ├── spatial/              Phase 2: geometry, calibration_schema, calibration_store, calibration_tool,
│   │                         synchronizer, filters, fusion, service, results, synthetic
│   ├── coordination/         Phase 3: coordinator, sensor_agent, scoring, set_selection, host_adapter
│   │                         (SessionCoordination), messages, audit, simulation
│   └── gesture/              Phase 3: agent (GestureAgent/HandSample/InteractionObject), events 1.0, pinch, config
├── sensor-client/            Phase 1 browser client (index/operator html, src/{camera,landmark_detector,
│                             websocket_client,protocol,sensor_state,app}.js) + vendor/ (MediaPipe 1.1.1, local)
├── host/tests/               357 host tests; tests/ 54 adapter tests (pytest.ini runs both)
├── adapter/saga4_world/      Phase 4: attach, bridge, server, protocol, transform, status, config, p3
├── godot/                    Godot 4.3 project: project.godot, scenes/main.tscn, scripts/{world_client,main,
│                             hand_marker,grabbable_cube,status_ui}.gd
├── scripts/                  run_host.py(.sh), run_tests.sh, calibrate.py, e2e_fusion_live.py,
│                             demo_coordination.py, fetch_assets.sh, make_dev_cert.sh, smoke_consolidated.py
├── config/                   app, camera, thresholds, fusion, gesture, coordination (host) + world.yaml (Phase 4)
├── calibration/              README + example_synthetic (committed); real captures git-ignored; currently EMPTY of real data
└── docs/                     this audit + setup, coordinates, world_protocol, demo_script, testing, architecture,
                              PHASE4_MAIN_WORKSPACE_MIGRATION_REPORT.md, host/ (phase 1–3 docs incl. spatial.md)
```

**Architectural observations**
- One authoritative implementation per component; no duplication found.
- Fusion consumes **only 2-D pixel landmarks + calibration** — MediaPipe's per-camera 3-D model landmarks are deliberately not used (`docs/host/spatial.md` §goal). Consistent across phases.
- Phase 4 performs the *sole* rig→Godot transform (`adapter/saga4_world/transform.py`, `config/world.yaml transform:`); Godot performs no coordinate logic (`docs/coordinates.md`). Consistent.
- Known documented limitation: with exactly 2 views, errors **along the epipolar line** are undetectable (`docs/host/spatial.md`; `test_spatial_fusion.py` documents it). More cameras would not remove this; measuring a physical reference point is the practical countermeasure.
- `attach.py` still wires sessions via runtime wrapping of `SessionManager.create_session/stop_session` (deliberately preserved by consolidation; validated by tests; optional refactor listed in the backlog).

---

## 4. Phase 1 Complete Audit — Sensor Acquisition and Tracking

### 4.1 A. Camera acquisition

| Item | Status | Evidence |
|---|---|---|
| Camera access (`getUserMedia`) | IMPLEMENTED (synthetic) | `sensor-client/src/camera.js` — `video: { facingMode: {ideal}, width/height/frameRate: {ideal} }` from `config/camera.yaml` |
| Permission handling | IMPLEMENTED (synthetic) | `camera.js` distinguishes `NotAllowedError/SecurityError` and `NotFoundError/DevicesNotFoundError`; `index.html` shows a `secure-warning` and `isSecureContext` is checked (HTTPS required for phone cameras) |
| Camera selection | IMPLEMENTED | facing-mode selector (`user`/`environment`) in `index.html`; explicit device picking **MISSING** (no `enumerateDevices` device picker) — acceptable for a 2-camera rig |
| Resolution/framerate config | IMPLEMENTED | `config/camera.yaml` 640×480@30 ideal (browser gives best-effort; actual values returned by `camera.js`) |
| Stream handling, errors, disconnection | IMPLEMENTED (synthetic) | `sensor_state.js` + operator page show rate, gaps, reconnects, last error |
| Reconnection | IMPLEMENTED (synthetic) | `websocket_client.js`: bounded exponential backoff with jitter (`computeBackoffMs`), reconnect states `connecting/reconnecting/closed` |
| Multiple cameras | IMPLEMENTED (design: one browser tab per camera) | validated with 2 simulated sensors in `e2e_fusion_live.py`; real multi-tab operation HARDWARE REQUIRED |

### 4.2 B. Sensor registration and identity
IMPLEMENTED (synthetic). `sensor_registry.py` + `sensor_state.js`: unique sensor IDs, registration on HELLO, lifecycle states (`online/degraded/disconnected` — seen live in the e2e event log), duplicate/late-HELLO rejection, disconnect cleanup (`test_registration.py`, `test_sessions.py`). Auto-binding of sensor→camera ID for calibration is exposed via `POST /api/sessions/{id}/calibration/bindings` and the operator page.

### 4.3 C. MediaPipe
- Local WASM + model: IMPLEMENTED — `config/camera.yaml model.bundle_path/wasm_path/model_path` all point to `/client/vendor/...`; `vision_bundle.mjs` and `hand_landmarker.task` verified present and served locally (smoke test, consolidation session). No CDN dependency.
- **Hand landmarks: IMPLEMENTED** (float16 `hand_landmarker` 1.1.1). **Body/pose landmarks: MISSING** — only the hand model exists. The project's stated goal includes "body movements"; today only hand/wrist tracking feeds the pipeline (fusion target list is `[wrist]`, `config/fusion.yaml`). This is a genuine functional gap for the broader vision, not a blocker for the current wrist/pinch demo.
- Detection config/failures/loss: confidence thresholds and stale-landmark handling exist in `gesture/config.py` (`min_landmark_confidence`, `stale_landmark_ms`); browser-side detection failure logging exists. Real-model behaviour UNVERIFIED.

### 4.4 D. Data protocol
IMPLEMENTED (synthetic-verified on the wire). Protocol 1.0 (`host/app/schemas/`, `sensor-client/src/protocol.js`): HELLO/REGISTERED/HEARTBEAT(+ACK)/SENSOR_STATUS/LANDMARK_OBSERVATION/DISCONNECT/ERROR; sequence numbers, `captured_at_ms` timestamps, per-landmark structure, coordinate convention (pixel, edge-origin; host converts with `subtract_half_pixel: true`), strict both-direction validation (`test_protocol_validation.py`), `max_message_bytes` limit, backpressure (`websocket_client.js maxBufferedBytes`), reconnect-with-backoff.

### 4.5 E. Performance
- Browser FPS/latency/CPU/memory on a real phone: **UNVERIFIED** — must be measured on hardware (operator page already displays rate and observation ages; use it plus DevTools).
- Host-side processing: measured **synthetically** — capture→published median 3 ms, p95 4 ms (loopback); well inside the 150 ms budget for the host alone. End-to-end (browser→Godot) latency: UNMEASURED.

### 4.6 Phase 1 verdict

**What Phase 1 must have before Phase 2 consumes real data:** working browser streams (HTTPS + permission), ≥2 sensors streaming **un-mirrored** frames with `captured_at_ms` timestamps, verified `flip_handedness` convention in a manual smoke test, and per-sensor stable camera IDs bound for calibration. All software is ready; everything remaining is physical (§6, §15 Stage 1). Missing code: none blocking; body-pose detection is a future addition.

---

## 5. Phase 2 Complete Audit — Calibration and 3D Fusion (critical section)

### 5.1 A. Calibration prerequisites vs the planned board

| Planned | In repo | Verdict |
|---|---|---|
| 9×6 inner corners (10×7 squares) | `calibrate.py --pattern` default `9x6`; docs specify **odd×even so the origin corner is unambiguous** — 9×6 satisfies this | MATCH |
| Square size must match print | `--square-size-m` default 0.04 m with help text "MEASURE the printed square edge"; `docs/host/spatial.md` requires 100% print scale on flat backing | MATCH (user must measure the print) |
| Images at streaming resolution | Enforced in code: `load_samples` rejects size-mismatched images; `calibrate_rig` raises `RESOLUTION_MISMATCH` between reference images and intrinsics; docs require capture "at EXACTLY the resolution/orientation the sensor streams" | MATCH (snap-button PNGs are saved at exact stream resolution) |

No discrepancy found. The repository's defaults already agree with the plan.

### 5.2 B. Calibration tooling (`scripts/calibrate.py` + `host/app/spatial/`)

All 8 subcommands exist and were inspected (`capture, intrinsics, rig, inspect, invalidate, accuracy, selftest, example`):

| Command | Reads | Writes | Real cameras? | Quality gates |
|---|---|---|---|---|
| `capture --device N --out DIR --count --interval` | local `cv2.VideoCapture(device int)` webcam | PNGs | USB/laptop webcam only (untested in CI) | none (capture aid) |
| `intrinsics --images DIR --camera-id ...` | image dir | `calibration/intrinsics/<camera_id>__<W>x<H>.json` | yes | min 10 usable images; RMS ≤ 1.0 px; per-sample ≤ 2.0 px with ≤12 outlier-rejection rounds; coverage ≥ 0.35 and tilt spread ≥ 10° produce **warnings** (not refusals); `fix_k3`; explicit error codes `TOO_FEW_SAMPLES / OPENCV_FAILED / NO_CONVERGENCE / RMS_TOO_HIGH / IMPLAUSIBLE_RESULT` |
| `rig --cameras cid:dir ...` | intrinsics + reference images | `calibration/<rig_id>/<camera_id>.json` (+`history/`) | yes | ≥2 cameras; same board target (`TARGET_MISMATCH`); extrinsic RMS ≤ 2.0 px (`EXTRINSIC_RMS_TOO_HIGH`); `BOARD_BEHIND_CAMERA`; pose-ambiguity warning (<1.5 ratio); per-pair triangulation cross-check of board corners vs known geometry (`rig_check` mean/max mm + ray angle) |
| `inspect` | calibration root | none | — | exit 0 only if ≥ 2 valid, mutually compatible cameras; currently prints `NOT READY ... (have 0)` |
| `invalidate --camera-id` | — | validity flag | — | fusion refuses invalid cameras |
| `accuracy --fusion-log --xyz ...` | `logs/sessions/<id>/fusion.jsonl` | report | yes (physical ground truth) | mean/median/p95/max error, repeatability std, bias |
| `selftest` | synthetic | none | no | full synthetic pipeline table |
| `example` | — | `calibration/example_synthetic/` | no | synthetic-flagged artifacts |

Phone-based capture exists and needs **no development**: the sensor page's **"Save calibration frame (local file)"** button (`index.html` `#snap-btn`, `app.js` `toBlob` download, filename `<label>_<W>x<H>_<time>.png`) saves the current **un-mirrored** frame at exact stream resolution; nothing is uploaded. The user then moves the PNGs into an images directory for `intrinsics`/`rig`.

Supporting modules verified: `calibration_store.py` (atomic save/load, history, invalidation, rig compatibility), `calibration_schema.py` (versioned, validated; **synthetic artifacts refused unless `SAGA_ALLOW_SYNTHETIC_CALIBRATION=1`**), `synthetic.py`.

### 5.3 C. Geometry and triangulation (`host/app/spatial/geometry.py`, 16 tests)

- `CameraModel`, projection with distortion, DLT triangulation, Gauss-Newton refinement (5 iterations default), residual/depth/ray-angle checks, homogeneous-w degeneracy check. Validated by 16 unit tests including synthetic self-consistency (`selftest` reproduces focal 600→601.5, rotation error <0.2°).
- Covered by tests: two-view triangulation, degenerate ray angles, depth bounds, reprojection gating, outlier rejection, half-pixel convention, hand-agreement conflict.
- **Not covered:** real distortion fields, rolling-shutter skew, motion blur — inherently hardware matters.

### 5.4 D. Fusion system (`fusion.py`, `service.py`, `synchronizer.py`, `filters.py`; 32 fusion tests + e2e)

- `FusionEngine`/`FusionService` consume 2-D landmarks + calibration; per-sensor clock-offset correction (heartbeat-estimated), `max_skew_ms 50`, staleness 250 ms, bounded per-sensor buffers (16), out-of-order tolerance, clock-suspect detection.
- Quality = f(reprojection, sync, geometry); status vocabulary `TRACKING_MULTI_VIEW / SYNC_DEGRADED / SINGLE_VIEW_FALLBACK / INSUFFICIENT_VIEWS / TARGET_LOST / FUSION_OUTLIER / GEOMETRY_DEGENERATE / CALIBRATION_REQUIRED`; One-Euro smoothing (15 Hz params); 500 ms hold; track-discontinuity reset (8 m/s).
- **Assumptions only satisfied by synthetic data:** noise-free/controlled landmark statistics; perfectly regular heartbeat-derived clock offsets. Real phones will exercise `SYNC_DEGRADED` paths that synthetic tests touch only unit-wise. Everything needed to *observe* this exists (operator page + `/fusion?recent=` API).

### 5.5 E. Physical calibration readiness (practical)

See §6 for the readiness checklist and `docs/SAGA3D_HUMAN_ACTION_CHECKLIST.md` for the printable version. Summary of requirements fixed by code/docs (nothing invented):

- **Hardware:** ≥2 cameras (phones ideal), one PC on the same LAN, printed 9×6 checkerboard (square size measured), flat backing, stable mounting, even lighting.
- **Intrinsics:** ≥15 frames per camera at exact streaming resolution, varied positions/depths/tilts (quality gates will warn below 35% coverage / 10° tilt spread).
- **Rig:** board static in the workspace; **2–5 reference stills per camera** with the board tilted 20–45°; board and cameras untouched during the whole rig step; the board *defines* the world frame (origin = first inner corner, X along columns, Y along rows, Z = X×Y = into/away per `calibration_tool.py` docstring — Z up out of the board plane).
- **Validation:** `inspect` (≥2 usable cameras), `accuracy` against ≥5 physically measured locations × ≥30 samples (`docs/host/spatial.md` §accuracy).
- **Failure recovery:** explicit error codes above; `invalidate` on camera movement; per-sample rejection reports names+reasons.

### 5.6 F. Phase 2 blockers

| Category | Blockers |
|---|---|
| Software | **none** — all commands exist, are tested synthetically, and refuse bad data with named errors |
| Configuration | `SAGA_CALIBRATION_DIR`/`SAGA_ALLOW_SYNTHETIC_CALIBRATION` defaults are correct for real use (synthetic refused); no changes needed |
| Documentation | complete (`docs/host/spatial.md` operator procedure + §11 hardware checklist); minor: capture-on-phone workflow is described in client UI/docs but not as a numbered recipe in spatial.md |
| Hardware | cameras, board print, mounting, lighting — **the actual blockers** |
| Physical setup | camera placement with overlapping views of the shared volume; stable positions (any movement invalidates extrinsics) |

### 5.7 G. Direct answers

1. **Can the user start physical calibration right now?** YES — software-side, unconditionally (capture → intrinsics → rig → inspect are ready and tested). Physically, they first need the board and two positioned cameras.
2. Blockers to *starting*: none in software; physical materials only (see checklist).
3. Hardware/materials: 2 phones (or 1 phone + 1 webcam), printed 9×6 board with measured square size, flat backing, mounts, Wi-Fi LAN, HTTPS cert (`make_dev_cert.sh`) for phones.
4. Exact commands: see §15 Stage 2 (all real, verified against the repo).
5. Expected outputs: `calibration/intrinsics/<camera>__<W>x<H>.json`, `calibration/default_rig/<camera>.json`, quality fields (RMS, coverage, tilt, rig_check pairs).
6. Success: `inspect` exit 0 with "READY"/≥2 usable cameras; RMS within gates; rig_check mean error small; later `accuracy` vs measured points.
7. After calibration, before "physically validated": real-stream fusion session showing `TRACKING_MULTI_VIEW` with a hand; `accuracy` report vs ≥5 measured locations; sync quality on real phones; both §11 hardware items in `docs/host/spatial.md`.

---

## 6. Phase 2 Physical Calibration Readiness — prioritized checklist

| Bucket | Item | Why / file | Priority |
|---|---|---|---|
| READY TO START | All 8 CLI subcommands | `scripts/calibrate.py` | — |
| READY TO START | Phone frame capture UI | `sensor-client/index.html #snap-btn` + `app.js:180-197` | — |
| READY TO START | Board 9×6 / measured square / streaming resolution | `calibrate.py` defaults + `docs/host/spatial.md` | — |
| MUST PREPARE PHYSICALLY | Print board 100% scale, flat backing, measure square mm | detector needs true metric size | P0 |
| MUST PREPARE PHYSICALLY | 2+ cameras mounted, stable, overlapping views | extrinsics invalid on any camera move | P0 |
| MUST PREPARE PHYSICALLY | HTTPS dev cert for phones | `scripts/make_dev_cert.sh`; camera needs secure context | P0 |
| MUST EXECUTE DURING | ≥15 intrinsic frames/camera; 2–5 tilted reference stills/camera; do not move anything mid-rig | `docs/host/spatial.md`; gates in `calibration_tool.py` | P0 |
| MUST VERIFY AFTER | `inspect` → exit 0, ≥2 usable | `scripts/calibrate.py inspect` | P0 |
| MUST VERIFY AFTER | rig_check pair errors small; warnings resolved | `calibration/*.json quality.rig_check` | P1 |
| MUST VERIFY AFTER | `accuracy` vs ≥5 measured locations × ≥30 samples | `calibrate.py accuracy`; `docs/host/spatial.md` | P1 |
| MUST COMPLETE BEFORE P3 HW | fusion session shows `TRACKING_MULTI_VIEW` on real hands; sync healthy (`SYNC_DEGRADED` rare) | operator page, `/fusion` API | P1 |

**Answer to "can it start now": YES — after the physical items in `MUST PREPARE PHYSICALLY`.**

---

## 7. Phase 3 Complete Audit — Coordination and Gesture

### 7.1 Agent architecture — IMPLEMENTED (synthetic)
`GestureAgent` (deterministic FSM `IDLE→HOVER→GRABBED→RELEASED→IDLE`, one transition per call, bounded loss handling, `acknowledge()` for GRAB/RELEASE acks, audit log) — `host/app/gesture/agent.py`; `HandSample.from_fusion_result` conversion (validity, xyz, pinch ratio, track epoch, calibration flag) — same file; `InteractionObject`, `GestureOutput`, `InteractionEvent` 1.0 + deduper — `gesture/events.py`; `SessionCoordination` adapter consuming live fusion — `coordination/host_adapter.py`; scoring/set-selection/lease/adaptation — `coordination/*` (11+11+6 tests, 9-scenario demo passes).

### 7.2 Gesture recognition — IMPLEMENTED (synthetic)
Scale-aware pinch (thumb-tip↔index-tip distance / palm length **in the same view**), hysteresis (enter 0.25 < exit), confirm_ms evidence window, reach hysteresis, confidence gating, stale-landmark rejection, bounded grab-loss freeze then safe `GRAB_CANCELLED`, track-discontinuity cancel, 30 Hz `MOVE_TARGET` cap. 43 machine+pinch tests pass. **Real-gesture accuracy/threshold tuning: HARDWARE REQUIRED** — every threshold is a documented starting point (`config/gesture.yaml`).

### 7.3 Event protocol — IMPLEMENTED (synthetic)
`INTERACTION_EVENT 1.0` versioning, event IDs, acks (`require_adapter_ack: true` in `config/world.yaml`, 500 ms ack timeout → safe default = no grab), dedup (`EventDeduper`), ordering via sequence numbers, session-scoped consistency. Acks/dedup covered by tests.

### 7.4 Integration with Phase 2 — IMPLEMENTED (synthetic)
Phase 3 consumes actual `FusionService` output through `SessionCoordination`/`HandSample.from_fusion_result`; units (metres, board frame), timestamps (`sample_ms`), missing observations (`valid=false`), and tracking loss propagation are part of the contract and tested. Continuous operation on live fused data was exercised synthetically end-to-end (e2e 11/11 with the gesture path enabled). **Never on real camera data.**

### 7.5 Real-world validation
All gesture tests are synthetic/simulated. No real user gesture has ever been classified. Required hardware tests: real pinch repetition rates (false-positive/negative), real tracking-loss timing, real hover reach distances → threshold tuning session.

**What Phase 2 must deliver before meaningful Phase 3 hardware testing:** a stable calibrated rig producing `TRACKING_MULTI_VIEW` wrist positions at a healthy rate with real hands (Stage 3 gate), plus measured sync skew within 50 ms. Without that, gesture states will just churn on `TARGET_LOST`.

---

## 8. Phase 4 Complete Audit — Bridge, Transform, Godot

### 8.1 Backend bridge — IMPLEMENTED (synthetic)
`adapter/saga4_world/`: `attach.py` (combined app; `/ws/world` route; 20 Hz tick; session attach/detach wrapping), `bridge.py` (SessionWorld per session), `server.py` (WorldSocketSession, hello timeout 5 s, heartbeat 15 s), `protocol.py` (strict both-direction validation; one Godot client per session — `WORLD_CLIENT_EXISTS` fatal on second connect), bounded queues (`event_buffer_max 256` discrete events never dropped while connected; `pose_slot_bound 2` collapsing), backpressure, `transform.py` (validated orthonormal R, det=+1, fingerprint, volume flag/rejection, fail-closed on non-finite), `status.py`. 54 adapter tests (50 unit + 4 real-uvicorn e2e) pass.

### 8.2 Coordinate transformation — IMPLEMENTED, UNVALIDATED
`godot = scale*(R@rig)+t`; default `R = [[1,0,0],[0,0,1],[0,-1,0]]`, `t = [0,0,-1.6]` — a **starting point**; `docs/coordinates.md` mandates the two-reference-point physical verification before any hardware session (fingerprint resets on change). Rig frame from the board: X along columns, Y along rows, Z up — matches `calibration_tool.py`. Units: metres everywhere, scale 1.0. Consistency verified on paper; **physical verification HARDWARE REQUIRED**.

### 8.3 Godot project — code present, execution UNVERIFIED (Godot 4.3 NOT FOUND)
- `godot/project.godot` (config_version=5, main scene `res://scenes/main.tscn`, Godot 4.3 per docs).
- `world_client.gd`: full signal set (pose_valid/invalid, hover, grab request/confirmed/move/release/cancelled, tracking_lost, host state/errors, world_ready, connected_changed), bounded reconnect 1→5 s, heartbeat 5 s, session from CLI `--session=`, fatal-error stop policy. **The earlier `WebSocketPeer.poll()` bug is fixed** (commit `d5a68be`).
- `main.gd`: all signals wired to handlers; session id from args; status UI updates.
- `hand_marker.gd`, `grabbable_cube.gd`, `status_ui.gd`: marker movement, grabbable cube, status panel.
- **No Godot script test / headless check was ever executed** (no binary). Every Godot behaviour is UNVERIFIED until `godot --headless --check-only` + an interactive run on the user's machine.

### 8.4 Actual interaction — implemented in code, unproven end-to-end
Receiving positions, marker display, hover, grab request/ack, move at ≤30 Hz, release, tracking-loss (marker hidden + tracking_lost signal), disconnect mid-grab (local release + OBJECT_STATE re-declaration on re-HELLO), invalid-input recovery (host fail-closed + Godot parse guard). All inspected in the scripts; none observed in a running Godot.

### 8.5 Validation
Which tests exist and ran: 54 adapter tests pass (Python side). Godot availability: **NOT FOUND**. Headless validation: impossible here; exact commands in `docs/setup.md` (`--headless --check-only` pattern and interactive F5 run). Any end-to-end with real hardware: none.

**What must be completed before real hand movements control Godot objects:** (1) real calibration + fusion session (Stages 2–3), (2) install Godot 4.3 and validate the project (headless check, then interactive), (3) two-reference-point transform verification, (4) real pinch producing GRAB/CONFIRM/MOVE/RELEASE (Stage 5).

---

## 9. Cross-Phase Integration Audit

| Connection | Implemented | Tested | Test type | Remaining problems |
|---|---|---|---|---|
| Cameras → P1 (browser→host) | Yes | Yes | **synthetic** (simulated WS clients over real wire) | Real phone/browser stream never tested; HTTPS + permission flow physical |
| P1 → P2 (obs→fusion) | Yes | Yes | synthetic (unit + live e2e 11/11) | Real distortion/skew/clock-offset behaviour unmeasured; real calibration absent |
| P2 → P3 (fusion→coordinator/gesture) | Yes | Yes | synthetic (unit + engine-integration tests) | Real threshold behaviour unknown |
| P3 → P4 (events→bridge) | Yes | Yes | synthetic (adapter tests incl. ack discipline) | Same |
| P4 → Godot (WS→scene) | Yes (both ends coded) | **Python side only** | synthetic | **Godot side never executed**; no real hardware end-to-end ever |
| Whole chain → user interaction | coded | no | — | Full real-hardware run outstanding |

Schemas/units/timestamps/IDs are compatible by contract tests; errors and reconnections are handled on every link (bounded reconnects, ack timeouts, safe-stop). Nothing was marked verified merely because both sides have unit tests — the live synthetic e2e and (pending) hardware runs are the real evidence.

---

## 10. Full System End-to-End Readiness

- **Hardware:** cameras/phones, LAN, board, mounts, lighting — all **not yet arranged** (user action).
- **Software:** Python 3.12.4 ✓, Node 20.16.0 ✓ (tests only), deps pinned ✓, MediaPipe local assets ✓, OpenCV ✓; **Godot 4.3 ✗ (not installed)**.
- **Calibration:** tooling ready; **no real artifacts** (`inspect` = 0 usable).
- **Runtime:** single-process startup verified synthetically (`run_host.py` + smoke); startup order documented (runbook §); recovery paths coded (reconnect/hold/invalidate); shutdown clean.
- **Performance:** no real-hardware measurements exist anywhere. Host-only synthetic latencies exist (median 3 ms capture→publish). To measure the rest: operator-page rates, `/fusion` ages, Godot frame counter, `accuracy`/fusion.jsonl timing fields — the instruments already exist; only the hardware is missing.
- **Reliability:** every failure class listed in §9/§11 has a coded handler (sensor drop → degrade/lost; Godot drop → local release + re-hello; camera move → invalidate; ack timeout → safe no-grab). Repeated real-world behaviour: UNVERIFIED.

---

## 11. Hardware and Software Prerequisites

| Item | Status | Note |
|---|---|---|
| PC + Python venv (pinned reqs) | ready | `.venv` works, 411 tests |
| Node.js | ready | tests only |
| Godot 4.3 | **MISSING** | user must download; verify with `--version`, then headless check |
| 2+ cameras (phones ideal) | user | secure context needed (HTTPS) |
| Wi-Fi/LAN | user | same network as PC |
| 9×6 printed checkerboard | user | measure square size after printing |
| HTTPS dev cert | script ready | `bash scripts/make_dev_cert.sh <LAN-IP>` |
| Mounts / tripod / stands | user | extrinsics invalidate on movement |
| Lighting | user | even, no glare on board |

---

## 12. Master Missing-Work Register

| ID | Phase | Task | Status | Priority | Blocking? | Dependencies | Location | Verification |
|---|---|---|---|---|---|---|---|---|
| HW-01 | 2 | Print 9×6 board, measure square size | HARDWARE REQUIRED | P0 | Yes | none | `calibrate.py --square-size-m` | tape-measure value used in commands |
| HW-02 | 2 | Mount & position ≥2 cameras, stable | HARDWARE REQUIRED | P0 | Yes | HW-01 | physical | cameras hold position across rig capture |
| HW-03 | 1 | LAN + HTTPS setup for phones | HARDWARE REQUIRED | P0 | Yes | none | `scripts/make_dev_cert.sh` | sensor page loads via `https://<LAN-IP>:8765` |
| HW-04 | 2 | Capture ≥15 intrinsic frames/camera | HARDWARE REQUIRED | P0 | Yes | HW-01..03 | `calibrate.py capture` or snap-button | images exist at stream resolution |
| HW-05 | 2 | Run intrinsics per camera | PARTIALLY (tool ready, unrun) | P0 | Yes | HW-04 | `calibrate.py intrinsics` | RMS ≤1.0 px JSON |
| HW-06 | 2 | Rig calibration (2–5 tilted stills each) | PARTIALLY (tool ready, unrun) | P0 | Yes | HW-05 | `calibrate.py rig` | `default_rig/*.json` + rig_check |
| HW-07 | 2 | `inspect` → READY | UNVERIFIED | P0 | Yes | HW-06 | `calibrate.py inspect` | exit 0, 2 usable |
| HW-08 | 2 | accuracy vs measured points (≥5 loc × 30 samples) | UNVERIFIED | P1 | No | HW-07 | `calibrate.py accuracy` | report with mm errors |
| HW-09 | 2 | Real-stream fusion session `TRACKING_MULTI_VIEW` | UNVERIFIED | P1 | Yes (for P3 HW) | HW-07 | run_host + browsers | operator page status |
| HW-10 | 1 | Verify `flip_handedness` convention with real camera | UNVERIFIED | P1 | No | HW-03 | `config/camera.yaml`; manual smoke | labels match visual check |
| HW-11 | 1 | Measure real browser FPS/CPU/latency | UNVERIFIED | P2 | No | HW-03 | operator page + DevTools | recorded numbers |
| HW-12 | 4 | Install Godot 4.3 | HARDWARE REQUIRED | P0 | Yes | none | `docs/setup.md` | `godot --version` |
| HW-13 | 4 | Headless project check | UNVERIFIED | P0 | Yes | HW-12 | `--headless --check-only` | no script errors |
| HW-14 | 4 | Two-reference-point transform verification | UNVERIFIED | P1 | Yes (for correct interaction) | HW-07, HW-13 | `docs/coordinates.md` §two-point | both points agree |
| HW-15 | 3 | Real gesture tuning session (pinch rates, reach, loss timing) | HARDWARE REQUIRED | P1 | No | HW-09 | `config/gesture.yaml` | tuned values committed |
| HW-16 | all | Full end-to-end real-hardware demo | UNVERIFIED | P1 | Yes (final) | HW-09..15 | runbook | grab/move/release observed |
| SW-01 | 1 | Body/pose landmarks (project mentions body motion) | MISSING | P2 | No | — | only `hand_landmarker` exists | new model + pipeline extension |
| SW-02 | 1 | Explicit camera device picker (enumerateDevices UI) | MISSING | P3 | No | — | `camera.js`/`index.html` | device selector works |
| SW-03 | 2 | Numbered "phone capture recipe" in spatial.md | PARTIALLY (info exists, scattered) | P3 | No | — | `docs/host/spatial.md` + checklist | recipe added |
| SW-04 | 2 | Real-phone sync/clock-offset field validation | UNVERIFIED | P1 | No | HW-09 | `synchronizer.py` | skew stats in fusion log |
| SW-05 | 3 | Runtime gesture-threshold tuning controls (UI/config reload) | MISSING (manual config edit works today) | P3 | No | — | `config/gesture.yaml` | hot-reload or page control |
| SW-06 | 4 | Replace runtime monkey-patching with explicit hooks | PARTIALLY (works, validated; refactor optional) | P3 | No | — | `adapter/saga4_world/attach.py` | tests stay green |
| SW-07 | 4 | Godot-side automated script test | MISSING | P3 | No | HW-12 | `godot/` | headless GUT/`--check-only` run |
| SW-08 | 2 | Multi-camera (>2) epipolar coverage test on hardware | UNVERIFIED | P3 | No | HW-06 | documented 2-view limitation | accuracy improves with 3rd cam |
| SW-09 | all | End-to-end latency budget measurement (browser→Godot) | UNVERIFIED | P2 | No | HW-16 | fusion.jsonl + Godot timing | measured p95 vs 150 ms budget |

**Classification key:** P0 = blocks first real run; P1 = needed for first meaningful demo/validation; P2 = reliable repeated operation; P3 = improvement.

---

## 13. Critical Blockers (top of the queue)

1. **No real calibration data** (`inspect` = 0 usable cameras) — everything downstream (fusion on real data, gesture on real data, transform verification, Godot demo) is blocked on Stages 2–3.
2. **Godot not installed** — Phase 4 cannot even be smoke-run.
3. **No real camera session ever run** (Phase 1 on hardware, HTTPS/permissions, handedness check).
4. Physical materials absent: board, mounts, lighting.

---

## 14. Exact Phase 2 Starting Checklist

(Checklist version for humans lives in `SAGA3D_HUMAN_ACTION_CHECKLIST.md`; commands in §15 Stage 2.)

1. Print the board at 100%, glue to flat backing, **measure** the square edge (mm).
2. Mount two cameras (phones) stably with overlapping views of the intended interaction volume.
3. Generate HTTPS cert; start host; open sensor page on both cameras; join the session.
4. Verify both sensors registered (operator page) and note each camera's exact stream `WxH`.
5. Capture ≥15 board frames per camera via the snap button (vary position/depth/tilt).
6. Copy each camera's PNGs into its own folder.
7. Run `intrinsics` per camera with the **measured** square size.
8. Place the board in the workspace, leave everything untouched; capture 2–5 tilted stills per camera.
9. Run `rig` with all cameras.
10. Run `inspect` → must exit 0 with both cameras usable.
11. Review warnings (coverage/tilt/ambiguity) and `rig_check` pair errors; retake weak sets.
12. Run a live session: wave a hand in front of both cameras; confirm `TRACKING_MULTI_VIEW`.

---

## 15. Full Execution Roadmap (Stages 1–6)

**Stage 1 — Prepare Phase 2 (physical).** Prereq: repo runs (`pytest` green). Actions: HW-01..03. Pass: cameras stream on the operator page. Fail→fix: HTTPS/permission/LAN issues per runbook.

**Stage 2 — Execute Physical Calibration.**
1. Board prepared & measured (HW-01).
2. Cameras mounted (HW-02).
3. Camera identities confirmed (operator page; bind sensor↔camera).
4. Streaming resolution confirmed (operator page / PNG filename `WxH`).
5. Capture: `bash scripts/calibrate.py capture --device N --out captures/cam_left --count 15 --interval 1.5 --pattern 9x6 --square-size-m <MEASURED>` (webcam) **or** snap-button per phone.
6. Intrinsics: `.venv\Scripts\python scripts\calibrate.py intrinsics --images captures/cam_left --camera-id phone_left --pattern 9x6 --square-size-m <MEASURED>` (repeat right).
7. Rig: capture 2–5 tilted reference stills per camera, then `... calibrate.py rig --cameras phone_left:captures/rig_left --cameras phone_right:captures/rig_right --rig-id default_rig --pattern 9x6 --square-size-m <MEASURED>`.
8. Quality: read RMS/coverage/tilt/`rig_check` from outputs; warnings addressed.
9. Saved automatically to `calibration/` (atomic, with history).
10. Verify loading in runtime: restart host → `GET /api/sessions/{id}/calibration` shows both usable; `inspect` exit 0.
Expected outputs as in §5.2. Pass criteria: exit 0 + no `RMS/EXTRINSIC` refusals + both cameras compatible. Failure: named error codes → retake the named weak set (per-sample rejection lists filenames).

**Stage 3 — Validate Phase 2 on real hardware.** Live fusion session with a real hand: status `TRACKING_MULTI_VIEW`, plausible 3-D coordinates (metres, board frame); skew within 50 ms; `accuracy` vs ≥5 measured points × ≥30 samples; two-reference-point transform check (`docs/coordinates.md`). Automatable: `accuracy` report, fusion.jsonl stats. Physical: placing measured points, judging stability. **Gate for Stage 4.**

**Stage 4 — Validate Phase 3.** With Stage 3 running: perform repeated real pinches near the cube; observe `HOVER_ENTER → GRAB_REQUEST` in operator/gesture logs; count false positives/negatives; tune `config/gesture.yaml` (pinch ratios, confirm_ms, reach). Pass: repeatable grab attempts with correct transitions; loss handling observed (cover camera → TRACKING_LOST/GRAB_CANCELLED). **Gate for Stage 5.**

**Stage 5 — Validate Phase 4.** Install Godot (HW-12), headless check (HW-13), run `godot --path godot -- --session=<id>` with host up; verify `WORLD_READY`, marker follows hand (transform verified per HW-14), hover, GRAB_CONFIRMED, cube follows MOVE_TARGET, RELEASE returns cube. Pass: a full grab-move-release driven by the real hand.

**Stage 6 — Full System Test.** Complete runbook sequence from cold start (camera → … → release in Godot); record latency/failure/recovery observations (SW-09). Pass = the entire pipeline works end-to-end repeatedly; this is the project's "works in the real world" milestone.

---

## 16. Test Evidence and Validation Results

Executed during **this audit** (working dir `D:\collega active\phases\saga-3d-phase-4\`):

| Command | Result | Type |
|---|---|---|
| `.venv\Scripts\python.exe -m pytest` | **411 passed, 0 failed** (52.14 s) | synthetic |
| `cd sensor-client && node --test tests/*.test.mjs` | **16 pass / 0 fail** | synthetic |
| `.venv\Scripts\python.exe scripts\calibrate.py selftest` | intrinsic RMS 0.053–0.057 px (synthetic); triangulation error table consistent with docs | synthetic |
| `.venv\Scripts\python.exe scripts\calibrate.py inspect` | `NOT READY: need at least 2 valid, compatible calibrated cameras (have 0)`; no writes (git clean) | read-only |
| `where godot` | not found | environment |

Previously recorded (consolidation session, `docs/PHASE4_MAIN_WORKSPACE_MIGRATION_REPORT.md`): smoke 8/8, demo 9/9, e2e 11/11, independence test. None of these are hardware tests.

---

## 17. Risks and Technical Recommendations

- **Two-view epipolar limitation:** with exactly 2 cameras, errors along the epipolar line are invisible; the accuracy check vs measured points is the practical mitigation. A 3rd camera later would strengthen geometry (SW-08).
- **Clock sync on real phones:** heartbeat-estimated offsets are synthetic-validated only; expect `SYNC_DEGRADED` tuning (SW-04).
- **Gesture thresholds will need a tuning session** on real hands — budget for it; do not skip Stage 4.
- **Transform defaults are guesses until HW-14** — never "fix" misalignment inside Godot; adjust `config/world.yaml`.
- **Camera movement invalidates extrinsics** — physical stability is a system requirement, not a nicety.
- **Body tracking is missing** if the broader project goal needs it (SW-01) — plan as a later work item.

---

## 18. Final Readiness Verdict (mandatory questions)

**Phase 1**
- Ready to provide real sensor data? **Yes, in software**; never yet demonstrated with a real camera (HARDWARE REQUIRED). Remaining: real-stream smoke test, handedness check, HTTPS/LAN setup.
- Must verify before Phase 2 relies on it: stable IDs, un-mirrored frames at known resolution, plausible timestamps, real FPS.

**Phase 2**
- Can physical calibration start now? **YES** (software unconditionally ready; physical prep items HW-01..03 first).
- Exact blockers: none in software; board/cameras/mounting physically.
- Hardware/materials: 2 phones or phone+webcam, measured 9×6 board, mounts, LAN, HTTPS cert.
- Commands: `capture`/snap-button → `intrinsics` → `rig` → `inspect` (§15 Stage 2).
- After calibration remains: accuracy report, real-stream fusion validation, sync observation.
- Evidence to declare physically validated: `inspect` exit 0 + `TRACKING_MULTI_VIEW` on real hands + `accuracy` report vs measured points + rig_check numbers recorded.

**Phase 3**
- Foundation present? **Yes.** Integrated with Phase 2? **Yes (contract + synthetic live e2e).** Validated on real fused data? **No.** Needed first: Stage 3 gate, then a tuning session.

**Phase 4**
- Bridge implemented? **Yes, tested.** Godot integration verified? **No — Godot absent; scripts never executed.** Real gestures controlling objects? **Not yet possible** (needs Stages 2–5). To prove: install Godot, headless check, transform verification, interactive demo.

**Entire project**
- Can it run real-cameras→Godot today? **No.** Prevents it: no calibration, no Godot, no real-camera session.
- Shortest safe path: Stage 1 → 2 → 3 → 4 → 5 → 6 (§15), strictly in order.
- Order of tasks: HW-01..03 → HW-04..07 → HW-09 (+HW-08, HW-10) → Stage 4 (HW-15) → HW-12..14 → HW-16.
- **Next single action: print and measure the 9×6 checkerboard, then mount two cameras and run Stage 2 capture.**
