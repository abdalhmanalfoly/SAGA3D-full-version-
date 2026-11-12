# SAGA 3D — Real-World Runbook (operational startup, Phase 1 → Phase 4)

**How to use:** follow the 15 steps in order from a cold machine. Each step says who does it (**Agent** = possible for an AI assistant in this repo; **Human** = physical/manual), the exact action, expected output, success indicator, and recovery. Nothing here is invented — every command is taken from the repository.

**Standing prerequisites (once):** Python venv working (`411 passed`), Godot 4.3 installed (Step 12 gate), HTTPS cert generated, board calibrated (Steps 1–10 cover calibration on first run; after calibration is done, start at Step 3).

---

## Step 1 — Prepare the computer (Human)
- **Action:** confirm `.venv` exists; run `.venv\Scripts\python.exe -m pytest` once (expect `411 passed`).
- **Expected:** green suite. **Success:** yes. **Failure:** `pip install -r requirements.txt` into the venv (`.venv\Scripts\python -m pip install -r requirements.txt`).

## Step 2 — Connect the cameras to the network (Human)
- **Action:** PC + all camera devices on the same LAN; generate TLS cert if not done: `bash scripts/make_dev_cert.sh <LAN-IP>`; set `SAGA_TLS_CERT`/`SAGA_TLS_KEY` in `.env`.
- **Success:** cert files exist; `.env` references them. **Failure:** OpenSSL/mkcert missing → see `docs/setup.md`; without HTTPS, phones will refuse camera access.

