# PHASE 1 — HUMAN ACTION CHECKLIST (executable, in order)

**Goal:** real cameras streaming into the host, stably, with verified conventions.
**Do these in sequence; do not skip prerequisites.** Every item says what to do, with what, expected output, success/failure handling.

## Prerequisites (before touching devices)

- [ ] **P1-0.1 Confirm the venv is healthy.**
      Tool: terminal in `D:\collega active\phases\saga-3d-phase-4`. Command: `.venv\Scripts\python.exe -m pytest`
      Expect: `411 passed` (or later count ≥ 411). Decide: green = continue.
      Fail: `.venv\Scripts\python.exe -m pip install -r requirements.txt`, re-run.

- [ ] **P1-0.2 Confirm no real calibration is claimed yet.**
      Command: `.venv\Scripts\python.exe scripts\calibrate.py inspect`
      Expect: `NOT READY ... (have 0)`. This is correct pre-Phase-2 state.

## Network & server

- [ ] **P1-1. Put the PC and both camera devices on the same Wi-Fi/LAN.**
      Devices: PC, phone A (camera 1), phone B (camera 2).
      Check: from phone A's browser, later steps' URL must open (not time out).
      Fail: connect both to the same router/hotspot; disable AP isolation on the router if devices cannot see each other.

- [ ] **P1-2. Find the PC's LAN IP.**
      Command (Windows): `ipconfig` → note IPv4 (e.g. `192.168.1.42`).

- [ ] **P1-3. Generate the HTTPS dev certificate.**
      Tool: Git Bash. Command: `bash scripts/make_dev_cert.sh 192.168.1.42` (your IP).
      Expect: `certs/dev.crt` + `certs/dev.key` created.
      Fail: OpenSSL missing → install Git for Windows (includes it) and retry.

- [ ] **P1-4. Enable TLS in the host config (`.env`).**
      Tool: text editor. Action: copy `.env.example` to `.env` (if not present) and set:
      `SAGA_TLS_CERT=certs/dev.crt` and `SAGA_TLS_KEY=certs/dev.key` (create the file if the lines don't exist).
      Success: lines present, no typos. **(This is a configuration file you create; the audit did not modify it.)**

- [ ] **P1-5. Start the host.**
      Command: `.venv\Scripts\python scripts\run_host.py --session demo1`
      Expect: log line containing `host_started` and the `Operator: https://...` line; no traceback.
      Fail: port busy → rerun with `--port 8766` and use that port everywhere below; config error → the message names the YAML file.

- [ ] **P1-6. Verify server reachability.**
      Tool: PC browser. URL: `http://127.0.0.1:8765/api/health`.
      Expect: JSON with OK/health content.

## Cameras

- [ ] **P1-7. On phone A open the sensor page.**
      URL: `https://192.168.1.42:8765/client/` (your IP; accept the self-signed-certificate warning explicitly).
      Enter session code: `demo1`. Choose facing camera (front `user` / back `environment` — decide which physical camera this device is and stay consistent). Press **Start**.
      Expect: live video preview + connection indicator.
      Fail: camera blocked → the page must be HTTPS (step P1-4/5); permission prompt never shown → re-enable camera for the site in browser settings, reload.

- [ ] **P1-8. Grant camera permission when the browser asks.**
      Success: preview shows.

- [ ] **P1-9. Repeat P1-7/P1-8 on phone B.**

- [ ] **P1-10. Verify registration on the operator page.**
      Tool: PC browser. URL: `http://127.0.0.1:8765/client/operator.html`
      Expect: both sensor rows: state `online`, Rate > 0 Hz, Last-obs age small (tens of ms), Gaps 0/low, Reconnects not increasing.
      Fail: row absent → wrong session code or device on different network; rate 0 → vendor model not loaded (check `https://...:8765/client/vendor/mediapipe/vision_bundle.mjs` opens); reconnect loop → Wi-Fi drop, move devices closer.

- [ ] **P1-11. Verify the handedness convention.**
      Action: raise your **right** hand in front of one camera.
      Expect: the reported hand label is **Right** (`flip_handedness: true` in `config/camera.yaml` swaps MediaPipe's selfie-mirror labels; this manual check is the documented smoke test).
      Fail: label is Left → do NOT edit config silently; record the discrepancy — Phase 2's `require_hand_agreement` and Phase 3 use these labels, so it must be resolved before calibration.

- [ ] **P1-12. Record each camera's streaming resolution.**
      Where: operator page camera column, or press "Save calibration frame" once per device and read the PNG filename `..._<W>x<H>_...png`.
      Action: write down `camera A = WxH`, `camera B = WxH` — Phase 2 requires calibration images at exactly these resolutions.

- [ ] **P1-13. Stability run (10 minutes).**
      Action: leave both cameras streaming with a hand occasionally in view.
      Success: no reconnect storm; obs ages stay small; rate steady.
      Fail (isolated drop): check Wi-Fi strength; battery-saver on phones may throttle the browser — keep screens awake during sessions.

- [ ] **P1-14. Record real performance numbers.**
      Where: operator page (rate Hz), browser DevTools performance tab on one phone (FPS/CPU).
      Action: write down: FPS, typical obs age, any reconnects. These are Phase 1's performance evidence (nothing was measured before — nothing may be invented).

## Evidence to keep for handover

- Operator page screenshot with both sensors online.
- The resolution notes (P1-12), handedness result (P1-11), performance numbers (P1-14).
- Host log excerpt showing two `sensor_registered`-class events and a clean 10-min window.
