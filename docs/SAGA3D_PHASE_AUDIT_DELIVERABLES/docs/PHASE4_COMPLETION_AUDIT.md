# PHASE 4 — COMPLETION AUDIT: Godot Integration & Final System

**Date:** 2026-11-12 · **Repo:** `saga-3d-phase-4` @ `bd01443` · read-only audit

**Phase gate status: IN PROGRESS** — the Python bridge is *IMPLEMENTATION COMPLETE — NOT OPERATIONALLY VERIFIED against a real Godot*; the Godot side exists as code but has **never been executed** (Godot 4.3 is not installed on this machine — verified `where godot` empty). Highest achieved verification = level 3/4 for the bridge (54 adapter tests incl. 4 real-uvicorn e2e); the Godot project is at level 1 only (code inspection).

---

## 1. Phase ownership

| Component | Path | Role |
|---|---|---|
| Combined launcher | `adapter/saga4_world/attach.py`, `scripts/run_host.py` | one process: Phase 1–3 host + `/ws/world` + 20 Hz ticker + per-session bridge wiring |
| Bridge | `adapter/saga4_world/bridge.py`, `server.py` | `SessionWorld` per session; `WorldSocketSession` (hello 5 s, heartbeat 15 s) |
| Protocol | `adapter/saga4_world/protocol.py` | strict both-direction validation; `WORLD_HELLO` (client_id, objects ≤16); one client per session (`WORLD_CLIENT_EXISTS`) |
| Transform | `adapter/saga4_world/transform.py` | THE single rig→Godot map: `godot = scale*(R@rig)+t`; validated orthonormal, det +1, fingerprint, volume flag, fail-closed on non-finite |
| Status | `adapter/saga4_world/status.py` | host-state → `HOST_STATUS` stream |
| Config | `config/world.yaml` | endpoint, bounds (16 KB msg, 16 objects, 60 Hz pose cap, event buffer 256, pose slots 2), ack discipline, transform |
| Godot project | `godot/` (`project.godot`, `scenes/main.tscn`, `scripts/{world_client,main,hand_marker,grabbable_cube,status_ui}.gd`) | world client + scene + interaction UI |
| Docs | `docs/world_protocol.md`, `docs/coordinates.md`, `docs/demo_script.md`, `docs/setup.md` | wire contract, transform math + two-point verification, demo walkthrough |
| Tests | `tests/` (54: 50 unit + 4 real-server e2e) | all pass |

**Consumes from Phases 1–3:** fused pose (transformed) + `INTERACTION_EVENT` stream + ack channel + calibration/host status.
**Consumes from the environment:** Godot 4.3 executable (MISSING on this machine).

## 2. Implementation audit

**IMPLEMENTED (inspection + tests):**
- Bridge lifecycle: hello timeout, heartbeat, bounded reconnection on the Godot side (1→5 s cap, `world_client.gd`), fatal-error policy (`retry_after_fatal: false`), one-client-per-session enforcement, session attach/detach via wrapped `create_session`/`stop_session` (validated by tests; explicit-hook refactor listed as optional).
- Queues/backpressure: discrete-event buffer 256 (never dropped while connected), pose-slot collapsing (2) — designed for a 20 Hz tick under load.
- Ack discipline: `require_adapter_ack: true`, 500 ms GRAB/RELEASE ack timeouts — safe default (no grab without ack).
- Transform: constant, fingerprinted; fingerprint change forces track/interaction reset (logged at attach, sent in `WORLD_READY.transform_fingerprint`); `reject_outside_volume` option; non-finite → fail closed.
- Godot scripts: `world_client.gd` — full signal set (pose valid/invalid, hover, grab request/confirmed/move/release/cancelled, tracking lost, host status/errors, world ready, connection), heartbeat (idle > ~1 s), CLI `--session=`, OBJECT_STATE re-declaration on re-hello (mid-grab disconnect recovery); the earlier `WebSocketPeer.poll()` bug is FIXED (commit `d5a68be`). `main.gd` wires all signals; `hand_marker.gd`, `grabbable_cube.gd`, `status_ui.gd` implement marker/cube/panel.
- Startup/shutdown: `run_host.py --session demo1` verified (smoke/e2e); clean session stop observed in e2e logs (`COORDINATOR_STOPPED`, `session_stopped`).

**PARTIALLY IMPLEMENTED:** Godot-side automated testing (no headless script test exists — depends on installing Godot).
**MISSING:** nothing in code; the **environment** (Godot executable) and the **physical transform verification** are absent.
**Present but never operationally verified:** every Godot runtime behaviour (project import, scene load, WS connect, marker motion, grab interaction); the default transform against a physical rig; runtime stability over long sessions.
**Disconnections/recovery (coded, unproven on Godot):** host drop → Godot backoff reconnect + OBJECT_STATE re-declare; Godot drop → bridge marks degraded after 15 s heartbeat timeout; mid-grab → local release + re-hello.

## 3. Real-world operational audit

