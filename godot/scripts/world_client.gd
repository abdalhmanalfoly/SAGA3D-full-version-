# SAGA 3D Phase 4 — Godot side of the world protocol (docs/world_protocol.md v1.0).
#
# Role: a BROWSER-like CLIENT, not a trust boundary. Every host message is validated here BEFORE any
# scene action: shape, protocol version, session identity, per-stream sequence ordering, finite
# numbers, known event types, exact-once per event_id. Anything invalid is counted + reported to the
# status UI and never applied.
#
# The host performs the rig -> Godot coordinate transform; this script does NO coordinate conversion
# of its own. All positions are Godot world-space metres.
class_name WorldClient
extends Node

signal connected_changed(is_connected: bool, detail: String)
signal world_ready(info: Dictionary)
signal host_error(code: String, detail: String, fatal: bool)
signal host_state_changed(state: String, detail: String, body: Dictionary)
signal pose_valid(pos: Vector3, quality: float, sample_ms: float)
signal pose_invalid(status: String, detail: String)
signal hover_enter(object_id: String)
signal hover_exit(object_id: String)
signal grab_request(event_id: String, object_id: String, hand_pos: Vector3)
signal grab_confirmed(object_id: String)
signal move_target(pos: Vector3)
signal release_request(event_id: String, object_id: String)
signal grab_cancelled(event_id: String, object_id: String, cancel_reason: String)
signal tracking_lost(reason: String)

const PROTOCOL_VERSION := "1.0"
const KNOWN_EVENT_TYPES := ["HOVER_ENTER", "HOVER_EXIT", "GRAB_REQUEST", "GRAB_CONFIRMED",
	"RELEASE", "GRAB_CANCELLED", "TRACKING_LOST"]

@export var host: String = "127.0.0.1"
@export var port: int = 8765
@export var ws_path: String = "/ws/world"
@export var client_id: String = "godot_1"
@export var heartbeat_interval_s: float = 5.0
@export var reconnect_min_s: float = 1.0      # bounded reconnection: 1 s backoff growing to the cap, then the cap
@export var reconnect_max_s: float = 5.0
@export var retry_after_fatal: bool = false   # a FATAL error stops retries (Session_Mismatch etc.)
@export var session_id: String = ""           # project UI, main.gd, or --session=sess_x on the command line

var _peer: WebSocketPeer = WebSocketPeer.new()
var _open := false
var _regime := "IDLE"                         # IDLE | CONNECTING | CONNECTED | RECONNECTING | CLOSED
var _client_seq := 0                          # our outbound stream (strictly increasing)
var _seq_control := 0                         # host streams: control / pose / event (see docs/world_protocol.md)
var _seq_pose := 0
var _seq_event := 0
var _seen_events: Dictionary = {}             # event_id -> true ; exact-once, bounded
var objects: Dictionary = {}                  # object_id -> Node3D (register_object)
var _reconnect_in := 0.0
var _reconnect_delay := 1.0
var _last_heartbeat_ms := 0
var _invalid_count := 0
var _dropped_count := 0

func _ready() -> void:
	_reconnect_delay = reconnect_min_s
	_set_regime("IDLE", "no session configured yet")

func set_session(sid: String) -> void:
	if sid == session_id:
		return
	session_id = sid
	_seq_control = 0
	_seq_pose = 0
	_seq_event = 0
	_client_seq = 0
	_reconnect_delay = reconnect_min_s
	_reconnect_in = 0.0
	if sid == "":
		_set_regime("IDLE", "session cleared")
	else:
		_start_connect()

func set_regime_idle(message: String) -> void:
	_set_regime("CLOSED", message)   # e.g. host reported SHUTTING_DOWN/STOPPED: no retry storm
	_peer.close()

func register_object(object_id: String, node: Node3D) -> void:
	objects[object_id] = node

func _url() -> String:
	return "ws://%s:%d%s?session=%s" % [host, port, ws_path, session_id]

func _start_connect() -> void:
	if session_id == "":
		return
	var err: Error = _peer.connect_to_url(_url())
	if err != OK:
		_set_regime("RECONNECTING", "connect failed (%d), retrying in %.1fs" % [err, _reconnect_delay])
		_reconnect_in = _reconnect_delay
	else:
		_set_regime("CONNECTING", _url())

