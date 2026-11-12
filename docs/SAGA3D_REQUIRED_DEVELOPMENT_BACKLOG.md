# SAGA 3D — Required Development Backlog (code tasks ONLY)

**Scope:** software implementation/improvement tasks. Physical/manual work lives in `SAGA3D_HUMAN_ACTION_CHECKLIST.md`; operational procedure in `SAGA3D_REAL_WORLD_RUNBOOK.md`.
**Baseline:** all four phases' current code is consolidated and synthetic-tested (411 pytest + 16 node, this audit). **Nothing here blocks starting physical calibration** — hardware work proceeds in parallel.

Priority: **P0** blocks the first real run · **P1** needed for the first meaningful real demo · **P2** reliable repeated operation · **P3** improvement/optional.

| ID | P | Phase | Task | Why it matters | Location | Type | Verification |
|---|---|---|---|---|---|---|---|
| DEV-01 | P3 | 1 | Body/pose landmark support (pose model + pipeline extension) | Project goal mentions body motion; only `hand_landmarker` exists today | `config/camera.yaml` model section; `sensor-client/src/landmark_detector.js`; `host/app` targets (`config/fusion.yaml targets: [wrist]`) | new feature | pose landmarks flow end-to-end (synthetic first, then hardware) |
| DEV-02 | P3 | 1 | Explicit camera device picker (`enumerateDevices` UI) | Removes facing-mode guesswork on multi-camera phones | `sensor-client/src/camera.js`, `index.html` | small UI | user can select a specific device |
| DEV-03 | P1* | 2 | Numbered "phone capture recipe" (snap-button → folder → CLI) in `docs/host/spatial.md` | The pieces exist but the full phone-only workflow isn't written as one recipe | `docs/host/spatial.md` (+ this checklist already provides it) | docs | a new operator can calibrate from docs alone |
| DEV-04 | P1* | 2 | Real-phone sync/clock-offset field validation script/notes | Heartbeat-estimated offsets are synthetic-validated only; real phones need measurement | `host/app/spatial/synchronizer.py`; `logs/sessions/*/fusion.jsonl` skew stats | measurement aid | recorded skew stats from a real 2-phone session within `max_skew_ms 50` |
| DEV-05 | P2 | 2 | Optional: capture-time auto QC report for a folder of images (dry-run summary before running `intrinsics`) | Saves reshoot cycles on weak image sets | `host/app/spatial/calibration_tool.py` (load_samples already rejects with reasons) | convenience | per-folder report of usable/weak images |
| DEV-06 | P3 | 3 | Runtime gesture-threshold tuning controls (config hot-reload or operator-page sliders) | Stage 3 tuning currently requires manual `config/gesture.yaml` edits + restart | `config/gesture.yaml`; `host/app/gesture/config.py` | convenience | threshold change takes effect without code edit |
| DEV-07 | P2 | 3 | Gesture-threshold tuning helper (aggregated pinch/reach/loss statistics from logs) | Makes the hardware tuning session data-driven instead of trial-and-error | new script over `logs/` audit/fusion events | measurement aid | per-session stats of enter/exit ratios, confirm times, loss gaps |
| DEV-08 | P0* | 4 | Godot headless smoke check wired into docs/tests | Godot is not installed on the dev machine; a repeatable check makes validation possible the moment it is | `docs/setup.md` §4 commands; optional `scripts/` helper | validation automation | `--headless --check-only` passes on the user's machine |
| DEV-09 | P2 | 4 | End-to-end latency instrumentation (browser snap → Godot marker move) | 150 ms budget never measured end-to-end on hardware | `sensor-client` + fusion log timestamps + Godot timing | measurement aid | recorded p95 end-to-end latency |
| DEV-10 | P3 | 4 | Replace `SessionManager.create_session/stop_session` runtime wrapping with explicit host hooks | Monkey-patching works and is fully tested, but explicit hooks are cleaner long-term | `adapter/saga4_world/attach.py` | refactor (optional) | all 54 adapter + 4 e2e tests stay green after refactor |
| DEV-11 | P3 | all | Package `host/`+`adapter/` as installable package | Removes remaining (idempotent, repo-local) `sys.path` inserts | `pyproject.toml`; `attach.py`, `scripts/run_host.py`, `tests/conftest.py` | hygiene | tests pass when launched from another cwd |

\* Priority when its stage begins: DEV-03/04 become P1 at Stage 2/3; DEV-08 is P0 at Stage 5 (blocked on Godot being installed, which is a human action).

**Explicit non-tasks (already complete, do not rework):** calibration CLI and quality gates; fusion/sync/triangulation math; gesture FSM/acks/dedup; world protocol validation; transform module; Godot scripts (pending only their first execution); all consolidation infrastructure.

**Order of execution recommendation:** none of DEV-01..11 blocks Stage 2. Natural sequence:
1. (Now) nothing — start physical calibration.
2. After first real fusion session → DEV-04, DEV-07.
3. After Godot installed → DEV-08, then DEV-09 after the first interactive demo.
4. DEV-06, DEV-05, DEV-10, DEV-11 as convenience/quality passes; DEV-01/02 when the project scope expands beyond the wrist/pinch demo.
