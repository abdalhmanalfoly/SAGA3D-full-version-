# PHASE 2 — DEVELOPMENT CHECKLIST (code tasks only)

**Honest scope:** Phase 2's calibration/fusion software is complete and quality-gated. There is **no P0 development work**; the critical path is physical (see human checklist). Items below are grounded in repo evidence; optional conveniences are labelled.

## DEV-P2-1 — Consolidate the phone-capture recipe into the operator doc (P3, docs)
- **Problem:** the pieces of the phone-only capture workflow exist (snap button in `sensor-client/index.html:22` + `app.js:180–197`; folder import in `calibration_tool.load_samples`) but `docs/host/spatial.md` describes capture mostly in terms of the webcam `capture` subcommand; the phone path is scattered across client UI/docs.
- **Affected files:** `docs/host/spatial.md` (add one numbered recipe: snap → folder → `intrinsics`/`rig`).
- **Implementation:** documentation only (requires authorization in a future task).
- **Why:** a new operator calibrating only from spatial.md would look for a phone path that isn't written as one procedure.
- **Dependencies:** none.
- **Acceptance criteria:** spatial.md contains the recipe; consistent with this checklist.

## DEV-P2-2 — Image-folder pre-QC dry-run (optional, P3)
- **Problem:** weak image sets are discovered during `intrinsics` (per-sample rejection loop, max 12 rounds in `calibrate_intrinsics`), costing reshoot cycles.
- **Affected files:** `host/app/spatial/calibration_tool.py` (reuses `load_samples`, which already rejects unreadable/no-board/size-mismatch with reasons); new CLI flag e.g. `calibrate.py intrinsics --dry-run`.
- **Implementation:** report per-folder: images found, boards detected, coverage/tilt estimates — before committing to calibration.
- **Why for real operation:** quality gates (RMS ≤ 1.0 px, coverage ≥ 0.35, tilt ≥ 10°) are strict; a pre-flight avoids half-failed runs.
- **Dependencies:** none.
- **Acceptance criteria:** dry-run on `calibration/example_synthetic` renders a plausible report without writing artifacts.

## DEV-P2-3 — Real-phone synchronization field aid (P2, measurement helper, execute after first real session)
- **Problem:** per-sensor clock offsets are heartbeat-estimated (`synchronizer.py`); correctness on real phones is synthetic-validated only. `e2e_fusion_live.py` measured skew on a synthetic rig (median 6 ms); real Wi-Fi phones may differ, and `SYNC_DEGRADED` tuning may be needed.
- **Affected files:** new analysis helper over `logs/sessions/<id>/fusion.jsonl` + sensor event logs (offsets, skew distribution, `SYNC_DEGRADED` frequency); no behaviour change to `synchronizer.py` required first.
- **Implementation:** print per-sensor offset/skew stats and `SYNC_DEGRADED` rate for a session; optionally suggest whether `max_skew_ms 50` / `degrade_grace_ms 120` need tuning (tuning itself is a decision, not automatic).
- **Why:** Phase 2's DoD requires sync behaviour observed on real hardware; today the evidence exists only synthetically.
- **Dependencies:** a real session having run (Phase 2 checklist step P2-16).
- **Acceptance criteria:** report generated from a real session log; skew numbers recorded.
- **Label:** grounded (synthetic-only evidence), not a code defect.

## Explicitly NOT broken — do not rework
- Intrinsics/rig maths and gates: 20 calibration tests + 16 geometry tests + synthetic selftest (this session) all pass; error codes are explicit and actionable.
- Synthetic-artifact safety: real runs cannot accidentally use the example rig (`SAGA_ALLOW_SYNTHETIC_CALIBRATION` refusal) — leave untouched.
- The 2-view epipolar-line limitation is documented and by-design; adding a 3rd camera later is an operational upgrade, not a code fix.
- Board 9×6 / measured square / streaming-resolution enforcement already match the project plan — **no discrepancy found**.
