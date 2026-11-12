# PHASE 3 — COMPLETION AUDIT: Gesture Recognition & Agent Coordination

**Date:** 2026-11-12 · **Repo:** `saga-3d-phase-4` @ `bd01443` · read-only audit

**Phase gate status: IN PROGRESS** — software side *IMPLEMENTATION COMPLETE — NOT OPERATIONALLY VERIFIED* (synthetic only); the user has **not started practical Phase 3 execution**. Highest achieved verification = level 3/4 (synthetic scenarios + engine-integration tests + the 9-scenario demo and synthetic live e2e where the gesture path runs on simulated fusion frames). Real human gestures: never.

---

## 1. Phase ownership

| Component | Path | Role |
|---|---|---|
| Gesture agent | `host/app/gesture/agent.py` | `GestureAgent` FSM `IDLE→HOVER→GRABBED→RELEASED→IDLE`, `HandSample` (+`from_fusion_result`), `InteractionObject`, `GestureOutput`, `acknowledge()` |
| Events | `host/app/gesture/events.py` | `INTERACTION_EVENT` v1.0, `EventDeduper`, event ids/types |
| Pinch | `host/app/gesture/pinch.py` | scale-aware pinch ratio (thumb-tip↔index-tip / palm length, same view), multi-view combination |
| Gesture config | `host/app/gesture/config.py` + `config/gesture.yaml` | all thresholds (documented starting points), hysteresis validation |
| Coordination core | `host/app/coordination/{coordinator,sensor_agent,scoring,set_selection,messages,audit,simulation}.py` | multi-sensor negotiation, lease, adaptation, audit |
| Host adapter | `host/app/coordination/host_adapter.py` | `SessionCoordination` — consumes live fusion into the coordinator |
| Config | `config/coordination.yaml` | scoring weights, timeouts |
| Demo | `scripts/demo_coordination.py` | 9 synthetic scenarios (passes 9/9) |
| Tests | `test_gesture_machine.py`(29), `test_gesture_pinch.py`(14), `test_coord_*.py`(~50), `test_coord_engine_integration.py` | all pass |

**Consumes from Phase 2:** fused wrist `world_xyz_m` + validity/quality/status + calibration validity + pinch-relevant landmark confidences (via `SessionCoordination`/`GestureAgent.update(HandSample,…)`).
**Provides to Phase 4:** `INTERACTION_EVENT` 1.0 stream — `GRAB_REQUEST`/`MOVE_TARGET`/`RELEASE`/`GRAB_CANCELLED`/hover events + ack discipline (`acknowledge()`), consumed by the Phase 4 bridge (`adapter/saga4_world/`).

## 2. Implementation audit

**IMPLEMENTED (inspection + 93+ passing tests + synthetic demos):**
- Deterministic FSM, at most one transition per call; bounded loss handling (hover timeout; grabbed freezes then safely cancels `GRAB_CANCELLED` after `grab_loss_timeout_ms` ≤ 5000); stale coordinates never replayed — `agent.py` docstring matches implementation.
- Scale-aware pinch with hysteresis (`enter 0.25 < exit`), `confirm_ms` evidence window, multi-view ratio combination; confidence gates (`min_confidence`, `exit_confidence`, `min_landmark_confidence`); reach hysteresis (enter < exit, metres).
- Object selection: nearest grabbable object within reach; `InteractionObject(position, grabbable)`; hover enter/exit.
- Acks: GRAB_REQUEST and RELEASE wait for adapter ack (`config/world.yaml require_adapter_ack: true`, 500 ms timeout → safe default no-grab); dedup via `EventDeduper`; move rate cap 30 Hz (`move_max_hz`).
- Coordination: sensor scoring, set selection, leases, adaptation, occlusion/delay/disconnect scenarios (demo 1–6b), fusion-failure handling, audit log.
- Integration: `SessionCoordination` consumes real `FusionService` output; `test_coord_engine_integration.py` covers the seam; Phase 4's `attach.py` wires it per session.

