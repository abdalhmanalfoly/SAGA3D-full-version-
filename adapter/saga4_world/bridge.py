"""The world bridge: ONE glue object per live session that connects the Phase 1-3 pipeline to Godot.

Responsibilities (strictly separated; nothing from the CV/coordination pipeline is duplicated):
  * consumes FusionResult   (Phase 2 contract  -> spatial/results.py) -> validated HandSample + pinch evidence
  * feeds GestureAgent      (Phase 3 contract  -> gesture/agent.py)    -> discrete events + MOVE_TARGET stream
  * transforms positions    (module transform.py, the ONLY conversion) -> Godot-space payload
  * hosts ONE Godot connection; collapses stale pose/move traffic, preserves discrete events (bounded queues)
  * derives HOST_STATUS via pure status.derive()
  * never publishes a position that fusion did not validate; never claims tracking while degraded
Phase 3 event/state names pass through unchanged; new world-side schemas live only in protocol.py.
"""
from __future__ import annotations

import asyncio
import collections
from dataclasses import dataclass
from typing import Any, Sequence

from .config import WorldConfig
from .protocol import (MT_INTERACTION_EVENT, KNOWN_EVENT_TYPES, build_control, build_error, build_interaction,
                       build_pose, build_status)
from .status import StatusInputs, derive, detail_for
from .transform import TransformError, WorldTransform

# =============================================================================== outbound paths
Pose = tuple[float, float, float]


@dataclass
class PoseSlot:
    """One collapsed pose update (Godot space) waiting to be sent; newest wins."""
    position: Pose | None
    world_position_m: Pose | None                # raw fusion value in the rig frame (diagnostic only)
    status: str
    sample_timestamp_ms: float | None
    world_frame_id: str | None
    quality_score: float | None
    warnings: list[str]
    fusion_sequence: int
    # transport metadata for latency measurement: fusion publication time (host clock, ms)
    published_at_ms: float


