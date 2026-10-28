"""Behaviour tests for the per-session bridge (fusion -> gesture -> Godot payload).

Uses the REAL Phase 3 GestureAgent and REAL pydantic FusionResult contract (see conftest),
plus a duck-typed session/engine so no host process is needed.
"""
import time
import types

import pytest

from conftest import FakeClock, drain_conn, fusion_result, make_bridge, pinch_landmarks


def frames_of(frames, mt):
    return [f for f in frames if f.get("message_type") == mt]


def last_pose(frames):
    poses = frames_of(frames, "POSE_UPDATE")
    return poses[-1] if poses else None


def feed_valid(world, clock, seq, pos=(0.0, 0.05, 0.05), sources=None, pinch=None, quality=0.95):
    """One VALID fusion result; optional pinch evidence attached to the contributing sensor."""
    if pinch is not None:
        buf = world.session.fusion.engine.sync.buffers["cam_a"]
        buf.append(type(buf[0])(seq, pinch_landmarks(pinch), int(clock.now_ms())))
    r = fusion_result(seq=seq, world=pos, sources=sources or [("cam_a", seq)], ts=clock.now_ms(), quality_score=quality)
    world.on_fusion_result(r)


def feed(world, clock, seq, status="TRACKING_MULTI_VIEW", pos=None, sources=None):
    r = fusion_result(seq=seq, world=pos, status=status, sources=sources or [("cam_a", seq)], ts=clock.now_ms())
    world.on_fusion_result(r)


def connect(world):
    """Bridge-level Godot handshake (the socket layer is covered separately)."""
    msg = types.SimpleNamespace(sequence_number=0, fields={
        "client_id": "godot_t",
        "objects": [types.SimpleNamespace(object_id="cube_1", position=(0.0, 0.04, -1.6), grabbable=True)]})
    return world.register_client(msg, 1000.0)


def send_ack(world, etype, eid, accepted=True, target="cube_1"):
    world.on_client_message(types.SimpleNamespace(message_type="ACK",
                                                  fields={"ack_event_type": etype, "event_id": eid,
                                                          "accepted": accepted, "target_object_id": target,
                                                          "reason": None}))


def hover_then_grab(world, clock, open_ratio=0.8, closed_ratio=0.15):
    """Drive hover + a confirmed grab; returns the emitted frames after the GRAB_REQUEST cycle."""
    frames = []
    s = 1
    for _ in range(7):                                # open hand in reach -> HOVER
        feed_valid(world, clock, s, pinch=open_ratio)
        clock.advance(50)
        s += 1
    frames += drain_conn(world)[0]
    for _ in range(8):                                # pinched for >= confirm_ms -> GRAB_REQUEST
        feed_valid(world, clock, s, pinch=closed_ratio)
        clock.advance(50)
        s += 1
    frames += drain_conn(world)[0]
    return frames, s


def request_id(frames):
    reqs = [f for f in frames_of(frames, "INTERACTION_EVENT") if f.get("event_type") == "GRAB_REQUEST"]
    return reqs[-1]["event_id"] if reqs else None


# ------------------------------------------------------------------ pose path
def test_valid_pose_is_transformed_and_forwarded(world_cfg):
    world, session, clock, events = make_bridge(world_cfg)
    connect(world)
    # rig (0.5, 0.1, 1.0) -> godot (0.5, 1.0, -0.1 - 1.6) with the documented axis map + translation
    feed_valid(world, clock, 1, pos=(0.5, 0.1, 1.0))
    frames, _ = drain_conn(world)
    pose = last_pose(frames)
    assert pose is not None
    assert pose["position"] == pytest.approx([0.5, 1.0, -1.7])
    assert pose["world_position_m"] == pytest.approx([0.5, 0.1, 1.0])
    assert pose["unit"] == "m" and pose["world_frame_id"] == "rig_1"
    assert pose["valid"] is True and pose["status"] == "TRACKING_MULTI_VIEW"
    assert pose["sequence_number"] == 1                # pose stream starts at 1 per connection


def test_invalid_fusion_never_publishes_a_position(world_cfg):
    world, session, clock, events = make_bridge(world_cfg)
    connect(world)
    feed(world, clock, 1, status="TARGET_LOST")
    frames, _ = drain_conn(world)
    for f in frames_of(frames, "POSE_UPDATE"):
        assert f["position"] is None and f["valid"] is False