# ------------------------------------------------------------------ poll loop
func _process(delta: float) -> void:
	if session_id == "" or _regime == "CLOSED":
		return
	_peer.poll()                                      # REQUIRED every frame in Godot 4.x: the WebSocketPeer
	                                                  # state machine (incl. the HTTP handshake) only advances in poll()
	var rs: int = _peer.get_ready_state()
	if rs == WebSocketPeer.STATE_OPEN:
		_poll_messages()
		_maybe_heartbeat()
		return
	if _open:
		_open = false
		_on_lost("connection closed by peer (code %d)" % _peer.get_close_code())
		return
	if rs == WebSocketPeer.STATE_CLOSED and _regime == "CONNECTING":
		# the connect attempt failed: bounded backoff, capped at reconnect_max_s
		_set_regime("RECONNECTING", "server unreachable (close code %d)" % _peer.get_close_code())
		_reconnect_in = _reconnect_delay
		_reconnect_delay = minf(_reconnect_delay * 1.5, reconnect_max_s)
	elif _regime == "RECONNECTING":
		_reconnect_in -= delta
		if _reconnect_in <= 0.0:
			_start_connect()

func _poll_messages() -> void:
	while _peer.get_available_packet_count() > 0:
		var raw: PackedByteArray = _peer.get_packet()
		_handle_frame(raw.get_string_from_utf8())

func _handle_frame(text: String) -> void:
	var msg: Variant = JSON.parse_string(text)
	if typeof(msg) != TYPE_DICTIONARY:
		_invalid("MALFORMED_JSON", "frame is not a JSON object")
		return
	if str(msg.get("protocol_version", "")) != PROTOCOL_VERSION:
		_invalid("UNSUPPORTED_PROTOCOL_VERSION", str(msg.get("protocol_version")))
		return
	if str(msg.get("session_id", "")) != session_id:
		_invalid("SESSION_MISMATCH", str(msg.get("session_id")))
		return
	var mt: String = str(msg.get("message_type", ""))
	var seq: int = int(msg.get("sequence_number", -1))
	match mt:
		"WORLD_READY":
			if seq <= _seq_control:
				_drop("control", seq)
				return
			_seq_control = seq
			world_ready.emit(msg)
		"POSE_UPDATE":
			_handle_pose(msg, seq)
		"INTERACTION_EVENT":
			_handle_event(msg, seq)
		"HOST_STATUS":
			if seq <= _seq_control:
				_drop("control", seq)
				return
			_seq_control = seq
			host_state_changed.emit(str(msg.get("state", "?")), str(msg.get("detail", "")), msg)
		"HEARTBEAT_ACK":
			if seq <= _seq_control:
				_drop("control", seq)
				return
			_seq_control = seq
		"ERROR":
			var fatal: bool = bool(msg.get("fatal", false))
			host_error.emit(str(msg.get("error_code", "?")), str(msg.get("detail", "")), fatal)
			if fatal:
				if retry_after_fatal:
					_regime = "RECONNECTING"      # permitted at operator discretion
				else:
					_set_regime("CLOSED", "%s: %s (fatal)" % [msg.get("error_code"), msg.get("detail")])
		_:
			_invalid("UNSUPPORTED_MESSAGE_TYPE", mt)

func _handle_pose(msg: Dictionary, seq: int) -> void:
	if seq <= _seq_pose:
		_drop("pose", seq)
		return
	_seq_pose = seq
	var status: String = str(msg.get("status", "?"))
	var pos: Variant = msg.get("position")
	if bool(msg.get("valid", false)):
		if typeof(pos) != TYPE_ARRAY or pos.size() != 3:
			_invalid("SCHEMA_VALIDATION_FAILED", "valid pose without a 3-element position")
			return
		var v3 := Vector3(float(pos[0]), float(pos[1]), float(pos[2]))
		if not v3.is_finite():
			_invalid("NON_FINITE_POSITION", str(pos))
			return
		var q: Variant = msg.get("quality")
		var qf := 0.0
		if typeof(q) == TYPE_FLOAT or typeof(q) == TYPE_INT:
			qf = float(q)
		var warnings: Variant = msg.get("warnings", [])
		if warnings is Array and warnings.has("POSITION_OUTSIDE_VOLUME"):
			pose_invalid.emit("POSITION_OUTSIDE_VOLUME", "pose is outside the configured interaction volume")
		pose_valid.emit(v3, qf, float(msg.get("sample_timestamp_ms", 0.0)))
	else:
		if pos != null:
			_invalid("SCHEMA_VALIDATION_FAILED", "invalid pose must carry position: null")
			return
		# No position for invalid statuses -> the hand marker freezes (never extrapolates).
		pose_invalid.emit(status, str(msg.get("reason", "")))

