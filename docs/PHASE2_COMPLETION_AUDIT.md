# PHASE 2 — COMPLETION AUDIT: Camera Calibration & 3D Fusion

**Date:** 2026-11-12 · **Repo:** `saga-3d-phase-4` @ `bd01443` · read-only audit

**Phase gate status: IN PROGRESS** — software side is *IMPLEMENTATION COMPLETE — NOT OPERATIONALLY VERIFIED*; the physical calibration itself has **not been started** by the project owner (this is the user's current phase). Highest achieved verification = level 4 (real-service execution with the synthetic rig: `e2e_fusion_live.py` 11/11); real hardware = never.

---

## 1. Phase ownership

| Component | Path | Role |
|---|---|---|
| Geometry maths | `host/app/spatial/geometry.py` | `CameraModel`, projection+distortion, DLT triangulation, Gauss-Newton refine, ray-angle/depth checks |
| Calibration artifacts | `host/app/spatial/calibration_schema.py` | versioned `IntrinsicsArtifact`/`CalibrationArtifact`, synthetic flag, validity |
| Calibration store | `host/app/spatial/calibration_store.py` | atomic save/load, `history/`, invalidation, rig compatibility |
| Calibration workflow | `host/app/spatial/calibration_tool.py` | corner detection, `calibrate_intrinsics`, `calibrate_rig`, cross-check, `accuracy_report` |
| Sync | `host/app/spatial/synchronizer.py` | per-sensor clock offsets, skew/staleness/buffers |
| Fusion | `host/app/spatial/fusion.py`, `service.py`, `filters.py`, `results.py` | FusionEngine/FusionService, quality, One-Euro smoothing, hold/lost |
| Synthetic rig | `host/app/spatial/synthetic.py` | rendered boards, accuracy tables |
| CLI | `scripts/calibrate.py` | capture/intrinsics/rig/inspect/invalidate/accuracy/selftest/example |
| Config | `config/fusion.yaml` | all thresholds/gates |
| Storage | `calibration/` (real data git-ignored; `example_synthetic/` committed) | artifacts |
| Doc | `docs/host/spatial.md` | definitive operator procedure + §11 hardware checklist |
| Tests | `test_spatial_geometry.py`(16), `test_spatial_calibration.py`(20), `test_spatial_fusion.py`(32), `test_spatial_sync_filters.py`, `test_spatial_integration.py` | 100 tests, all pass |

**Consumes from Phase 1:** 2-D pixel landmarks + `captured_at_ms` + handedness + heartbeats (via `FusionService` wired in `main.py`/`websocket_handler.py`).
**Provides to Phase 3:** fused `world_xyz_m` (metres, board frame) + validity + quality, consumed via `HandSample.from_fusion_result`.
**Provides to Phase 4:** the rig world frame that `transform.py` maps to Godot.

## 2. Implementation audit

**IMPLEMENTED (inspection + 100 passing tests + synthetic e2e):**
- Intrinsics: ≥10 usable images, RMS ≤ 1.0 px gate, per-sample ≤ 2.0 px with ≤12 outlier-rejection rounds, coverage ≥ 0.35 + tilt-spread ≥ 10° **warnings**, `fix_k3`, 5-coefficient distortion, named error codes (`TOO_FEW_SAMPLES`, `OPENCV_FAILED`, `NO_CONVERGENCE`, `RMS_TOO_HIGH`, `IMPLAUSIBLE_RESULT`) — `calibration_tool.py:calibrate_intrinsics`.
- Rig: ≥2 cameras, same-board check, static reference board defines the world frame (origin = first inner corner, X along columns, Y along rows, Z = X×Y), solvePnP-IPPE + RefineLM, extrinsic RMS ≤ 2.0 px, `BOARD_BEHIND_CAMERA`, pose-ambiguity warning, per-camera-pair triangulation cross-check vs known board geometry (`rig_check`) — `calibrate_rig`.
- Store: atomic writes, history, invalidation, rig compatibility, **synthetic artifacts refused unless `SAGA_ALLOW_SYNTHETIC_CALIBRATION=1`**.
- Sync: heartbeat-estimated clock offsets, `max_skew_ms 50`, staleness 250 ms, bounded buffers (16/sensor), out-of-order tolerance, clock-suspect detection.
- Triangulation: DLT + refine (5 iters), min 2 views, reprojection gates (6/12 px), ray-angle 2°, depth 0.05–20 m, half-pixel convention, hand-agreement requirement.
- Fusion: quality = f(reprojection, sync, geometry); 8-status vocabulary; One-Euro smoothing (15 Hz); 500 ms hold; 8 m/s discontinuity reset; per-tick 50 ms.
- CLI completeness: all 8 subcommands verified; `inspect` currently (correctly) reports `NOT READY ... (have 0)`.
- **Phone capture path exists:** sensor-page "Save calibration frame" (un-mirrored PNG at exact stream resolution).

**PARTIALLY IMPLEMENTED:** none material.
**MISSING (software):** none blocking; body-target fusion would arrive with Phase 1's pose extension.
**Present but never operationally verified:** the entire chain on real images/cameras (detector behaviour on real board photos, real distortion, real clock offsets, real sync skew).
**Documented limitation (correct, not a defect):** with exactly 2 views, errors along the epipolar line are undetectable; the physical accuracy check is the designed countermeasure (`docs/host/spatial.md`; test documents it).
**Hidden dependencies on Phase 1:** stable sensor↔camera IDs, consistent un-mirrored frames, plausible `captured_at_ms` — guaranteed by Phase 1's handover contract, not yet demonstrated on hardware.

## 3. Real-world operational audit

**Hardware required:** ≥2 cameras (phones ideal), same LAN, printed 9×6 checkerboard (odd×even default `9x6` = 10×7 squares — matches the plan; `--square-size-m` must be the **measured** print, default 0.04 m), flat backing, rigid mounts, even lighting.

**Physical procedures (commands from the repo, none invented):**

1. **Intrinsic frames:** ≥15 per camera at exactly the streaming resolution, varied position/depth/tilt (gates warn below 35% coverage / 10° tilt spread). Capture via sensor-page snap button (phones) or `bash scripts/calibrate.py capture --device N --out DIR --count 15 --interval 1.5` (webcam).
2. **Intrinsics:** `.venv\Scripts\python scripts\calibrate.py intrinsics --images DIR --camera-id <id> --pattern 9x6 --square-size-m <MEASURED>` → `calibration/intrinsics/<id>__<W>x<H>.json`.
3. **Rig:** board static in the workspace, tilted 20–45°, 2–5 stills per camera; `... calibrate.py rig --cameras <id>:DIR ... --rig-id default_rig ...` → `calibration/default_rig/<id>.json`.
4. **Verify:** `... calibrate.py inspect` (exit 0, ≥2 usable) → live session `TRACKING_MULTI_VIEW` → `... calibrate.py accuracy --fusion-log logs\sessions\<id>\fusion.jsonl --xyz x y z` against ≥5 measured locations × ≥30 samples.

**Success indicators:** JSON artifacts with gates passed + small `rig_check` pair errors; `inspect` READY; fusion status `TRACKING_MULTI_VIEW` on a real hand; accuracy report with mm-level errors.
**Failure handling:** named CLI errors → reshoot named weak images; `invalidate` after any camera move; per-image rejection lists name files.

## 4. Actual verification audit

| Level | Achieved? | Evidence |
|---|---|---|
| 1 Code inspection | ✔ | full read of `calibration_tool.py`, `calibrate.py`, configs |
| 2 Automated tests | ✔ | 100 spatial tests green (in 411) |
| 3 Synthetic execution | ✔ | `selftest` table (this session); `example_synthetic` rig; e2e 11/11 |
| 4 Real service execution | ✔ (synthetic rig) | e2e over real wire |
| 5 Real hardware execution | ✘ | no real board/camera ever calibrated |
| 6 Operational demo | ✘ | — |

## 5. Missing-work register

| ID | Class | Task | Files | Why | Action | Depends | P | Completion criteria | Evidence |
|---|---|---|---|---|---|---|---|---|---|
| P2-H1 | HUMAN | Print 9×6 board at 100%, flat backing, **measure** square size | — | metric model needs true size | print + tape measure | P1 handover | P0 | measured mm value recorded | note |
| P2-H2 | HUMAN | Mount ≥2 cameras rigidly with overlapping views | — | extrinsics invalid on movement | physical setup | P1 handover | P0 | cameras hold position across rig step | observation |
| P2-H3 | HUMAN | Even lighting, no board glare | — | detector robustness | setup | P2-H1 | P0 | board detectable in preview | snap test |
| P2-C1 | CONFIG | Confirm calibration root/synthetic refusal (defaults are correct) | `config/fusion.yaml` | safety: synthetic refused by default | no change needed | — | P0 | defaults untouched | file state |
| P2-H4 | HUMAN | Capture ≥15 intrinsic frames/camera at stream resolution | sensor page / `calibrate.py capture` | intrinsics input | shoot | P2-H1..3 | P0 | folders with ≥15 PNGs each | folder listing |
| P2-H5 | HUMAN | Run intrinsics per camera (measured size) | `calibrate.py intrinsics` | K + distortion | run | P2-H4 | P0 | RMS ≤1.0 px, no named failure | JSON quality block |
| P2-H6 | HUMAN | Rig capture (static tilted board, 2–5 stills/camera) | snap button | shared world frame | shoot, don't move anything | P2-H5 | P0 | stills in per-camera dirs | folder listing |
| P2-H7 | HUMAN | Run `calibrate.py rig` | CLI | extrinsics + cross-check | run | P2-H6 | P0 | `default_rig/*.json`, rig_check small | JSON rig_check |
| P2-H8 | HUMAN | `inspect` → READY | CLI | runtime acceptance | run | P2-H7 | P0 | exit 0, 2 usable | CLI output |
| P2-H9 | HUMAN | Live fusion check with a real hand | host + operator page | prove geometry on real data | wave hand | P2-H8 | P0 | `TRACKING_MULTI_VIEW`, metre-scale coords | operator page/API |
| P2-H10 | HUMAN | Accuracy campaign (≥5 points × ≥30 samples) | `calibrate.py accuracy` | physical validation | measure + run | P2-H9 | P1 | mm-level mean/std recorded | accuracy reports |
| P2-H11 | HUMAN | Transform verification support (2 marked points for Phase 4) | `docs/coordinates.md` | Phase 4 alignment | supply fusion readings at 2 points | P2-H9 | P1 | both readings recorded | note |
| P2-D1 | DEVELOPMENT | Phone-capture recipe consolidated into spatial.md | `docs/host/spatial.md` | pieces exist, one recipe missing | docs edit (authorized) | — | P3 | recipe present | — |
| P2-D2 | DEVELOPMENT | Folder pre-QC dry-run report (optional) | `calibration_tool.py` | fewer reshoot cycles | optional feature | — | P3 | report tool | — |
| P2-V1 | VALIDATION | Sync behaviour on real phones observed | logs | synthetic-only so far | observe skew/`SYNC_DEGRADED` during P2-H9 | P2-H9 | P1 | skew within 50 ms or tuning done | log excerpt |
| P2-B1 | BLOCKER | Real camera data (unblocks at P1 handover) | — | — | — | Phase 1 D1 | P0 | — | — |

## 6. Definition of Done (Phase 2)

1. Real intrinsics + rig artifacts exist for ≥2 cameras, all gates passed, warnings resolved or justified.
2. `inspect` exit 0; runtime loads them (`/api/sessions/{id}/calibration` usable).
3. Live session shows `TRACKING_MULTI_VIEW` on a real hand with plausible metre-scale motion.
4. Accuracy campaign recorded (≥5 locations × ≥30 samples) with acceptable errors.
5. Evidence: artifact JSONs + CLI outputs + accuracy reports + session log.

**Handover to Phase 3: NOT READY until the above pass** (`PHASE2_HANDOVER_CONTRACT.md`).
