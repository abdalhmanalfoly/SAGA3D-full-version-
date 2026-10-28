"""Shared fixtures for the Phase 4 world-adapter tests.

The Phase 1-3 code is used READ-ONLY: we import its gesture modules and build REAL pydantic
``FusionResult`` objects (the actual Phase 2 contract) instead of mocks where practical.
"""
import sys
import time
import types
from collections import deque
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
ADAPTER = REPO_ROOT / "adapter"
for p in (str(ADAPTER),):
    if p not in sys.path:
        sys.path.insert(0, p)

from saga4_world.config import load_world_config  # noqa: E402
from saga4_world.p3 import p3 as make_p3              # noqa: E402

P3 = make_p3()


@pytest.fixture()
def world_cfg():
    cfg = load_world_config()
    # tests run faster: shorter ack windows are NOT used - keep the production values (real contract).
    return cfg


# ----------------------------------------------------------------------- fakes
class FakeSmoother:
    def __init__(self):
        self.resets: list[str] = []


class FakeObs:
    def __init__(self, seq, landmarks, effective_ms=1000):
        self.sequence_number = seq
        self.effective_ms = effective_ms
        self.landmarks = landmarks


class FakeSync:
    def __init__(self):
        self.buffers = {"cam_a": deque([FakeObs(1, SAMPLE_LANDMARKS)], maxlen=16)}


class FakeEngine:
    def __init__(self):
        self.sync = FakeSync()
        self.smoothers = {"wrist": FakeSmoother()}

    def reset(self, reason=""):
        self.smoothers["wrist"].resets.append(reason)


class FakeRegistry:      # calibration registry port
    problem = None
    artifact = types.SimpleNamespace(camera_id="phone_left")

    def resolve(self, sensor_id, width=None, height=None):
        return self


class FakeFusion:
    def __init__(self):
        self.engine = FakeEngine()
        self.registry = FakeRegistry()


class FakeRecords:
    def __init__(self):
        self.records: dict = {}

    def snapshot(self, rec, now_ms):
        return {"connected": bool(rec.get("connected", True)), "state": rec.get("state", "online")}


class FakeSession:
    def __init__(self, sid="sess_worldtest1"):
        self.session_id = sid
        self.state = "active"
        self.fusion = FakeFusion()
        self.registry = FakeRecords()
        self.registry.records = {"cam_a": {"connected": True, "state": "online"},
                                 "cam_b": {"connected": True, "state": "online"}}

    def status(self):
        return {"session_id": self.session_id}


class FakeClock:
    def __init__(self, start=1_700_000_000_000):
        self._t = start

    def now_ms(self) -> int:
        return self._t

    def advance(self, ms: float) -> None:
        self._t += int(round(ms))


class NoopEvents:
    def log(self, *a, **kw):
        pass


# ----------------------------------------------------------------------- fusion payload
SAMPLE_LANDMARKS = {
    "wrist": (320.0, 400.0, None),
    "wrist_tip": (0.0, 0.0, None),
    "thumb_tip": (300.0, 400.0, None),
    "index_tip": (300.0, 400.0, None),
    "index_mcp": (320.0, 320.0, None),
    "pinky_mcp": (200.0, 400.0, None),
}


def pinch_landmarks(ratio: float, scale=100.0):
    """Craft 2D landmarks whose pinch_ratio == ratio (|thumb-index|/|wrist-index_mcp|)."""
    return {
        "wrist": (0.0, 0.0, None),
        "thumb_tip": (0.0, 0.0, None),
        "index_tip": (ratio * scale, 0.0, None),
        "index_mcp": (0.0, scale, None),
    }


FUSION_STATUS = types.SimpleNamespace(TRACKING_MULTI_VIEW="TRACKING_MULTI_VIEW",
                                      INSUFFICIENT_VIEWS="INSUFFICIENT_VIEWS",
                                      TARGET_LOST="TARGET_LOST",
                                      CALIBRATION_REQUIRED="CALIBRATION_REQUIRED")


def fusion_result(session_id="sess_worldtest1", *, seq=1, world=None, status="TRACKING_MULTI_VIEW",
                  sources=None, ts=1_700_000_000_000, quality_score=0.95, frame="rig_1",
                  warnings=None, reason=None):
    """A REAL (validated by pydantic) Phase 2 FusionResult built with the actual model."""
    from host.app.spatial.results import QualityInfo, SourceInfo, FusionStatus, FusionResult
    used = sources or [("cam_a", 1)]
    q = QualityInfo(score=quality_score, reprojection=0.9, sync=0.9, geometry=0.9)
    srcs = [SourceInfo(sensor_id=sid, camera_id=f"cam_{sid}", calibration_id="cal_1", sequence_number=sq,
                       frame_id=sq, captured_at_ms=ts, received_at_ms=ts, effective_time_ms=float(ts),
                       age_ms=0.0, transport_delay_ms=3.0, reprojection_error_px=0.5, used=True, note=None)
            for (sid, sq) in used]
    st = FusionStatus(status)
    valid = st == FusionStatus.TRACKING_MULTI_VIEW
    return FusionResult(
        protocol_version="1.0", message_type="POSE_UPDATE", session_id=session_id, target_landmark="wrist",
        fusion_sequence=seq, status=st, valid=valid, reason=reason,
        message="synthetic" if valid else "synthetic invalid", timestamp_ms=float(ts), published_at_ms=ts + 5,
        world_frame_id=frame if valid else None,
        world_xyz_m=list(world) if valid else None,
        raw_world_xyz_m=list(world) if valid else None,
        held_world_xyz_m=None, held_age_ms=None, single_view_ray=None,
        source_sensor_ids=[s for (s, _) in used], sources=srcs, skew_ms=2.0,
        aggregate_reprojection_error_px=0.5, ray_angle_deg=45.0, quality=q, calibration=None,
        smoothing_applied=True, warnings=warnings or [])


def make_bridge(world_cfg, session=None, clock=None, events=None, coordinator_source=None):
    from saga4_world.bridge import SessionWorld
    session = session or FakeSession()
    clock = clock or FakeClock()
    events = events if events is not None else NoopEvents()
    world = SessionWorld(session, clock, events, world_cfg, coordinator_source=coordinator_source)
    return world, session, clock, events


def drain_conn(world):
    """All frames queued for the connection right now (pops them for assertions)."""
    frames = []
    conn = world.conn
    if conn is None:
        return frames, {}
    while conn.control:
        frames.append(conn.control.popleft())
    while conn.events:
        frames.append(conn.events.popleft())
    frames.extend(conn.drain())
    return frames, {"dropped": conn.dropped_events, "control_seq": conn.control_seq, "pose_seq": conn.pose_seq}
