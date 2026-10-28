"""SAGA 3D Phase 4 WORLD protocol — version 1.0 (this file is the authoritative contract; see docs/world_protocol.md).

Transport: WebSocket, one JSON object per TEXT frame, endpoint ``/ws/world?session=<id>`` on the SAME
server that runs the Phase 1-3 sensor host (phase 4 launcher, ``adapter/saga4_world/attach.py``) — runs on one process and one port.
Direction: Godot is a CLIENT (connects to the host). Exactly one Godot client per active session (a
second connect is refused with ERROR(WORLD_CLIENT_EXISTS)).

Invariants that hold for every message on both directions:
  1. ``protocol_version`` == "1.0" and ``message_type`` are required.
  2. All fields are REQUIRED; absence is always an explicit ``null``. Unknown fields are rejected.
  3. JSON text frames only; max size 16384 bytes. Non-finite numbers (NaN/Infinity) are rejected — JSON never carries them.
  4. ``session_id`` of the bound session (mismatch = ERROR, the message is ignored).
  5. ``sequence_number`` strictly increases per stream. Streams are per direction and per channel:
       - control (host -> Godot):  WORLD_READY, HOST_STATUS, WORLD_STOP, HEARTBEAT_ACK, ERROR share one stream
       - pose (host -> Godot):     POSE_UPDATE
       - event (host -> Godot):    INTERACTION_EVENT
       - client (Godot -> host):   every client message shares one stream (Godot is slow compared to the host;
                                   no separate streams are needed client-side)
  6. ``timestamp_ms`` is the SENDER clock in epoch ms. It is used for staleness diagnostics only; ordering is by sequence.
  7. Positions are explicitly labelled: ``position`` is Godot coordinates ([x, y, z], 1 unit = 1 m),
     ``world_position_m`` is the raw fusion value in the rig/world frame (metres). ``world_frame_id`` is the
     calibration frame id; the adapter records both plus the transform identity on every pose.
  8. Godot NEVER blindly trusts the host: message shape, session, sequence ordering, event types and
     finite numerics are validated (see adapter/../protocol and godot/scripts/world_client.gd) before ANY scene action.
  9. The host NEVER blindly trusts Godot either: same checks client-side (this module) + every object id
     Godot declares is validated against a whitelist pattern; object positions are converted through the
     inverse transform and re-validated inside the safe volume before the gesture agent sees them.

Reuses / extends the Phase 3 event names 1:1 (host/app/gesture/events.py EventType):
  HOVER_ENTER, HOVER_EXIT, GRAB_REQUEST, GRAB_CONFIRMED, MOVE_TARGET, RELEASE, GRAB_CANCELLED,
  TRACKING_LOST  — packaged inside INTERACTION_EVENT ``event_type``. No renames.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from typing import Any, Mapping

WORLD_PROTOCOL_VERSION = "1.0"

MESSAGE_SIZE_LIMIT = 16384
_SESSION_RE = re.compile(r"^[A-Za-z0-9_-]{4,64}$")
_ID_RE = re.compile(r"^[A-Za-z0-9_:.-]{1,64}$")

# --------------------------------------------------------------------------
# message type names
# --------------------------------------------------------------------------
# host -> Godot
MT_WORLD_READY = "WORLD_READY"
MT_POSE_UPDATE = "POSE_UPDATE"
MT_INTERACTION_EVENT = "INTERACTION_EVENT"
MT_HOST_STATUS = "HOST_STATUS"
MT_WORLD_STOP = "WORLD_STOP"
MT_HEARTBEAT_ACK = "HEARTBEAT_ACK"
MT_ERROR = "ERROR"
# Godot -> host
MT_WORLD_HELLO = "WORLD_HELLO"
MT_OBJECT_STATE = "OBJECT_STATE"
MT_ACK = "ACK"
MT_HEARTBEAT = "HEARTBEAT"

HOST_TO_GODOT = frozenset({MT_WORLD_READY, MT_POSE_UPDATE, MT_INTERACTION_EVENT, MT_HOST_STATUS, MT_WORLD_STOP, MT_HEARTBEAT_ACK, MT_ERROR})
GODOT_TO_HOST = frozenset({MT_WORLD_HELLO, MT_OBJECT_STATE, MT_ACK, MT_HEARTBEAT})

# host -> Godot stream channels
STREAM_CONTROL = "control"
STREAM_POSE = "pose"
STREAM_EVENT = "event"
_STREAM_OF = {
    MT_POSE_UPDATE: STREAM_POSE,
    MT_INTERACTION_EVENT: STREAM_EVENT,
    MT_WORLD_READY: STREAM_CONTROL,
    MT_HOST_STATUS: STREAM_CONTROL,
    MT_WORLD_STOP: STREAM_CONTROL,
    MT_HEARTBEAT_ACK: STREAM_CONTROL,
    MT_ERROR: STREAM_CONTROL,
}

# Godot -> host ACK must reference exactly these host event types (Phase 3 names, unchanged)
ACKABLE_EVENTS = frozenset({"GRAB_REQUEST", "RELEASE", "GRAB_CANCELLED"})

# INTERACTION_EVENT event types Godot accepts; everything else is forwarded to logs but NOT applied
KNOWN_EVENT_TYPES = frozenset({"HOVER_ENTER", "HOVER_EXIT", "GRAB_REQUEST", "GRAB_CONFIRMED", "MOVE_TARGET", "RELEASE", "GRAB_CANCELLED", "TRACKING_LOST"})
# topo-level host states (docs/architecture.md); Godot shows them verbatim in the status panel
HOST_STATES = frozenset({"STOPPED", "INITIALIZING", "WAITING_FOR_SENSORS", "CALIBRATION_REQUIRED", "READY", "TRACKING", "DEGRADED", "ERROR", "SHUTTING_DOWN"})


class WorldProtocolError(ValueError):
    """A world message violated the contract. ``code`` is a machine-readable reason; the message is never trusted."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _require(condition: bool, code: str, detail: str = "") -> None:
    if not condition:
        raise WorldProtocolError(code, detail)


