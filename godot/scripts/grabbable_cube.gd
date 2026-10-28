# SAGA 3D Phase 4 — one grabbable cube. The host's gesture agent decides hover/grab/release; this
# script only renders feedback and enforces movement SANITY limits.
#
# Behaviour invariants (docs/world_protocol.md):
#   * GRAB_REQUEST: attach only if grabbable and not already held; ACK the request (accepted or
#     explicit reason). Godot decides availability, the HOST decides whether a grab happens.
#   * MOVE_TARGET: pure kinematic follow of the validated hand target while frozen; updates are
#     Physics-process-rate and frame-rate independent; implausible jumps are rejected locally
#     (a configurable safety limit) and counted, never applied.
#   * RELEASE / GRAB_CANCELLED: detach, restore the normal rigid-body behaviour with NO impulse
#     (phase 3 contract: "let the object fall or behave normally in place").
#   * WebSocket disconnect while grabbed: force release (connect event in main.gd); the object is
#     never left attached to a silent host.
class_name GrabbableCube
extends RigidBody3D

signal object_moved(address: String)

@export var max_move_jump_m: float = 0.5      # safety screen on MOVE_TARGET plausibility
@export var hover_color := Color(1.0, 0.9, 0.2)
@export var grabbed_color := Color(0.4, 0.9, 1.0)
@export var idle_color := Color(0.8, 0.35, 0.25)

var grabbable := true
var held := false

var _hovered := false
var _last_move := Vector3.ZERO
var _last_move_ms := 0
var _last_jump_reject_ms := 0
var _mat: StandardMaterial3D
var _rest_reported := true

func _ready() -> void:
	_mat = _material()
	set_color(idle_color)
	# The cube starts resting on the floor plane; it rests again after release -> report via Godot > OBJECT_STATE.

func is_grabbable() -> bool:
	return grabbable and not held

func set_hovered(active: bool) -> void:
	_hovered = active
	if not held:
		set_color(hover_color if active else idle_color)

func begin_grab(hand_pos: Vector3, grabbable_ok: bool) -> void:
	if not grabbable_ok:
		return
	held = true
	freeze = true
	freeze_mode = RigidBody3D.FREEZE_MODE_KINEMATIC
	linear_velocity = Vector3.ZERO
	angular_velocity = Vector3.ZERO
	_last_move = hand_pos
	_last_move_ms = Time.get_ticks_msec()
	global_position = hand_pos
	set_color(grabbed_color)
	_rest_reported = false

func confirm_grab() -> void:
	set_color(grabbed_color)

func move_to(pos: Vector3) -> void:
	if not held:
		return
	var now_ms := Time.get_ticks_msec()
	var dt := (now_ms - _last_move_ms) / 1000.0
	if dt > 0.0:
		var jump := (pos - _last_move).length() / maxf(dt, 0.001)
		if jump > max_move_jump_m * 10.0:     # far ABOVE typical hand speed: refuse, count, keep last sane target
			if now_ms - _last_jump_reject_ms > 1000:
				print("[saga4] MOVE_TARGET rejected: implausible speed %.2f m/s (limit %.2f)" % [jump, max_move_jump_m * 10.0])
				_last_jump_reject_ms = now_ms
			return
	if pos.is_finite():
		_last_move = pos
		_last_move_ms = now_ms
		global_position = pos

func release_grab() -> void:
	if not held:
		return
	held = false
	freeze = false                               # restore normal physics, zero impulse
	freeze_mode = RigidBody3D.FREEZE_MODE_STATIC
	linear_velocity = Vector3.ZERO
	angular_velocity = Vector3.ZERO
	set_color(hover_color if _hovered else idle_color)

func _physics_process(_delta: float) -> void:
	if held or _rest_reported:
		return
	# after a release the body may still settle: when it comes to rest, report the final resting position once
	if linear_velocity.length() < 0.05:
		_rest_reported = true
		object_moved.emit("resting")

func set_color(c: Color) -> void:
	if _mat != null:
		_mat.albedo_color = c
		_mat.emission_enabled = c != idle_color
		_mat.emission = c
		_mat.emission_energy_multiplier = 0.35

func _material() -> StandardMaterial3D:
	var mesh_node := get_node_or_null("Mesh")
	if mesh_node == null:
		return null
	var cur: Variant = mesh_node.get("material_override")
	if cur is StandardMaterial3D:
		return cur
	var mat := StandardMaterial3D.new()
	mesh_node.set("material_override", mat)
	return mat
