# PHASE 4 — HUMAN ACTION CHECKLIST (executable, in order)

**Prerequisites:** Phase 1 handover (cameras streaming) + Phase 2 handover (calibrated rig, live `TRACKING_MULTI_VIEW`) + Phase 3 real-gesture campaign done.
**You need:** the Godot 4.3 installer, your calibrated camera rig, the host running.

## Install & first launch

- [ ] **P4-1. Download Godot 4.3 stable (standard, win64)** from godotengine.org.
      Verify from a terminal: `"C:\path\to\Godot_v4.3-stable_win64.exe" --version`
      Success: prints `4.3.x`. Fail: re-download the **standard** build (not .NET/Mono for this project).
- [ ] **P4-2. Headless project check (first real execution of the Godot side).**
      Command (run in `D:\collega active\phases\saga-3d-phase-4`): `"C:\path\to\Godot_v4.3-stable_win64.exe" --path godot --headless --check-only`
      Expect: exits without script errors.
      Fail: a script error names a `.gd` file — record it exactly (that's a development item, not something to hand-tweak blindly).
- [ ] **P4-3. Start the host with a session** (if not running):
      `.venv\Scripts\python scripts\run_host.py --session demo1`
      Expect: `host_started` + `world_adapter_started` with a transform fingerprint line.
- [ ] **P4-4. Launch Godot against the session.**
      Command: `"C:\path\to\Godot_v4.3-stable_win64.exe" --path godot -- --session=demo1`
      (Editor alternative: open `godot/project.godot`, run the `main` scene with the same `--session=demo1` command-line arg.)
      Expect: 3D window opens; status panel shows connection then **`WORLD_READY`**.
      Fail: `connection refused` → host down/port mismatch (you used `--port`? match it); `WORLD_CLIENT_EXISTS` → another Godot instance is attached — close it; `SESSION_MISMATCH` → wrong `--session`.

## Transform verification (the one-time alignment gate)

- [ ] **P4-5. Prepare two marked physical points** inside the calibrated camera volume: ≥0.5 m apart, **different heights**, positions tape-measured.
- [ ] **P4-6. Point 1 check.** Hold a marker (or your wrist with a visible landmark) at point 1; read fusion `world_xyz_m` (`GET /api/sessions/demo1/fusion` or operator page) AND watch the Godot hand marker position over the same physical spot.
      Record both numbers.
- [ ] **P4-7. Point 2 check.** Repeat at point 2; record both numbers.
- [ ] **P4-8. Decide.**
      Success: both points agree within a few centimetres (one point fixes translation; two confirm rotation/scale — `docs/coordinates.md` §5).
      Fail: marker offset looks like a constant shift → adjust `translation_m` in `config/world.yaml`; axis confusion (e.g. up/down swapped) → a 90° rotation error, adjust `rotation:` rows per the rig convention (rig: X along board columns, Y along rows, Z up). **Never patch inside Godot or the bridge** — the transform is the single definition. Record the new values (this finalizes `config/world.yaml`).

## The real interaction demo

- [ ] **P4-9. Hover.** Move your open hand near the cube in the shared volume.
      Expect: cube highlights (hover) — `HOVER` in Godot status; `hover_enter` event.
- [ ] **P4-10. Grab.** Pinch while hovering.
      Expect: `GRAB_REQUEST` (host log, with event id) → ack within 500 ms → cube attaches to your hand (`GRAB` state on panel).
      Fail: no grab → check pinch evidence logs (Phase 3 tuning); `GRAB_REQUEST` without confirm → ack timeout — check bridge logs.
- [ ] **P4-11. Move.** Carry your hand across the volume.
      Expect: cube follows smoothly (`MOVE_TARGET` ≤30 Hz); no jumps (track-discontinuity guard).
- [ ] **P4-12. Release.** Open the pinch.
      Expect: cube stays where released; `RELEASE` on panel.
- [ ] **P4-13. Repeat 3×** — repeatability is the acceptance bar, not a single lucky run.

## Stability & recovery demos

- [ ] **P4-14. Godot disconnect mid-session.** Close the Godot window during a session; relaunch with the same `--session`.
      Expect: reconnect (bounded backoff, visible on status panel), objects re-declared, interaction resumes.
- [ ] **P4-15. Camera loss mid-grab.** While grabbed, cover one camera.
      Expect: brief frozen hold, then safe release/cancel (`GRAB_CANCELLED`); no stale cube motion; marker hides on `tracking_lost`.
- [ ] **P4-16. Host restart.** Stop the host (Ctrl-C), start again, reconnect Godot.
      Expect: clean re-handshake; no orphaned session errors (one-client rule frees on disconnect).

## Final acceptance run

- [ ] **P4-17. Execute `docs/SAGA3D_REAL_WORLD_RUNBOOK.md` start-to-finish from a cold machine** (all 15 steps), ticking as you go.
- [ ] **P4-18. Archive the evidence pack** (below) — this completes the project.

## Evidence pack for final acceptance
- Godot version output; headless check output.
- `WORLD_READY` screenshot with fingerprint (from host log).
- The two reference-point readings (fusion vs Godot) + any `config/world.yaml` transform change you made and its re-verification.
- Grab/move/release recordings or stepwise screenshots ×3.
- Recovery-demo notes (P4-14..16) + the completed runbook checklist.
