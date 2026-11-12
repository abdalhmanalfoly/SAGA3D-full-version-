# SAGA 3D — MASTER COMPLETION ROADMAP (from current state to a running real-world system)

**Starting point (verified this audit):** all software consolidated @ `bd01443`; 411 pytest + 16 node green; no real calibration; Godot not installed; no real-camera session ever run.
**Rule:** the roadmap is strictly ordered; a stage starts only when its predecessor's gate is green. Parallel-safe items are marked ∥.

---

## STAGE 0 — Environment health (today, ~15 min)
1. ☐ `pytest` green (411). 2. ☐ `calibrate.py inspect` shows NOT READY/0 (correct pre-state). — *Agent-executable; already verified this audit.*

## STAGE 1 — Phase 1 real-hardware handover (gates: D1)
∥ 1. ☐ Prepare LAN + phones (P1-1). 2. ☐ HTTPS cert + `.env` (P1-3..4). 3. ☐ Host up (P1-5). 4. ☐ Both cameras streaming + registered (P1-7..10). 5. ☐ Handedness verified (P1-11). 6. ☐ Resolutions recorded (P1-12). 7. ☐ 10-min stability run (P1-13). 8. ☐ Performance numbers recorded (P1-14).
**Gate D1:** both sensors online ≥10 min, no reconnect storms. → `PHASE1_HANDOVER_CONTRACT.md` accepted.
*(Fail → recover per checklist; do not proceed to Stage 2 capture with unstable streams.)*

## STAGE 2 — Phase 2 physical calibration (gates: D2)
∥ (board printing/mounts can overlap Stage 1)
1. ☐ Board printed 100% + measured square (P2-1..3). 2. ☐ Cameras mounted + lighting (P2-4..5). 3. ☐ ≥15 intrinsic frames/camera (P2-6..8). 4. ☐ `intrinsics` ×2 (P2-9..10). 5. ☐ Static tilted board + 2–5 stills/camera (P2-11..12). 6. ☐ `rig` (P2-13). 7. ☐ `inspect` READY (P2-14). 8. ☐ Runtime loads calibration (P2-15). 9. ☐ Live `TRACKING_MULTI_VIEW` on real hand (P2-16). 10. ☐ Accuracy campaign ≥5 points × ≥30 samples (P2-17).
**Gate D2:** `inspect` exit 0 + live fusion + recorded accuracy reports. → `PHASE2_HANDOVER_CONTRACT.md` accepted.
∥ *After D2 (any time):* Godot install + headless check (P4-1..2) — independent of Phase 3.

## STAGE 3 — Phase 3 real-gesture validation (gates: D3)
1. ☐ Session with calibrated rig (P3-1..2). 2. ☐ Real-pinch campaign ×10 + tally (P3-4..5). 3. ☐ Condition variation notes (P3-6). 4. ☐ Hover/reach checks (P3-7). 5. ☐ Loss safety: mid-hover + mid-grab (P3-8..9). 6. ☐ Tuning if needed + values finalized (P3-10..11).
**Gate D3:** FSM behaves correctly and repeatably on real landmarks; FP/FN baseline recorded. → `PHASE3_HANDOVER_CONTRACT.md` accepted.

## STAGE 4 — Phase 4 Godot validation (gates: V1–V4)
1. ☐ Godot installed + version check (P4-1). 2. ☐ Headless check (P4-2). 3. ☐ Host + Godot connect → `WORLD_READY` + fingerprint (P4-3..4). 4. ☐ Two-reference-point transform verification; finalize `config/world.yaml` (P4-5..8). 5. ☐ Interaction demo hover→grab→move→release ×3 (P4-9..13). 6. ☐ Recovery demos: Godot restart, camera loss mid-grab, host restart (P4-14..16).

## STAGE 5 — Final system acceptance
1. ☐ Full cold-start runbook executed (P4-17 / runbook steps 1–15). 2. ☐ Stability: 15-min continuous session (A-5.4). 3. ☐ Evidence pack archived per `PHASE4_FINAL_ACCEPTANCE_CHECKLIST.md`.
**Gate FINAL:** every acceptance box ticked → project operational.

---

## Milestone statement template (per phase)

> "I completed Phase N. Evidence: <D-N recordings + artifact/log evidence>. Its working output to Phase N+1: <contract §5 output>. Handover contract: `docs/PHASEN_HANDOVER_CONTRACT.md` (accepted by Phase N+1 owner)."

- After Stage 1 → Phase 1 handover to Phase 2.
- After Stage 2 → Phase 2 handover to Phase 3 (+ unlock transform verification).
- After Stage 3 → Phase 3 handover to Phase 4.
- After Stage 5 → project complete.

## If something fails at a gate

- Stage 1 failures → `PHASE1_HUMAN_ACTION_CHECKLIST.md` failure notes (network/permissions/vendor).
- Stage 2 failures → named CLI error codes → reshoot the named weak set; never bypass gates.
- Stage 3 failures → tune `config/gesture.yaml` with recorded data (P3-10).
- Stage 4 failures → transform math per `docs/coordinates.md` (adjust `config/world.yaml` only); script errors → development item.
- Never substitute a synthetic run for a gate.
