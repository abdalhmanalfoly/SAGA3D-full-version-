# PHASE 4 — DEVELOPMENT CHECKLIST (code tasks only)

**Honest scope:** the bridge is complete and tested (54 tests); the Godot scripts are complete but never executed. **No P0 development work** — the critical path is: install Godot (human) → validate → verify transform → demo. Items below are grounded in repo evidence.

## DEV-P4-1 — Godot headless validation harness (P3, but do it right after install)
- **Problem:** nothing automates Godot-side validation; the only check is the manual `--headless --check-only` (documented in `docs/setup.md`). Once Godot is installed, a repeatable harness makes every future change safe.
- **Affected files:** new `scripts/check_godot.py` or `.sh` (locates the Godot executable via env var e.g. `SAGA_GODOT_EXE`, runs `--headless --check-only`, reports pass/fail); optionally a GUT-style script test later.
- **Implementation:** thin wrapper + doc note; no changes to `godot/` scripts required for the check-only level.
- **Why:** the Phase 4 gate requires *executed* evidence; a one-command harness turns it into a repeatable step.
- **Dependencies:** Godot installed (P4-H1).
- **Acceptance criteria:** running the harness on this repo exits 0 and reports the Godot version.

## DEV-P4-2 — End-to-end latency instrumentation (P2, after the first interactive demo)
- **Problem:** the 150 ms design budget was only ever measured synthetically host-side (median 3 ms capture→publish, loopback). Browser→host→fusion→agent→bridge→Godot end-to-end latency has never been measured anywhere.
- **Affected files:** timestamp pass-through check in `adapter/saga4_world/bridge.py` (poses/events already carry `sample_ms`/`timestamp_ms`), a Godot-side log of marker-update deltas in `hand_marker.gd` or `status_ui.gd` (optional), a summarizing helper over host logs.
- **Implementation:** compute p50/p95 from `captured_at_ms → event/pose receipt` across a recorded session; add Godot render-side jitter note manually if needed.
- **Why:** Phase 4's "runtime stability" DoD and the project's performance readiness require a real number.
- **Dependencies:** a real interactive session having run.
- **Acceptance criteria:** p95 recorded; compared against the 150 ms budget explicitly.

## DEV-P4-3 — Explicit lifecycle hooks refactor (P3, optional hygiene)
- **Problem:** `attach.py` wires per-session bridging by wrapping live `SessionManager.create_session/stop_session` instances (monkey-patching on the live object, never source edits). It works and is fully covered by tests, but explicit hooks would be cleaner.
- **Affected files:** `adapter/saga4_world/attach.py`; possible small hook additions in `host/app/session_manager.py`.
- **Implementation:** add optional lifecycle callbacks to `SessionManager`; `attach.py` registers them instead of wrapping. Preserve behaviour exactly (wrap remains a fallback).
- **Why:** maintainability only — explicitly deferred by the consolidation to minimize risk.
- **Dependencies:** none.
- **Acceptance criteria:** all 54 adapter tests (incl. 4 real-server e2e) stay green; smoke 8/8 stays green.

## DEV-P4-4 — Godot scene automated smoke (P3, optional, after harness exists)
- **Problem:** `--check-only` validates scripts, not scene instantiation or `world_client.gd` runtime behaviour.
- **Affected files:** `godot/` (a minimal headless test scene/script), optional GUT addon.
- **Implementation:** headless script that instantiates `main.tscn`, asserts `world_client` node exists and its exported vars parse; deeper wire tests would need a mock WS host (possible: point `world_client` at a local Python stub).
- **Why:** currently any Godot-side regression is caught only interactively.
- **Dependencies:** DEV-P4-1.
- **Acceptance criteria:** headless run reports scene + client checks.
- **Label:** optional; the manual checklist covers acceptance.

## Explicitly NOT broken — do not rework
- Protocol validation both directions, one-client rule, hello/heartbeat timeouts, bounded queues/backpressure: 54 tests green.
- Transform module: validated orthonormality/det/fingerprint/fail-closed — the *default values* are the unvalidated part (physical verification task, not code).
- `world_client.gd` reconnect/heartbeat/acks: code-correct; the historical `WebSocketPeer.poll()` bug is already fixed (`d5a68be`) — do not re-introduce changes around it without the harness.
- Mid-grab disconnect recovery (local release + OBJECT_STATE re-declaration): implemented per `docs/setup.md` §6; awaiting live proof only.
- No placeholder or dead modules found in Phase 4 ownership areas; `config/world.yaml` bounds are coherent with the bridge limits.
