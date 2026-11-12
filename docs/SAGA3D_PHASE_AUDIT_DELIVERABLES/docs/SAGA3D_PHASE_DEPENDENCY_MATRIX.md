# SAGA 3D — PHASE DEPENDENCY MATRIX

**Repo:** `saga-3d-phase-4` @ `bd01443` · read-only analysis · complements the per-phase contracts.

## 1. What each phase needs from the others

### Phase 2 needs from Phase 1
| Need | Contract source | Guarantee status |
|---|---|---|
| ≥2 stable sensor streams (2-D pixel landmarks, confidences) | protocol 1.0 `LANDMARK_OBSERVATION` | synthetic-verified only; real demo D1 outstanding |
| Per-sensor `captured_at_ms` + heartbeat cadence (clock-offset estimation) | `websocket_handler`/synchronizer | same |
| Un-mirrored frames + verified handedness labels (`flip_handedness`) | `config/camera.yaml`; P1-H11 | verification outstanding |
| Known per-camera streaming resolution | sensor page / snap-PNG filename | recording outstanding |
| Sensor↔camera ID binding | `POST /calibration/bindings`, operator page | UI exists; real use outstanding |

### Phase 3 needs from Phases 1+2
| Need | Contract source | Guarantee status |
|---|---|---|
| Fused `world_xyz_m` (metres, board frame), validity, quality, status | `FusionService` → `HandSample.from_fusion_result` | contract-tested; real-data demo D2 outstanding |
| Calibration-validity flag per camera | calibration store/API | works; meaningless until real calibration exists |
| Metric accuracy at the few-cm level (reach distances are metres) | `calibrate.py accuracy` campaign | outstanding |
| Tracking-loss semantics (hold 500 ms → `TARGET_LOST`) | `fusion.py` | synthetic-verified |
| Handedness-consistent landmarks (`require_hand_agreement`) | fusion config | depends on P1-H11 |

### Phase 4 needs from Phases 1+2+3
| Need | Contract source | Guarantee status |
|---|---|---|
| Transformed poses + `INTERACTION_EVENT` 1.0 stream + acks | `adapter/saga4_world` over Phases 2–3 outputs | bridge tests green; Godot side never executed |
| Verified rig→Godot transform | `docs/coordinates.md` two-point check | **defaults unvalidated**; blocked on real rig |
| Object declarations (`grabbable`) | `WORLD_HELLO`/`OBJECT_STATE` | protocol-tested |
| Gesture events actually produced by a human hand | Phase 3 D3 | outstanding |
| Stable long-running host (single process) | `run_host.py` | smoke/e2e verified synthetically |

## 2. Hard dependency chain (gates)

```
P1 handover (D1: real streams stable)
   └─> P2 physical calibration (D2: inspect READY + TRACKING_MULTI_VIEW + accuracy)
         └─> P3 real-gesture campaign (D3: FSM correct on real landmarks, thresholds tuned)
               └─> P4 Godot install + connect (P4-V1/V2)
                     ├─> transform two-point verification (needs P2 rig)  ← can run as soon as P2 done + Godot installed
                     └─> interaction demo (needs P3 D3)  →  FINAL ACCEPTANCE
```

**Parallel-safe work (no phase stops another):**
- Phase 2 hardware prep (board, mounts) can start immediately.
- Godot installation (P4-H1) can happen anytime — it depends on nothing.
- Godot headless check (P4-V1) only needs the executable + repo.
- DEV-* items in each phase's development checklist are independent of the hardware chain unless stated.

## 3. Blocked items register (current true blockers)

| Blocked task | Blocked by | Class |
|---|---|---|
| All Phase 2 physical steps | P1 handover (real streams) + materials | DEPENDENCY + HUMAN |
| All Phase 3 real-gesture validation | Phase 2 D2 | DEPENDENCY |
| Transform verification (P4-H2/H3) | Phase 2 rig + Godot install | DEPENDENCY |
| Interaction demo (P4-V3) | Phase 3 D3 + transform verification | DEPENDENCY |
| Final acceptance | the whole chain | DEPENDENCY |
| — | Godot absent on this machine | BLOCKER (environment) |

## 4. Cross-phase assumptions NOT yet guaranteed (checked against code, flagged honestly)

| Assumption | Where relied on | Current guarantee |
|---|---|---|
| Hand labels match physical reality | fusion `require_hand_agreement`; gesture left/right logic | manual smoke test documented; not yet run on real camera |
| Phone clock offsets fit `max_skew_ms 50` | synchronizer, fusion gating | synthetic-only measurement (median 6 ms) |
| Board-frame Z is "up" in the room | `config/world.yaml` rotation rows, Godot mapping | derivation consistent; physical two-point check will confirm |
| Grab reach distances meaningful in metres | gesture reach thresholds | depends on Phase 2 accuracy campaign |
| 30 Hz MOVE_TARGET smooth in Godot | `world_client.gd` interpolation/label usage | code supports; real smoothness unproven |

## 5. Minimum work per phase (do not redo completed work)

- **Phase 1:** only real-hardware demo D1 + evidence pack. Software: done.
- **Phase 2:** physical execution P2-1..P2-17. Software: done (no P0 dev).
- **Phase 3:** real-gesture campaign + possible tuning. Software: done (no P0 dev).
- **Phase 4:** install Godot, execute validations, verify transform, acceptance run. Bridge software: done; Godot scripts done but unexecuted.
- **Explicitly out of minimum scope:** body landmarks, device picker, tuning UI, attach-hook refactor, Godot test harness (all P3 convenience — `*_DEVELOPMENT_CHECKLIST.md`).
