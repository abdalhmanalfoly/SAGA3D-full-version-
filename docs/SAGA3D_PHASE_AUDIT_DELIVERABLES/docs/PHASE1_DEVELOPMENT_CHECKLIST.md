# PHASE 1 — DEVELOPMENT CHECKLIST (code tasks only)

**Honest scope:** Phase 1's software is functionally complete for the current pipeline (hand/wrist tracking). The items below are NOT required before Phase 1's first real-hardware handover; they are grounded in repository evidence and ordered by relevance. Anything speculative is labelled **unverified concern**.

## DEV-P1-1 — Camera device picker (optional, P3)
- **Problem:** camera selection is facing-mode only (`config/camera.yaml facing_mode: user|environment`); on a phone with both cameras usable, the user cannot pick an exact device. `enumerateDevices` is never called in `sensor-client/src/camera.js`.
- **Affected files:** `sensor-client/src/camera.js`, `sensor-client/index.html`.
- **Implementation:** after permission, call `navigator.mediaDevices.enumerateDevices()`, populate a `<select>` with `videoinput` entries, pass `deviceId: {exact}` into the existing `getUserMedia` constraints.
- **Why for real operation:** with 2 phones it's workable today (one tab each); it becomes necessary only if a single device must host two cameras.
- **Dependencies:** none.
- **Acceptance criteria:** user can select a specific camera and the stream switches to it; `camera.js` unit tests still pass (16/16).
- **Evidence:** manual device switch demo + node test run.

## DEV-P1-2 — Body/pose landmarks (P3, scope expansion)
- **Problem:** the project's stated goal includes body movement, but only the hand model exists (`config/camera.yaml model.name: hand_landmarker`); fusion targets are `[wrist]` (`config/fusion.yaml`).
- **Affected files:** `config/camera.yaml` (add pose model block), `sensor-client/src/landmark_detector.js` (second detector), `config/fusion.yaml` (extra targets), possibly `host/app/spatial/service.py` target handling.
- **Implementation:** add MediaPipe pose landmarker with local vendor assets (extend `scripts/fetch_assets.sh`), stream pose landmarks on the same observation message family (schema check in `host/app/schemas/`), extend fusion targets.
- **Dependencies:** none for software; real-hardware validation after.
- **Acceptance criteria:** pose landmarks visible in operator page + fusion produces estimates for a chosen body target; all existing tests stay green.
- **Evidence:** synthetic e2e extension + real-camera observation.
- **Label:** grounded gap (hand-only today), not a regression.

## DEV-P1-3 — Observability aid for real-device performance (P2, measurement helper)
- **Problem:** no real-hardware performance numbers exist anywhere (operator page shows rates/ages, but nothing aggregates FPS/CPU/latency across devices for the handover evidence).
- **Affected files:** new small script (e.g. `scripts/perf_report.py`) reading `logs/sessions/<id>/` event/fusion JSONL; optionally a browser-side FPS counter in `sensor-client/src/sensor_state.js`.
- **Implementation:** aggregate per-sensor rate, obs-age percentiles, gap counts, reconnect counts over a time window; print a table.
- **Why:** Phase 1 handover requires recorded performance evidence; today a human must eyeball the operator page.
- **Dependencies:** a real session having run (logs exist).
- **Acceptance criteria:** running it on a real session log produces the table.
- **Evidence:** script output on a captured log.

## Explicitly NOT broken — do not rework
- Protocol validation, registration, backpressure, reconnect backoff: implemented and tested (16 node tests; host protocol/registration suites within 411).
- Local MediaPipe assets: present, served locally, smoke-verified — **no CDN dependency, no work needed** unless a fresh clone (`bash scripts/fetch_assets.sh`).
- No placeholders, no duplicate implementations, no obsolete modules found in Phase 1 ownership areas.
