"""World socket server: the Godot-FACING WebSocket endpoint logic (client role belongs to Godot).

Design rules (docs/world_protocol.md):
  * One process, one port: the world socket lives on the SAME FastAPI app as the sensor host (attach.py
    mounts it), so Godot and the browser sensor pages talk to one server.
  * Per connection: WORLD_HELLO handshake within hello_timeout_s, then registration with the session bridge.
  * Reader and writer run concurrently but NEVER share a mutable queue without the bridge lock discipline:
    the bridge mutates bounded dequeues synchronously (no awaits), the writer drains + sends. A writer that
    blocks on send stalls only itself (per-connection), never the fusion/gesture pipeline.
  * Protocol violations produce a machine-readable ERROR and the message is ignored; fatal codes close the
    socket (references: the sensor host error vocabulary, plus the world-specific codes below).
"""
from __future__ import annotations

import asyncio
import json
import time

from .config import WorldConfig
from .protocol import (ParsedMessage, WorldProtocolError, parse_client_message)
from .bridge import SessionWorld, WorldConnection

# world-specific error codes (all non-fatal unless noted)
FATAL_CODES = frozenset({"SESSION_MISMATCH", "SESSION_NOT_ACTIVE", "WORLD_CLIENT_EXISTS", "HELLO_TIMEOUT", "UNSUPPORTED_PROTOCOL_VERSION"})


class WorldSocketSession:
    """Serve ONE Godot websocket for ONE session."""

    def __init__(self, ws, bridge: SessionWorld, cfg: WorldConfig, session_id: str):
        self.ws = ws
        self.bridge = bridge
        self.cfg = cfg
        self.session_id = session_id
        self.conn: WorldConnection | None = None
        self.closed = False

    # ------------------------------------------------------------------ entry point
    async def run(self) -> None:
        accepted = False
        try:
            hello = await self._handshake()
            conn = self.bridge.register_client(hello, time.monotonic())
            if conn is None:
                await self._send_raw_error("WORLD_CLIENT_EXISTS", f"session {self.session_id} already has a Godot client", fatal=True)
                return
            self.conn = conn
            accepted = True
            self._log("world_socket_accepted", session_id=self.session_id,
                      client_id=conn.client_id, objects=len(self.bridge.objects))
            reader = asyncio.create_task(self._reader(conn))
            writer = asyncio.create_task(self._writer(conn))
            done, pending = await asyncio.wait({reader, writer}, return_when=asyncio.FIRST_COMPLETED)
            for t in pending:
                t.cancel()
            for t in done:
                exc = t.exception()
                if exc and not isinstance(exc, asyncio.CancelledError):
                    self._log("world_socket_error", session_id=self.session_id,
                              severity="error", reason=type(exc).__name__, detail=str(exc)[:200])
        except WorldProtocolError as exc:
            await self._send_raw_error(exc.code, exc.detail, fatal=exc.code in FATAL_CODES)
        finally:
            if accepted:
                self.bridge.on_client_disconnect("socket_closed")
            self._log("world_socket_closed", session_id=self.session_id, accepted=accepted)

    # ------------------------------------------------------------------ handshake
    async def _handshake(self) -> ParsedMessage:
        async def receive_hello() -> ParsedMessage:
            raw = await self.ws.receive_text()
            return parse_client_message(raw, self.session_id, None)

        try:
            return await asyncio.wait_for(receive_hello(), timeout=self.cfg.hello_timeout_s)
        except asyncio.TimeoutError:
            raise WorldProtocolError("HELLO_TIMEOUT",
                                     f"no WORLD_HELLO within {self.cfg.hello_timeout_s:.0f}s (fatal)") from None

    async def _reader(self, conn: WorldConnection) -> None:
        while True:
            raw = await self.ws.receive_text()
            try:
                parsed = parse_client_message(raw, self.session_id, conn.last_client_seq)
            except WorldProtocolError as exc:
                conn.enqueue_error(exc.code, exc.detail, fatal=exc.code in FATAL_CODES)
                conn.wake.set()
                if exc.code in FATAL_CODES:
                    raise
                continue
            conn.note_client_seq(parsed.sequence_number)
            try:
                self.bridge.on_client_message(parsed)
            except WorldProtocolError as exc:
                conn.enqueue_error(exc.code, exc.detail)
            except Exception as exc:                       # client input must never kill the reader
                self._log("world_client_message_error", session_id=self.session_id, severity="error", reason=type(exc).__name__)
                conn.enqueue_error("INTERNAL", f"message not processed: {type(exc).__name__}")
            conn.wake.set()

    async def _writer(self, conn: WorldConnection) -> None:
        idle = 0
        while not self.closed:
            frames = conn.drain()
            if not frames:
                conn.wake.clear()
                frames = conn.drain()                      # enqueue raced with the clear: catch it, or go to sleep
                if not frames:
                    idle += 1
                    if idle > 250:                         # ~1 s without traffic -> exercise heartbeat watchdog
                        await asyncio.sleep(0.004)
                        continue
                    await conn.wake.wait()
                    continue
            idle = 0
            for f in frames:
                await self.ws.send_text(json.dumps(f))

    # ------------------------------------------------------------------ helpers
    async def _send_raw_error(self, code: str, detail: str, *, fatal: bool = False) -> None:
        try:
            from .protocol import build_error
            msg = build_error(self.session_id, 0, float(self.bridge.clock.now_ms()), code, detail, fatal=fatal)
            await self.ws.send_text(json.dumps(msg))
            if fatal:
                await self.ws.close(code=1008, reason=code)
        except Exception:
            pass

    def _log(self, name: str, **kw) -> None:
        if self.bridge.events is not None:
            try:
                self.bridge.events.log(name, **kw)
            except Exception:
                pass
