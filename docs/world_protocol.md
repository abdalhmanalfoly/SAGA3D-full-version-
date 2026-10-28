# World Protocol 1.0 (`INTERACTION_EVENT 1.0` / world contract)

`/ws/world` is served by the SAME FastAPI process and port as the Phase 1-3 sensor host
(default `ws://127.0.0.1:8765/ws/world?session=<session_id>`). Godot 4.x is always the
client; the host never dials out. Exactly one Godot client per session — a second
connection is answered with `ERROR(WORLD_CLIENT_EXISTS, fatal)` and closed.

This document describes the wire contract enforced by `adapter/saga4_world/protocol.py`.
Validation is strict: unknown fields are rejected (`SCHEMA_VALIDATION_FAILED`), binary
frames are rejected (`BINARY_NOT_SUPPORTED`), and every message carries a monotonically
increasing `sequence_number` **per direction** (stale sequences produce a non-fatal
`STALE_SEQUENCE` ERROR; a DROP in a critical sequence is fatal).

## Framing rules

* WebSocket TEXT frames only, UTF-8 JSON, `max_message_bytes` = 16384 bytes.
* Every message has: `protocol_version` ("1.0"), `message_type`, `session_id`,
  `sequence_number` (int, each side maintains its own counter), `timestamp_ms`.
* Extra fields in either direction are protocol violations (futures need a version bump,
  they are not silently ignored).

## Handshake

1. Godot connects, then sends `WORLD_HELLO` (client → host):

```json
{"protocol_version": "1.0", "message_type": "WORLD_HELLO", "session_id": "sess_x",
 "sequence_number": 0, "timestamp_ms": 1730000000000, "client_id": "godot-win-1",
 "objects": [
   {"object_id": "cube_1", "position": [0.0, 0.04, -1.6],
    "grabbable": true, "seen": true, "grabbable_conflict": false}
 ]}
```

`objects` (max 16) declares the scene's interactive objects **in Godot coordinates**; the
host applies the inverse transform (docs/coordinates.md) to place them in rig space for the
gesture agent. Server-side, a session that sends no `WORLD_HELLO` within
`hello_timeout_s` (5 s) is rejected.

2. Host answers `WORLD_READY` (host → Godot), echoing accepted objects and the transform
   fingerprint:

```json
{"protocol_version": "1.0", "message_type": "WORLD_READY", "session_id": "sess_x",
 "sequence_number": <n>, "timestamp_ms": ..., "host_version": "saga4-world-1.0",
 "world_protocol_version": "1.0",
 "transform_fingerprint": "1|1,0,0|0,0,1|0,-1,0|0,0,-1.6|False|x:-2..2;y:-0.2..2;z:-4..0.2"}
```

## Host → Godot messages

| message_type | contents |
|---|---|
| `WORLD_READY` | handshake result (above) |
| `POSE_UPDATE` | collapsed latest pose slot: `position` [x,y,z] (Godot metres), `world_position_m` (rig metres, same sample), `world_frame_id`, `quality` 0..1, `sample_timestamp_ms`, `status`, `valid`, up to 8 `warnings`; when nothing valid arrived the position is `null` and `valid: false` |
| `INTERACTION_EVENT` | one discrete gesture event: `event_id` (globally unique, used for ACKs), `event_type`, `target_object_id`, optional `hand_position`, `reason` |
| `HOST_STATUS` | derived host state: `state` (REDUCED_STOPPED / INITIALIZING / WAITING_FOR_SENSORS / CALIBRATION_REQUIRED / READY / TRACKING / DEGRADED / ERROR / SHUTTING_DOWN), `detail`, compact counters/sensor snapshot |
| `WORLD_STOP` | session is stopping; Godot must release anything attached and reconnect for a new session |
| `HEARTBEAT_ACK` | echo of Godot's `HEARTBEAT` timestamp |
| `ERROR` | `error_code`, `detail`, `fatal`; fatal errors are followed by a server close (1008) |

`KNOWN_EVENT_TYPES`: `HOVER_ENTER`, `HOVER_EXIT`, `GRAB_REQUEST`, `GRAB_CONFIRMED`,
`MOVE_TARGET`, `RELEASE`, `GRAB_CANCELLED`, `TRACKING_LOST`. The 2D event detail is the
Phase 3 `InteractionEvent` passed through (`event_id` unique, `gesture_state`,
`interaction_id`, `cancel_reason`, `reason`, `continuous`); `hand_target` additionally
carries the Godot-space position. Acks are expected on: `GRAB_REQUEST`, `RELEASE`,
`GRAB_CANCELLED`.

`HOST_STATUS` carries the derived state plus compact counters (sensor/fusion/quality
snapshots); states are the Phase 3 `HOST_STATES` set: `STOPPED`, `INITIALIZING`,
`WAITING_FOR_SENSORS`, `CALIBRATION_REQUIRED`, `READY`, `TRACKING`, `DEGRADED`, `ERROR`,
`SHUTTING_DOWN`.

## Godot → host messages (`GODOT_TO_HOST`)

| message_type | contents |
|---|---|
| `WORLD_HELLO` | scene declaration (above) |
| `OBJECT_STATE` | refreshed object list; same shape as `WORLD_HELLO.objects`. Sent on discrete scene changes (grab started/ended, reset) — a few Hz, never per frame |
| `ACK` | `ack_event_type` ∈ {GRAB_REQUEST, RELEASE, GRAB_CANCELLED}, `event_id`, `accepted` bool, `target_object_id`, `reason` |
| `HEARTBEAT` | keep-alive; answered by `HEARTBEAT_ACK`; `heartbeat_timeout_s` (15 s) without one marks the link degraded |

`MOVE_TARGET` is never acknowledged and is rate-limited by the gesture agent (30 Hz) plus
the pose-slot collapse; a drop of a MOVE_TARGET slot is not an error by design.

## Error codes

Non-fatal (message ignored, link stays up): `SCHEMA_VALIDATION_FAILED`,
`MALFORMED_JSON`, `MALFORMED_MESSAGE`, `MESSAGE_TOO_LARGE`, `UNSUPPORTED_MESSAGE_TYPE`
(per-message), `STALE_SEQUENCE`, `BINARY_NOT_SUPPORTED`.

Fatal (ERROR then close 1008, `FATAL_CODES` in `server.py`): `SESSION_MISMATCH`,
`SESSION_NOT_ACTIVE`, `WORLD_CLIENT_EXISTS`, `HELLO_TIMEOUT`,
`UNSUPPORTED_PROTOCOL_VERSION`. `UNKNOWN_SESSION` (at connect time) closes before accept.

## Receipt discipline (defined here and nowhere else)

* `GRAB_REQUEST` — Godot answers `ACK(accepted=true)` only if the object exists, is
  currently grabbable and not already held; otherwise `accepted=false` + `reason`.
  No ack within `ack_timeout_ms` (500) → the host cancels the grab (GRAB_CANCELLED) —
  absence of ack is never treated as implicit consent.
* `RELEASE` / `GRAB_CANCELLED` — same discipline with `release_ack_required: true`.

## Sequence semantics

Per-message-direction counters; `STALE_SEQUENCE` (repeat or backwards) is reported and
the message ignored but is NOT fatal — a client may recover. Discrete events use bounded
FIFO queues (256) and are never dropped while the client is connected; pose slots
(collapse to latest 2) drop silently when overloaded. The server's `_writer` drains with
priority: control > discrete events > (aging) MOVE_TARGET (older than `move_yield_ms` is
sent before a pose so continuous pose traffic cannot starve it) > collapsed poses.
