# Coordinates: rig (fusion) -> Godot, the ONE transform

All rig→Godot coordinate maths lives in a single module, `adapter/saga4_world/transform.py`
(`WorldTransform`), configured by the `transform:` section of `config/world.yaml`. Nothing
else — not the bridge, not the Godot scripts — performs an axis swap, a scale, or an
offset. Godot receives already-transformed positions; it performs no additional
coordination of its own (Phase 3 handoff §6 contract).

## Formula

```
godot = scale * (R @ rig) + translation_m
rig   = Rᵀ @ ((godot - translation_m) / scale)
```

* `R` is a constant 3×3 orthonormal, right-handed matrix (rows = godot basis expressed in
  rig coordinates). `from_config` validates unit length, orthogonality and `det = +1`.
* `scale` is metres → Godot units. Keep `1.0` (1 Godot unit = 1 m everywhere in this demo).
* Volume checks: poses work in GODOT coordinates; the configured `volume_m` describes an
  axis-aligned safe interaction volume in Godot space. With
  `reject_outside_volume: false` (default) an outside pose is still forwarded but flagged
  `position_outside_volume`; with `true` it raises `TransformError(OUT_OF_VOLUME)` and the
  host drops it.

## Default configuration (config/world.yaml)

rig assumed: board frame, right-handed metres — `+X` right along the board columns,
`+Y` along the rows (horizontally away from the operator), `+Z = X × Y` = UP.
Godot assumed: right-handed metres, `+X` right, `+Y` up, `-Z` into the screen.

```
scale   = 1.0
R       = [[1,0,0],[0,0,1],[0,-1,0]]   # godot_x = rig_x, godot_y = rig_z (up), godot_z = -rig_y
translation_m = [0,0,-1.6]             # rig origin 1.6 m in front of the Godot default camera, on the floor plane
```

Sanity check of the rotation: rig `+Z` (up) row picks `1` in godot row 2 → godot `+Y`;
rig `+Y` row picks `-1` in godot row 3 → rig forward maps to godot `-Z` (into the screen) —
both frames stay right-handed.

## Two-reference-point verification (do this before any hardware session)

1. Place two marked physical points inside the calibrated camera volume, well separated
   (≥ 0.5 m apart, different heights).
2. Read their fusion `world_xyz_m` (host TRUST/pose output or `GET /api/sessions/{id}/fusion`).
3. Watch the same points pass under the Godot hand marker; extract the marker position.
4. Insert both pairs into the formula above (symbolically or with a scratch script) and
   confirm BOTH reproduce the expected Godot positions within a few centimetres.

Agreement at ONE point fixes the translation, agreement at TWO confirms the rotation/scale.
If the second point disagrees, adjust `R` (typical camera mounting error: a 90° rotation
about one axis) — never patch the transform in Godot or in the bridge.

## Fingerprint / invalidation

`WorldTransform.fingerprint()` produces a stable string of the parameters, e.g.:

```
1|1,0,0|0,0,1|0,-1,0|0,0,-1.6|False|x:-2..2;y:-0.2..2;z:-4..0.2
```

It is logged when the adapter attaches, sent in `WORLD_READY.transform_fingerprint`, and
treated as an identity: a change of fingerprint means the smoothed track and any active
interaction MUST reset (a different world frame silently mixed into one grab would be a
safety fault).

## Known limits

* The rotation values are a STARTING POINT: none of this is validated against physical
  cameras yet (Phase 4 report, "not yet hardware-validated").
* Non-finite positions raise immediately (transform and bridge fail closed).
* Only positions are transformed in Phase 4 (no orientations, no quaternions).