def _num(v: Any, name: str, *, nullable: bool = False) -> float | None:
    if v is None:
        _require(nullable, "SCHEMA_VALIDATION_FAILED", f"{name} must not be null")
        return None
    _require(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v), "SCHEMA_VALIDATION_FAILED", f"{name} must be a finite number")
    return float(v)


def _int(v: Any, name: str) -> int:
    _require(isinstance(v, int) and not isinstance(v, bool), "SCHEMA_VALIDATION_FAILED", f"{name} must be an integer")
    return int(v)


def _str(v: Any, name: str, *, pattern: re.Pattern[str] | None = None, nullable: bool = False) -> str | None:
    if v is None:
        _require(nullable, "SCHEMA_VALIDATION_FAILED", f"{name} must not be null")
        return None
    _require(isinstance(v, str) and (pattern is None or pattern.match(v)), "SCHEMA_VALIDATION_FAILED", f"{name} failed its pattern")
    return v


def _vec3(v: Any, name: str, *, nullable: bool = False) -> tuple[float, float, float] | None:
    if v is None:
        _require(nullable, "SCHEMA_VALIDATION_FAILED", f"{name} must not be null")
        return None
    _require(isinstance(v, (list, tuple)) and len(v) == 3, "SCHEMA_VALIDATION_FAILED", f"{name} must be [x, y, z]")
    x = _num(v[0], f"{name}[0]")
    y = _num(v[1], f"{name}[1]")
    z = _num(v[2], f"{name}[2]")
    return (x, y, z)


def _obj(mapping: Mapping[str, Any], expected: set[str], code_detail: str = "") -> dict:
    _require(isinstance(mapping, dict), "MALFORMED_MESSAGE", "message must be a JSON object")
    missing = expected - set(mapping)
    _require(not missing, "SCHEMA_VALIDATION_FAILED", f"missing fields {sorted(missing)} {code_detail}")
    extra = set(mapping) - expected
    _require(not extra, "SCHEMA_VALIDATION_FAILED", f"unknown fields {sorted(extra)} {code_detail}")
    return dict(mapping)


def decode_frame(raw: str | bytes) -> dict:
    """Decode one incoming text frame; raises WorldProtocolError on anything the contract refuses."""
    if not isinstance(raw, str) and not isinstance(raw, bytes):
        raise WorldProtocolError("BINARY_NOT_SUPPORTED", "world frames must be UTF-8 text frames")
    try:
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
    except UnicodeDecodeError:
        raise WorldProtocolError("BINARY_NOT_SUPPORTED", "frame is not valid UTF-8 text") from None
    _require(len(text.encode("utf-8")) <= MESSAGE_SIZE_LIMIT, "MESSAGE_TOO_LARGE", f"world frames max {MESSAGE_SIZE_LIMIT} bytes")
    try:
        obj = json.loads(text)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise WorldProtocolError("MALFORMED_JSON", str(exc)) from None
    _require(isinstance(obj, dict), "MALFORMED_JSON", "message must be a JSON object")
    return obj


# --------------------------------------------------------------------------
# Godot -> host message parsing (host NEVER trusts the client)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class ParsedMessage:
    message_type: str
    session_id: str
    sequence_number: int
    timestamp_ms: float
    fields: dict = field(default_factory=dict)  # rest of the validated payload


