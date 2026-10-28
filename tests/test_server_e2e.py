"""End-to-end tests: a REAL uvicorn server (full Phase 1-3 host + the Phase 4 world adapter) exercised
with a simulated Godot WebSocket client (websockets lib). Integration level: validation, sequence
ordering, acks and single-client enforcement against the actual wire protocol."""
import asyncio
import json
import socket
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
import uvicorn
import websockets

REPO = Path(__file__).resolve().parents[1]


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture()
def saga_server(tmp_path):
    """Run the combined app in its own thread/loop; yield a handle dict."""
    import sys
    import os
    for candidate in (str(REPO / "adapter"),):
        if candidate not in sys.path:
            sys.path.insert(0, candidate)
    os.environ["SAGA3_ROOT"] = str(REPO.parent / "saga-3d phase 3")
    os.environ["SAGA_LOG_DIR"] = str(tmp_path / "logs")
    os.environ["SAGA_CALIBRATION_DIR"] = str(tmp_path / "calibration")
    from saga4_world.attach import create_phase4_app

    app = create_phase4_app()
    port = free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):                                # wait until serving
        try:
            with httpx.Client() as c:
                if c.get(f"http://127.0.0.1:{port}/api/health", timeout=0.5).status_code == 200:
                    break
        except Exception:
            time.sleep(0.05)
    else:
        server.should_exit = True
        thread.join(3)
        raise RuntimeError("uvicorn did not start")
    loop = app.state.saga4["loop"]                      # set inside saga4_lifespan (attach.py)
    try:
        yield {"port": port, "app": app, "server": server, "loop": loop}
    finally:
        server.should_exit = True
        thread.join(5)
        for k in ("SAGA3_ROOT", "SAGA_LOG_DIR", "SAGA_CALIBRATION_DIR"):
            os.environ.pop(k, None)


def create_session(app) -> str:
    """Create a session through the REAL SessionManager (wrapped by Phase 4 to attach the bridge)."""
    return app.state.manager.create_session().session_id


def run_on_loop(saga_server, coro):
    fut = asyncio.run_coroutine_threadsafe(coro, saga_server["loop"])
    return fut.result(timeout=20)


def hello_msg(session, seq=0, objects=None, client_id="godot_py"):
    return {"protocol_version": "1.0", "message_type": "WORLD_HELLO", "session_id": session,
            "sequence_number": seq, "timestamp_ms": int(time.time() * 1000),
            "client_id": client_id,
            "objects": objects if objects is not None else
            [{"object_id": "cube_1", "position": [0.0, 0.04, -1.6], "grabbable": True}]}


# ---------------------------------------------------------------------------
async def simulated_godot(ws, session, outputs, stop: asyncio.Event):
    """Hello, then collect frames; ACKs GRAB_REQUEST/RELEASE like the real Godot client does."""
    await ws.send(json.dumps(hello_msg(session)))
    out_seq = 10
    while not stop.is_set():
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=0.2)
        except asyncio.TimeoutError:
            continue
        msg = json.loads(raw)
        outputs.append(msg)
        mt = msg.get("message_type")
        if mt in ("GRAB_REQUEST_ACKED",):
            continue
        if mt == "INTERACTION_EVENT" and msg.get("event_type") in ("GRAB_REQUEST", "RELEASE"):
            out_seq += 1
            await ws.send(json.dumps({"protocol_version": "1.0", "message_type": "ACK", "session_id": session,
                                      "sequence_number": out_seq, "timestamp_ms": int(time.time() * 1000),
                                      "ack_event_type": msg["event_type"], "event_id": msg["event_id"],
                                      "accepted": True, "target_object_id": msg.get("target_object_id"),
                                      "reason": None}))
        elif mt == "WORLD_STOP":
            break


def make_buffer(world, sensor="cam_a"):
    """Real sessions have no registered sensors: create the sync buffer lazily for this test."""
    from collections import deque
    buf = world.session.fusion.engine.sync.buffers.get(sensor)
    if buf is None:
        buf = world.session.fusion.engine.sync.buffers[sensor] = deque(maxlen=16)
    return buf


async def _drive(port, session, outputs, stop, world, clock):
    async with websockets.connect(f"ws://127.0.0.1:{port}/ws/world?session={session}", max_size=1 << 16) as ws:
        collector = asyncio.create_task(simulated_godot(ws, session, outputs, stop))
        from conftest import fusion_result, pinch_landmarks
        from host.app.spatial.synchronizer import ObsRef     # REAL Phase 2 buffer entry (read-only import)
        night = clock.now_ms()
        seq = 1

        def inject(pinch=None):
            nonlocal seq
            night = clock.now_ms()                            # REAL clock: a fresh sample is never STALE
            if pinch is not None:
                make_buffer(world).append(ObsRef(
                    sensor_id="cam_a", sequence_number=seq, frame_id=seq, captured_at_ms=night,
                    received_at_ms=night + 5, effective_ms=float(night), image_width=640, image_height=480,
                    status="tracked", hand="Right", landmarks=pinch_landmarks(pinch)))
            world.on_fusion_result(fusion_result(
                session_id=world.session_id,                       # REAL session id: the bridge validates it
                seq=seq, world=(0.0, 0.05, 0.05),
                sources=[("cam_a", seq)], ts=night))
            world.tick()
            seq += 1

        await asyncio.sleep(0.4)                          # let the socket settle after handshake
        # One CONTINUOUS stream (no dead gaps: the app's 20 Hz ticker would tick on a stale sample
        # and safe-stop the hover): open hand first to ARM the hover, then pinch to request the grab.
        for _ in range(8):
            inject(pinch=0.8)                             # hover: open hand in reach -> ARMED
            await asyncio.sleep(0.04)
        for _ in range(10):                               # pinched; >=3 samples across >120 ms confirms
            inject(pinch=0.15)                            # -> GRAB_REQUEST -> our client ACKs it
            await asyncio.sleep(0.04)
        await asyncio.sleep(0.8)
        stop.set()
        await asyncio.wait_for(collector, timeout=5)


