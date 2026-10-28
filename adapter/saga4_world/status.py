"""Top-level host status derivation for the world adapter viewer.

States (stable names, used verbatim in HOST_STATUS messages and in the Godot status panel):
  STOPPED / INITIALIZING / WAITING_FOR_SENSORS / CALIBRATION_REQUIRED / READY / TRACKING / DEGRADED / ERROR / SHUTTING_DOWN

Derived by a pure function so it is unit-testable; the bridge evaluates it from
  * session state,
  * gesture agent state,
  * coordinator degraded status (``tracking_trusted``),
  * latest fusion result,
  * calibration status.
The value is deliberately conservative: the host never claims TRACKING unless fusion is valid, the
coordinator reports tracking_trusted AND an interaction is actually active.
"""
from __future__ import annotations

from dataclasses import dataclass

STOPPED = "STOPPED"
INITIALIZING = "INITIALIZING"
WAITING_FOR_SENSORS = "WAITING_FOR_SENSORS"
CALIBRATION_REQUIRED = "CALIBRATION_REQUIRED"
READY = "READY"
TRACKING = "TRACKING"
DEGRADED = "DEGRADED"
ERROR = "ERROR"
SHUTTING_DOWN = "SHUTTING_DOWN"


@dataclass(frozen=True)
class StatusInputs:
    session_active: bool
    connected_sensors: int          # sensors with an open socket AND online state
    calibrated_sensors: int         # sensors whose bound camera has VALID, compatible calibration
    calibration_ok: bool            # >= one valid compatible calibration is loaded and reachable by fusion
    fusion_valid: bool              # latest FusionResult.valid (== status TRACKING_MULTI_VIEW)
    tracking_trusted: bool          # coordinator: no active DEGRADED_STATUS / lease healthy
    gesture_state: str              # Phase 3 gesture states: IDLE | HOVER | GRABBED | RELEASED (inhibited -> "INHIBITED")
    held_interaction: bool          # a grab is currently active
    world_connected: bool           # the Godot client is currently connected
    shutting_down: bool = False


def derive(s: StatusInputs) -> str:
    # decision order: fatal/terminal first, then explicit blocking states, then healthy tracking, then degraded.
    if s.shutting_down:
        return SHUTTING_DOWN
    if not s.session_active or s.gesture_state in ("INHIBITED", "STOPPED"):
        return STOPPED
    if not s.calibration_ok:
        return CALIBRATION_REQUIRED
    if s.fusion_valid and s.tracking_trusted and s.held_interaction:
        return TRACKING
    # from here: the pipeline is alive but the demo is not fully trusted
    if s.connected_sensors >= 2 and s.calibrated_sensors < 2:
        return DEGRADED          # two cameras but calibration covers fewer: no trusted 3D available
    if s.connected_sensors >= 2 and s.calibrated_sensors >= 2:
        # rigs/sensors alive with enough calibrated views: READY until tracking becomes trusted again
        return READY if s.world_connected else DEGRADED
    if s.connected_sensors == 1:
        return DEGRADED          # one camera can never give a trusted multi-view result
    return WAITING_FOR_SENSORS   # no sensor connected yet


def detail_for(state: str, latest_fusion_reason: str | None = None, degraded_reason: str | None = None) -> str:
    """Human-facing reason (the host's own view; never a claim that something is fine when it is not)."""
    if state == CALIBRATION_REQUIRED:
        return latest_fusion_reason or "no valid compatible calibration for the observing sensors"
    if state == DEGRADED:
        return degraded_reason or latest_fusion_reason or "tracking not trusted (see operator page)"
    if state == STOPPED:
        return "waiting for an active session / stopped"
    if state == SHUTTING_DOWN:
        return "session is stopping"
    if state == READY:
        return "session running; waiting for trusted multi-view tracking"
    if state == TRACKING:
        return "trusted multi-view fusion active"
    if state == WAITING_FOR_SENSORS:
        return "no sensor connected yet"
    return degraded_reason or ""
