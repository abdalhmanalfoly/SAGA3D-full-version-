"""Top-level status derivation tests: the host must never over-claim."""
from saga4_world.status import CALIBRATION_REQUIRED, DEGRADED, READY, SHUTTING_DOWN, STOPPED, StatusInputs, TRACKING, WAITING_FOR_SENSORS, derive


def si(**over):
    base = dict(session_active=True, connected_sensors=2, calibrated_sensors=2, calibration_ok=True,
                fusion_valid=False, tracking_trusted=True, gesture_state="IDLE", held_interaction=False,
                world_connected=True)
    base.update(over)
    return StatusInputs(**base)


def test_stopped_when_session_inactive():
    assert derive(si(session_active=False)) == STOPPED
    assert derive(si(shutting_down=True)) == SHUTTING_DOWN


def test_calibration_gate():
    assert derive(si(calibration_ok=False)) == CALIBRATION_REQUIRED


def test_tracking_claim_requires_valid_and_interaction():
    assert derive(si(fusion_valid=True, held_interaction=True)) == TRACKING
    assert derive(si(fusion_valid=True, held_interaction=False)) == READY
    # a degraded coordinator can NEVER be reported as trusted tracking
    assert derive(si(fusion_valid=True, held_interaction=True, tracking_trusted=False)) == READY


def test_degraded_when_only_one_camera():
    assert derive(si(connected_sensors=1, calibrated_sensors=1)) == DEGRADED


def test_waiting_without_sensors():
    assert derive(si(connected_sensors=0, calibrated_sensors=0)) == WAITING_FOR_SENSORS


def test_ready_requires_two_calibrated_sensors():
    assert derive(si(connected_sensors=2, calibrated_sensors=1)) == DEGRADED
