# SAGA 3D Phase 4 — demo/interaction controller for the minimal grab-move-release scene.
#
# Scene roles (docs/demo_script.md):
#   * hand marker   -> follows validated fusion output only (host transformed)
#   * grabbable cube-> GRAB / MOVE / RELEASE driven ONLY by host INTERACTION_EVENTs
#   * status UI     -> shows connection, host state, gesture state, quality, invalid-counter
# Game logic never trusts unvalidated data here: world_client.gd is the single validation gate.
class_name SagaMain
extends Node3D

@export var session_id: String = ""          # empty -> read from --session=... command line arg
@export var marker_stale_after_ms: float = 400.0

var world: Node
var marker: Node3D
var cube: Node3D
var status_ui: Node
var session_active := false

var _hovering := false
var _grabbing := false
var _grab_object_id := ""

func _ready() -> void:
	session_id = get_session_id_from_args()
	world = get_node_or_null("WorldClient")
	marker = get_node_or_null("HandMarker")
	cube = get_node_or_null("GrabbableCube")
	status_ui = get_node_or_null("StatusUI")
	if world != null and session_id != "":
		world.set_session(session_id)
	if world == null:
		return
	world.register_object("cube_1", cube)
	world.pose_valid.connect(_on_pose_valid)
	world.pose_invalid.connect(_on_pose_invalid)
	world.hover_enter.connect(_on_hover_enter)
	world.hover_exit.connect(_on_hover_exit)
	world.grab_request.connect(_on_grab_request)
	world.grab_confirmed.connect(_on_grab_confirmed)
	world.move_target.connect(_on_move_target)
	world.release_request.connect(_on_release_request)
	world.grab_cancelled.connect(_on_grab_cancelled)
	world.tracking_lost.connect(_on_tracking_lost)
	world.host_state_changed.connect(_on_host_status)
	world.host_error.connect(_on_host_error)
	world.world_ready.connect(_on_world_ready)
	world.connected_changed.connect(_on_connected_changed)
	if status_ui != null:
		status_ui.call("set_session_id", session_id)
	send_object_state()

static func get_session_id_from_args() -> String:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--session="):
			return arg.substr(10)
	return ""

# ------------------------------------------------------------------- pose -> marker
func _on_pose_valid(pos: Vector3, _quality: float, _sample_ms: float) -> void:
	if marker != null:
		marker.call("set_target", pos)
		marker.call("set_state", "TRACKING")

func _on_pose_invalid(status: String, detail: String) -> void:
	if marker != null:
		marker.call("mark_lost")
	if status_ui != null:
		status_ui.call("set_tracking", status, detail)

func _on_tracking_lost(_reason: String) -> void:
	if marker != null:
		marker.call("mark_lost")
	if status_ui != null:
		status_ui.call("set_tracking", "TRACKING_LOST", "gesture reports tracking loss (object frozen or released)")

# ------------------------------------------------------------------- interactions
func _on_hover_enter(object_id: String) -> void:
	_hovering = true
	if cube != null:
		cube.call("set_hovered", object_id == "cube_1")
	if status_ui != null:
		status_ui.call("set_hover", true)

func _on_hover_exit(_object_id: String) -> void:
	_hovering = false
	if cube != null:
		cube.call("set_hovered", false)
	if status_ui != null:
		status_ui.call("set_hover", false)

func _on_grab_request(event_id: String, object_id: String, hand_pos: Vector3) -> void:
	# Godot must confirm the object really exists and is grabbable (world_client already validated the shape).
	var ok: bool = cube != null and object_id == "cube_1" and not _grabbing and cube.call("is_grabbable")
	if ok:
		_grabbing = true
		_grab_object_id = object_id
		cube.call("begin_grab", hand_pos, true)
	if status_ui != null:
		status_ui.call("set_gesture", "GRAB_REQUESTED")
	world.send_ack("GRAB_REQUEST", event_id, ok, object_id, "" if ok else "OBJECT_NOT_AVAILABLE")
	if not ok and status_ui != null:
		status_ui.call("note", "grab rejected: object not available or already held")

func _on_grab_confirmed(_object_id: String) -> void:
	if cube != null:
		cube.call("confirm_grab")
	if status_ui != null:
		status_ui.call("set_gesture", "GRABBED")

func _on_move_target(pos: Vector3) -> void:
	if _grabbing and cube != null:
		cube.call("move_to", pos)       # the cube script applies its own plausibility screen

func _on_release_request(event_id: String, object_id: String) -> void:
	if _grabbing and object_id == _grab_object_id:
		if cube != null:
			cube.call("release_grab")
		_grabbing = false
		_grab_object_id = ""
		world.send_ack("RELEASE", event_id, true, object_id)
		send_object_state()
	if status_ui != null:
		status_ui.call("set_gesture", "RELEASED")

func _on_grab_cancelled(event_id: String, object_id: String, cancel_reason: String) -> void:
	if _grabbing:
		if cube != null:
			cube.call("release_grab")
		_grabbing = false
		_grab_object_id = ""
		world.send_ack("GRAB_CANCELLED", event_id, true, object_id)
		send_object_state()
	if status_ui != null:
		status_ui.call("set_gesture", "GRAB_CANCELLED (%s)" % cancel_reason)
		status_ui.call("note", "grab cancelled: %s" % cancel_reason)

# ------------------------------------------------------------------- host status
func _on_host_status(state: String, detail: String, body: Dictionary) -> void:
	if status_ui != null:
		status_ui.call("set_host_state", state, detail)
		status_ui.call("set_fusion_from_body", body)
	send_object_state()                          # session state can move objects (reset/cancel)

func _on_host_error(code: String, detail: String, fatal: bool) -> void:
	if status_ui != null:
		status_ui.call("note", "%s%s: %s" % ["FATAL " if fatal else "", code, detail])

func _on_world_ready(info: Dictionary) -> void:
	session_active = true
	if status_ui != null:
		status_ui.call("note", "world ready: %s" % str(info.get("host_version", "?")))

func _on_connected_changed(is_connected: bool, detail: String) -> void:
	if status_ui != null:
		status_ui.call("set_connection", is_connected, detail)
	if not is_connected and _grabbing:
		_grabbing = false
		_grab_object_id = ""
		if cube != null:
			cube.call("release_grab")            # disconnect never leaves an object attached

# every discrete state change re-reports object positions (idle ObjectState, at most a few Hz)
func send_object_state() -> void:
	if world != null:
		world.send_object_state()
