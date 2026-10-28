"""Coordinate transform tests: known points, inverse consistency, safety, volume handling."""
import math

import pytest

from saga4_world.transform import TransformError, WorldTransform


def cfg():
    from saga4_world.config import load_world_config
    return load_world_config().transform


def test_identity_round_trip():
    t = WorldTransform.from_config({"rotation": [[1, 0, 0], [0, 1, 0], [0, 0, 1]], "translation_m": [0, 0, 0], "scale": 1.0})
    p = t.rig_to_godot((0.31, -0.12, 0.77))
    assert all(abs(a - b) < 1e-12 for a, b in zip(p, (0.31, -0.12, 0.77)))
    assert t.godot_to_rig(p) == pytest.approx((0.31, -0.12, 0.77))


def test_default_axis_map_documented_semantics():
    # verifier: the DEFAULT config's rotation part (translation excluded from axis semantics)
    from saga4_world.config import load_world_config
    t = load_world_config().transform
    rot_no_trans = WorldTransform.from_config({"rotation": [
        [t.rotation[0][0], t.rotation[0][1], t.rotation[0][2]],
        [t.rotation[1][0], t.rotation[1][1], t.rotation[1][2]],
        [t.rotation[2][0], t.rotation[2][1], t.rotation[2][2]]]})
    # rig: X right, Y horizontal-away, Z up  ->  godot: X right, Y up, -Z into the screen
    assert rot_no_trans.rig_to_godot((1, 0, 0)) == pytest.approx((1, 0, 0))    # X preserved
    assert rot_no_trans.rig_to_godot((0, 1, 0)) == pytest.approx((0, 0, -1))   # rig 'away' -> godot -Z
    assert rot_no_trans.rig_to_godot((0, 0, 1)) == pytest.approx((0, 1, 0))    # rig up -> godot up


def test_translation_and_scale():
    t = WorldTransform.from_config({"rotation": [[1, 0, 0], [0, 1, 0], [0, 0, 1]], "scale": 2.0, "translation_m": [10, 20, 30]})
    p = t.rig_to_godot((1, 1, 1))
    assert p == pytest.approx((12, 22, 32))
    assert t.godot_to_rig(p) == pytest.approx((1, 1, 1))


def test_inverse_matches_forward():
    t = WorldTransform.from_config({"rotation": [[1, 0, 0], [0, 0, 1], [0, -1, 0]], "translation_m": [0, 0, -1.6]})
    for p in [(0, 0, 0), (0.5, -0.2, 1.3), (-0.7, 0.05, 2.0)]:
        assert t.godot_to_rig(t.rig_to_godot(p)) == pytest.approx(p, abs=1e-12)


def test_non_finite_refused():
    t = cfg()
    for bad in [(float("nan"), 0, 0), (0, float("inf"), 0), (0, 0, float("-inf")), (1, 2)]:
        with pytest.raises(TransformError) as e:
            t.rig_to_godot(bad)
        assert e.value.code == "NON_FINITE"


def test_volume_flagged_and_rejectable():
    t = WorldTransform.from_config({"volume_m": {"x": [-1, 1], "y": [0, 2], "z": [-3, 0]}})
    out = t.rig_to_godot((5.0, 0, -1))                       # x far outside
    assert not t.is_inside_volume(out)                       # flagged, per default config NOT dropped
    t2 = WorldTransform.from_config({"volume_m": {"x": [-1, 1], "y": [0, 2], "z": [-3, 0]}, "reject_outside_volume": True})
    with pytest.raises(TransformError) as e:
        t2.rig_to_godot((5.0, 0, -1))
    assert e.value.code == "OUT_OF_VOLUME"


def test_object_registration_inverse_inside_volume():
    t = cfg()
    obj_godot = (0.0, 0.04, -1.6)
    rig = t.godot_to_rig(obj_godot)
    assert t.rig_to_godot(rig) == pytest.approx(obj_godot)   # object re-registers identically


def test_fingerprint_changes_detectable():
    t = cfg()
    f1 = t.fingerprint()
    t2 = WorldTransform.from_config({"rotation": [[1, 0, 0], [0, 0, 1], [0, -1, 0]]})
    assert t2.fingerprint() != f1


def test_invalid_config_refused():
    for bad in [{"scale": 0}, {"scale": -1}, {"rotation": [[1, 0], [0, 1]]},
                {"rotation": [[2, 0, 0], [0, 1, 0], [0, 0, 1]]},                       # not unit
                {"rotation": [[1, 0.5, 0], [0.5, 1, 0], [0, 0, 1]]},                  # not orthogonal
                {"volume_m": {"x": [5, -5]}}, {"bogus_key": 1}]:
        with pytest.raises(TransformError):
            WorldTransform.from_config(bad)


def test_axis_flip_detected_as_left_handed():
    with pytest.raises(TransformError):
        WorldTransform.from_config({"rotation": [[1, 0, 0], [0, 1, 0], [0, 0, -1]]})
