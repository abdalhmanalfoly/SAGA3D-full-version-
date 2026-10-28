"""Phase 4 launcher glue: builds the COMPLETE Phase 1-3 host app + the world adapter in ONE process.

Runtime wiring only — the Phase 1-3 repository stays READ-ONLY:
  * ``host.app.main:create_app`` supplies the sensor HTTP/WS routes, registry, session manager and fusion.
  * A ``/ws/world`` WebSocket route for Godot and a ~20 Hz tick task are ADDED here.
  * ``SessionManager.create_session`` / ``stop_session`` are wrapped (monkey-patched on the live instance,
    never a source edit) so every live session also gets a ``SessionWorld`` bridge and, when available, the
    Phase 3 ``SessionCoordination`` adapter (the Phase 3 handoff §5.2 explicitly defers that wiring here).
  * Runtime writes stay OUT of the Phase 1-3 tree: SAGA_LOG_DIR / SAGA_CALIBRATION_DIR default into the
    Phase 4 directory unless explicitly configured otherwise (see .env.example).
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import WebSocket

from .bridge import SessionWorld
from .config import WorldConfig, load_world_config, phase3_root
from .protocol import WORLD_PROTOCOL_VERSION
from .server import WorldSocketSession

REPO_ROOT = Path(__file__).resolve().parents[2]


def _import_p3_host():
    """Import the READ-ONLY Phase 1-3 host modules after adding its repository root to sys.path."""
    root = phase3_root()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    try:
        from host.app.main import create_app                      # noqa: PLC0415
        from host.app.config import load_settings                  # noqa: PLC0415
        return create_app, load_settings, root
    except ImportError as exc:                                     # most likely a missing pip dependency
        raise RuntimeError(
            f"cannot import the Phase 1-3 host from {root}: {exc}. "
            "Install the pinned dependencies into the Phase 4 venv first "
            "(.venv/Scripts/python -m pip install -r requirements.txt)") from exc


class _FallbackCoordination:
    """Used when the real coordination adapter cannot run; host trust then relies on fusion validity alone."""

    def tick(self) -> None:
        return None

    def coordinator(self):                                         # duck-type accessor matching SessionCoordination
        return None


def create_phase4_app(world_cfg: WorldConfig | None = None) -> Any:
    create_app, load_settings, root = _import_p3_host()
    try:
        from host.app.coordination.config import load_coordination_config
        from host.app.coordination.host_adapter import SessionCoordination
    except ImportError as exc:
        raise RuntimeError(f"cannot import the Phase 3 coordination adapter from {root}: {exc}") from exc

    # ---------------------------------------------------------------- configuration
    cfg = world_cfg or load_world_config()
    env = os.environ
    env.setdefault("SAGA_LOG_DIR", str(REPO_ROOT / "logs"))
    env.setdefault("SAGA_CALIBRATION_DIR", str(REPO_ROOT / "calibration"))
    try:
        settings = load_settings()
    except Exception as exc:                                       # malformed Phase 1-3 yaml/config
        raise RuntimeError(f"Phase 1-3 host configuration failed: {exc}") from exc

    app = create_app(settings)
    manager, clock, events = app.state.manager, app.state.clock, app.state.events

    worlds: dict[str, SessionWorld] = {}
    coordinations: dict[str, SessionCoordination | _FallbackCoordination] = {}
    app.state.saga4 = {"worlds": worlds, "coordinations": coordinations, "cfg": cfg}

    def _coordinator_source(sc):
        """Trust is UNTRUSTED only when the Phase 3 coordinator is explicitly in DEGRADED."""
        def source():
            c = getattr(sc, "coordinator", None)
            st = getattr(c, "state", None)
            if st is None:
                return {"degraded": False, "reason_code": None}     # no coordinator wired: fusion decides
            if st.value == "DEGRADED":
                reason = getattr(c, "degraded", None) or {}
                return {"degraded": True, "reason_code": str(reason.get("reason") or "DEGRADED")}
            return {"degraded": False, "reason_code": None}
        return source

    original_create = manager.create_session

    def wrapped_create():
        session = original_create()
        sid = session.session_id
        sc: SessionCoordination | _FallbackCoordination = _FallbackCoordination()
        if session.fusion is not None:
            try:
                ccfg = load_coordination_config()                 # Phase 3 defaults (config/coordination.yaml)
                sc = SessionCoordination(session, ccfg, clock, events)
            except Exception as exc:                              # coordination problems never block sensor ingest
                events.log("world_coordination_failed", session_id=sid, severity="warning", reason=type(exc).__name__)
        coordinations[sid] = sc
        try:
            world = SessionWorld(session, clock, events, cfg,
                                 coordinator_source=None if isinstance(sc, _FallbackCoordination) else _coordinator_source(sc))
            worlds[sid] = world
            if session.fusion is not None:
                session.fusion.engine.subscribe(world.on_fusion_result)
            events.log("world_session_attached", session_id=sid, world_protocol=cfg.world_protocol_version,
                       transform=cfg.transform.fingerprint())
        except Exception as exc:
            events.log("world_attach_failed", session_id=sid, severity="error", reason=type(exc).__name__, detail=str(exc)[:200])
        return session

    manager.create_session = wrapped_create

    original_stop = manager.stop_session

    async def wrapped_stop(session_id: str, reason: str = "operator_request"):
        world = worlds.get(session_id)
        if world is not None:
            try:
                world.on_session_stop(reason)
            except Exception as exc:
                events.log("world_stop_error", session_id=session_id, severity="error", reason=type(exc).__name__)
        sc = coordinations.get(session_id)
        if sc is not None and not isinstance(sc, _FallbackCoordination):
            with contextlib.suppress(Exception):                  # best effort; session teardown continues regardless
                sc.coordinator.stop("SESSION_STOPPED")
        result = await original_stop(session_id, reason)
        with contextlib.suppress(Exception):
            worlds.pop(session_id, None)
            coordinations.pop(session_id, None)
        return result

    manager.stop_session = wrapped_stop

    # ---------------------------------------------------------------- Godot WebSocket
    @app.websocket(cfg.ws_path)
    async def world_socket(ws: WebSocket):
        await ws.accept()
        sid = ws.query_params.get("session") or ""
        session = manager.get(sid) if sid else None
        if session is None:
            await _reject_socket(ws, sid, "UNKNOWN_SESSION")
            return
        if session.state != "active":
            await _reject_socket(ws, sid, "SESSION_NOT_ACTIVE")
            return
        world = worlds.get(sid)
        if world is None:                      # session created by a caller outside create_phase4_app (tests)
            world = SessionWorld(session, clock, events, cfg, coordinator_source=None)
            if session.fusion is not None:
                session.fusion.engine.subscribe(world.on_fusion_result)  # late attach (test-only path)
            worlds[sid] = world
        await WorldSocketSession(ws, world, cfg, sid).run()

    # ---------------------------------------------------------------- ~20 Hz tick task
    async def ticker() -> None:
        while True:
            await asyncio.sleep(0.05)
            for sid in [s for s, sess in manager.sessions.items() if sess.state == "active"]:
                sc = coordinations.get(sid)
                if sc is not None:
                    try:
                        sc.tick()
                    except Exception as exc:
                        events.log("world_coordination_tick_error", session_id=sid, severity="error", reason=type(exc).__name__)
                world = worlds.get(sid)
                if world is not None:
                    try:
                        world.tick()
                    except Exception as exc:
                        events.log("world_tick_error", session_id=sid, severity="error", reason=type(exc).__name__)

    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def saga4_lifespan(a):
        task = asyncio.create_task(ticker())
        app.state.saga4["loop"] = asyncio.get_running_loop()      # for tests/tools driving the app loop
        events.log("world_adapter_started", world_protocol=cfg.world_protocol_version)
        try:
            async with original_lifespan(a):
                yield
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
            for sid, world in list(worlds.items()):
                with contextlib.suppress(Exception):
                    if not world.stopped:
                        world.on_session_stop("host_shutdown")
            events.log("world_adapter_stopped")

    app.router.lifespan_context = saga4_lifespan
    return app


async def _reject_socket(ws, sid: str, code: str) -> None:
    """Tell Godot why it was refused, then close (fatal world error)."""
    try:
        await ws.send_text(json.dumps({"protocol_version": WORLD_PROTOCOL_VERSION, "message_type": "ERROR",
                                       "session_id": sid or "", "sequence_number": 0, "timestamp_ms": 0,
                                       "error_code": code, "detail": "world socket rejected", "fatal": True}))
        await ws.close(code=1008, reason=code)
    except Exception:
        pass
