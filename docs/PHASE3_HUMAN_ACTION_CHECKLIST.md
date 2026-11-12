# PHASE 3 — HUMAN ACTION CHECKLIST (executable, in order)

**Prerequisite:** Phase 2 handover complete — real calibration loaded, live session shows `TRACKING_MULTI_VIEW` with a real hand (`PHASE2_HANDOVER_CONTRACT.md` accepted).
**No new hardware or installs.** Phase 3 runs inside the same host process; your job is to exercise it with real movements and record what happens.

## Setup

- [ ] **P3-1. Start a session with the calibrated rig.**
      Command: `.venv\Scripts\python scripts\run_host.py --session demo1`
      Expect: `host_started`; operator page shows both cameras usable and fusion healthy when you show a hand.
- [ ] **P3-2. Open the observation surfaces.**
      PC browser: `http://127.0.0.1:8765/client/operator.html` (sensor + fusion + gesture state columns).
      Optionally watch `logs/sessions/<session-id>/` files and the host console for `GESTURE_TRANSITION`, `GRAB_REQUEST`, coordinator events.

## Real-pinch campaign (the core demonstration)

- [ ] **P3-3. Warm-up pass.** Show your hand to both cameras; confirm fusion stays `TRACKING_MULTI_VIEW` while you move naturally.
      Fail: statuses churn (`TARGET_LOST`/`SINGLE_VIEW_FALLBACK`) → improve coverage/lighting FIRST; gesture data is meaningless without a stable track.
- [ ] **P3-4. Perform 10 pinch gestures in open air** (no object needed for state transitions): open hand → hover → pinch → hold ~1 s → open.
      Expected in logs/operator: gesture state `HOVER` while near/reach… (state machine transitions `IDLE→HOVER` when reach+confidence met; pinch evidence with `confirm_ms` drives `GRABBED` only when an object is in reach — in air you should see HOVER enter/exit and pinch evidence counters; with Phase 4 attached you'd see full GRAB paths).
      Record per attempt: did the state change when expected? Any spurious transitions?
- [ ] **P3-5. Tally false positives and false negatives.**
      False positive = grab/pinch state while you did NOT pinch. False negative = pinched, no state change (check `confirm_ms`/ratio counters in logs for evidence of why).
- [ ] **P3-6. Vary conditions:** faster/slower pinches, hand farther/nearer, rotate your hand. Note which conditions break recognition — this feeds tuning.
- [ ] **P3-7. Hover/reach check.** Move your open hand as if reaching for the cube's future position; observe HOVER enter/exit hysteresis in logs (enter within `reach_enter_m`, exit beyond `reach_exit_m`).

## Tracking-loss safety

- [ ] **P3-8. Mid-hover loss.** While in HOVER, cover one camera (or leave the volume).
      Expect: brief hold, then `HOVER` exits to `IDLE` after `hover_loss_timeout_ms`; no stale coordinates.
- [ ] **P3-9. Mid-grab loss (only meaningful with Phase 4 attached or with an object in reach):** expect `GRABBED` to freeze (no MOVE_TARGET) for at most `grab_loss_timeout_ms` (≤5 s, config-bounded), then `GRAB_CANCELLED` — never a replay of stale positions.

## Tuning (only if P3-4..P3-7 show systematic misbehaviour)

- [ ] **P3-10. Adjust `config/gesture.yaml`** (text editor) — the documented starting points: pinch `enter/exit` ratios (hysteresis, enter < exit), `confirm_ms`, reach distances, confidence floors.
      Save, restart the host, repeat P3-4/P3-5.
- [ ] **P3-11. Record final tuned values** in the evidence pack (these are part of the Phase 3 handover).

## Joint validation with Phase 4 (when its client exists)

- [ ] **P3-12. With the Godot client connected:** perform one full hover→pinch→move→open cycle on the cube.
      Expect in host/bridge logs: `GRAB_REQUEST` (event id) → adapter ack → `GRAB_CONFIRMED` → `MOVE_TARGET` stream (≤30 Hz) → `RELEASE`. No duplicate event ids (`EventDeduper`).
      This is the cross-phase demonstration Phase 4's acceptance also relies on.

## Evidence pack for handover to Phase 4
- P3-4/P3-5 tally (attempts, transitions, FP/FN counts).
- P3-8/P3-9 loss-behaviour log excerpts.
- Tuned `config/gesture.yaml` values (or justification of defaults).
- P3-12 event-flow log excerpt (if Phase 4 was attached).