func _handle_event(msg: Dictionary, seq: int) -> void:
	if seq <= _seq_event:
		_drop("event", seq)
		return
	_seq_event = seq
	var etype: String = str(msg.get("event_type", ""))
	# collapsed continuous MOVE_TARGET (no dedicated event id; never a state transition)
	if bool(msg.get("continuous", false)) and etype == "MOVE_TARGET":
		var t: Variant = msg.get("hand_target")
		if typeof(t) == TYPE_ARRAY and t.size() == 3:
			var mv := Vector3(float(t[0]), float(t[1]), float(t[2]))
			if mv.is_finite():
				move_target.emit(mv)
		else:
			_invalid("MOVE_WITHOUT_TARGET", "continuous MOVE_TARGET without hand_target")
		return
	if not KNOWN_EVENT_TYPES.has(etype):
		_invalid("UNKNOWN_EVENT_TYPE", etype)
		return
	var evid: String = str(msg.get("event_id", ""))
	if evid == "":
		_invalid("MISSING_EVENT_ID", etype)
		return
	if _seen_events.has(evid):                    # exact-once per event_id
		return
	_seen_events[evid] = true
	if _seen_events.size() > 512:                 # bounded memory
		_seen_events.erase(_seen_events.keys()[0])
	var target: String = str(msg.get("target_object_id", ""))
	var pos := Vector3.ZERO
	var t: Variant = msg.get("hand_target")
	if typeof(t) == TYPE_ARRAY and t.size() == 3:
		var p := Vector3(float(t[0]), float(t[1]), float(t[2]))
		if p.is_finite():
			pos = p
	match etype:
		"HOVER_ENTER":
			hover_enter.emit(target)
		"HOVER_EXIT":
			hover_exit.emit(target)
		"GRAB_REQUEST":
			grab_request.emit(evid, target, pos)
		"GRAB_CONFIRMED":
			grab_confirmed.emit(target)
		"RELEASE":
			release_request.emit(evid, target)
		"GRAB_CANCELLED":
			grab_cancelled.emit(evid, target, str(msg.get("cancel_reason", "")))
		"TRACKING_LOST":
			tracking_lost.emit(str(msg.get("reason", "")))

# ------------------------------------------------------------------ outbound
func _send(msg: Dictionary) -> bool:
	if _peer.get_ready_state() != WebSocketPeer.STATE_OPEN:
		return false
	_client_seq += 1
	msg["protocol_version"] = PROTOCOL_VERSION
	msg["session_id"] = session_id
	msg["sequence_number"] = _client_seq
	msg["timestamp_ms"] = int(Time.get_unix_time_from_system() * 1000.0)
	return _peer.send_text(JSON.stringify(msg)) == OK

func send_hello() -> void:
	_send({"message_type": "WORLD_HELLO", "client_id": client_id, "objects": _objects_state()})
	# parsed/validated host-side; until WORLD_READY the scene stays idle (connection progressed)

func send_ack(ack_event_type: String, event_id: String, accepted: bool, target_object_id: String, reason := "") -> void:
	_send({"message_type": "ACK", "ack_event_type": ack_event_type, "event_id": event_id,
		"accepted": accepted, "target_object_id": target_object_id,
		"reason": (reason if reason != "" else null)})

func send_object_state() -> void:
	var objs := _objects_state()
	if not objs.is_empty():
		_send({"message_type": "OBJECT_STATE", "objects": objs})

func _objects_state() -> Array:
	var objs: Array = []
	for oid: String in objects.keys():
		var node: Node3D = objects.get(oid)
		if node == null:
			continue
		var p := node.global_position
		if not p.is_finite():
			continue                                # never report a non-finite object position
		var g: Variant = node.get("grabbable")
		objs.append({"object_id": oid,
			"position": [p.x, p.y, p.z],
			"grabbable": true if typeof(g) != TYPE_BOOL else bool(g)})
	return objs

func notify_state(state_label: String) -> void:
	_send({"message_type": "HEARTBEAT", "fps": Engine.get_frames_per_second(), "state": state_label})

func _maybe_heartbeat() -> void:
	var now_ms := int(Time.get_unix_time_from_system() * 1000.0)
	if now_ms - _last_heartbeat_ms >= int(heartbeat_interval_s * 1000.0):
		_last_heartbeat_ms = now_ms
		notify_state("READY" if _regime == "CONNECTED" else _regime)

# ------------------------------------------------------------------ lifecycle helpers
func _on_lost(detail: String) -> void:
	_seq_control = 0                                # sequences reset per connection (docs/world_protocol.md)
	_seq_pose = 0
	_seq_event = 0
	_seen_events.clear()
	_reconnect_delay = reconnect_min_s + randf() * 0.2
	_reconnect_in = _reconnect_delay
	connected_changed.emit(false, detail)
	_set_regime("RECONNECTING", "%s; retrying %.0f..%.0f s" % [detail, reconnect_min_s, reconnect_max_s])

func _drop(stream: String, seq: int) -> void:
	_dropped_count += 1
	_invalid("STALE_SEQUENCE_%s" % stream.to_upper(), "sequence %d did not increase" % seq)

func _invalid(code: String, detail: String) -> void:
	_invalid_count += 1
	host_error.emit(code, detail, false)

func _set_regime(r: String, detail: String) -> void:
	_regime = r
	connected_changed.emit(r == "CONNECTED", "%s: %s" % [r, detail])
