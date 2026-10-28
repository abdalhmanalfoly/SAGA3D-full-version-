"""THE coordinate transform: fusion world frame (rig) -> Godot world space. This module is the ONLY place a
conversion lives (Godot receives pre-transformed positions; see docs/coordinates.md for the derivation and the
two-reference-point verification procedure).

    godot = scale * (R @ rig) + translation
where R is a constant 3x3 orthonormal matrix (documented axis semantics/scale), scale is metres -> Godot units
and translation is metres in Godot coordinates. The inverse (used for OBJECT_STATE, reported by Godot in its
own coordinates) is:
    rig = R^T @ ((godot - translation) / scale)

Safety rules encoded here:
  * NaN/inf in, garbage out is refused: a non-finite input raises OUT_OF_VOLUME? no - ``TransformError("NON_FINITE")``.
  * Inputs outside the configured interaction volume are flagged (``WorldTransform.is_inside``); per
    ``reject_outside_volume`` they are either dropped (TransformError) or passed through with a warning that
    the caller must surface; the hand marker may be drawn but interaction targets outside the volume are
    clamped by the gesture reach logic anyway.
  * The transform is frozen at session start (``WorldTransform.fingerprint()``); a config change mid-session
    must invalidate the smoothed track - callers use the fingerprint to detect this (bridge does).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

Vec3 = tuple[float, float, float]


class TransformError(ValueError):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


def _num3(v: Sequence[Any], what: str) -> Vec3:
    if len(v) != 3 or not all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in v):
        raise TransformError("INVALID_TRANSFORM_CONFIG", f"{what} must be 3 finite numbers")
    return (float(v[0]), float(v[1]), float(v[2]))


def _mat3(raw: Any) -> tuple[Vec3, Vec3, Vec3]:
    if not isinstance(raw, (list, tuple)) or len(raw) != 3:
        raise TransformError("INVALID_TRANSFORM_CONFIG", "rotation must be a 3x3 matrix")
    r0, r1, r2 = (_num3(r, "rotation row") for r in raw)
    # orthonormality check (rows): |r|=1, mutual dot ~ 0, det = +1
    for name, r in (("row0", r0), ("row1", r1), ("row2", r2)):
        n = math.sqrt(r[0] ** 2 + r[1] ** 2 + r[2] ** 2)
        if abs(n - 1.0) > 1e-6:
            raise TransformError("INVALID_TRANSFORM_CONFIG", f"rotation {name} is not unit length")
    d01, d02, d12 = (r0[0] * r1[0] + r0[1] * r1[1] + r0[2] * r1[2],
                     r0[0] * r2[0] + r0[1] * r2[1] + r0[2] * r2[2],
                     r1[0] * r2[0] + r1[1] * r2[1] + r1[2] * r2[2])
    if max(abs(d01), abs(d02), abs(d12)) > 1e-6:
        raise TransformError("INVALID_TRANSFORM_CONFIG", "rotation rows are not orthogonal")
    det = (r0[0] * (r1[1] * r2[2] - r1[2] * r2[1])
           - r0[1] * (r1[0] * r2[2] - r1[2] * r2[0])
           + r0[2] * (r1[0] * r2[1] - r1[1] * r2[0]))
    if abs(abs(det) - 1.0) > 1e-6:
        raise TransformError("INVALID_TRANSFORM_CONFIG", "rotation is not invertible")
    if det < 0:
        raise TransformError("INVALID_TRANSFORM_CONFIG", "rotation must be right-handed (det=+1)")
    # transpose = inverse for orthonormal matrices
    return (r0, r1, r2)


@dataclass(frozen=True)
class WorldTransform:
    scale: float
    rotation: tuple[Vec3, Vec3, Vec3]           # rig -> godot rows
    translation: Vec3                           # godot metres
    volume: dict[str, Vec3]                     # godot-space axis ranges
    reject_outside_volume: bool
    source_frame: str = "rig_world"
    target_frame: str = "godot_world"
    units_note: str = "metres on both sides; keep scale 1.0 (1 Godot unit = 1 m) unless you deliberately rescale the scene"

    # ------------------------------------------------------------------ apply
    def _apply(self, p: Vec3) -> Vec3:
        x, y, z = p
        r0, r1, r2 = self.rotation
        rx, ry, rz = r0[0] * x + r0[1] * y + r0[2] * z, r1[0] * x + r1[1] * y + r1[2] * z, r2[0] * x + r2[1] * y + r2[2] * z
        return (self.scale * rx + self.translation[0], self.scale * ry + self.translation[1], self.scale * rz + self.translation[2])

    def rig_to_godot(self, p: Sequence[float]) -> Vec3:
        """Fusion world position (rig) -> Godot space. Raises TransformError on non-finite (and out-of-volume when configured to reject)."""
        if len(p) != 3 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in p):
            raise TransformError("NON_FINITE", "rig_to_godot requires 3 finite numbers")
        out = self._apply((float(p[0]), float(p[1]), float(p[2])))
        if not self.is_inside_volume(out) and self.reject_outside_volume:
            raise TransformError("OUT_OF_VOLUME", f"position {out} outside configured interaction volume")
        return out

    def godot_to_rig(self, p: Sequence[float]) -> Vec3:
        """Godot space -> rig frame (used for OBJECT_STATE). Requires the position to be inside the volume: an object
        Godot reports outside it is a configuration problem, not a tracking estimate."""
        if len(p) != 3 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in p):
            raise TransformError("NON_FINITE", "godot_to_rig requires 3 finite numbers")
        g = ((float(p[0]) - self.translation[0]) / self.scale, (float(p[1]) - self.translation[1]) / self.scale, (float(p[2]) - self.translation[2]) / self.scale)
        r0, r1, r2 = self.rotation                                    # R^T rows are R columns
        return (r0[0] * g[0] + r1[0] * g[1] + r2[0] * g[2], r0[1] * g[0] + r1[1] * g[1] + r2[1] * g[2], r0[2] * g[0] + r1[2] * g[1] + r2[2] * g[2])

    # ------------------------------------------------------------------ volume / identity
    def is_inside_volume(self, p: Sequence[float]) -> bool:
        rng = self.volume
        return all(rng[a][0] <= v <= rng[a][1] for a, v in zip(("x", "y", "z"), p))

    def fingerprint(self) -> str:
        """Stable identity of these transform parameters; a change means the smoothed track + interaction must reset."""
        r = "|".join(",".join(f"{v:.6g}" for v in row) for row in self.rotation)
        return (f"{self.scale:.6g}|{r}|{','.join(f'{v:.6g}' for v in self.translation)}"
                f"|{self.reject_outside_volume}|{';'.join(f'{a}:{v[0]:.6g}..{v[1]:.6g}' for a, v in sorted(self.volume.items()))}")

    # ------------------------------------------------------------------ construction
    @classmethod
    def from_config(cls, data: Mapping[str, Any] | None) -> "WorldTransform":
        data = dict(data or {})
        if set(data) - {"scale", "rotation", "translation_m", "volume_m", "reject_outside_volume", "source_frame", "target_frame"}:
            raise TransformError("INVALID_TRANSFORM_CONFIG", f"unknown transform keys {sorted(set(data))}")
        scale = data.get("scale", 1.0)
        if not isinstance(scale, (int, float)) or isinstance(scale, bool) or not math.isfinite(scale) or scale <= 0:
            raise TransformError("INVALID_TRANSFORM_CONFIG", "scale must be a positive finite number")
        rot = _mat3(data.get("rotation", [[1, 0, 0], [0, 0, 1], [0, -1, 0]]))
        trans = _num3(data.get("translation_m", [0.0, 0.0, 0.0]), "translation_m")
        vol_raw = data.get("volume_m") or {"x": [-1000, 1000], "y": [-1000, 1000], "z": [-1000, 1000]}
        vol: dict[str, Vec3] = {}
        for axis, rng in vol_raw.items():
            if axis not in ("x", "y", "z"):
                raise TransformError("INVALID_TRANSFORM_CONFIG", f"unknown volume axis {axis!r}")
            if not isinstance(rng, (list, tuple)) or len(rng) != 2:
                raise TransformError("INVALID_TRANSFORM_CONFIG", f"volume_m.{axis} must be [low, high]")
            lo = float(rng[0])
            hi = float(rng[1])
            if lo > hi:
                raise TransformError("INVALID_TRANSFORM_CONFIG", f"volume_m.{axis} low value > high value")
            vol[axis] = (lo, hi)
        return cls(scale=float(scale), rotation=rot, translation=trans, volume=vol,
                   reject_outside_volume=bool(data.get("reject_outside_volume", False)))
