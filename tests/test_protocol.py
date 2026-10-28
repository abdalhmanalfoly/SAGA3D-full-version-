"""World protocol validation tests (host side): the trust boundary the Godot messages cross."""
import json

import pytest

from saga4_world.protocol import (ParsedMessage, WorldProtocolError, build_control, build_error, decode_frame,
                                  parse_ack, parse_client_message, parse_object_state, parse_world_hello)

SESSION = "sess_proto_test1"


def hello(seq=0, **over):
    base = {"protocol_version": "1.0", "message_type": "WORLD_HELLO", "session_id": SESSION,
            "sequence_number": seq, "timestamp_ms": 1700000000000, "client_id": "godot_1",
            "objects": [{"object_id": "cube_1", "position": [0.0, 0.04, -1.6], "grabbable": True}]}
    base.update(over)
    return base


def ack(seq=1, **over):
    base = {"protocol_version": "1.0", "message_type": "ACK", "session_id": SESSION,
            "sequence_number": seq, "timestamp_ms": 1700000000000,
            "ack_event_type": "GRAB_REQUEST", "event_id": "sess_g1",
            "accepted": True, "target_object_id": "cube_1", "reason": None}
    base.update(over)
    return base


def objs(seq=2, **over):
    base = {"protocol_version": "1.0", "message_type": "OBJECT_STATE", "session_id": SESSION,
            "sequence_number": seq, "timestamp_ms": 1700000000001,
            "objects": [{"object_id": "cube_1", "position": [0.1, 0.04, -1.6], "grabbable": True}]}
    base.update(over)
    return base


def hb(seq=3, **over):
    base = {"protocol_version": "1.0", "message_type": "HEARTBEAT", "session_id": SESSION,
            "sequence_number": seq, "timestamp_ms": 1700000000002, "fps": 60, "state": "READY"}
    base.update(over)
    return base


def raw(d):
    return json.dumps(d)


# -------------------------------------------------------------------------- happy paths
def test_hello_ok():
    parsed = parse_client_message(raw(hello()), SESSION, None)
    assert parsed.message_type == "WORLD_HELLO" and parsed.fields["client_id"] == "godot_1"
    assert parsed.fields["objects"][0].object_id == "cube_1"


def test_ack_ok_with_grab_and_release_types():
    for t in ("GRAB_REQUEST", "RELEASE"):
        parse_client_message(raw(ack(ack_event_type=t)), SESSION, 0)


# -------------------------------------------------------------------------- envelope rules
def test_unknown_session_rejected():
    with pytest.raises(WorldProtocolError) as e:
        parse_client_message(raw(hello(session_id="sess_other")), SESSION, None)
    assert e.value.code == "SESSION_MISMATCH"


def test_wrong_protocol_version_rejected():
    with pytest.raises(WorldProtocolError) as e:
        parse_client_message(raw(hello(protocol_version="2.0")), SESSION, None)
    assert e.value.code == "UNSUPPORTED_PROTOCOL_VERSION"


def test_unknown_client_type_rejected():
    with pytest.raises(WorldProtocolError) as e:
        parse_client_message(raw(hello(message_type="WORLD_MAGIC")), SESSION, None)
    assert e.value.code == "UNSUPPORTED_MESSAGE_TYPE"


def test_missing_field_rejected():
    d = hello()
    del d["client_id"]
    with pytest.raises(WorldProtocolError) as e:
        parse_client_message(raw(d), SESSION, None)
    assert e.value.code == "SCHEMA_VALIDATION_FAILED"


def test_extra_field_rejected():
    with pytest.raises(WorldProtocolError) as e:
        parse_client_message(raw(hello(extra_field=1)), SESSION, None)
    assert e.value.code == "SCHEMA_VALIDATION_FAILED"


def test_non_finite_number_rejected_from_json_text():
    # NaN/Infinity are not valid JSON but json.loads WILL accept them; the protocol must not.
    text = raw(hello()).replace('"timestamp_ms": 1700000000000', '"timestamp_ms": NaN')
    with pytest.raises(WorldProtocolError) as e:
        parse_client_message(text, SESSION, None)
    assert e.value.code == "SCHEMA_VALIDATION_FAILED"


def test_binary_and_oversize_rejected():
    with pytest.raises(WorldProtocolError) as e:
        decode_frame(b"\xff\xfe\x00")            # non-UTF-8 bytes: a binary frame
    assert e.value.code == "BINARY_NOT_SUPPORTED"
    with pytest.raises(WorldProtocolError) as e:
        parse_client_message("x" * (16384 + 1), SESSION, None)
    assert e.value.code == "MESSAGE_TOO_LARGE"


def test_not_json_rejected():
    with pytest.raises(WorldProtocolError) as e:
        parse_client_message("[1,2,3]", SESSION, None)
    assert e.value.code in ("MALFORMED_JSON", "SCHEMA_VALIDATION_FAILED")


# -------------------------------------------------------------------------- sequence discipline
def test_sequence_must_increase():
    parse_client_message(raw(objs(seq=2)), SESSION, 1)
    with pytest.raises(WorldProtocolError) as e:
        parse_client_message(raw(objs(seq=2)), SESSION, 2)     # repeat
    assert e.value.code == "STALE_SEQUENCE"
    with pytest.raises(WorldProtocolError):
        parse_client_message(raw(objs(seq=1)), SESSION, 2)     # regression


def test_object_position_must_be_3_finite():
    with pytest.raises(WorldProtocolError):
        parse_client_message(raw(objs(objects=[{"object_id": "c1", "position": [float("inf"), 0, 0], "grabbable": True}])), SESSION, None)
    with pytest.raises(WorldProtocolError):
        parse_client_message(raw(objs(objects=[{"object_id": "c1", "position": [0, 0], "grabbable": True}])), SESSION, None)


def test_object_id_pattern_enforced():
    with pytest.raises(WorldProtocolError):
        parse_client_message(raw(objs(objects=[{"object_id": "bad id!", "position": [0, 0, 0], "grabbable": True}])), SESSION, None)


def test_duplicate_object_ids_rejected():
    dup = {"object_id": "cube_1", "position": [0, 0, 0], "grabbable": True}
    with pytest.raises(WorldProtocolError):
        parse_client_message(raw(objs(objects=[dup, dup])), SESSION, None)


def test_ack_type_must_be_known():
    with pytest.raises(WorldProtocolError):
        parse_client_message(raw(ack(ack_event_type="HOVER")), SESSION, None)


def test_ack_accepted_must_be_bool():
    with pytest.raises(WorldProtocolError):
        parse_client_message(raw(ack(accepted="yes")), SESSION, None)


def test_hosts_builders_carry_the_required_fields():
    for msg in (build_control("HOST_STATUS", SESSION, 1, 1700000000000, {"state": "READY", "detail": ""}),
                build_error(SESSION, 1, 1700000000000, "X", "d")):
        assert {"protocol_version", "message_type", "session_id", "sequence_number", "timestamp_ms"} <= set(msg)
