# PHASE 4 — FINAL ACCEPTANCE CHECKLIST (the project's completion gate)

**This checklist accepts Phase 4 AND the whole SAGA 3D project.** It requires all previous phase handovers (1→2→3) as prerequisites. Every item is a real, observable demonstration — no synthetic substitutes count here.

## Prerequisites (must all be TRUE before starting)

- [ ] **A-0.1** Phase 1 handover accepted: two real cameras streaming stably, conventions verified (`PHASE1_HANDOVER_CONTRACT.md`).
- [ ] **A-0.2** Phase 2 handover accepted: real calibration loaded, `inspect` READY, live `TRACKING_MULTI_VIEW`, accuracy campaign recorded (`PHASE2_HANDOVER_CONTRACT.md`).
- [ ] **A-0.3** Phase 3 handover accepted: real-gesture campaign done, FP/FN baseline recorded, loss safety demonstrated, thresholds finalized (`PHASE3_HANDOVER_CONTRACT.md`).

## 1. Environment

- [ ] **A-1.1** Godot 4.3 installed: `"…Godot_v4.3-stable_win64.exe" --version` prints 4.3.x.
- [ ] **A-1.2** Headless project check passes: `… --path godot --headless --check-only` — no script errors.

## 2. Connectivity

- [ ] **A-2.1** Cold start per runbook Steps 1–7: host up (HTTPS optional for this phase — Godot connects over plain `ws://127.0.0.1:8765`), calibration loaded, sensors streaming.
- [ ] **A-2.2** Godot connects: status panel `WORLD_READY`; host log shows `world_session_attached` with the transform fingerprint; exactly-one-client rule verified (second instance rejected with `WORLD_CLIENT_EXISTS`).

## 3. Coordinate correctness

- [ ] **A-3.1** Two-reference-point verification passed (`docs/coordinates.md` §5): both physical points' fusion `world_xyz_m` vs Godot marker agree within a few centimetres.
- [ ] **A-3.2** Final transform values recorded in `config/world.yaml` (post-verification state) and fingerprint matches the runtime log.

## 4. Interaction (the project's purpose)

- [ ] **A-4.1** Hover: real hand → cube highlights.
- [ ] **A-4.2** Grab: pinch → `GRAB_REQUEST` → ack → `GRAB_CONFIRMED` → cube attaches.
- [ ] **A-4.3** Move: hand motion → cube follows at ≤30 Hz without jumps.
- [ ] **A-4.4** Release: pinch opens → cube stays put.
- [ ] **A-4.5** Repeatability: the full cycle succeeds ≥3 consecutive times.

## 5. Stability & recovery

- [ ] **A-5.1** Godot restart mid-session → bounded reconnect, objects re-declared, interaction resumes.
- [ ] **A-5.2** Camera covered mid-grab → bounded freeze → safe `GRAB_CANCELLED`; no stale motion.
- [ ] **A-5.3** Host restart → clean re-handshake; no orphaned one-client locks.
- [ ] **A-5.4** 15-minute continuous session without reconnect storms, stalls, or unbounded memory growth (observe host console + Godot status).

## 6. Performance evidence

- [ ] **A-6.1** End-to-end feel recorded: motion-to-marker latency smooth (no visible lag artifacts); note any stutters.
- [ ] **A-6.2** (Optional, stronger) instrumented p95 latency recorded (DEV-P4-2) and compared with the 150 ms design budget.

## 7. Shutdown & hand-back

- [ ] **A-7.1** Full runbook (`docs/SAGA3D_REAL_WORLD_RUNBOOK.md`) executed from cold machine; all 15 steps ticked.
- [ ] **A-7.2** Clean shutdown: host Ctrl-C produces orderly logs (`session_stopped`, no tracebacks); Godot closes cleanly.
- [ ] **A-7.3** Evidence pack archived: version outputs, headless-check output, `WORLD_READY` + fingerprint screenshot, two-point readings (+ any transform change + re-verification), interaction recordings ×3, recovery notes, completed runbook.

## Verdict rule

- ALL boxes ticked → **Phase 4 = COMPLETE AND VERIFIED; SAGA 3D project operational.**
- Any box failed → record exactly which, the failure output, and the recovery attempted; fix or classify (human/development/dependency) before re-running the affected item and everything downstream of it.
- No box may be ticked on synthetic evidence alone.