def test_stale_pose_slot_collapses(world_cfg):
    world, session, clock, events = make_bridge(world_cfg)
    connect(world)
    for s in range(1, 6):
        feed_valid(world, clock, s, pos=(0.01 * s, 0.05, 0.05))
        clock.advance(20)
    frames, _ = drain_conn(world)
    poses = frames_of(frames, "POSE_UPDATE")
    assert len(poses) <= 2                             # collapse: not all 5 forward
    assert len(drain_conn(world)[0]) == 0              # and nothing else lingers: bounded queues


def test_full_pipeline_never_blocks_on_missing_godot(world_cfg):
    world, session, clock, events = make_bridge(world_cfg)
    for s in range(1, 30):                             # no connection at all: bridge still ticks fine
        feed_valid(world, clock, s, pinch=0.8)
        clock.advance(50)
        world.tick()
    assert world.counters["world_pose_in"] >= 1


# ------------------------------------------------------------------ gesture path
def test_exactly_one_hover_and_one_grab(world_cfg):
    world, session, clock, events = make_bridge(world_cfg)
    connect(world)
    frames, s = hover_then_grab(world, clock)
    hovers = [f for f in frames_of(frames, "INTERACTION_EVENT") if f.get("event_type") == "HOVER_ENTER"]
    grabs = frames_of(frames, "INTERACTION_EVENT")
    grabs = [f for f in grabs if f.get("event_type") == "GRAB_REQUEST"]
    assert len(hovers) == 1 and len(grabs) == 1
    assert grabs[0]["target_object_id"] == "cube_1"
    assert grabs[0]["hand_target"] is not None         # grab events carry their transformed target


def test_duplicate_grab_events_never_repeat(world_cfg):
    world, session, clock, events = make_bridge(world_cfg)
    connect(world)
    frames, s = hover_then_grab(world, clock)
    frames += drain_conn(world)[0]
    grabs = [f for f in frames_of(frames, "INTERACTION_EVENT") if f.get("event_type") == "GRAB_REQUEST"]
    assert len(grabs) >= 1
    # keep feeding pinched data; the gesture state machine must not re-emit (already GRABBED)...
    for i in range(5):
        feed_valid(world, clock, s, pinch=0.15)
        clock.advance(60)
        s += 1
        frames += drain_conn(world)[0]
    assert len([f for f in frames_of(frames, "INTERACTION_EVENT") if f.get("event_type") == "GRAB_REQUEST"]) == 1


def test_grab_requires_godot_ack(world_cfg):
    world, session, clock, events = make_bridge(world_cfg)   # config default require_adapter_ack: true
    assert world.gesture_cfg.require_adapter_ack is True
    connect(world)
    frames, s = hover_then_grab(world, clock)
    eid = request_id(frames)
    assert eid is not None
    frames += drain_conn(world)[0]
    # ...before the ack there is NO GRAB_CONFIRMED (no invalid record confirmed by host)
    assert not [f for f in frames_of(frames, "INTERACTION_EVENT") if f.get("event_type") == "GRAB_CONFIRMED"]
    send_ack(world, "GRAB_REQUEST", eid, accepted=True)
    frames, _ = drain_conn(world)
    confirms = [f for f in frames_of(frames, "INTERACTION_EVENT") if f.get("event_type") == "GRAB_CONFIRMED"]
    assert len(confirms) == 1
    # a duplicate ACK id must be ignored: no second CONFIRMED / no transitions
    send_ack(world, "GRAB_REQUEST", eid, accepted=True)
    frames, _ = drain_conn(world)
    assert not [f for f in frames_of(frames, "INTERACTION_EVENT") if f.get("event_type") == "GRAB_CONFIRMED"]


def test_ack_rejection_cancels_grab(world_cfg):
    world, session, clock, events = make_bridge(world_cfg)
    connect(world)
    frames, s = hover_then_grab(world, clock)
    eid = request_id(frames)
    drain_conn(world)
    send_ack(world, "GRAB_REQUEST", eid, accepted=False)
    frames, _ = drain_conn(world)
    cancelled = [f for f in frames_of(frames, "INTERACTION_EVENT") if f.get("event_type") == "GRAB_CANCELLED"]
    assert len(cancelled) == 1 and cancelled[0]["cancel_reason"] == "ADAPTER_REJECTED"