@dataclass(frozen=True)
class ClientObject:
    object_id: str
    position: tuple[float, float, float]
    grabbable: bool


def parse_common(msg: Mapping[str, Any], *, expected_type: str | None, session_id: str,
                 extra_keys: set[str]) -> tuple[int, float]:
    """Shared envelope check; ``extra_keys`` are the message-type specific fields (full whitelist)."""
    _obj(msg, {"protocol_version", "message_type", "session_id", "sequence_number", "timestamp_ms"} | extra_keys,
         expected_type or "")
    _require(msg["protocol_version"] == WORLD_PROTOCOL_VERSION, "UNSUPPORTED_PROTOCOL_VERSION", f"expected {WORLD_PROTOCOL_VERSION}")
    mt = _str(msg["message_type"], "message_type")
    _require(mt in GODOT_TO_HOST, "UNSUPPORTED_MESSAGE_TYPE", f"unknown client type {mt!r}")
    if expected_type is not None:
        _require(mt == expected_type, "UNSUPPORTED_MESSAGE_TYPE", f"expected {expected_type}, got {mt}")
    _require(msg["session_id"] == session_id, "SESSION_MISMATCH", f"bound to {session_id}")
    return _int(msg["sequence_number"], "sequence_number"), _num(msg["timestamp_ms"], "timestamp_ms")


def _parse_objects(raw: Any) -> list[ClientObject]:
    _require(isinstance(raw, list) and len(raw) <= 16, "SCHEMA_VALIDATION_FAILED", "objects must be a list of at most 16 entries")
    out = {}
    for i, o in enumerate(raw):
        _require(isinstance(o, dict), "SCHEMA_VALIDATION_FAILED", f"objects[{i}] must be an object")
        _obj(o, {"object_id", "position", "grabbable"}, f"objects[{i}]")
        oid = _str(o["object_id"], "object_id", pattern=_ID_RE)
        _require(oid not in out, "SCHEMA_VALIDATION_FAILED", f"duplicate object_id {oid!r}")
        out[oid] = ClientObject(oid, _vec3(o["position"], f"objects[{i}].position"), bool(o["grabbable"]))
    return list(out.values())


def parse_world_hello(msg: Mapping[str, Any], session_id: str) -> ParsedMessage:
    seq, ts = parse_common(msg, expected_type=MT_WORLD_HELLO, session_id=session_id, extra_keys={"client_id", "objects"})
    cid = _str(msg["client_id"], "client_id", pattern=_ID_RE)
    objects = _parse_objects(msg.get("objects", []))
    return ParsedMessage(MT_WORLD_HELLO, session_id, seq, ts, {"client_id": cid, "objects": objects})


def parse_object_state(msg: Mapping[str, Any], session_id: str) -> ParsedMessage:
    seq, ts = parse_common(msg, expected_type=MT_OBJECT_STATE, session_id=session_id, extra_keys={"objects"})
    objects = _parse_objects(msg.get("objects", []))
    return ParsedMessage(MT_OBJECT_STATE, session_id, seq, ts, {"objects": objects})


def parse_ack(msg: Mapping[str, Any], session_id: str) -> ParsedMessage:
    seq, ts = parse_common(msg, expected_type=MT_ACK, session_id=session_id,
                           extra_keys={"ack_event_type", "event_id", "accepted", "target_object_id", "reason"})
    aet = _str(msg["ack_event_type"], "ack_event_type")
    _require(aet in ACKABLE_EVENTS, "SCHEMA_VALIDATION_FAILED", f"ack_event_type must be one of {sorted(ACKABLE_EVENTS)}")
    eid = _str(msg["event_id"], "event_id", pattern=_ID_RE)
    accepted = msg["accepted"]
    _require(isinstance(accepted, bool), "SCHEMA_VALIDATION_FAILED", "accepted must be a boolean")
    target = _str(msg["target_object_id"], "target_object_id", pattern=_ID_RE, nullable=True)
    reason = _str(msg["reason"], "reason", pattern=re.compile(r"^[A-Za-z0-9 _.-]{1,200}$"), nullable=True)
    return ParsedMessage(MT_ACK, session_id, seq, ts,
                         {"ack_event_type": aet, "event_id": eid, "accepted": accepted, "target_object_id": target, "reason": reason})


