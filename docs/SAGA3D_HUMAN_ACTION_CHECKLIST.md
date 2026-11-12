# SAGA 3D — Human Action Checklist (physical / manual actions ONLY)

**Companion to:** `docs/SAGA3D_COMPLETE_PROJECT_READINESS_AUDIT.md` · Code tasks are NOT here (see `docs/SAGA3D_REQUIRED_DEVELOPMENT_BACKLOG.md`).
**Current project position:** Phase 2, before physical calibration. Work top-to-bottom; do not skip ahead.

Legend: 🖨 prepare · ▶ execute · ✔ verify

---

## Stage 0 — One-time workspace checks (≈15 min)

- [ ] **✔ Run the test suite once** — proves your environment is healthy before touching hardware.
      `.venv\Scripts\python.exe -m pytest` → expect `411 passed`.
- [ ] **✔ Confirm calibration status** — `.venv\Scripts\python.exe scripts\calibrate.py inspect`
      → expect `NOT READY ... (have 0)` (correct until you calibrate).

## Stage 1 — Phase 1 hardware preparation

- [ ] **🖨 Choose cameras.** Minimum 2 (two phones is ideal; one phone + one webcam works). Why: fusion needs ≥2 calibrated views (`config/fusion.yaml min_views: 2`).
- [ ] **🖨 Put the PC and all cameras on the same Wi-Fi/LAN.** Why: browser clients connect to the host over the network.
- [ ] **🖨 Generate the HTTPS dev certificate.** Why: phone browsers block the camera on plain HTTP.
      `bash scripts/make_dev_cert.sh <your-LAN-IP>` → `certs/dev.crt` + `certs/dev.key`.
- [ ] **🖨 Set `SAGA_TLS_CERT`/`SAGA_TLS_KEY` in `.env`** (copy from `.env.example`) so the host serves HTTPS.
- [ ] **▶ Start the host:** `.venv\Scripts\python scripts\run_host.py --session demo1`
- [ ] **▶ On each camera device, open** `https://<PC-LAN-IP>:8765/client/`, enter the session code, pick the facing camera, press **Start**, and **grant camera permission** when the browser asks.
- [ ] **✔ Verify each sensor is registered:** open `http://127.0.0.1:8765/client/operator.html` on the PC → both sensors online, non-zero rate, small observation ages.
- [ ] **✔ Verify handedness convention** (`config/camera.yaml flip_handedness: true`): raise your **right** hand and confirm the client/host reports Right. If wrong, revisit the documented smoke test before calibrating.
- [ ] **✔ Note each camera's exact streaming WxH** (operator page / later from a saved PNG filename). Calibration images must match it.

**Phase 1 operational when:** both cameras stream, register, and send landmark observations you can see counted on the operator page.

## Stage 2 — Physical calibration (your current phase)

### Prepare

- [ ] **🖨 Print the 9×6 checkerboard (9 cols × 6 rows of inner corners = 10×7 squares) at 100 % scale.** Do not let the printer "fit to page".
- [ ] **🖨 Glue/tape it to something completely flat** (cardboard/foam board). Why: warp corrupts the metric model.
- [ ] **🖨 MEASURE the actual printed square edge in metres** (e.g. 0.04 m) and write it down — you will pass it to every calibration command.
- [ ] **🖨 Mount both cameras rigidly** (tripod/stand/taped) with overlapping views of the volume where your hand will interact. Why: any camera movement invalidates its extrinsics (`calibrate.py invalidate` would be needed).
- [ ] **🖨 Set up even lighting** — no strong glare on the board, no hard shadows.

### Capture intrinsics images (per camera)

- [ ] **▶ Hold the board in front of camera 1 and press "Save calibration frame (local file)"** on that camera's sensor page ≥15 times, moving the board each time: different positions (fill the frame corners), distances, and **tilts (~20–45°)**. Frames are saved as local PNGs at the exact stream resolution.
- [ ] **▶ Copy that camera's PNGs into a folder**, e.g. `captures/phone_left/`. Repeat for camera 2 → `captures/phone_right/`.
  *(Webcam alternative: `bash scripts/calibrate.py capture --device 0 --out captures/webcam --count 15 --interval 1.5`)*

### Run intrinsics

- [ ] **▶** `.venv\Scripts\python scripts\calibrate.py intrinsics --images captures\phone_left --camera-id phone_left --pattern 9x6 --square-size-m <MEASURED>`
      (repeat with `phone_right`).