def test_move_target_only_while_grabbed(world_cfg):
    world, session, clock, events = make_bridge(world_cfg)
    connect(world)
    frames, s = hover_then_grab(world, clock)
    eid = request_id(frames)
    drain_conn(world)
    send_ack(world, "GRAB_REQUEST", eid, accepted=True)
    drain_conn(world)
    # moving while GRABBED produces several MOVE_TARGET updates (rate-limited 30 Hz)
    for i in range(8):
        feed_valid(world, clock, s, pos=(0.0, 0.05, 0.5 + 0.01 * i), pinch=0.15)
        clock.advance(50)
        s += 1
    time.sleep(0.06)                                   # MOVE_TARGET drain yields to CONTROL/events; real-time gate
    frames, _ = drain_conn(world)
    moves = [f for f in frames_of(frames, "INTERACTION_EVENT") if f.get("event_type") == "MOVE_TARGET"]
    assert len(moves) >= 1
    tgt = moves[-1]["hand_target"]
    # rig z 0.57 (max feed z) -> godot y = 0.57? no: godot = (x, z, -y): y=0.57? check x/y/z mapping below
    assert tgt[0] == pytest.approx(0.0)
    assert tgt[1] == pytest.approx(0.5 + 0.01 * 7)     # rig z -> godot y
    assert tgt[2] == pytest.approx(-0.05 - 1.6)        # rig y -> -godot z, plus the configured translation
    # hover with an open hand while idle produces NO move targets
    world2, session2, clock2, _ = make_bridge(world_cfg)
    connect(world2)
    for i in range(7):
        feed_valid(world2, clock2, i + 1, pos=(0.0, 0.05, 0.05), pinch=0.8)   # open hand in reach -> HOVER only
        clock2.advance(50)
    time.sleep(0.001)
    frames2, _ = drain_conn(world2)
    moves2 = [f for f in frames_of(frames2, "INTERACTION_EVENT") if f.get("event_type") == "MOVE_TARGET"]
    assert not moves2


def test_release_exact_once(world_cfg):
    world, session, clock, events = make_bridge(world_cfg)
    connect(world)
    frames, s = hover_then_grab(world, clock)
    eid = request_id(frames)
    drain_conn(world)
    send_ack(world, "GRAB_REQUEST", eid, accepted=True)
    drain_conn(world)
    for _ in range(6):                                 # open the hand: RELEASE (after release_confirm_ms)
        feed_valid(world, clock, s, pinch=0.8)
        clock.advance(50)
        s += 1
    frames, _ = drain_conn(world)
    releases = [f for f in frames_of(frames, "INTERACTION_EVENT") if f.get("event_type") == "RELEASE"]
    assert len(releases) == 1
    rel_eid = releases[0]["event_id"]
    # release ack completes the RELEASED state cleanly
    send_ack(world, "RELEASE", rel_eid, accepted=True)
    for _ in range(3):
        feed_valid(world, clock, s, pinch=0.8)
        clock.advance(60)
        s += 1
    frames += drain_conn(world)[0]
    assert len([f for f in frames_of(frames, "INTERACTION_EVENT") if f.get("event_type") == "RELEASE"]) == 1


def test_tracking_loss_freezes_then_cancels(world_cfg):
    world, session, clock, events = make_bridge(world_cfg)
    connect(world)
    frames, s = hover_then_grab(world, clock)
    eid = request_id(frames)
    drain_conn(world)
    send_ack(world, "GRAB_REQUEST", eid, accepted=True)
    drain_conn(world)
    feed(world, clock, s, status="TARGET_LOST")        # tracking gone while GRABBED
    clock.advance(150)                                 # > tracking_lost_report_ms (100) without valid data
    world.tick()
    frames, _ = drain_conn(world)
    lost = frames_of(frames, "INTERACTION_EVENT")
    assert [f.get("event_type") for f in lost].count("TRACKING_LOST") == 1
    # > grab_loss_timeout_ms: bounded safe release
    clock.advance(world.gesture_cfg.grab_loss_timeout_ms + 150)
    world.tick()
    frames, _ = drain_conn(world)
    cancels = [f for f in frames_of(frames, "INTERACTION_EVENT") if f.get("event_type") == "GRAB_CANCELLED"]
    assert len(cancels) == 1 and cancels[0]["cancel_reason"] == "TRACKING_LOST_TIMEOUT"


