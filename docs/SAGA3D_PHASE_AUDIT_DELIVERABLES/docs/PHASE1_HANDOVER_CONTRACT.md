# PHASE 1 — HANDOVER CONTRACT → Phase 2

**From:** Phase 1 owner (sensor acquisition) · **To:** Phase 2 owner (calibration & 3D fusion)
**Gate at writing:** IMPLEMENTATION COMPLETE — NOT OPERATIONALLY VERIFIED. **Handover is NOT granted yet.**

## 1. Must be implemented before completion
Nothing blocks handover in code. All Phase 1 software (acquisition, registration, protocol, reconnection, calibration-frame capture aid) is implemented and synthetic-verified in the consolidated repo.

## 2. Must be configured
- `.env` with `SAGA_TLS_CERT`/`SAGA_TLS_KEY` (HTTPS for phone cameras).
- Per-camera facing-mode choice recorded (front/back per physical device).
- Session id convention agreed with Phase 2 (e.g. `demo1`).

## 3. Human must physically do
- LAN + HTTPS cert (`scripts/make_dev_cert.sh <LAN-IP>`).
- Start host; open `/client/` on each camera; grant permissions.
- Verify handedness convention manually (right hand → "Right").
- Record each camera's streaming WxH and real FPS/latency numbers.
- 10-minute stability run.

## 4. Real-world demonstration that must succeed
**Demo D1:** two real cameras streaming simultaneously into one session for ≥10 minutes with stable registration (no reconnect storms, obs ages small, rate > 0) — observed on `client/operator.html`.

## 5. Output Phase 2 receives (the actual interface — derived from the code, not assumed)
- **WebSocket stream** of `LANDMARK_OBSERVATION` messages (protocol 1.0) on `/ws/sensor`: per-landmark pixel coordinates + confidences, `sensor_id`, `sequence_number`, **`captured_at_ms`** (per-sensor clock), handedness label.
- **Sensor registry state** per session (`/api/sessions/{id}`): sensor ids, online/degraded state, rates, ages.
- **Calibration-frame capture aid**: sensor-page "Save calibration frame" button → local PNGs named `<label>_<W>x<H>_<time>.png` at exact stream resolution (Phase 2's image source for phones).
- **Clock-sync substrate**: heartbeat cadence Phase 2's synchronizer uses to estimate per-sensor offsets.

## 6. Contracts that must be respected
- Protocol version `1.0` both directions; strict validation in `host/app/schemas/` — Phase 2 must consume observations *only* through `FusionService` (2-D pixel landmarks + `captured_at_ms`), never MediaPipe's model-space 3-D points (`docs/host/spatial.md`).
- Landmark pixel convention: edge-origin from MediaPipe; host-side conversion `subtract_half_pixel: true` stays in Phase 2's config — Phase 1 must keep sending raw un-mirrored pixels.
- Handedness labels must match physical reality (verified in demo D1) or the discrepancy recorded and handled before Phase 2's rig calibration.

## 7. Documentation delivered with handover
- This contract + `PHASE1_COMPLETION_AUDIT.md`.
- Handover evidence pack (below).
- `docs/setup.md` §(HTTPS, client) already covers the operational steps.

## 8. Tests & evidence accompanying the handover
- pytest 411 + node 16 green (recorded).
- **D1 recording**: operator-page screenshot + ≥10-min session log showing both sensors online, stable.
- Recorded values: per-camera WxH, handedness check result, FPS/obs-age numbers, reconnect count.
- Known-limitations list (§9) acknowledged by Phase 2 owner.

## 9. Known limitations that MAY be handed over
- No body/pose landmarks (hand-only pipeline today) — Phase 2 fuses `wrist` only; no impact.
- No per-device camera picker (facing-mode selection).
- Performance numbers are initial measurements, not optimized baselines.
- Phone clock offsets are heartbeat-estimated; Phase 2's synchronizer owns their correction (its `SYNC_DEGRADED` handling is the designed response).

## 10. Issues that MUST NOT be passed on as unfinished work
- Unstable reconnect loops, zero-rate sensors, wrong session binding — these are Phase 1 defects.
- HTTPS/permission failures — environment setup, Phase 1's responsibility.
- Handedness mismatch left unrecorded — labels feed Phase 2 geometry (`require_hand_agreement: true`).

## Acceptance criteria for READY FOR HANDOVER
All of `PHASE1_HUMAN_ACTION_CHECKLIST.md` items P1-1…P1-14 checked, demo D1 succeeded, evidence pack archived. Until then the gate remains **IMPLEMENTATION COMPLETE — NOT OPERATIONALLY VERIFIED**.