- [ ] **✔ Success:** no error; JSON written under `calibration/intrinsics/` with `quality.intrinsic_rms_px ≤ 1.0`.
      **Failure:** the CLI prints a named reason (`TOO_FEW_SAMPLES`, `RMS_TOO_HIGH`, `NO_CONVERGENCE`, or a per-image rejection list) — reshoot the named weak images and retry.

### Rig (shared world frame)

- [ ] **▶ Place the board in the middle of the interaction volume, tilted 20–45° toward the cameras. Do not move board OR cameras for the rest of this step.**
- [ ] **▶ Capture 2–5 reference stills per camera** (snap button each time) into e.g. `captures/rig_left/`, `captures/rig_right/`.
- [ ] **▶** `.venv\Scripts\python scripts\calibrate.py rig --cameras phone_left:captures\rig_left --cameras phone_right:captures\rig_right --rig-id default_rig --pattern 9x6 --square-size-m <MEASURED>`
- [ ] **✔ Success:** `calibration/default_rig/<camera>.json` written; the cross-check `quality.rig_check.pairs` shows small mean/max mm errors.
      **Failure:** `EXTRINSIC_RMS_TOO_HIGH` / `BOARD_BEHIND_CAMERA` / `POSE_AMBIGUITY` → retake the tilted stills (a stronger tilt fixes ambiguity).

### Verify

- [ ] **✔** `.venv\Scripts\python scripts\calibrate.py inspect` → must now report **2 valid, compatible cameras** (exit 0).
- [ ] **✔ Restart the host and check** `GET /api/sessions/<id>/calibration` (or operator page) shows both cameras usable — runtime loading confirmed.
- [ ] **✔ Wave a real hand in view of both cameras** → operator page / `GET /api/sessions/<id>/fusion` shows `TRACKING_MULTI_VIEW` with metre-scale coordinates that move plausibly.

### Accuracy record (completes Phase 2)

- [ ] **▶ Mark ≥5 physical points** in the volume at known, tape-measured locations (vary height).
- [ ] **▶ With a hand at each point, let fusion record ≥30 samples** (fusion log runs automatically), then:
      `.venv\Scripts\python scripts\calibrate.py accuracy --fusion-log logs\sessions\<session>\fusion.jsonl --xyz x y z --target wrist` per point.
- [ ] **✔ Success:** mean error of a few millimetres to ~1–2 cm and stable repeatability; record the numbers.

**Phase 2 physically validated when:** `inspect` READY + live `TRACKING_MULTI_VIEW` + recorded accuracy numbers.

## Stage 3 — Phase 3 real-hardware validation (only after Stage 2)

- [ ] **▶ With fusion running, perform repeated pinch gestures near the object's expected position** (10+ repetitions) and watch hover/grab events on the operator page/logs.
- [ ] **▶ Note false positives (grab attempts when you didn't pinch) and false negatives (pinches ignored).**
- [ ] **▶ Cover one camera and verify graceful behaviour** (held estimate → `TARGET_LOST`, no stale grabs).
- [ ] **▶ Tune `config/gesture.yaml`** if transitions misfire (pinch enter/exit ratios, `confirm_ms`, reach distances) and repeat. **Record the final tuned values.**

## Stage 4 — Phase 4 Godot (only after Stage 3)

- [ ] **🖨 Download Godot 4.3 (stable, standard win64)** from godotengine.org and note the executable path.
- [ ] **✔** `"C:\path\to\Godot_v4.3-stable_win64.exe" --version`
- [ ] **✔ Headless check:** `"C:\path\to\Godot..." --path godot --headless --check-only` → no script errors.
- [ ] **▶ Start host with a session, then** `"C:\path\to\Godot..." --path godot -- --session=demo1`
- [ ] **✔ Verify:** status panel `WORLD_READY`; hand marker follows your real hand.
- [ ] **▶ Two-reference-point transform verification** (`docs/coordinates.md`): hold a marked point at a measured location, compare fusion `world_xyz_m` vs the Godot marker position; repeat at a second point (≥0.5 m apart, different height). If they disagree, adjust `R`/`translation_m` in `config/world.yaml` (never patch Godot).
- [ ] **▶ Perform a real pinch on the cube:** hover → cube highlights → pinch → `GRAB` → move hand → cube follows → open pinch → cube releases.
- [ ] **✔ Mid-grab disconnect test:** stop a camera during a grab → object releases safely, Godot reconnects.

## Stage 5 — Full system run

- [ ] **▶ Execute `docs/SAGA3D_REAL_WORLD_RUNBOOK.md` start-to-finish from a cold machine** and note any friction, timings, and recovery actions.
