# SAGA 3D Phase 4 — status panel: connection, host state, gesture state, tracking quality.
# Pure display; it never decides anything (single source: the host messages, once validated).
class_name StatusUI
extends CanvasLayer

var labels := {}
const LINES := [
	["connection", "connection: -"],
	["session", "session: -"],
	["host_state", "host: -"],
	["gesture", "gesture: -"],
	["hover", "hover: -"],
	["tracking", "tracking: -"],
	["fusion", "fusion: -"],
	["notes", ""],
]

func _ready() -> void:
	# Panel/Body children are created in main.tscn in EXACTLY the LINES order; map them by index.
	var p := get_node_or_null("Panel/Body")
	if p == null:
		return
	var children := p.get_children()
	for i in mini(LINES.size(), children.size()):
		labels[LINES[i][0]] = children[i]
		children[i].set("text", LINES[i][1])

func set_connection(ok: bool, detail: String) -> void:
	var label := _label("connection")
	if label != null:
		label.set("text", ("connection: CONNECTED" if ok else "connection: DOWN") + " - " + detail)

func set_session_id(sid: String) -> void:
	var label := _label("session")
	if label != null:
		label.set("text", "session: %s" % (sid if sid != "" else "-"))

func set_host_state(state: String, detail: String) -> void:
	var label := _label("host_state")
	if label != null:
		label.set("text", "host: %s%s" % [state, (" - " + detail) if detail != "" else ""])

func set_gesture(state: String) -> void:
	var label := _label("gesture")
	if label != null:
		label.set("text", "gesture: %s" % state)

func set_hover(active: bool) -> void:
	var label := _label("hover")
	if label != null:
		label.set("text", "hover: %s" % ("IN REACH" if active else "-"))

func set_tracking(status: String, detail: String) -> void:
	var label := _label("tracking")
	if label != null:
		label.set("text", "tracking: %s%s" % [status, (" - " + detail) if detail != "" else ""])

func set_fusion_from_body(body: Dictionary) -> void:
	var label := _label("fusion")
	if label != null:
		var st: String = str(body.get("last_fusion_status", "-"))
		var sens: String = str(body.get("connected_sensors", "0"))
		var cal: String = str(body.get("calibrated_sensors", "0"))
		var q: String = str(body.get("last_fusion_quality", "-"))
		label.set("text", "fusion: %s | sensors %s calibrated %s | quality %s | trusted %s" % [st, sens, cal, q, str(body.get("tracking_trusted", "-"))])

func note(text: String) -> void:
	var label := _label("notes")
	if label != null:
		label.set("text", text)

func _label(key: String) -> Node:
	return labels.get(key)