def parse_heartbeat(msg: Mapping[str, Any], session_id: str) -> ParsedMessage:
    seq, ts = parse_common(msg, expected_type=MT_HEARTBEAT, session_id=session_id, extra_keys={"fps", "state"})
    extra = {k: msg[k] for k in ("fps", "state") if k in msg}
    if "state" in extra:
        _require(extra["state"] is None or isinstance(extra["state"], str), "SCHEMA_VALIDATION_FAILED", "state must be a string or null")
    return ParsedMessage(MT_HEARTBEAT, session_id, seq, ts, extra)


_CLIENT_PARSERS = {MT_WORLD_HELLO: parse_world_hello, MT_OBJECT_STATE: parse_object_state, MT_ACK: parse_ack, MT_HEARTBEAT: parse_heartbeat}


def parse_client_message(raw: str | bytes, session_id: str, last_client_seq: int | None) -> ParsedMessage:
    """Full client-side validation: decode, type dispatch, session match and per-connection sequence monotonicity."""
    obj = decode_frame(raw)
    mt = obj.get("message_type")
    if mt not in _CLIENT_PARSERS:
        raise WorldProtocolError("UNSUPPORTED_MESSAGE_TYPE", f"unknown client type {mt!r}")
    parsed = _CLIENT_PARSERS[mt](obj, session_id)
    if last_client_seq is not None and parsed.sequence_number <= last_client_seq:
        raise WorldProtocolError("STALE_SEQUENCE", f"client sequence {parsed.sequence_number} <= {last_client_seq}")
    return parsed


# --------------------------------------------------------------------------
# host -> Godot message builders (the host produced them, Godot still validates)
# --------------------------------------------------------------------------
def build_control(mt: str, session_id: str, sequence: int, timestamp_ms: float, extra: Mapping[str, Any]) -> dict:
    return {"protocol_version": WORLD_PROTOCOL_VERSION, "message_type": mt, "session_id": session_id,
            "sequence_number": sequence, "timestamp_ms": int(timestamp_ms), **extra}


def build_pose(session_id: str, sequence: int, timestamp_ms: float, *, sample_timestamp_ms: float | None, status: str,
               position: tuple[float, float, float] | None, world_position_m: tuple[float, float, float] | None,
               world_frame_id: str | None, quality_score: float | None, warnings: list[str]) -> dict:
    return {"protocol_version": WORLD_PROTOCOL_VERSION, "message_type": MT_POSE_UPDATE, "session_id": session_id,
            "sequence_number": sequence, "timestamp_ms": int(timestamp_ms), "sample_timestamp_ms": None if sample_timestamp_ms is None else int(round(sample_timestamp_ms)),
            "target_landmark": "wrist", "status": status, "valid": position is not None,
            "position": None if position is None else list(position),
            "world_position_m": None if world_position_m is None else list(world_position_m),
            "unit": "m", "world_frame_id": world_frame_id,
            "quality": None if quality_score is None else round(float(quality_score), 4),
            "warnings": list(warnings)[:8]}


def build_interaction(session_id: str, sequence: int, timestamp_ms: float, ev: Mapping[str, Any],
                      hand_target: tuple[float, float, float] | None) -> dict:
    """Pass through a Phase 3 InteractionEvent (validated host-side) + the transformed Godot-space target."""
    return {"protocol_version": WORLD_PROTOCOL_VERSION, "message_type": MT_INTERACTION_EVENT, "session_id": session_id,
            "sequence_number": sequence, "timestamp_ms": int(timestamp_ms),
            "event_id": ev["event_id"], "event_type": ev["event_type"], "gesture_state": ev["gesture_state"],
            "interaction_id": ev["interaction_id"], "target_object_id": ev["target_object_id"],
            "hand_target": None if hand_target is None else list(hand_target),
            "hand_target_world_m": ev["hand_target_xyz_m"],
            "world_frame_id": ev["world_frame_id"] if ev.get("hand_target_xyz_m") is not None else None,
            "sample_timestamp_ms": ev.get("sample_timestamp_ms"),
            "confidence": ev.get("confidence"), "cancel_reason": ev.get("cancel_reason"),
            "reason": ev.get("reason"), "continuous": bool(ev.get("continuous", False))}


def build_status(session_id: str, sequence: int, timestamp_ms: float, *, state: str, detail: str, **counts: Any) -> dict:
    return build_control(MT_HOST_STATUS, session_id, sequence, timestamp_ms, {"state": state, "detail": detail, **counts})


def build_error(session_id: str | None, sequence: int, timestamp_ms: float, code: str, detail: str, *, fatal: bool = False, event_id: str | None = None) -> dict:
    msg = build_control(MT_ERROR, session_id or "?", sequence, timestamp_ms, {"error_code": code, "detail": detail[:400], "fatal": fatal})
    if event_id:
        msg["event_id"] = event_id
    return msg