class WorldConnection:
    """One connected Godot client: per-connection sequence streams + bounded queues.

    Queue discipline (documented: docs/world_protocol.md §queues):
      * control  : bounded FIFO — WORLD_READY / HOST_STATUS / WORLD_STOP / HEARTBEAT_ACK / ERROR.
                   Overflow drops the OLDEST control message (a counter records it).
      * events   : bounded FIFO for DISCRETE InteractionEvents. Overflow drops the oldest event WITH a
                   counter; high-frequency pose traffic can NEVER evict a grab/release.
      * poses    : collapse slot (newest wins). Overload intentionally discards obsolete intermediate poses.
      * move     : collapse slot for MOVE_TARGET (newest wins; the agent already rate-limits to 30 Hz).
    The dispatcher sends one control / one event / one pose / one move per drain call so that a burst of
    poses can never starve a discrete event for more than one frame.
    """

    def __init__(self, bridge: "SessionWorld", client_id: str, client_seq: int, opened_at: float):
        self.bridge = bridge
        self.client_id = client_id
        self.opened_at = opened_at
        self.last_client_seq = client_seq
        self.control_seq = 0
        self.pose_seq = 0
        self.event_seq = 0
        self.control: collections.deque[dict] = collections.deque(maxlen=64)
        self.events: collections.deque[dict] = collections.deque(maxlen=self.bridge.cfg.event_buffer_max)
        self.pose: PoseSlot | None = None
        self.move: Pose | None = None
        self.move_queued_at = 0.0
        self.last_heartbeat_at = opened_at
        self.dropped_events = 0
        self.closed = False
        self.wake = asyncio.Event()                # the server writer sleeps on this; every enqueue sets it

    # ------------------------------------------------------------------ outgoing (called by the bridge)
    def _next(self, stream: str) -> int:
        attr = {"control": "control_seq", "pose": "pose_seq", "event": "event_seq"}[stream]
        val = getattr(self, attr) + 1
        setattr(self, attr, val)
        return val

    def enqueue_control(self, msg_type: str, extra: dict) -> None:
        msg = build_control(msg_type, self.bridge.session_id, self._next("control"), float(self.bridge.clock.now_ms()), extra)
        if len(self.control) >= self.control.maxlen:
            dropped = self.control.popleft()
            self.bridge.count(f"world_control_overflow:{dropped.get('message_type', '?').lower()}")
        self.control.append(msg)
        self.wake.set()

    def enqueue_pose(self, slot: PoseSlot) -> None:
        self.pose = slot                                       # collapse: newest pose wins
        self.wake.set()

    def enqueue_move(self, pos: Pose) -> None:
        self.move = pos                                        # collapse: newest MOVE_TARGET wins
        import time
        self.move_queued_at = time.monotonic()
        self.wake.set()

    def enqueue_event(self, msg: dict) -> None:
        if len(self.events) >= self.events.maxlen:
            oldest = self.events.popleft()
            self.dropped_events += 1
            self.bridge.count(f"world_event_overflow:{oldest.get('event_type', '?').lower()}")
        self.events.append(msg)
        self.wake.set()

    def enqueue_error(self, code: str, detail: str, *, fatal: bool = False, event_id: str | None = None) -> None:
        self.control.append(build_error(self.bridge.session_id, self._next("control"), float(self.bridge.clock.now_ms()),
                                        code, detail, fatal=fatal, event_id=event_id))
        self.wake.set()

    # ------------------------------------------------------------------ drain (called by the server task)
    def drain(self) -> list[dict]:
        """Frames to send in this round. Priority: control > discrete events > (aging) moves > poses.
        A waiting MOVE_TARGET older than ``move_yield_ms`` is sent BEFORE a pose so continuous pose traffic
        at the cap can never starve object movement indefinitely."""
        out: list[dict] = []
        if self.control:
            out.append(self.control.popleft())
            return out
        if self.events:
            out.append(self.events.popleft())
            if self.events and self.pose is None:              # piggy-back a second event while no pose waits
                out.append(self.events.popleft())
            return out
        import time
        now_mono = time.monotonic()
        move_due = self.move is not None and (now_mono - self.move_queued_at) >= self.MOVE_YIELD_S
        pose_interval = 1.0 / max(self.bridge.cfg.max_pose_hz, 1e-3)
        if move_due:
            pos, self.move = self.move, None
            self.event_seq += 1
            out.append({"protocol_version": self.bridge.cfg.world_protocol_version, "message_type": MT_INTERACTION_EVENT,
                        "session_id": self.bridge.session_id, "sequence_number": self.event_seq,
                        "timestamp_ms": int(self.bridge.clock.now_ms()),
                        "event_id": "MOVE_TARGET", "event_type": "MOVE_TARGET", "continuous": True, "hand_target": list(pos)})
            return out
        if self.pose is not None and now_mono - self.bridge.last_pose_send >= pose_interval:
            self.bridge.last_pose_send = now_mono
            s = self.pose
            out.append(build_pose(self.bridge.session_id, self._next("pose"), float(self.bridge.clock.now_ms()),
                                  sample_timestamp_ms=s.sample_timestamp_ms, status=s.status, position=s.position,
                                  world_position_m=s.world_position_m, world_frame_id=s.world_frame_id,
                                  quality_score=s.quality_score, warnings=s.warnings))
            self.pose = None
        return out

    MOVE_YIELD_S = 0.05                                        # moves never wait more than ~3 frames behind poses

    # ------------------------------------------------------------------ incoming bookkeeping
    def note_client_seq(self, seq: int) -> None:
        self.last_client_seq = seq


# =============================================================================== per-session bridge
@dataclass(frozen=True)
class ObjectEntry:
    object_id: str
    position_rig_m: Pose
    grabbable: bool


