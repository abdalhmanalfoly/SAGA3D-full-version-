# Demo script: what the Phase 4 show-piece demonstrates

## Scene roles (godot/scenes/main.tscn)

| node | script | role |
|---|---|---|
| `WorldClient` | `scripts/world_client.gd` | THE single WebSocket/validation gate: every host frame is parsed and whitelisted here; signals emitted to the rest |
| `HandMarker` | `scripts/hand_marker.gd` | the only node following validated fusion pose; `mark_lost()` freezes, it NEVER dead-reckons |
| `GrabbableCube` | `scripts/grabbable_cube.gd` | hover highlight + GRAB/MOVE/RELEASE driven ONLY by host `INTERACTION_EVENT`s; plausibility screen (max speed / max distance per tick) on MOVE_TARGET |
| `StatusUI` | `scripts/status_ui.gd` | connection, derived host state, gesture state, quality, object counters (labels maps by index so no hard-coded number drift) |
| `SagaMain` (`scripts/main.gd`) | wiring + ACK dispatch |

## Beat by beat

1. **Connect.** Host starts (`scripts/run_host.py --session demo1`), Godot joins,
   sends `WORLD_HELLO` (declares `cube_1` at its scene position), the host returns
   `WORLD_READY` + the transform fingerprint (both panels go "READY"/"world ready").
2. **Pose.** Each `POSE_UPDATE` moves the marker (collapsed pose slot; intermediate
   positions collapse). An invalid pose freezes the marker at its last valid position and
   the UI goes TRACKING_LOST — no extrapolation, ever (safety-first contract).
3. **Hover.** An open hand that comes within reach of the (rig-space inverse-transformed)
   cube triggers `HOVER_ENTER` on the host; Godot highlights the cube.
4. **Grab.** Pinch confirmed (≥3 samples inside `confirm_ms`) emits `GRAB_REQUEST`. Godot
   checks the object is local, grabbable and free, begins the grab and sends
   `ACK(accepted=true, event_id=...)`. The host answers `GRAB_CONFIRMED`.
   Note the deliberate two-phase protocol: host asks, Godot answers, host confirms.
5. **Move.** While grabbed, `MOVE_TARGET` (30 Hz, transformed Godot coordinates) drags the
   cube — bypassing the plausibility screen only as far as per-frame distance limits allow.
6. **Release.** Pinch opens → `RELEASE` event → Godot drops it at the last confirmed
   position and ACKs → `release_ack_required: true` closes the loop host-side.
7. **Cancel path.** Tracking loss (hand out of volume, low confidence, session teardown,
   ack timeout) yields `TRACKING_LOST` / `GRAB_CANCELLED`; the cube is released safely
   (never flung, never kept attached to a phantom hand) and the ACK loop is the same.
8. **Stop.** Session stop sends `WORLD_STOP`; Godot releases anything attached, shows the
   stop reason, and (re)connecting becomes possible for a new session.

## Root safety invariants demonstrated

* Discrete interlocks remain discrete: HOST_STATUS/ERROR and events never collapse into
  the pose stream (different queues / priorities — docs/world_protocol.md).
* No ack → no grab: the host NEVER presumes consent (docs/world_protocol.md §Receipt).
* Godot validates everything it consumes (protocol.py mirrors the same contract); the
  host validates everything Godot sends (unknown fields rejected).
* Marks of trust: HOST_STATUS is DERIVED (WAITING_FOR_SENSORS/CALIBRATION_REQUIRED)
  rather than asserted by the bridge — the demo shows the inhibitory path live when no
  calibrated sensor is attached.