def test_calibration_invalid_blocks_interaction(world_cfg):
    world, session, clock, events = make_bridge(world_cfg)
    connect(world)
    frames, s = hover_then_grab(world, clock)
    drain_conn(world)
    feed(world, clock, s, status="CALIBRATION_REQUIRED")
    frames, _ = drain_conn(world)
    # safe stop: CALIBRATION_REQUIRED carries no position; any held grab must be cancelled
    assert frames_of(frames, "POSE_UPDATE") == []
    etypes = [f.get("event_type") for f in frames_of(frames, "INTERACTION_EVENT")]
    assert etypes.count("MOVE_TARGET") == 0 and etypes.count("GRAB_REQUEST") == 0
    for i in range(4):
        feed_valid(world, clock, s, pinch=0.15)
        clock.advance(50)
        s += 1
    frames, _ = drain_conn(world)
    etypes = [f.get("event_type") for f in frames_of(frames, "INTERACTION_EVENT")]
    assert etypes.count("GRAB_REQUEST") == 0            # the pinched entry without an armed hover must not grab
    hover_after_cal = etypes.count("HOVER_ENTER")       # the FIRST valid sample after the calibration flag resumes hover
    # a valid result again restores the pipeline: hover stays; no MORE hover_enter events may repeat
    for i in range(6):
        feed_valid(world, clock, s, pinch=0.8)
        clock.advance(60)
        s += 1
    frames, _ = drain_conn(world)
    hovers = [f for f in frames_of(frames, "INTERACTION_EVENT") if f.get("event_type") == "HOVER_ENTER"]
    assert hover_after_cal + len(hovers) == 1           # interaction resumed exactly once from valid data


def test_out_of_session_data_ignored(world_cfg):
    world, session, clock, events = make_bridge(world_cfg)
    connect(world)
    r = fusion_result(session_id="sess_OTHER", seq=1, world=(0, 0, 0), ts=clock.now_ms())
    world.on_fusion_result(r)
    frames, _ = drain_conn(world)
    assert last_pose(frames) is None


def test_second_godot_client_is_refused(world_cfg):
    world, session, clock, events = make_bridge(world_cfg)
    assert connect(world) is not None
    assert connect(world) is None                       # explicit reject: WORLD_CLIENT_EXISTS downstream


def test_object_registration_uses_inverse_transform(world_cfg):
    world, session, clock, events = make_bridge(world_cfg)
    msg = types.SimpleNamespace(sequence_number=0, fields={"objects": [
        types.SimpleNamespace(object_id="cube_1", position=(0.1, 0.5, -1.0), grabbable=True)]})
    assert world.register_client(msg, 1000.0) is not None
    assert world.transform.rig_to_godot(world.objects["cube_1"].position_rig_m) == pytest.approx((0.1, 0.5, -1.0))


def test_out_of_volume_object_rejected_with_error(world_cfg):
    world, session, clock, events = make_bridge(world_cfg)
    connect(world)
    world.on_client_message(types.SimpleNamespace(message_type="OBJECT_STATE", fields={"objects": [
        types.SimpleNamespace(object_id="cube_x", position=(99.0, 9.0, -1.0), grabbable=True)]}))
    frames, _ = drain_conn(world)
    errs = frames_of(frames, "ERROR")
    assert len(errs) == 1 and errs[0]["error_code"] == "OBJECT_OUTSIDE_VOLUME"
    assert "cube_x" not in world.objects


def test_transform_change_resets_interaction(world_cfg):
    world, session, clock, events = make_bridge(world_cfg)
    connect(world)
    frames, s = hover_then_grab(world, clock)
    drain_conn(world)
    # simulate a calibration change: a DIFFERENT transform fingerprint must reset the interaction
    from saga4_world.transform import WorldTransform
    world.transform = WorldTransform.from_config({"rotation": [[1, 0, 0], [0, 0, 1], [0, -1, 0]],
                                                  "translation_m": [0.1, 0.0, -1.5], "scale": 1.0})
    try:
        feed_valid(world, clock, s, pinch=0.15)
        frames, _ = drain_conn(world)
        cancels = frames_of(frames, "INTERACTION_EVENT")
        assert [f.get("event_type") for f in cancels].count("GRAB_CANCELLED") >= 1
        assert world.counters.get("world_transform_changed", 0) >= 1
    finally:
        pass