class SessionWorld:
    """Bridge for ONE live session (one per Session). Constructed by attach.py for every session created."""

    def __init__(self, session, clock, events, cfg: WorldConfig, phase3=None, coordinator_source=None,
                 gesture_cfg=None, extra_status: dict | None = None):
        self.session = session
        self.session_id = session.session_id
        self.clock = clock
        self.events = events
        self.cfg = cfg
        self.transform: WorldTransform = cfg.transform
        self.transform_fingerprint = self.transform.fingerprint()
        self._p3 = phase3 if phase3 is not None else None
        if self._p3 is None:
            from .p3 import p3
            self._p3 = p3()
        self.gesture_cfg = gesture_cfg or self._p3.gesture_cfg_with(cfg.gesture_overrides)
        self.gesture = self._p3.GestureAgent(
            self.session_id, self.gesture_cfg,
            audit=self._p3.AuditLog(clock, component="gesture", session_id=self.session_id, sink=events),
            clock=clock)
        self._deduper = self._p3.EventDeduper(4096)                # belt & braces on top of the agent's own idempotency
        self.coordinator_source = coordinator_source               # callable () -> {"degraded": bool, "reason_code": str|None}
        self.extra_status = extra_status or {}
        self.counters: dict[str, int] = collections.Counter()
        self.conn: WorldConnection | None = None
        self.objects: dict[str, ObjectEntry] = {}
        self.stopped = False
        self.last_pose_send = 0.0
        self._last_status: dict | None = None
        self._last_status_at = 0.0
        self._calibration_flagged = False
        self._last_fusion_status: str | None = None
        self._last_fusion_reason: str | None = None
        self._last_fusion_world_frame: str | None = None
        self._last_fusion_valid = False
        self._last_fusion_quality: float | None = None
        self._last_pose_slot: PoseSlot | None = None

    # ================================================================== fusion -> gesture
    def on_fusion_result(self, r) -> None:
        """FusionEngine subscriber. Validates then converts; nothing unvalidated reaches Godot."""
        try:
            now = self.clock.now_ms()
            if getattr(r, "session_id", None) != self.session_id:
                self.count("world_fusion_session_mismatch")
                return
            self._ingest_meta(r)
            sample = self._hand_sample(r)
            objects = self._interaction_objects()
            out = self.gesture.update(sample, objects, now)
            self._emit_gesture_out(out, now)
            self._update_calibration_state()
            self._update_status()
        except Exception as exc:                                   # a bridge bug must never break sensor ingestion
            self.count("world_bridge_error")
            self._log("world_bridge_error", severity="error", reason=type(exc).__name__, detail=str(exc)[:200])

    def _ingest_meta(self, r) -> None:
        st = getattr(getattr(r, "status", None), "value", None)
        q = getattr(r, "quality", None)
        self._last_fusion_status = st
        self._last_fusion_valid = bool(getattr(r, "valid", False)) and getattr(r, "world_xyz_m", None) is not None
        self._last_fusion_reason = getattr(r, "reason", None)
        self._last_fusion_world_frame = getattr(r, "world_frame_id", None)
        self._last_fusion_quality = getattr(q, "score", None) if q is not None else None

    def _interaction_objects(self):
        """The Godot-declared objects in the RIG frame for the gesture agent (its contract input)."""
        out = []
        for entry in self.objects.values():
            try:
                out.append(self._p3.InteractionObject(entry.object_id, entry.position_rig_m, entry.grabbable))
            except Exception:
                continue
        return out

    def _hand_sample(self, r) -> dict:
        """Validated Phase-3 HandSample + (when the fusion result is valid) a transformed Godot pose slot."""
        p3 = self._p3
        valid = self._last_fusion_valid
        raw = tuple(float(v) for v in r.world_xyz_m) if valid else None
        xyz: Pose | None = None
        warnings: list[str] = list(getattr(r, "warnings", []) or ())
        try:
            smoother = self.session.fusion.engine.smoothers.get(getattr(r, "target_landmark", "wrist"))
            epoch = len(smoother.resets) if smoother else 0        # ANY smoother reset == track change
        except AttributeError:
            self.count("world_no_smoother")
            epoch = 0
        if self.transform.fingerprint() != self.transform_fingerprint:
            self.transform_fingerprint = self.transform.fingerprint()
            self.count("world_transform_changed")
            now = self.clock.now_ms()
            self._emit_gesture_out(self.gesture.reset(now, "world transform changed"), now)
        if valid:
            try:
                xyz = self.transform.rig_to_godot(raw)             # may raise NON_FINITE/OUT_OF_VOLUME
            except TransformError as te:
                self.count(f"world_pose_reject:{te.code}")
                self._last_fusion_valid = False
                valid = False
                xyz = None
            if xyz is not None and not self.transform.is_inside_volume(xyz):
                warnings.append("POSITION_OUTSIDE_VOLUME")
                self.count("world_pose_outside_volume")
        if xyz is not None:
            slot = PoseSlot(position=xyz, world_position_m=raw, status=self._last_fusion_status or "TRACKING_MULTI_VIEW",
                            sample_timestamp_ms=getattr(r, "timestamp_ms", None), world_frame_id=self._last_fusion_world_frame,
                            quality_score=self._last_fusion_quality, warnings=warnings,
                            fusion_sequence=int(r.fusion_sequence), published_at_ms=float(getattr(r, "published_at_ms", 0)))
            self._last_pose_slot = slot
            self._publish_pose_slot(slot)
        else:
            self._last_pose_slot = None                            # freeze; never publish stale coordinates
        cal_valid = self._last_fusion_status != "CALIBRATION_REQUIRED"
        return p3.HandSample(
            session_id=self.session_id,
            timestamp_ms=float(r.timestamp_ms) if getattr(r, "timestamp_ms", None) is not None else float("nan"),
            fusion_valid=valid, hand_xyz_m=raw if valid else None,
            confidence=None if getattr(r, "quality", None) is None else r.quality.score,
            pinch_ratio=self._pinch_ratio_for(r), fusion_sequence=int(r.fusion_sequence),
            world_frame_id=self._last_fusion_world_frame, track_epoch=epoch, calibration_valid=cal_valid)

    def _pinch_ratio_for(self, r) -> float | None:
        """Pinch evidence (2D landmarks) from the sensors that CONTRIBUTED to this fusion result; median across views."""
        p3 = self._p3
        wanted = {src.sensor_id: src.sequence_number for src in getattr(r, "sources", []) or () if getattr(src, "used", False)}
        if not wanted:
            return None
        try:
            buffers = self.session.fusion.engine.sync.buffers
        except AttributeError:
            self.count("world_no_sync_buffers")
            return None
        ratios: list[float] = []
        for sid, seq in wanted.items():
            buf = buffers.get(sid)
            obs = None
            if buf:
                for cand in reversed(buf):                     # exact sequence match first (buffer is bounded)
                    if cand.sequence_number == seq:
                        obs = cand
                        break
                if obs is None:
                    obs = buf[-1]
            if obs is None:
                continue
            ratio, why = p3.pinch_ratio(obs.landmarks, self.gesture_cfg)
            if ratio is None:
                self.count(f"world_pinch_invalid:{why}")
            else:
                ratios.append(ratio)
        self.count(f"world_pinch_views:{min(len(ratios), 4)}")
        return p3.combine_view_ratios(ratios)

    # ================================================================== gesture "refreshed"/out
    def _emit_gesture_out(self, out, now: float) -> None:
        conn = self.conn
        for ev in out.events:
            try:
                if not self._deduper.accept(ev):
                    self.count("world_event_duplicate_dropped")
                    continue
            except Exception:
                pass
            msg = self._interaction_message(ev, now)
            if msg is None:
                continue
            if conn is not None and not conn.closed:
                conn.enqueue_event(msg)
                self.count(f"world_event_sent:{ev.event_type.value}")
            else:
                self.count(f"world_event_noworld:{ev.event_type.value}")
        for mv in out.moves:
            pos = mv.hand_target_xyz_m
            if pos is None:
                continue
            target = self._transform_pos(pos, "move")
            if target is not None and conn is not None and not conn.closed:
                conn.enqueue_move(target)

    def _transform_pos(self, world_pos, what: str) -> Pose | None:
        try:
            p = self.transform.rig_to_godot(tuple(float(v) for v in world_pos))
        except TransformError as te:
            self.count(f"world_{what}_transform_reject:{te.code}")
            return None
        if not self.transform.is_inside_volume(p):
            self.count(f"world_{what}_outside_volume")
        return p

    def _interaction_message(self, ev, now: float) -> dict | None:
        """Defensive validation of a phase-3 event before serialisation."""
        if ev.event_type.value not in KNOWN_EVENT_TYPES:
            self.count(f"world_event_unknown:{ev.event_type.value}")
            return None
        ev_dict = ev.to_dict()
        if ev.event_type.value == "GRAB_CANCELLED" and ev_dict.get("cancel_reason") is None:
            self.count("world_event_cancel_without_reason")
            return None
        hand = None
        if ev_dict.get("hand_target_xyz_m") is not None:
            hand = self._transform_pos(ev_dict["hand_target_xyz_m"], "event")
            if hand is None:
                return None
        return build_interaction(self.session_id, 0, float(now), ev_dict, hand)

    def _publish_pose_slot(self, slot: PoseSlot) -> None:
        if self.conn is not None and not self.conn.closed:
            self.conn.enqueue_pose(slot)
        self.count("world_pose_in")                          # collapsed downstream when Godot is offline

    # ================================================================== session objects (declared by Godot)
    def register_client(self, hello, opened_at: float) -> WorldConnection | None:
        """First Godot wins; a late second connection is refused explicitly (bounded single-consumer design)."""
        if self.conn is not None and not self.conn.closed:
            self.count("world_reject_second_client")
            return None
        client_id = (getattr(hello, "fields", {}) or {}).get("client_id", "godot")
        conn = WorldConnection(self, client_id, hello.sequence_number, opened_at)
        for o in (getattr(hello, "fields", {}) or {}).get("objects", []):
            self._register_object(o.object_id, o.position, o.grabbable, opened_at)
        self.conn = conn
        self.count("world_client_connected")
        conn.enqueue_control("WORLD_READY", {
            "host_version": self.cfg.host_version_label,
            "world_frame_id": self._world_frame_id(),
            "transform": {"source_frame": self.transform.source_frame, "target_frame": self.transform.target_frame,
                          "scale": self.transform.scale, "fingerprint": self.transform_fingerprint,
                          "translation_m": list(self.transform.translation)},
            "accepted_objects": sorted(self.objects)})
        self._send_snapshot(conn)
        return conn

    def _send_snapshot(self, conn: WorldConnection) -> None:
        """After (re)connect send current state; never replay stale pose/event traffic."""
        conn.enqueue_control("HOST_STATUS", self._status_body())
        self.count("world_snapshot")

    def _register_object(self, oid: str, position: Sequence[float], grabbable: bool, at: float) -> bool:
        if not oid or len(oid) > 64:
            self.count("world_object_bad_id")
            return False
        try:
            rig = self.transform.godot_to_rig(position)            # raises on non-finite
        except TransformError as te:
            self.count(f"world_object_reject:{te.code}")
            self._maybe_error("OBJECT_TRANSFORM_REJECTED", f"object {oid} unusable: {te}")
            return False
        if not self.transform.is_inside_volume(position):
            self.count("world_object_outside_volume")
            self._maybe_error("OBJECT_OUTSIDE_VOLUME",
                              f"object {oid} is outside the configured interaction volume; it is IGNORED for hover/grab")
            return False
        self.objects[oid] = ObjectEntry(oid, rig, bool(grabbable))
        return True

    def on_client_message(self, parsed) -> None:
        """Dispatch a parsed Godot message."""
        mt = parsed.message_type
        fields = parsed.fields or {}
        now = self.clock.now_ms()
        self.count(f"world_client_msg:{mt.lower()}")
        if mt == "HEARTBEAT":
            if self.conn is not None:
                self.conn.last_heartbeat_at = now
                self.conn.enqueue_control("HEARTBEAT_ACK", {"echo": parsed.sequence_number})
            self._send_fingerprints_if_needed()
            return
        if mt == "OBJECT_STATE":
            accepted = []
            ts = getattr(parsed, "timestamp_ms", None)
            ts = self.clock.now_ms() if ts is None else ts
            for o in fields["objects"]:
                if self._register_object(o.object_id, o.position, o.grabbable, ts):
                    accepted.append(o.object_id)
            self._update_status()
            self._send_fingerprints_if_needed()
            return
        if mt == "ACK":
            ev_id = fields["event_id"]
            etype = fields["ack_event_type"]
            target = fields["target_object_id"]
            if etype == "GRAB_REQUEST":
                if target is None:
                    self._maybe_error("ACK_MISSING_TARGET", "GRAB_REQUEST ack must carry target_object_id")
                ok = bool(fields["accepted"])
                if ok:                                             # Godot validated the object really is grabbable
                    ok = target in self.objects and self.objects[target].grabbable
                    if not ok:
                        self.count("world_grab_rejected_object_gone")
                self._apply_ack(ev_id, now, accepted=ok)
            elif etype in ("RELEASE", "GRAB_CANCELLED"):
                self._apply_ack(ev_id, now, accepted=True)         # failure to release can NEVER hold an object
            else:
                self.count("world_client_msg_unhandled:ack_type")
            return
        self.count(f"world_client_msg_unhandled:{mt.lower()}")

    def _apply_ack(self, event_id: str | None, now: float, accepted: bool) -> None:
        if event_id is None:
            self.count("world_ack_no_event_id")
            return
        out = self.gesture.acknowledge(event_id, now, accepted=accepted)
        self._emit_gesture_out(out, now)
        self._update_status()

    def on_client_disconnect(self, reason: str) -> None:
        conn = self.conn
        self.conn = None
        if conn is not None:
            conn.closed = True
        for oid in list(self.objects):
            self.count("world_object_orphaned")
        self.count("world_client_disconnected")
        self._log("world_client_disconnected", session_id=self.session_id, reason=reason)
        self._update_status()

    # ================================================================== services
    def tick(self) -> None:
        """~20 Hz from the server task: gesture timers (tracking loss, ack timeouts), status, heartbeats."""
        if self.stopped:
            return
        now = self.clock.now_ms()
        try:
            out = self.gesture.tick(now)
            self._emit_gesture_out(out, now)
        except Exception as exc:
            self.count("world_tick_error")
            self._log("world_tick_error", session_id=self.session_id, severity="error", reason=type(exc).__name__)
        self._update_status()

    def on_session_stop(self, reason: str = "operator_request") -> None:
        now = self.clock.now_ms()
        out = self.gesture.on_session_stop(now)
        self._emit_gesture_out(out, now)
        self.stopped = True
        if self.conn is not None:
            self.conn.enqueue_control("WORLD_STOP", {"reason": reason})
        self._update_status(force=True)
        self.count("world_session_stopped")

    def on_calibration_invalidated(self) -> None:
        """Hook for explicit calibration invalidation (Phase 3 handoff §6; also automatic via fusion result)."""
        out = self.gesture.on_calibration_invalid(self.clock.now_ms())
        self._emit_gesture_out(out, self.clock.now_ms())
        self._update_status()

    def on_calibration_restored(self) -> None:
        self.gesture.on_calibration_restored()
        self._update_status()

    # ================================================================== status
    def _connected_sensor_count(self) -> int:
        try:
            now = self.clock.now_ms()
            return sum(1 for rec in self.session.registry.records.values()
                       if (s := self.session.registry.snapshot(rec, now)).get("connected") and s.get("state") in ("online", "degraded"))
        except Exception:
            return 0

    def _calibrated_sensor_count(self) -> int:
        try:
            fusion = self.session.fusion
            if fusion is None:
                return 0
            now = self.clock.now_ms()
            n = 0
            for rec in list(self.session.registry.records.values()):
                try:
                    res = fusion.registry.resolve(rec.sensor_id)
                    # resolve only counts when a VALID calibration artifact exists for the bound camera
                    if res is not None and getattr(res, "problem", None) is None and getattr(res, "artifact", None) is not None:
                        n += 1
                except Exception:
                    continue
            return n
        except Exception:
            return 0

    def _tracking_trusted(self) -> bool:
        if self.coordinator_source is not None:
            info = self.coordinator_source() or {}
            if info.get("degraded"):
                return False
        return True

    def _status_body(self) -> dict:
        si = self._status_inputs()
        state = derive(si)
        body: dict[str, Any] = {
            "state": state,
            "connected_sensors": si.connected_sensors,
            "calibrated_sensors": si.calibrated_sensors,
            "world_connected": self.conn is not None and not self.conn.closed,
            "tracking_trusted": self._tracking_trusted(),
            "calibration_ok": si.calibration_ok,
            "last_fusion_valid": si.fusion_valid,
            "last_fusion_status": self._last_fusion_status,
            "last_fusion_reason": self._last_fusion_reason,
            "last_fusion_quality": self._last_fusion_quality,
            "last_pose_valid": self._last_pose_slot is not None and self._last_pose_slot.position is not None,
            "gesture_state": self.gesture.state.value,
            "transform_fingerprint": self.transform_fingerprint,
        }
        if callable(self.extra_status):
            body.update(self.extra_status(self))
        elif isinstance(self.extra_status, dict):
            body.update(self.extra_status)
        body["detail"] = detail_for(state, self._last_fusion_reason, self._degraded_reason())
        return body

    def _degraded_reason(self) -> str | None:
        if self.coordinator_source is not None:
            info = self.coordinator_source() or {}
            if info.get("degraded"):
                return str(info.get("reason_code") or "DEGRADED")
        if self._calibration_flagged:
            return "CALIBRATION_FLAG"
        return None

    def _status_inputs(self) -> StatusInputs:
        session_active = getattr(self.session, "state", "active") == "active" and not self.stopped
        calibrated = self._calibrated_sensor_count()
        return StatusInputs(
            session_active=session_active,
            connected_sensors=self._connected_sensor_count(),
            calibrated_sensors=calibrated,
            calibration_ok=self._last_fusion_status != "CALIBRATION_REQUIRED" and calibrated >= 1,
            fusion_valid=self._last_fusion_valid,
            tracking_trusted=self._tracking_trusted(),
            gesture_state=self.gesture.state.value,
            held_interaction=self.gesture.state.value == "GRABBED",
            world_connected=self.conn is not None and not self.conn.closed,
            shutting_down=False)

    def _update_calibration_state(self) -> None:
        was = self._calibration_flagged
        now = self._last_fusion_status == "CALIBRATION_REQUIRED"
        if now and not was:
            self._calibration_flagged = True
            out = self.gesture.on_calibration_invalid(self.clock.now_ms())
            self._emit_gesture_out(out, self.clock.now_ms())
            self._log("world_calibration_invalid", session_id=self.session_id, reason=self._last_fusion_reason)
        elif was and not now and self._last_fusion_valid:
            self._calibration_flagged = False
            self.gesture.on_calibration_restored()
            self._log("world_calibration_restored", session_id=self.session_id)

    def _send_fingerprints_if_needed(self) -> None:
        """Gesture state changes surface via HOST_STATUS when the derived body changes (cheap, at most 1 Hz)."""
        self._update_status(force=False)

    def _maybe_error(self, code: str, detail: str) -> None:
        if self.conn is not None and not self.conn.closed:
            self.conn.enqueue_error(code, detail)

    def _update_status(self, force: bool = False) -> None:
        body = self._status_body()
        if body == self._last_status:
            return
        if not force and self._last_status is not None and self.clock.now_ms() - self._last_status_at < 1000.0:
            return                                           # at most 1/s unless forced (status flips line up)
        if self.conn is not None and not self.conn.closed:
            self.conn.enqueue_control("HOST_STATUS", body)
            self.count(f"world_status_sent:{body['state'].lower()}")
        self._last_status = body
        self._last_status_at = self.clock.now_ms()

    def count(self, key: str) -> None:
        self.counters[key] += 1

    def _log(self, *args, **kw) -> None:
        if self.events is not None:
            try:
                self.events.log(*args, **kw)
            except Exception:
                pass

    def _world_frame_id(self) -> str | None:
        try:
            res = self.session.fusion.engine.latest.get("wrist")
        except AttributeError:
            return None
        return getattr(res, "world_frame_id", None)
