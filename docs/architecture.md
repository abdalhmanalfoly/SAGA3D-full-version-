# Architecture: Phase 4 in one page

```
            Phases 1-3 repo  (READ-ONLY, imported; never edited)
   +-------------------------------------------------------------+
   | host.app.main:create_app -> FastAPI                          |
   |   /api/*  REST      /ws/sensor  cameras (Phase 1-3 protocol)  |
   |   SessionManager -> sessions -> fusion engine -> GestureAgent |
   |   SessionCoordination (Phase 3 host_adapter) per session      |
   +-------------------------------------------------------------+
                ^ imported via SAGA3_ROOT (attach.py adds its path)
                |
   +------------+-------------------------------------------------+
   | saga4_world (Phase 4 workspace, this repo)                    |
   |                                                               |
   |  attach.py        create_phase4_app(): the combined app        |
   |     - wraps manager.create_session/stop_session (live instance) |
   |     - adds /ws/world (WorldSocketSession) + 20 Hz ticker       |
   |     - SAGA_LOG_DIR / SAGA_CALIBRATION_DIR default OUT of P3    |
   |                                                               |
   |  bridge.py        SessionWorld: fusion result -> validated     |
   |                   HandSample -> GestureAgent (REAL Phase 3     |
   |                   task) -> events/poses -> per-conn queues     |
   |                   WorldConnection: pose slots (collapse),      |
   |                   event FIFO (256), drain priority             |
   |                                                               |
   |  server.py        WorldSocketSession: reader/writer tasks,     |
   |                   handshake, heartbeat, fatal/close discipline |
   |  protocol.py      strict wire validation BOTH directions       |
   |  transform.py     WorldTransform: the ONE rig->Godot mapping   |
   |  status.py        derived host state (TRUST states, not blind) |
   |  config.py        config/world.yaml + env (SAGA3_ROOT etc.)    |
   |  p3.py            contract symbols from Phases 1-3 (GestureAgent,  |
   |                   HandSample, InteractionObject, SessionCoordination) |
   |                   imports; attach.py additionally imports host.app  |
   +-------------------------------------------------------------+
                   |  ws://.../ws/world?session=<id>    (INTERACTION_EVENT 1.0)
                   v
   +-------------------------------------------------------------+
   | Godot 4.3 project (godot/)                                   |
   |   world_client.gd   single validation gate                   |
   |   main.gd           SIG wiring, ACK dispatch (GRAB/RELEASE)  |
   |   hand_marker.gd    pose only, freeze-on-invalid             |
   |   grabbable_cube.gd events only, plausibility-screened moves |
   |   status_ui.gd      connection/host/gesture/quality panels   |
   +-------------------------------------------------------------+
```

## Data flow (grab)

sensor frame -> Phase 2 sync -> Phase 2 fusion (FusionResult) -> `bridge.on_fusion_result ->
validated HandSample + pinch evidence (median over contributing views) -> REAL GestureAgent.update ->
out.events[] (HOVER_*, GRAB_REQUEST, RELEASE, GRAB_CANCELLED) and out.moves[] (MOVE_TARGET) -> queues
-> WorldSocketSession._writer (drain priority) -> Godot world_client.gd validates -> main.gd ACKs
GRAB_REQUEST/RELEASE -> agent's `acknowledge()` continues the state machine (require_adapter_ack=true)
-> GRAB_CONFIRMED/RELEASE_CONFIRMED back over the wire.

## Deliberate design decisions

* **One process, one port.** Godot talks to the same uvicorn as the cameras; no second
  daemon, no extra state to keep in sync.
* **Monkey-patched runtime wiring, zero source edits.** create_session/stop_session are
  wrapped ON THE INSTANCE (Phase 3 handoff explicitly defers that wiring); Phase 1-3 files
  are byte-identical after a Phase 4 run (verified by `git status` in that repo).
* **Transform only in one place.** (docs/coordinates.md).
* **Bounded everything.** Event FIFO 256, pose slots 2, max 16 objects,
  max_message_bytes 16384: a malicious or broken client can queue-bloat a channel but not
  exhaust memory.
* **Collapse poses, keep events.** Continuous pose is best-effort by nature; discrete
  interlock events are never silently dropped while connected.
* **Fail closed.** Transform errors, protocol errors, calibration absence and fusion
  invalid all suppress interaction rather than degrade it silently.
* **Real Phase 3 logic exercised.** The gesture state machine, pinch detector, trust
  states and the acknowledgment loop are the ACTUAL Phase 3 code, not re-implementations;
  tests import from the real repo.