**PARTIALLY IMPLEMENTED:** none material.
**MISSING:** body-gesture concepts (would follow Phase 1's pose extension); runtime tuning UI (thresholds are config-file today — intentional).
**Present but never operationally verified:** pinch/reach/confirm behaviour on **real human hands** and the tuned values; interaction continuity over long real sessions; real tracking-loss timing.
**Known correctness-by-construction:** transition rules are deterministic and hysteresis-guarded; false-positive/negative behaviour on real hands is *unknown by design until tuned* — this is the phase's core remaining validation.
**Hidden dependencies:** Phase 1's handedness labels (`require_hand_agreement: true` in fusion) and Phase 2's metre-scale accuracy (reach distances are metric).

## 3. Real-world operational audit

- **Hardware:** the calibrated Phase 2 rig (no new hardware).
- **Install:** nothing new (Phase 3 code ships in the same process).
- **Configure:** only tuning after observation (`config/gesture.yaml` — pinch ratios, `confirm_ms`, reach distances, loss timeouts).
- **Start:** automatic — the agent and coordinator attach per session (no separate service).
- **What the human sees when it works:** operator page / logs show gesture state transitions `IDLE→HOVER→GRABBED→RELEASED`; `GRAB_REQUEST` events with ids; Phase 4 (if connected) confirms/denies via acks.
- **Failure diagnosis:** audit log (`GESTURE_TRANSITION`, reasons), coordinator events (`FUSION_IGNORED`, `NO_ACTIVE_LEASE`, lease/scoring events), `EventDeduper` counters.
- **Recovery:** tracking loss → bounded hold → safe cancel; session stop → coordinator `STOPPED` (seen in real e2e logs).

## 4. Actual verification audit

| Level | Achieved? | Evidence |
|---|---|---|
| 1 Code inspection | ✔ | agent/pinch/coordinator read in full |
| 2 Automated tests | ✔ | ~93 gesture+coordination tests green (in 411) |
| 3 Synthetic execution | ✔ | demo 9/9 scenarios; FSM/pinch sims |
| 4 Real service execution | ✔ (simulated fusion) | synthetic live e2e (gesture path over real wire) |
| 5 Real hardware execution | ✘ | no real hand ever classified |
| 6 Operational demo | ✘ | — |

## 5. Missing-work register

| ID | Class | Task | Files | Why | Action | Depends | P | Completion criteria | Evidence |
|---|---|---|---|---|---|---|---|---|---|
| P3-H1 | HUMAN | Real-pinch repetition campaign (≥10 pinches × repeat sessions) | operator page/logs | prove FSM on real landmarks | perform + observe | Phase 2 D2 | P0 | transitions correct on ≥80% of attempts (pre-tuning baseline) | log excerpt |
| P3-H2 | HUMAN | False-positive/negative tally | same | tune thresholds with data | count misses/false grabs | P3-H1 | P0 | counts recorded | tally |
| P3-H3 | HUMAN | Reach/hover behaviour check | same | reach distances metric-validated | hover near object | P3-H1 | P1 | hover enter/exit matches expectation | log |
| P3-H4 | HUMAN | Tracking-loss behaviour check (cover camera mid-hover/grab) | same | safe cancel path on real loss | cover camera | P3-H1 | P0 | hold → `GRAB_CANCELLED`/`TARGET_LOST`, no stale replay | log |
| P3-H5 | HUMAN | Tuning session if needed | `config/gesture.yaml` | real-hand fit | edit values, restart, repeat P3-H1 | P3-H2 | P1 | stable transition behaviour | tuned values + rerun log |
| P3-C1 | CONFIG | Threshold values finalized (post-tuning) | `config/gesture.yaml` | handover values | record tuned values | P3-H5 | P1 | values committed/documented | note |
| P3-D1 | DEVELOPMENT | Tuning-statistics helper (optional) | new script over logs | data-driven tuning | implement | P3-H1 | P3 | stats report | — |
| P3-D2 | DEVELOPMENT | Runtime threshold controls (optional) | gesture config path | avoid restart-per-tune | implement later | — | P3 | hot-tune works | — |
| P3-D3 | DEVELOPMENT | Body-gesture extension (follows Phase 1 pose work) | gesture/pipeline | scope expansion | future | P1-D2 | P3 | — | — |
| P3-V1 | VALIDATION | Ack/dedup behaviour observed on real events (with Phase 4 attached) | bridge logs | interface proof end-to-end | run with Phase 4 client | P3-H1, Phase 4 install | P1 | acks observed; no duplicate events | bridge/host logs |
| P3-B1 | BLOCKER | Real fused wrist data (unblocks at Phase 2 handover D2) | — | — | — | Phase 2 | P0 | — | — |

## 6. Definition of Done (Phase 3)

1. Real sensor-derived landmarks drive the FSM: hover, pinch-grab, move, release transitions occur correctly and repeatably with a human hand.
2. False-positive/negative baseline recorded; thresholds tuned (or justified as adequate).
3. Tracking loss produces the designed safe outcomes on real loss (no stale replays, bounded cancels).
4. Events consumed by Phase 4 with ack/dedup observed (with Phase 4's client or bridge harness).
5. Evidence: logs/audit excerpts + tuned config values + tally.

**Handover to Phase 4: NOT READY until the above pass** (`PHASE3_HANDOVER_CONTRACT.md`).
