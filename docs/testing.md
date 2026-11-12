# Testing: what is verified and how to re-run it

All commands run from THIS repository (consolidated; no external checkout involved):

```bat
cd "D:\collega active\phases\saga-3d-phase-4"
.venv\Scripts\python -m pytest            -q   :: adapter tests + host tests (411 total)
.venv\Scripts\python -m pytest tests      -q   :: adapter tests only (54 total)
.venv\Scripts\python -m pytest host\tests -q   :: host tests only (357 total)
```

Adapter status: **54 passed** (50 unit + 4 e2e), 0 failed, ~10 s wall clock.
Consolidated host suite: **357 passed**, 0 failed (pytest.ini runs both suites by default).

## Suite layout

| file | level | what it pins down |
|---|---|---|
| `tests/test_transform.py` | unit | the one transform: round-trip, orthonormality validation, volume checks, fingerprint stability |
| `tests/test_protocol.py` | unit | strict envelope both directions, per-type whitelists, extra fields rejected, stale sequence, binary frames, non-UTF-8, size cap |
| `tests/test_status.py` | unit | derived host states (no blind trust) STOPPED/SENSOR_WAITING/CALIBRATION/DEGRADED/ERROR transitions |
| `tests/test_bridge.py` | unit | HandSample validation, pinch evidence across views, gesture events to queues, acks, safe stops, calibrations, one-client, orphan cleanup |
| `tests/test_server_e2e.py` | e2e | a REAL uvicorn server with a real websockets client |

## e2e tests (integration with the real wire)

1. `test_end_to_end_grab_release` — full handshake + HOVER_ENTER (bridge level of the real
   gesture agent) + pinch confirm (`GRAB_REQUEST` on the wire) + Godot-side simulated ACK +
   `GRAB_CONFIRMED` (acknowledge loop at wire level). Patched knobs (documented inline):
   * `world._calibrated_sensor_count = lambda: 2` — no physical sensor/calibration exists
     in a test session; the host CORRECTLY enters CALIBRATION_REQUIRED and inhibits
     interaction otherwise (that path is covered in tests/test_status + test_bridge).
   * `manager.fusion_tick = lambda: None` — the real fusion ticker would consume the
     synthetic ObsRef entries and emit single-view fallback results that fight the test's
     own injections.
   * Synthetic poses are injected with the REAL SystemClock (`clock.now_ms()`): a canned
     timestamp looks stale by the time the agent sees it (250 ms) — that staleness
     detection is part of what makes the agent safe, so the test must honor it.
2. `test_second_world_client_rejected` — a second Godot gets `ERROR(WORLD_CLIENT_EXISTS,
   fatal)` followed by the server close.
3. `test_stale_sequence_reported_not_fatal` — repeated `sequence_number` yields a
   NON-fatal `STALE_SEQUENCE` ERROR and the link stays usable.
4. `test_unknown_session_refused` — connecting to a nonexistent session yields a fatal
   `ERROR(UNKNOWN_SESSION)` then the close.

## What e2e does NOT cover (be honest in demos)

* No physical WebSpace camera; no real calibration flow (see the report's "not yet
  hardware-validated" section); no Godot transport test — Godot-side correctness was
  validated by Godot 4.3 headless parse checks plus the simulated protocol mirror.
* Optimistically live things like reconnect-under-load and 30 Hz MOVE_TARGET saturation
  are unit-covered (protocol/bridge) but not driven experimentally end to end.

## Godot checks (manual, runnable even without Python)

```bat
"C:\...\Godot_v4.3-stable_win64.exe" --headless --path godot --quit
for each script:  --headless --path godot --check-only --script scripts/<name>.gd
```

Both are currently parse/dependency-clean on Godot 4.3-stable.

## Consolidated host regression (now part of THIS repository)

```bat
.venv\Scripts\python -m pytest host\tests -q
(cd sensor-client && node --test tests/*.test.mjs)    :: browser-logic tests (16)
```

The old phase repositories are no longer referenced at runtime; there is no upstream
working tree to keep byte-identical anymore. Historical references remain untouched at
`..\saga-3d phase 1|2|3`.
