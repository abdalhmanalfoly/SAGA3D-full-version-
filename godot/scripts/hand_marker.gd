# SAGA 3D Phase 4 — visible hand marker.
#
# Follows ONLY validated host positions (pose_valid). Local smoothing is a small lerp for visual
# comfort - it does NOT duplicate the Phase 2 One Euro smoothing, adds at most a frame or two of
# lag and never extrapolates. When no valid pose arrives within stale_after_ms the marker dims,
# freezes in place and shows STALE; it never keeps moving on an old coordinate.
class_name HandMarker
extends Node3D

@export var follow_speed: float = 12.0        # m/s at which the visual marker chases the estimate
@export var stale_after_ms: float = 400.0     # no VALID pose for this long -> visual "stale"
@export var tracking_color := Color(0.35, 1.0, 0.45)
@export var stale_color := Color(1.0, 0.85, 0.3)
@export var lost_color := Color(1.0, 0.35, 0.3)

var _target := Vector3.ZERO
var _has_target := false
var _state := "LOST"                          # TRACKING | STALE | LOST
var _last_valid_ms := -1

func _ready() -> void:
	set_state("LOST")

func set_target(pos: Vector3) -> void:
	_target = pos
	_has_target = true
	_last_valid_ms = Time.get_ticks_msec()
	if _state != "STALE":
		set_state("TRACKING")

func set_state(state: String) -> void:
	_state = state
	var mat := _material()
	if mat != null:
		mat.albedo_color = tracking_color if state == "TRACKING" else (stale_color if state == "STALE" else lost_color)
		mat.emission_enabled = state != "LOST"
		mat.emission = mat.albedo_color
		mat.emission_energy_multiplier = 0.6 if state == "TRACKING" else 0.15

func mark_stale() -> void:
	if _state == "TRACKING":
		set_state("STALE")
		_has_target = false                       # freeze in place; never chase an old coordinate

func mark_lost() -> void:
	set_state("LOST")
	_has_target = false                          # freeze; never continue on an old coordinate

func _process(_delta: float) -> void:
	if _has_target:
		var now := Time.get_ticks_msec()
		if float(now - _last_valid_ms) > stale_after_ms:
			mark_stale()
		var step: float = minf(follow_speed * _delta * 10.0, 1.0)
		global_position = global_position.lerp(_target, step)

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