## Step 3 — Start the backend (Human)
- **Action:** `.venv\Scripts\python scripts\run_host.py --session demo1`
- **Expected:** log line `host_started ... v0.1.0 protocol 1.0`; `world_adapter_started`.
- **Success:** `GET http://127.0.0.1:8765/api/health` returns OK. **Failure:** port busy → `--port 8766` (and match Godot's port); YAML/config error → message names the file.

## Step 4 — Open the sensor client on each camera (Human)
- **Action:** on each phone/camera browser: `https://<PC-LAN-IP>:8765/client/`, enter session code `demo1`, pick facing camera, **Start**.
- **Expected:** live video preview; connection state connected. **Failure:** no camera → permissions or insecure context (must be HTTPS for phones); wrong camera → facing selector.

## Step 5 — Grant camera permissions (Human)
- **Action:** accept the browser's camera prompt on every device.
- **Failure:** previously denied → site settings → allow → reload.

## Step 6 — Verify sensor registration (Human, checks on Agent tooling)
- **Action:** open `http://127.0.0.1:8765/client/operator.html` on the PC.
- **Expected:** each sensor row: state online, rate > 0 Hz, small obs/capture ages, no reconnect loop.
- **Failure:** absent sensor → device not on page/wrong session; rate 0 → landmark model not loaded (check `/client/vendor` reachable).

## Step 7 — Calibration on file? (first run: perform; else verify)
- **Agent/verify:** `.venv\Scripts\python scripts\calibrate.py inspect` → READY (≥2 usable cameras). If NOT READY:
- **Human (first-run capture):** follow `docs/SAGA3D_HUMAN_ACTION_CHECKLIST.md` Stage 2 — snap ≥15 frames/camera → `calibrate.py intrinsics` (with **measured** square size) → static tilted board, 2–5 stills/camera → `calibrate.py rig` → `inspect`.
- **Success:** exit 0, both cameras compatible.

## Step 8 — Fusion running with real data (Human performs gesture, both verify)
- **Action:** wave your hand in the shared view.
- **Expected (operator page / `GET /api/sessions/demo1/fusion`):** status `TRACKING_MULTI_VIEW`, `world_xyz_m` values in metres that track your wrist.
- **Failure:** `CALIBRATION_REQUIRED` → Step 7; `SINGLE_VIEW_FALLBACK` → second camera not seeing the hand (reposition); `SYNC_DEGRADED` often → network/clock issue, note skew stats.

## Step 9 — Phase 3 agents active (Automatic; Human verifies)
- The gesture agent and coordinator attach automatically per session (bridge wiring).
- **Human check:** hover your open hand near the cube position → `HOVER` gesture state in logs/operator; pinch → `GRAB_REQUEST`.
- **Failure:** no states → confirm fusion is `TRACKING_MULTI_VIEW` and hand confidence adequate; repeated misfires → Stage 3 tuning of `config/gesture.yaml`.

## Step 10 — Phase 4 bridge active (Automatic)
- The `/ws/world` route is part of the same process. **Success indicator:** log `world_session_attached` with the transform fingerprint (e.g. `1|1,0,0|0,0,1|0,-1,0|0,0,-1.6|...`).

## Step 11 — Open the Godot project (Human; needs Godot installed)
- **First-time gate (Agent if Godot present, else Human):** `"C:\path\to\Godot_v4.3-stable_win64.exe" --path godot --headless --check-only` → no script errors.

## Step 12 — Launch Godot and connect (Human)
- **Action:** `"C:\path\to\Godot_v4.3-stable_win64.exe" --path godot -- --session=demo1`
- **Expected:** status panel shows connected → `WORLD_READY`; hand marker present.
- **Failure:** connection refused → host down or port mismatch; `WORLD_CLIENT_EXISTS` → another Godot is attached (close it); `SESSION_MISMATCH` → wrong `--session`.

## Step 13 — Verify coordinate alignment (Human, one-time per rig)
- **Action:** two-reference-point check (`docs/coordinates.md`): hold a marker at a measured physical point; compare fusion `world_xyz_m` with the Godot marker position; repeat at a second point (≥0.5 m apart, different height).
- **Success:** both agree within a few cm. **Failure:** adjust `transform:` in `config/world.yaml` (rotation/translation) — never patch Godot or the bridge.

## Step 14 — Perform a real gesture (Human)
- **Action:** move your hand to the cube → hover highlight → **pinch** → hold → **move** your hand → **open pinch** to release.
- **Expected:** `HOVER` → cube highlighted → `GRAB` (`GRAB_CONFIRMED`) → cube follows hand (`MOVE_TARGET` ≤30 Hz) → `RELEASE` → cube stays.
- **Failure:** grab never confirms → pinch thresholds/`confirm_ms` (Stage 3 tuning) or ack timeout — check logs for `GRAB_REQUEST`/ack; cube jumps → hold expired (`grab_loss_timeout_ms`) — improve coverage/lighting.

## Step 15 — Observe interaction & record (Human + Agent)
- **Success (project milestone):** a full grab/move/release driven by your real hand, repeatedly, with clean recovery from tracking loss and a mid-grab disconnect test.
- **Record:** end-to-end latency notes (operator ages, Godot smoothness), any tuning values, any failures+recoveries — this becomes your evidence that SAGA 3D runs on real hardware.

---

## Quick failure-recovery index

| Symptom | Likely cause | Recovery |
|---|---|---|
| Phone camera blocked | HTTP (insecure context) | Use HTTPS cert (`make_dev_cert.sh`) |
| Sensor not registering | Wrong session code / network | Re-enter code; same LAN check |
| `CALIBRATION_REQUIRED` | No/invalid calibration | Step 7; `calibrate.py inspect` |
| `SINGLE_VIEW_FALLBACK` | One camera lost the hand | Reposition cameras/hand |
| Fusion status churn `TARGET_LOST` | Poor coverage/lighting/sync | Improve lighting; check skew; recalibrate if camera moved |
| Godot `WORLD_CLIENT_EXISTS` | Second client on session | Close the other client |
| Grab not confirmed | Ack timeout / thresholds | Check host logs; tune `config/gesture.yaml` |
| Godot marker misaligned | Transform not verified | Step 13; edit `config/world.yaml` |
| Camera physically moved | Extrinsics stale | `calibrate.py invalidate <camera>` → recalibrate that camera |
