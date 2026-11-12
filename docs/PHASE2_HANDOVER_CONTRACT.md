# PHASE 2 — HANDOVER CONTRACT → Phase 3

**From:** Phase 2 owner (calibration & 3D fusion) · **To:** Phase 3 owner (gesture & agent coordination)
**Gate at writing:** IN PROGRESS (software implementation complete — not operationally verified; physical calibration not started). **Handover NOT granted yet.**

## 1. Must be implemented before completion
Nothing in code. All Phase 2 software (intrinsics, rig, store, sync, triangulation, fusion, accuracy) is implemented, quality-gated, and synthetic-verified in the consolidated repo. The completion gap is entirely physical execution + validation.

## 2. Must be configured
- `SAGA_CALIBRATION_DIR` default (`calibration/`) is correct — **no change**; `SAGA_ALLOW_SYNTHETIC_CALIBRATION` must remain unset for real runs (synthetic artifacts refused by design).
- `--rig-id default_rig` and `--pattern 9x6 --square-size-m <MEASURED>` used consistently across all three calibration commands.
- Fusion thresholds (`config/fusion.yaml`) stay at documented starting points until the real-hardware validation justifies tuning.

## 3. Human must physically do
Full sequence in `PHASE2_HUMAN_ACTION_CHECKLIST.md`: print/measure board → mount cameras → ≥15 intrinsic frames/camera → intrinsics → static tilted board + 2–5 stills/camera → rig → `inspect` READY → live `TRACKING_MULTI_VIEW` → accuracy campaign (≥5 points × ≥30 samples).

## 4. Real-world demonstration that must succeed
**Demo D2:** with real cameras calibrated, a human hand moving through the shared volume produces continuous `TRACKING_MULTI_VIEW` wrist estimates in metres (board frame), and the `accuracy` campaign against ≥5 physically measured points reports recorded mm/low-cm errors.

## 5. Output Phase 3 receives (actual interface, from the code)
- **Per-session fused wrist track** from `FusionService`: target `wrist`, fields `world_xyz_m` (metres, board/world frame defined by the reference board), `valid` flag, quality score, status vocabulary (`TRACKING_MULTI_VIEW`, `SINGLE_VIEW_FALLBACK`, `TARGET_LOST`, …), `sample_ms` timestamps.
- **Calibration validity state** per camera (`inspect`/`/api/sessions/{id}/calibration`) — Phase 3's `HandSample.from_fusion_result` consumes `calibration_valid` directly.
- **Tracking-loss semantics**: bounded 500 ms hold then `TARGET_LOST` — the contract Phase 3's FSM (hover/grab loss timeouts) is built on.
- **Board world-frame definition**: origin = first inner corner of the static reference board, X along corner columns, Y along rows, Z = X×Y — the frame Phase 3's reach distances (metres) and Phase 4's transform assume.

## 6. Contracts that must be respected
- Units: **metres**; single right-handed world frame; fusion only publishes estimates it deems valid (quality-gated) — Phase 3 must treat `valid=false`/held/lost states as no-position, never replay stale coordinates (agent code already enforces this).
- Fusion consumes 2-D pixels + calibration only; Phase 3 must not expect MediaPipe 3-D model coordinates.
- Sync contract: observations within `max_skew_ms 50` (corrected clocks); older than 250 ms are stale — Phase 3's `max_evidence_gap_ms`/`stale_landmark_ms` interlock with these.
- Artifact format: versioned `CalibrationArtifact` (`CALIBRATION_VERSION`) — any future schema change requires Phase 2 + runtime updates together.

## 7. Documentation delivered
- This contract + `PHASE2_COMPLETION_AUDIT.md`; `docs/host/spatial.md` (operator procedure, quality gates, §11 hardware checklist) remains the canonical Phase 2 doc.
- Evidence pack (§8) + board placement description (world-frame origin definition).

## 8. Tests & evidence accompanying the handover
- 100 spatial tests green (within 411) + `selftest` synthetic table (recorded).
- **D2 recording**: calibration JSONs (with `rig_check`), `inspect` exit-0 output, operator screenshot `TRACKING_MULTI_VIEW`, five accuracy reports, sync-skew observation.

## 9. Known limitations that MAY be handed over
- Exactly-2-views epipolar-line blindness (documented) — mitigated by the physical accuracy check; a 3rd camera would strengthen geometry later.
- Thresholds (`config/fusion.yaml`, smoothing, hold) are starting points, to be tuned during Phase 3's real-gesture sessions if needed.
- Real-phone clock-offset behaviour measured only once during D2 — `SYNC_DEGRADED` may appear under load; the status vocabulary is the designed signal.

## 10. Issues that MUST NOT be passed on as unfinished work
- Failed quality gates (RMS/coverage/tilt/ambiguity) left unresolved — recalibrate instead.
- Cameras not rigidly mounted (extrinsics staleness risk) — fix physically before handover.
- Unloaded calibration (runtime showing `CALIBRATION_REQUIRED`).
- Accuracy campaign skipped — Phase 3's reach/pinch distances are meaningless without recorded scale accuracy.

## Acceptance criteria for READY FOR HANDOVER
`PHASE2_HUMAN_ACTION_CHECKLIST.md` P2-1…P2-17 all checked; demo D2 succeeded; evidence pack archived. Gate until then: **IN PROGRESS / IMPLEMENTATION COMPLETE — NOT OPERATIONALLY VERIFIED (software)**.
