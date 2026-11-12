# PHASE 2 — HUMAN ACTION CHECKLIST (physical calibration, executable, in order)

**Prerequisite:** Phase 1 handover done (two cameras streaming stably — `PHASE1_HANDOVER_CONTRACT.md` acceptance met).
**You need before starting:** printed checkerboard, tape measure (or ruler with mm), 2 rigid mounts, scissors/glue + flat board, good lighting.

## A. Prepare materials

- [ ] **P2-1. Print the checkerboard at 100% scale.**
      Target: 9 columns × 6 rows of **inner corners** (= 10 × 7 squares — this is the repo default `--pattern 9x6`; an odd×even board keeps the origin corner unambiguous).
      Printer setting: "Actual size"/100% — NOT "fit to page".
- [ ] **P2-2. Mount the print flat.** Glue/tape onto cardboard or foam board. Check: no visible waves when held level.
- [ ] **P2-3. Measure the square edge.**
      Tool: tape measure/ruler. Action: measure one printed square's side in millimetres, repeat on 3 squares, average. Write the value in **metres** (e.g. 39.8 mm → `0.0398`).
      This exact value goes into EVERY calibration command below.
- [ ] **P2-4. Mount both cameras rigidly** (tripod/stand/taped phones).
      Placement: both cameras must see the whole board region **and** the volume where your hand will interact; views must overlap substantially.
      Rule: once rig capture starts (step P2-9), NOTHING (board or cameras) may move until it ends — any movement invalidates extrinsics (`calibrate.py invalidate`).
- [ ] **P2-5. Lighting:** even indoor light on the board; no lamp glare, no hard shadows across the squares.
      Check: open each camera's sensor page and confirm the board's corners are all visible in the preview.

## B. Intrinsics (per camera)

- [ ] **P2-6. Capture ≥15 board frames from camera A.**
      Where: camera A's sensor page (`https://<PC-IP>:8765/client/`, session joined).
      Action: hold the board in view; press **"Save calibration frame (local file)"** ≥15 times, between presses move/tilt the board: centre + all four image corners, near + far, tilts ~20–45°.
      Expect: PNG downloads named `<label>_<W>x<H>_<time>.png` — **the WxH in the filename is your streaming resolution; keep it** (Phase 2 refuses mismatched images).
- [ ] **P2-7. Move camera A's PNGs into a folder**, e.g. `captures/phone_left/` (all PNGs with the same WxH).
- [ ] **P2-8. Repeat P2-6/P2-7 for camera B** → `captures/phone_right/`.
      *(Webcam alternative: `bash scripts/calibrate.py capture --device 0 --out captures/webcam --count 15 --interval 1.5` — press Ctrl-C to stop early.)*
- [ ] **P2-9. Run intrinsics for camera A.**
      Command: `.venv\Scripts\python scripts\calibrate.py intrinsics --images captures\phone_left --camera-id phone_left --pattern 9x6 --square-size-m 0.0398` (your measured value)
      Expect: JSON written under `calibration/intrinsics/` with `quality.intrinsic_rms_px ≤ 1.0`; warnings about `LOW_COVERAGE`/`LOW_TILT_VARIETY` mean reshoot that aspect.
      Fail: `TOO_FEW_SAMPLES` → not enough boards detected (lighting/blur/glare — reshoot); `RMS_TOO_HIGH`/per-image rejection list → reshoot the named files; `NO_CONVERGENCE` → mixed conditions, reshoot the whole set.
- [ ] **P2-10. Run intrinsics for camera B** (same command pattern, `phone_right`).

## C. Rig (shared world frame — do not move anything)

- [ ] **P2-11. Place the board in the interaction volume, tilted 20–45° toward the cameras.** This board position **defines the world frame** (origin = its first inner corner; X along corner columns; Y along rows; Z up out of the board). Choose a placement you can reproduce for Phase 4's transform checks.
- [ ] **P2-12. Capture 2–5 reference stills per camera** (snap button) into `captures/rig_left/` and `captures/rig_right/`. Between stills, change nothing except tiny shutter releases; board and cameras stay fixed.
- [ ] **P2-13. Run the rig calibration.**
      Command: `.venv\Scripts\python scripts\calibrate.py rig --cameras phone_left:captures\rig_left --cameras phone_right:captures\rig_right --rig-id default_rig --pattern 9x6 --square-size-m 0.0398`
      Expect: `calibration/default_rig/phone_left.json` + `phone_right.json`; each contains `quality.rig_check.pairs` with mean/max mm cross-check numbers.
      Fail: `EXTRINSIC_RMS_TOO_HIGH` → retake stills (sharper, better light); `BOARD_BEHIND_CAMERA`/`POSE_AMBIGUITY` → increase the board tilt (20–45°) and retake; `TARGET_MISMATCH` → board pattern/size differed between the two intrinsics runs — recalibrate consistently.

## D. Verify

- [ ] **P2-14.** `.venv\Scripts\python scripts\calibrate.py inspect`
      Success: reports 2 valid, compatible cameras (exit 0).
- [ ] **P2-15. Confirm the runtime loads it.** Restart the host, open the operator page → calibration table shows both cameras usable/valid; `GET /api/sessions/demo1/calibration` returns both artifacts as usable.
- [ ] **P2-16. Live fusion check.** Wave your hand in the shared volume; operator page / `GET /api/sessions/demo1/fusion` must show status `TRACKING_MULTI_VIEW` with `world_xyz_m` values in metres that move plausibly with your hand.
      Fail: `CALIBRATION_REQUIRED` → artifacts not loaded (check calibration dir env / rig id); `SINGLE_VIEW_FALLBACK` → one camera lost the hand (reposition); frequent `SYNC_DEGRADED` → note the skew stats (record them — Phase 2 validation evidence).
- [ ] **P2-17. Accuracy campaign (completes Phase 2).**
      Action: mark ≥5 physical points in the volume at tape-measured positions (vary height); rest your wrist at each point for ≥30 samples (fusion log writes automatically), then per point:
      `.venv\Scripts\python scripts\calibrate.py accuracy --fusion-log logs\sessions\<session-id>\fusion.jsonl --xyz <x> <y> <z> --target wrist`
      Success: mean error ~mm to low-cm with small repeatability std; record all five reports — this is the physical proof.

## Evidence pack for handover to Phase 3
- Both `intrinsics/*.json` + both `default_rig/*.json` (with rig_check numbers).
- `inspect` exit-0 output; operator-page screenshot with `TRACKING_MULTI_VIEW`.
- The five accuracy reports + measurement notes; sync-skew observation from P2-16.
- Board placement description/photos (Phase 4 needs the world-frame origin definition).