| Requirement | Where | Status |
|---|---|---|
| Godot 4.3 install | godotengine.org (standard win64) | **HUMAN ACTION — not installed** |
| Import project / open scene | open `godot/project.godot`; main scene preconfigured | documented |
| Headless check | `Godot.exe --path godot --headless --check-only` | command documented; never run |
| Interactive run | `Godot.exe --path godot -- --session=demo1` (or F5 with arg) | documented |
| Host integration | same process/port as sensor host (`ws://127.0.0.1:8765/ws/world?session=…`) | smoke-verified route exists |
| Transform alignment | two-reference-point physical check (`docs/coordinates.md` §5) | procedure exists; **requires Phase 2 rig** |
| What you see when it works | `WORLD_READY` on status panel; marker follows hand; cube grabs/moves/releases | defined in `docs/demo_script.md` |
| Failure diagnosis | status panel errors (`host_error` signals), host logs (`world_socket_*`, `message_rejected`), fingerprint log | tooling exists |
| Recovery | Godot reconnect (bounded), local release on disconnect, re-declare objects | coded; unproven live |

## 4. Actual verification audit

| Level | Achieved? | Evidence |
|---|---|---|
| 1 Code inspection | ✔ | all adapter modules + all 5 GDScripts read |
| 2 Automated tests | ✔ | 54 adapter tests (50 unit + 4 real-server e2e) green |
| 3 Synthetic execution | ✔ | real uvicorn server e2e; `/ws/world` handshake smoke |
| 4 Real service execution | ✔ (bridge) / ✘ (Godot) | bridge ran; Godot never launched |
| 5 Real hardware execution | ✘ | — |
| 6 End-to-end demo | ✘ | the project's final milestone |

## 5. Missing-work register

| ID | Class | Task | Files | Why | Action | Depends | P | Completion criteria | Evidence |
|---|---|---|---|---|---|---|---|---|---|
| P4-H1 | HUMAN | Install Godot 4.3 (stable win64) | environment | nothing Godot-side can run without it | download/install | — | P0 | `Godot.exe --version` works | version output |
| P4-V1 | VALIDATION | Headless project check | `godot/` | first execution evidence | `--headless --check-only` | P4-H1 | P0 | no script errors | console output |
| P4-V2 | VALIDATION | Bridge ↔ Godot connect demo | `world_client.gd` + bridge | prove the wire | launch with host+session | P4-V1 | P0 | `WORLD_READY`; status panel connected | screenshot/log |
| P4-H2 | HUMAN | Marker follows real hand | Phase 2 rig + Godot | transform proof (part 1) | hold marked point | P4-V2, Phase 2 D2 | P0 | marker position ≈ fusion reading | note |
| P4-H3 | HUMAN | Two-reference-point transform verification | `docs/coordinates.md` §5 | THE transform validation | 2 points, ≥0.5 m apart, diff heights | P4-H2 | P0 | both agree within a few cm; else adjust `config/world.yaml` transform | recorded readings |
| P4-V3 | VALIDATION | Full interaction demo (hover→grab→move→release) | scene + Phase 3 events | the project's purpose | perform real gestures on cube | P4-H3, Phase 3 D3 | P0 | cube follows hand and releases | video/log |
| P4-V4 | VALIDATION | Disconnect/recovery demo | both sides | stability proof | kill Godot mid-session; stop a camera mid-grab | P4-V3 | P1 | reconnect + local release; no stale grabs | logs |
| P4-V5 | VALIDATION | Complete startup/shutdown from cold | runbook | final acceptance | full runbook pass | all | P0 | 15 runbook steps pass | checklist |
| P4-C1 | CONFIG | Transform values finalized post-verification | `config/world.yaml` | record verified R/t | update after P4-H3 | P4-H3 | P0 | values match verification | file diff |
| P4-D1 | DEVELOPMENT | Godot headless script test harness | `godot/`, `scripts/` | repeatable validation | optional GUT/--check-only wrapper | P4-H1 | P3 | check runs in CI-like step | — |
| P4-D2 | DEVELOPMENT | Latency instrumentation (optional) | bridge/Godot | SW-09 evidence | timing fields | P4-V3 | P2 | p95 e2e recorded | — |
| P4-D3 | DEVELOPMENT | Explicit attach hooks refactor (optional) | `adapter/saga4_world/attach.py` | hygiene; behavior already validated | refactor | — | P3 | 54 tests stay green | test run |
| P4-B1 | BLOCKER | Godot executable absent | environment | blocks all Godot validation | install | — | P0 | — | — |
| P4-B2 | BLOCKER | Real calibration absent | — | transform verification + real poses impossible | Phase 2 D2 | Phase 2 | P0 | — | — |

## 6. Definition of Done (Phase 4 — and the project)

1. Godot installed; headless check passes.
2. Bridge ↔ Godot demo: `WORLD_HELLO` → `WORLD_READY` with fingerprint logged.
3. **Two-reference-point transform verification passed** (or transform corrected and re-verified).
4. Full interaction demo: real hand → marker → hover → grab → move → release, repeatable.
5. Recovery demos (disconnect/reconnect, mid-grab loss) behave as designed.
6. Complete cold-start runbook executed; evidence archived.

**FINAL ACCEPTANCE = all six above** (`PHASE4_FINAL_ACCEPTANCE_CHECKLIST.md`).
