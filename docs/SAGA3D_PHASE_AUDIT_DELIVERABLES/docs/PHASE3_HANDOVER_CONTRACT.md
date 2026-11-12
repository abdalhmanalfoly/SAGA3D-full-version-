# PHASE 3 — HANDOVER CONTRACT → Phase 4

**From:** Phase 3 owner (gesture & agent coordination) · **To:** Phase 4 owner (Godot integration & final system)
**Gate at writing:** IN PROGRESS (software implementation complete — not operationally verified; practical execution not started). **Handover NOT granted yet.**

## 1. Must be implemented before completion
Nothing in code. `GestureAgent`, pinch, events 1.0, dedup, acks, and `SessionCoordination` are implemented and synthetic-verified; `attach.py` already wires them into live sessions. The remaining work is the real-hardware campaign (checklist) and possible threshold tuning.

## 2. Must be configured
- Final tuned values recorded in `config/gesture.yaml` (or defaults justified by the campaign data).
- `move_max_hz` 30 / `ack_timeout_ms` 500 defaults stand unless the Phase 4 demo shows a need (changes must stay consistent with `config/world.yaml gesture_overrides`).

## 3. Human must physically do
`PHASE3_HUMAN_ACTION_CHECKLIST.md`: real-pinch campaign (≥10 attempts), FP/FN tally, hover/reach checks, tracking-loss safety checks (mid-hover and mid-grab), tuning if needed, joint event-flow check with Phase 4 attached.

## 4. Real-world demonstration that must succeed
**Demo D3:** a real human hand — tracked through the calibrated rig — produces the correct gesture-state sequence across repeated attempts: `HOVER` enter/exit by reach, pinch-evidence-driven `GRAB_REQUEST` with an object in reach, `MOVE_TARGET` stream during movement, `RELEASE` on opening, and safe `GRAB_CANCELLED` on real tracking loss — with FP/FN baseline recorded and thresholds finalized.

## 5. Output Phase 4 receives (actual interface, from the code)
- **`INTERACTION_EVENT` v1.0 stream** per session: discrete events (`GRAB_REQUEST`, `GRAB_CONFIRMED`, `RELEASE`, `GRAB_CANCELLED`, hover enter/exit, tracking-lost announcements) each with event id, `interaction_id`, object id, gesture state, `timestamp_ms`; and continuous `MOVE_TARGET` positions (≤30 Hz, target `wrist`, metres in the **rig/board frame** — Phase 4 transforms them).
- **Ack channel**: Phase 4 must `acknowledge(event_id, accepted)` GRAB_REQUEST/RELEASE within 500 ms (`require_adapter_ack: true`) — no ack ⇒ no grab (safe default).
- **Object declaration**: Godot declares objects (`object_id`, position, `grabbable`) — up to 16 per session (`config/world.yaml max_objects`); `InteractionObject` selection uses them.
- **Dedup/order**: event ids unique per interaction (`EventDeduper`); sequence numbers order streams.

## 6. Contracts that must be respected
- Positions in events/targets are **rig-frame metres**; ONLY `adapter/saga4_world/transform.py` converts to Godot coordinates — Phase 3 (and 4's bridge) must never re-transform.
- Loss semantics Phase 4 relies on: grabbed freezes ≤ `grab_loss_timeout_ms` (≤5 s) then `GRAB_CANCELLED`; `tracking_lost_report_ms` announcements; no stale replay — Godot's local release-on-disconnect mirrors this.
- Event schema/version: `world_protocol_version: "1.0"` must keep matching `host/app/gesture/events.py PROTOCOL_VERSION`.
- Move rate ≤ `move_max_hz` (30 Hz) — bridge enforces pose cap 60 Hz for pure poses, agent caps targets.

## 7. Documentation delivered
- This contract + `PHASE3_COMPLETION_AUDIT.md`; `docs/gesture.md` and `docs/coordination.md` (in `docs/host/`) remain the canonical Phase 3 references; tuned-values note.

## 8. Tests & evidence accompanying the handover
- ~93 gesture/coordination tests green (within 411) + demo 9/9 + synthetic e2e gesture path (recorded).
- **D3 recording**: transition logs/audit excerpts, FP/FN tally, loss-behaviour excerpts, tuned config values, and (if run) the P3-12 joint event-flow excerpt with the bridge.

## 9. Known limitations that MAY be handed over
- Thresholds are tuned for the specific rig/user of the D3 campaign; new users/rigs may need re-tuning (values are data, not code).
- Gesture vocabulary is pinch-only today (hover/grab/move/release); body gestures absent until Phase 1's pose extension.
- Fusion-quality interdependence: gesture stability inherits Phase 2's sync/coverage limitations (e.g. 2-view epipolar blindness) — status vocabulary is the designed signal, and Phase 4's UI shows quality.

## 10. Issues that MUST NOT be passed on as unfinished work
- Unexplained FP/FN rates left untallied — the baseline is the handover's core evidence.
- Loss paths that replay stale positions or exceed the bounded timeouts — Phase 3 defects.
- Ack/dedup anomalies (duplicated event ids, grabs without acks) — Phase 3/bridge defects, must be fixed before handover.
- Tuned values "in someone's head" — they must be written into `config/gesture.yaml`/handover notes.

## Acceptance criteria for READY FOR HANDOVER
`PHASE3_HUMAN_ACTION_CHECKLIST.md` P3-1…P3-12 checked (P3-12 may be deferred to Phase 4 acceptance only if the Phase 4 client is not yet available — but D3 without Phase 4 is mandatory); demo D3 succeeded; evidence pack archived. Gate until then: **IN PROGRESS / IMPLEMENTATION COMPLETE — NOT OPERATIONALLY VERIFIED (software)**.
