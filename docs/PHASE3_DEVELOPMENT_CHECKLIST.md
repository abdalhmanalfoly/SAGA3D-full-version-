# PHASE 3 — DEVELOPMENT CHECKLIST (code tasks only)

**Honest scope:** the gesture/coordination software is complete and heavily tested (≈93 tests green). There is **no P0 development work**; the critical path is real-hardware validation + possible threshold tuning (human work). Items below are grounded; optional conveniences labelled.

## DEV-P3-1 — Tuning-statistics helper (P2/P3, after first real campaign)
- **Problem:** Phase 3's remaining risk is threshold fit on real hands (`config/gesture.yaml` values are documented starting points). The FSM/pinch modules emit rich evidence (transition reasons, ratio counters, confirm timings) into the audit log, but nothing aggregates it for tuning.
- **Affected files:** new helper script over `logs/` audit/fusion JSONL (e.g. `scripts/gesture_stats.py`); no changes to `host/app/gesture/*`.
- **Implementation:** aggregate per-session: pinch-ratio distributions at enter/exit, confirm durations, reach distances at hover transitions, loss-gap durations at cancels, FP/FN candidate counts; print a table suggesting which thresholds look mis-fitted.
- **Why for real operation:** the tuning session (Phase 3 checklist P3-10) becomes data-driven instead of trial-and-error.
- **Dependencies:** a real gesture session having run.
- **Acceptance criteria:** report generated from a real session's logs; used during tuning.
- **Evidence:** report output.

## DEV-P3-2 — Runtime threshold controls (P3, optional)
- **Problem:** tuning today = edit `config/gesture.yaml` + restart host (`load_gesture_config` reads at startup; `GestureAgent` holds a frozen `GestureCfg`).
- **Affected files:** `host/app/gesture/config.py`, `host/app/gesture/agent.py` (config hot-swap or per-session override), possibly a small REST endpoint in the operator surface.
- **Implementation:** safest variant — a validated per-session config-override API that rebuilds the agent's `GestureCfg` between transitions (the FSM is deterministic per call; swapping configs at a transition boundary is safe).
- **Why:** faster hardware tuning loops; not required for correctness.
- **Dependencies:** DEV-P3-1 (need the data first).
- **Acceptance criteria:** threshold change applies without host restart; all 29 machine tests still green; config validation (`_chk` hysteresis rules) still enforced.
- **Label:** convenience; defaults must stay authoritative in `config/gesture.yaml`.

## DEV-P3-3 — Body-gesture extension (P3, follows Phase 1 pose work)
- **Problem/grounding:** only hand landmarks exist; if Phase 1 adds pose landmarks, gesture concepts beyond pinch (e.g. reach-by-body) become possible.
- **Affected files:** `host/app/gesture/{agent,pinch}.py`, `config/gesture.yaml`, fusion targets.
- **Implementation:** future design task; do not start before Phase 1 pose work exists.
- **Dependencies:** P1-D2.
- **Label:** scope expansion, not a defect.

## Explicitly NOT broken — do not rework
- FSM correctness: deterministic, hysteresis-guarded, bounded-loss, safe cancels — 29 machine tests + 14 pinch tests green; design documented in `agent.py`/`docs/gesture.md`.
- Ack/dedup discipline: `require_adapter_ack: true` (500 ms) + `EventDeduper` tested; safe default = no grab without ack.
- Coordination core: 9/9 demo scenarios (negotiation → adaptation → fusion outcome → gesture → safe cancellation) + ~50 unit tests — no defects found.
- `SessionCoordination` ↔ `FusionService` seam: covered by `test_coord_engine_integration.py`; consumed live in the synthetic e2e — the integration exists and is contract-tested; only *real-data* behaviour is outstanding (validation, not development).
- Event protocol v1.0 versioning: matches `config/world.yaml world_protocol_version: "1.0"` — consistent, tested.