def test_end_to_end_grab_release(saga_server):
    port = saga_server["port"]
    session = create_session(saga_server["app"])
    world = saga_server["app"].state.saga4["worlds"][session]
    clock = saga_server["app"].state.clock
    # This test exercises the WORLD LINK, not the CV pipeline: no real sensor/calibration exists in a
    # fresh session, so the (correctly) inhibiting CALIBRATION_REQUIRED path is bypassed here. The
    # calibration-driven safe-stop is covered in tests/test_bridge.py.
    world._calibrated_sensor_count = lambda: 2                 # type: ignore[method-assign]
    world._calibration_flagged = False
    # Also stop the REAL fusion engine ticker: our synthetic ObsRef entries would otherwise be consumed
    # by the real engine, which emits SINGLE_VIEW_FALLBACK results that fight the synthetic ones.
    saga_server["app"].state.manager.fusion_tick = lambda: None   # type: ignore[method-assign]
    stop = asyncio.Event()
    outputs: list = []

    run_on_loop(saga_server, _drive(port, session, outputs, stop, world, clock))

    types_ = [f.get("message_type") for f in outputs]
    assert "WORLD_READY" in types_                       # handshake reached the client
    interaction = [f for f in outputs if f.get("message_type") == "INTERACTION_EVENT"]
    event_types = [f.get("event_type") for f in interaction]
    assert event_types.count("GRAB_REQUEST") == 1        # bridged to the wire exactly once
    assert event_types.count("GRAB_CONFIRMED") == 1      # the host processed our ACK
    assert event_types.count("HOVER_ENTER") >= 1
    assert all(f.get("session_id") == session for f in outputs)
    statuses = [f for f in outputs if f.get("message_type") == "HOST_STATUS"]
    assert statuses                                      # status reaches the client


def test_second_world_client_rejected(saga_server):
    session = create_session(saga_server["app"])
    port = saga_server["port"]

    async def flow():
        url = f"ws://127.0.0.1:{port}/ws/world?session={session}"
        async with websockets.connect(url, max_size=1 << 16) as ws1:
            await ws1.send(json.dumps(hello_msg(session, client_id="godot_1", objects=[])))
            ready = None
            while ready is None:
                ready = json.loads(await asyncio.wait_for(ws1.recv(), timeout=5))
                if ready.get("message_type") == "WORLD_READY":
                    break
            # a SECOND Godot for the same session must be refused (fatal ERROR then close)
            async with websockets.connect(url, max_size=1 << 16) as ws2:
                await ws2.send(json.dumps(hello_msg(session, client_id="godot_2", objects=[])))
                codes = []
                hit_fatal = False
                try:
                    for _ in range(5):
                        raw = await asyncio.wait_for(ws2.recv(), timeout=5)
                        msg = json.loads(raw)
                        if msg.get("message_type") == "ERROR":
                            codes.append(msg)
                        if msg.get("message_type") == "ERROR" and msg.get("fatal"):
                            hit_fatal = True
                            continue                      # the server closes right after -> next recv raises
                except websockets.exceptions.ConnectionClosed:
                    pass
            assert hit_fatal
            assert any(c.get("error_code") == "WORLD_CLIENT_EXISTS" for c in codes)

    run_on_loop(saga_server, flow())


def test_stale_sequence_reported_not_fatal(saga_server):
    session = create_session(saga_server["app"])
    port = saga_server["port"]

    async def flow():
        url = f"ws://127.0.0.1:{port}/ws/world?session={session}"
        async with websockets.connect(url, max_size=1 << 16) as ws:
            await ws.send(json.dumps(hello_msg(session, seq=0, objects=[])))
            await ws.recv()                              # WORLD_READY
            for seq in (1, 1):                           # the repeat must produce a non-fatal ERROR
                await ws.send(json.dumps({"protocol_version": "1.0", "message_type": "OBJECT_STATE",
                                          "session_id": session, "sequence_number": seq,
                                          "timestamp_ms": int(time.time() * 1000),
                                          "objects": [{"object_id": "cube_1", "position": [0.0, 0.04, -1.6],
                                                       "grabbable": True}]}))
            err = None
            for _ in range(6):
                try:
                    msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=1.5))
                except asyncio.TimeoutError:
                    break
                if msg.get("message_type") == "ERROR" and msg.get("error_code") == "STALE_SEQUENCE":
                    err = msg
                    break
            assert err is not None
            assert err["fatal"] is False

    run_on_loop(saga_server, flow())


def test_unknown_session_refused(saga_server):
    port = saga_server["port"]

    async def flow():
        url = f"ws://127.0.0.1:{port}/ws/world?session=sess_nope123"
        async with websockets.connect(url) as ws:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            assert msg.get("message_type") == "ERROR" and msg.get("fatal") is True
            assert msg.get("error_code") == "UNKNOWN_SESSION"
            with pytest.raises((websockets.exceptions.ConnectionClosed, asyncio.TimeoutError)):
                await asyncio.wait_for(ws.recv(), timeout=5)

    run_on_loop(saga_server, flow())
