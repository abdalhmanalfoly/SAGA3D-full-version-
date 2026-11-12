# SAGA 3D — Phase 4 Main Workspace Migration Report

**Date:** 2026-11-12
**Branch:** `consolidation/main-workspace` (created from `main` @ `d5a68be`)
**Scope:** consolidation only; no feature rewrites, no silent replacements.

## A. Migration summary

The Phase 4 repository (`D:\collega active\phases\saga-3d-phase-4\`) now contains the complete
implementation of all four SAGA 3D phases and no longer references the old phase repositories
at runtime.

**Source commits used (recorded exactly):**

| Component | Source repository | Source commit | Destination |
|---|---|---|---|
| Python host (Phases 1-3 app + tests) | `saga-3d phase 3` | `df7335b` (first commit v-1) | `host/` |
| Browser sensor client | `saga-3d phase 3` | `df7335b` | `sensor-client/` |
| MediaPipe vendor assets | `saga-3d phase 1` | `b7b1826` (run) | `sensor-client/vendor/` |
| Host configs | `saga-3d phase 3` | `df7335b` | `config/` (merged with existing `world.yaml`) |
| Calibration seed data | `saga-3d phase 3` | `df7335b` | `calibration/` |
| Calibration/coordination/fusion scripts | `saga-3d phase 3` | `df7335b` | `scripts/` (merged with existing `run_host.py`) |
| Windows venv fix for `run_host.sh`/`run_tests.sh` | `saga-3d phase 2` | **uncommitted working-tree edit** in `scripts/run_host.sh` @ `27f6662` | adopted into the copied scripts (documented merge decision, see C) |
| Host documentation | `saga-3d phase 3` | `df7335b` | `docs/host/` (+ `docs/examples/` at repo root, where the host tests expect them) |

Copies were verified byte-identical to their sources (`diff -rq` of `host/`, `sensor-client/src`,
`vendor/`, `calibration/` — all clean). Nothing was copied from the Phase 4 working tree's own
files; no pre-existing Phase 4 file was overwritten except the explicit edits listed in section E.

**Merge decisions (differences between phase repos investigated, not silently resolved):**

1. `scripts/run_host.sh`: the Phase 2 repo has an **uncommitted** improvement adding
   `.venv/Scripts/python.exe` detection (Windows venv layout). The Phase 3 (source-of-truth)
   version only knows `.venv/bin/python`. Decision: adopted the Phase 2 fix into the
   consolidated copy (and into `run_tests.sh`), because this is a Windows machine and it makes
   the script functional here. This is the only file taken from Phase 2 besides vendor assets.
   The Phase 2 repository itself was not modified.
2. `host/app` diff between Phase 2 and Phase 3 repos: only `coordination/` and `gesture/` are
   new in Phase 3; every Phase 1/2 module is byte-identical. No competing versions existed, so
   the Phase 3 tree was copied as-is (one authoritative implementation).
3. Host docs were placed under `docs/host/` because the existing Phase 4 docs own the
   filenames `architecture.md`, `setup.md`, `testing.md` at `docs/` root. `docs/examples/`
   stays at the repo root because `host/tests` resolve it as `parents[2]/docs/examples`.
4. `.docx`/audit documents from the old repos were NOT copied (binary artifacts, not code);
   they remain in the old repositories.
5. Dev TLS certificates (`certs/dev.crt|key`) were NOT copied. `certs/` is git-ignored in the
   host convention and regenerable with `scripts/make_dev_cert.sh <LAN-IP>`.

## B. Final architecture

```text
saga-3d-phase-4/
├── host/                    Phases 1-3 (consolidated, unchanged file layout)
│   ├── app/
│   │   ├── schemas/ services/       Phase 1: protocol, clock, logging, observation recorder
│   │   ├── sensor_registry.py       Phase 1: sensor identification/registration/lifecycle
│   │   ├── websocket_handler.py     Phase 1: /ws/sensor ingest -> fusion
│   │   ├── session_manager.py       Phase 1: sessions
│   │   ├── spatial/                 Phase 2: calibration_tool, calibration_store,
│   │   │                            calibration_schema, geometry (DLT+refine), fusion,
│   │   │                            service (FusionService), synchronizer, filters, results, synthetic
│   │   ├── coordination/            Phase 3: coordinator, sensor_agent, scoring, set_selection,
│   │   │                            host_adapter (SessionCoordination), messages, audit, simulation
│   │   ├── gesture/                 Phase 3: agent (GestureAgent, HandSample, InteractionObject),
│   │   │                            events (INTERACTION_EVENT 1.0), pinch, config
│   │   ├── main.py config.py        Phase 1: FastAPI app factory + typed settings
│   └── tests/                       357 host tests (now run by this repo's pytest.ini)
├── sensor-client/           Phase 1: browser client (camera.js, landmark_detector.js [MediaPipe],
│                            websocket_client.js, protocol.js, sensor_state.js, app.js) + node tests
│   └── vendor/              MediaPipe tasks-vision 1.1.1 WASM + hand_landmarker.task (git-ignored,
│                            fetched by scripts/fetch_assets.sh; consolidated from Phase 1)
├── adapter/saga4_world/     Phase 4: attach.py (combined app), bridge.py (SessionWorld),
│                            server.py, protocol.py, transform.py, status.py, config.py, p3.py
├── godot/                   Phase 4: Godot 4.3 project (world_client.gd validation gate, main.gd,
│                            hand_marker.gd, grabbable_cube.gd, status_ui.gd, scenes/main.tscn)
├── scripts/                 run_host.py (Windows launcher), run_host.sh, run_tests.sh, calibrate.py,
│                            demo_coordination.py, e2e_fusion_live.py, fetch_assets.sh,
│                            make_dev_cert.sh, smoke_consolidated.py (new, added by migration)
├── config/                  app.yaml thresholds.yaml camera.yaml fusion.yaml gesture.yaml
│                            coordination.yaml (host) + world.yaml (Phase 4)
├── calibration/             README.md + example_synthetic/ (committed); real captures git-ignored
├── tests/                   54 Phase 4 adapter tests (50 unit + 4 real-server e2e)
├── docs/                    Phase 4 docs + docs/host/ (phase 1-3 docs) + docs/examples/
├── pytest.ini               pythonpath = . ; testpaths = host/tests tests
├── requirements.txt         pinned (matches the host requirements.lock.txt)
├── requirements-dev.txt requirements.lock.txt   (copied from host for reference/CI parity)
├── .env.example             no SAGA3_ROOT anymore
└── README.md                consolidated architecture + setup + running instructions
```

Ownership map (logical responsibilities, one Python package tree):

- **Phase 1 — Sensor acquisition:** `sensor-client/` + `host/app/{websocket_handler,sensor_registry,session_manager,schemas,services}`.
- **Phase 2 — Calibration & 3D fusion:** `host/app/spatial/` + `scripts/calibrate.py` + `config/fusion.yaml` + `calibration/`.
- **Phase 3 — Coordination & gesture:** `host/app/coordination/` + `host/app/gesture/` + `config/{coordination,gesture}.yaml` + `scripts/demo_coordination.py`.
- **Phase 4 — Godot bridge:** `adapter/` + `godot/` + `config/world.yaml`.

## C. Dependency inventory

**Copied into this repository (previously external):**

| Component | Files | Destination | Notes |
|---|---|---|---|
| Python host package | `host/` (app + tests, `__pycache__` excluded) | `host/` | byte-identical to source |
| Sensor client | `sensor-client/{index,operator}.html, src/, tests/, package.json, styles.css` | `sensor-client/` | byte-identical; no npm dependencies |
| MediaPipe assets | `vendor/mediapipe/**` (WASM + vision_bundle.mjs), `vendor/models/hand_landmarker.task(+.sha256)` | `sensor-client/vendor/` | from Phase 1; diff-verified identical; stays git-ignored per host convention |
| Host configs | `config/{app,thresholds,camera,fusion,gesture,coordination}.yaml` | `config/` | merged alongside existing `world.yaml` |
| Calibration seed | `calibration/README.md`, `calibration/example_synthetic/{phone_left,phone_right}.json` | `calibration/` | now tracked (gitignore merged accordingly) |
| Scripts | `calibrate.py, demo_coordination.py, e2e_fusion_live.py, fetch_assets.sh, make_dev_cert.sh, run_host.sh, run_tests.sh` | `scripts/` | run_host.sh/run_tests.sh include the Phase 2 Windows-venv fix |
| pytest config | `pytest.ini` | root | `testpaths` extended to also run `tests/` |
| Dependency manifests | `requirements-dev.txt`, `requirements.lock.txt` | root | `requirements.txt` already matched the lock |
| Host docs | `docs/host/*.md` + `docs/examples/**` | `docs/` | `docs/examples/` kept at root per host-test convention |

**Already present (Phase 4, untouched):** `adapter/saga4_world/*`, `godot/*`, `config/world.yaml`,
`tests/*`, `scripts/run_host.py`, `docs/{coordinates,demo_script,world_protocol,architecture,setup,testing}.md`,
`requirements.txt`, `PHASE4_IMPLEMENTATION_REPORT.md`.

**Still external (by design):**

- Godot 4.3 editor/runtime executable (documented in `docs/setup.md`).
- Python packages (installed into `.venv` from the pinned `requirements.txt`; `requirements.lock.txt` is the host-side source of truth).
- `sensor-client/vendor/` binaries are re-fetchable with `bash scripts/fetch_assets.sh`
  (network + npm needed only if the folder is missing; the consolidated copy is present and verified).
- Browser (Chrome/Edge) to run the sensor client page.

**Explicitly NOT copied:** `.env` files, `certs/`, `logs/` contents, `__pycache__`, `.pytest_cache`,
`node_modules`, `.docx` documents. The old repositories remain untouched as backup/reference copies.

## D. External dependencies

| Dependency | Version | Needed for | Setup |
|---|---|---|---|
| Python | 3.12 (developed with) | everything Python | `python -m venv .venv; .venv\Scripts\python -m pip install -r requirements.txt` |
| Godot | 4.3 stable | world demo | run `godot --path godot -- --session=<id>` (see docs/setup.md) |
| Node.js | >=18 (v20.16.0 used here) | browser-logic unit tests only | `cd sensor-client && node --test tests/*.test.mjs` |
| npm + network | once | re-fetching `sensor-client/vendor/` if missing | `bash scripts/fetch_assets.sh` (pinned `@mediapipe/tasks-vision 1.1.1`, hash-checked model) |
| mkcert or openssl | optional | HTTPS for phone cameras | `bash scripts/make_dev_cert.sh <LAN-IP>` |
| Environment vars | optional | `SAGA_HOST`, `SAGA_PORT`, `SAGA_LOG_DIR`, `SAGA_CALIBRATION_DIR`, `SAGA_ALLOWED_ORIGINS`, `SAGA_TLS_CERT/KEY`, `SAGA_CONFIG_DIR`, `SAGA_RIG_ID`, `SAGA_ALLOW_SYNTHETIC_CALIBRATION` | see `.env.example`; **`SAGA3_ROOT` no longer exists** |

## E. Code changes

All changes are inside the Phase 4 repository. No old repository was modified (verified by
`git status` before and after; Phase 1/2/3 working trees unchanged — Phase 2's pre-existing
uncommitted `run_host.sh` edit is untouched).

1. **`adapter/saga4_world/config.py`** — `phase3_root()` (SAGA3_ROOT resolution + external path
   validation) replaced by `host_root()` returning `REPO_ROOT` (this repository). The external
   `PHASE3_ROOT_DEFAULT` constant and the `SAGA3_ROOT` environment mechanism were removed.
2. **`adapter/saga4_world/p3.py`** — imports `host_root` instead of `phase3_root`; docstrings
   updated ("consolidated host tree inside this repository"). The `P3` facade symbol list is
   unchanged (GestureAgent, HandSample, InteractionObject, GestureOutput, InteractionEvent,
   EventDeduper, EventType, GestureState, pinch_ratio, combine_view_ratios, load_gesture_config,
   GestureCfg, GestureConfigError, AuditLog).
3. **`adapter/saga4_world/attach.py`** — `_import_p3_host()` uses `host_root()` and inserts
   `REPO_ROOT` into `sys.path` (idempotent, needed when uvicorn resolves the module by path from
   another cwd); docstrings and error messages updated. The runtime wiring itself (wrapping
   `create_session`/`stop_session`, `/ws/world` route, 20 Hz ticker, lifespan task) is **unchanged** —
   deliberately preserved per the "first make it work" rule; a future explicit-hook refactor is
   listed as optional work (G.4).
4. **`scripts/run_host.py`** — adds both `REPO_ROOT` and `REPO_ROOT/adapter` to `sys.path`
   (previously only `adapter/`); docstring updated; `--port` binds the combined server
   (verified during the e2e run).
5. **`tests/conftest.py`** — inserts `REPO_ROOT` too so `host.*` imports resolve from the
   consolidated tree.
6. **`tests/test_server_e2e.py`** — removed the dead `os.environ["SAGA3_ROOT"] = ...saga-3d phase 3` line
   and its cleanup entry (the variable was already ignored after the refactor; removing it
   makes the independence explicit).
7. **`host/tests/test_protocol_validation.py`** — ONE line adapted: the error-code doc check now
   reads `docs/host/protocol.md` instead of `docs/protocol.md` (the Phase 4 layer owns the
   `docs/` root filenames). Test intent fully preserved.
8. **`pytest.ini`** (new file) — `pythonpath = .`, `testpaths = host/tests tests`.
9. **`.gitignore` / `.env.example`** — merged with the host conventions (vendor/, certs/,
   captures/, calibration keep-rules); `SAGA3_ROOT` removed from the template.
10. **Documentation** — `README.md` rewritten for the consolidated workspace; `docs/setup.md`
    (added step 1b for vendor assets, removed SAGA3_ROOT), `docs/testing.md` (new commands,
    removed the old upstream-cleanliness check), `docs/architecture.md` (local host tree),
    `config/world.yaml` header comment.
11. **`scripts/run_host.sh`, `scripts/run_tests.sh`** — copied from Phase 3 with the Phase 2
    Windows-venv detection fix adopted (see A).
12. **`scripts/smoke_consolidated.py`** (new) — end-to-end smoke test for the consolidated
    workspace (real uvicorn + websockets + httpx; checks REST, client-config, static client,
    local vendor assets, both WS routes).

## F. Test results

All commands executed in `D:\collega active\phases\saga-3d-phase-4\` unless noted. All tests
are SYNTHETIC (no physical cameras involved anywhere).

| # | Command | Passed | Failed | Skipped | Nature |
|---|---|---|---|---|---|
| 1 | `.venv\Scripts\python.exe -m pytest` (runs `host/tests` + `tests` via pytest.ini) | **411** | 0 | 0 | synthetic |
| 2 | same as (1) **with all three old repositories hidden** (independence test) | **411** | 0 | 0 | synthetic |
| 3 | `cd sensor-client && node --test tests/*.test.mjs` | **16** | 0 | 0 | synthetic (browser logic in Node) |
| 4 | `.venv\Scripts\python.exe scripts\smoke_consolidated.py` | 8/8 checks PASS | 0 | — | synthetic (real uvicorn server: health, sessions, client-config, sensor page, MediaPipe bundle+model served locally from `vendor/`, `/ws/world` handshake, `/ws/sensor` validation) |
| 5 | `.venv\Scripts\python.exe scripts\demo_coordination.py` | 9/9 scenarios | 0 | — | synthetic (negotiation → adaptation → fusion outcome → gesture → safe cancellation) |
| 6 | start host with `SAGA_CALIBRATION_DIR=calibration\example_synthetic SAGA_ALLOW_SYNTHETIC_CALIBRATION=1 scripts\run_host.py --port 8798` then `.venv\Scripts\python.exe scripts\e2e_fusion_live.py http://127.0.0.1:8798` | **11/11** checks PASS | 0 | — | synthetic end-to-end over the real wire: registration, calibration binding, 75/75 valid fusion frames (mean error 5.5 mm on the synthetic rig), skew, latency, TARGET_LOST/hold/recovery, SINGLE_VIEW_FALLBACK |

Initial run of (1) after the copy had 12 failures, all caused by the relocated `docs/examples/`
(moved to the host-expected root location) and one path in the error-code doc check (E.7) — fixed,
then re-run to the 411-pass state. The Phase 2 module failure count before those two layout fixes
was 0 — all 12 were path-resolution issues, not logic issues.

**NOT executed in this session:** Godot headless scene load / `--check-only` script checks
(no Godot 4.3 executable was found on this machine). The exact commands remain documented in
`docs/setup.md` §4. Real-camera validation: NOT performed (see G).

## G. Remaining work

**1. Software implementation tasks**

- None blocking. All four phases' foundations are consolidated, importable, and tested.
- Optional: `scripts/fetch_assets.sh` verification run has already effectively been done for
  this checkout (assets consolidated and served locally; re-run only needed after a fresh clone).

**2. Physical hardware and calibration tasks (NOT done — do not treat as complete)**

- Perform the REAL calibration workflow with physical cameras:
  `bash scripts/calibrate.py capture ...` → `intrinsics` → `rig` (see `calibration/README.md`
  and `docs/host/spatial.md`). No real calibration artifacts exist yet.
- Verify the rig→Godot transform against two physical reference points (`docs/coordinates.md` §5).
- Validate real-camera end-to-end latency, 30 Hz MOVE_TARGET pacing, and mid-grab
  disconnect/reconnect on hardware (unit-level verified only; see PHASE4_IMPLEMENTATION_REPORT.md).
- Run the Godot headless + interactive demo on hardware once Godot 4.3 is available.

**3. Integration and end-to-end validation tasks**

- Godot executable validation: `"C:\path\to\Godot_v4.3-stable_win64.exe" --path godot --headless --check-only`
  and a human-watched demo run (documented commands in `docs/setup.md`).
- Full hardware demo: browser sensor pages (2+ phones/cameras) → real calibration → Godot grab/release.

**4. Optional architecture improvements**

- Replace the runtime monkey-patching of `SessionManager.create_session/stop_session` and the
  lifespan swap in `adapter/saga4_world/attach.py` with explicit host-side hooks. Behavior is
  fully covered by tests, so the refactor can be validated mechanically when attempted.
  Kept as-is in this migration to minimize risk.
- Consider packaging `host/` + `adapter/` as an installable package to remove the remaining
  `sys.path` inserts (they are now repo-local and idempotent; low priority).

## H. Independence result

**YES — Phase 4 now operates and is developed independently of the old Phase 1-3 repositories.**

Evidence:

1. **No reference mechanism remains:** `SAGA3_ROOT`, the external-path validation, and
   `phase3_root()` were removed from `adapter/saga4_world/config.py`; `p3.py` and `attach.py`
   resolve the host from this repository (`host_root()` → repo root). A repo-wide grep for
   `SAGA3_ROOT` / `saga-3d phase` / `phase3_root` over all Python, YAML, GDScript and env
   files returns only historical documentation prose — no executable reference.
2. **Controlled hiding test:** the directories `saga-3d phase 1`, `saga-3d phase 2`,
   `saga-3d phase 3` were temporarily renamed to `__saga_hidden_1/2/3__` (contents untouched)
   and the full validation was executed from Phase 4:
   - `pytest` → **411 passed, 0 failed**;
   - `scripts/smoke_consolidated.py` → **ALL PASS** (real server, both WS routes, local vendor assets,
     synthetic calibration);
   All three directories were then restored exactly (verified by listing `phases/`).
3. **Full pipeline runs from this tree:** the synthetic live fusion e2e (11/11) and the
   coordination demo (9 scenarios) ran against the consolidated host inside Phase 4.
4. Old repositories are untouched: `git status` in each shows the same state as before the
   migration (Phase 1/3: untracked docs only; Phase 2: the pre-existing uncommitted
   `run_host.sh` edit, which was adopted as a *copy* into Phase 4 with attribution).

The old repositories can now be archived or removed at the owner's discretion; nothing in the
daily development flow reads them.
